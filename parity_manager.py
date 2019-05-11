import json
import logging
import os
import requests
import shutil
import time
import toml

import docker
from web3 import Web3, HTTPProvider

from deploy_manager import DeployManager
from host_manager import HostManager

class ParityManager(DeployManager):

    datadir = "/home/ubuntu/parity"
    container_datadir = "/home/parity"
    network_name = "benchmark"
    node_name = "parity-node"
    account_password = "password"

    FILE_CONFIG = "./parity/config.toml"
    FILE_GENESIS = "./parity/genesis.json"
    FILE_PASSWORD = "./parity/password.txt"
    FILE_ENODES = "./parity/enodes.txt"

    temp_dir = "./tmp"

    def __init__(self, hosts):
        super().__init__(hosts)
        self.logger = logging.getLogger("ParityManager")

    def _init_setup(self):
        self.hosts_connections = HostManager.get_hosts_connections(self.hosts)
        self.hosts_accounts = {}
        self.enodes = []
        with open(self.FILE_CONFIG) as conf_file:
            self.node_config_template = toml.loads(conf_file.read())
        with open(self.FILE_PASSWORD, "w") as pw_file:
            pw_file.write(self.account_password)
    
    def _init_loop(self, host):
        self.check_docker(host)
        self.create_remote_datadir(host)
        self.__upload_config(host)
        self.__upload_genesis(host)
        self.enodes.append(self.__start_remote_node(host))
        account = self.hosts_connections[host]["web3"].personal.newAccount(self.account_password)
        self.__write_host_config(host, account)
        self.hosts_accounts[host] = account
        self.__stop_remote_node(host)
        self.logger.info("[%s]Generated account %s" % (host, account))

    def _start_setup(self):
        self.__init_genesis(self.FILE_GENESIS)
        self.__write_enodes_file(self.FILE_ENODES)
    
    def _start_loop(self, host):
        self.__upload_config(host, mining=True)
        self.__upload_password(host)
        self.__upload_enodes(host)
        self.__upload_genesis(host)
        try:
            self.__start_remote_node(host, mining=True, with_peers=True)
        except Exception as e:
            self.logger.error(e)

    def _stop_loop(self, host):
        self.__stop_remote_node(host)

    def __start_remote_node(self, host, mining=False, with_peers=False):
        start_cmd = "--chain genesis.json --config config.toml --geth --identity Parity-%s" % host
        if mining:
            start_cmd += " --unlock {0} --password {1}".format(self.hosts_accounts[host], os.path.join(self.container_datadir, "password.txt"))
        if with_peers:
            start_cmd += " --reserved-peers=%s --reserved-only" % os.path.join(self.container_datadir, os.path.basename(self.FILE_ENODES))
        docker_cnx = self.hosts_connections[host]["docker"]
        parity_container = docker_cnx["client"].containers.run(
            self.dinr.resolve("parity-node"),
            start_cmd,
            detach=True,
            volumes={
                self.datadir: {
                    "bind": self.container_datadir,
                    "mode": "rw"
                }
            },
            ports={
                "8545/tcp":"8545",
                "30303/tcp":"30303",
                "30303/udp":"30303"
            }, name=self.node_name, network=self.network_name)
        docker_cnx["containers"][self.node_name] = parity_container
        self.hosts_connections[host]["web3"] = Web3(HTTPProvider("http://%s:8545" % host))
        enode = self.wait_node(host)
        if enode:
            self.logger.info("[%s]Initialized node" % host)
        else:
            raise Exception("[%s]Can't contact Parity node" % host)
        return enode

    def __stop_remote_node(self, host):
        containers = self.hosts_connections[host]["docker"]["containers"]
        if self.node_name in containers:
            containers[self.node_name].stop()
            containers[self.node_name].remove()
    
    def __init_genesis(self, genesis_path):
        with open(genesis_path) as base_genesis:
            genesis_dict = json.load(base_genesis)
        accounts_balances = {}
        for account in self.hosts_accounts.values():
            accounts_balances[account] = {"balance": "0x200000000000000000000000000000000000000000000000000000000000000"}
        genesis_dict["engine"]["authorityRound"]["params"]["validators"]["list"] = list(self.hosts_accounts.values())
        genesis_dict["accounts"] = accounts_balances
        with open(genesis_path, "w") as genesis_file:
            json.dump(genesis_dict, genesis_file)
        return genesis_dict

    def __write_host_config(self, host, account):
        node_config = self.node_config_template.copy()
        node_config["mining"]["author"] = account
        node_config["mining"]["engine_signer"] = account
        with open(os.path.join(self.temp_dir, "%s.toml" % host), "w") as conf_file:
            conf_file.write(toml.dumps(node_config))

    def __upload_password(self, host):
        self.hosts_connections[host]["ssh"].put(self.FILE_PASSWORD, remote=os.path.join(self.datadir, "password.txt"))
        self.logger.info("[%s]Password file uploaded" % host)

    def __upload_genesis(self, host):
        self.hosts_connections[host]["ssh"].put(self.FILE_GENESIS, remote=os.path.join(self.datadir, "genesis.json"))
        self.logger.info("[%s]Genesis file uploaded" % host)

    def __upload_config(self, host, mining=False):
        if mining:
            conf_file_path = os.path.join(self.temp_dir, "%s.toml" % host)
        else:
            conf_file_path = self.FILE_CONFIG
        if os.path.isfile(conf_file_path):
            self.hosts_connections[host]["ssh"].put(conf_file_path, remote=os.path.join(self.datadir, "config.toml"))
            self.logger.info("[%s]Config file uploaded" % host)
        else:
            self.logger.warning("[%s]Couldn't update conf file. (Mining: %d)" % (host, mining))

    def __upload_enodes(self, host):
        self.hosts_connections[host]["ssh"].put(self.FILE_ENODES, remote=os.path.join(self.datadir, "enodes.txt"))
        self.logger.info("[%s]Enodes file uploaded" % host)

    def __write_enodes_file(self, file_path):
        with open(file_path, "w") as enodes_file:
            for enode in self.enodes:
                enodes_file.write("%s\n" % enode)
        self.logger.info("Written enodes file")

    def check_docker(self, host):
        docker_connection = self.hosts_connections[host]["docker"]
        try:
            benchmark_network = docker_connection["client"].networks.create(
                self.network_name,
                driver="bridge",
                check_duplicate=True)
            docker_connection["networks"][self.network_name] = benchmark_network
        except docker.errors.APIError as error:
            if error.status_code == 409:
                self.logger.info("[%s]Network already deployed" % host)
            else:
                self.logger.error(error)
        try:
            parity_node = docker_connection["client"].containers.get(self.node_name)
            parity_node.stop()
            parity_node.remove()
            self.logger.info("[{0}]Parity node found, stopped and removed".format(host))
        except docker.errors.APIError as error:
            if error.status_code == 404:
                pass
            else:
                self.logger.error(error)
    
    def create_remote_datadir(self, host):
        mkdir = self.hosts_connections[host]["ssh"].run("mkdir -p %s" % self.datadir)
        if not mkdir.ok:
            raise Exception("[%s]Can't create datadir" % host)
    
    def wait_node(self, host, attempts=10, delay_between_attempts=1):
        web3 = self.hosts_connections[host]["web3"]
        a = 0
        while a < attempts:
            try:
                requested_enode = web3.parity.enode()
                at_index = requested_enode.find("@")
                port_index = requested_enode.find(":30303")
                return requested_enode[0:at_index+1] + host + requested_enode[port_index:]
            except Exception as e: #TODO should see if it is worth to continue basing on which exception is raised
                a += 1
                time.sleep(delay_between_attempts)
                logging.getLogger("GethManager").debug(e)
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from host_manager import HostManager
    import sys, time
    hosts_file_path = sys.argv[1]
    host_manager = HostManager()
    host_manager.add_hosts_from_file(hosts_file_path)
    hosts = host_manager.get_hosts()
    manager = ParityManager(hosts)
    manager.init()
    # manager.cleanup()
    manager.start()
    time.sleep(120)
    manager.stop()
    manager.deinit()
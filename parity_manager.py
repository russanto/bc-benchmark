import json
import logging
import os
import requests
import shutil
import time

import docker
from web3 import Web3, HTTPProvider

from deploy_manager import DeployManager
from host_manager import HostManager

class ParityManager(DeployManager):

    datadir = "/home/ubuntu/parity"
    network_name = "benchmark"
    node_name = "parity-node"
    account_password = "password"

    FILE_CONFIG = "./parity/config.toml"
    FILE_GENESIS = "./parity/genesis.json"
    FILE_PASSWORD = "./parity/password.txt"
    FILE_ENODES = "./parity/enodes.txt"


    def __init__(self, hosts):
        super().__init__(hosts)
        self.logger = logging.getLogger("ParityManager")

    def _init_setup(self):
        self.local_connections = HostManager.get_local_connections()
        self.hosts_connections = HostManager.get_hosts_connections(self.hosts)
        self.accounts = []
        self.enodes = []
        self.create_local_datadir()
        with open(self.FILE_PASSWORD, "w") as pw_file:
            pw_file.write(self.account_password)
        self.check_docker_network(self.local_connections["docker"])
        self.enodes.append(self.__start_local_node())
        self.utility_account = self.local_connections["web3"].personal.newAccount(self.account_password)
        self.__stop_local_node()
        self.logger.info("Generated utility account")
    
    def _init_loop(self, host):
        self.check_docker_network(self.hosts_connections[host]["docker"])
        self.create_remote_datadir(host)
        self.enodes.append(self.__start_remote_node(host))
        self.accounts.append(self.hosts_connections[host]["web3"].personal.newAccount(self.account_password))
        self.__stop_remote_node(host)
        self.logger.info("[%s]Generated account" % host)

    def _start_setup(self):
        self.__init_genesis(self.FILE_GENESIS)
        self.__write_enodes_file(self.FILE_ENODES)
        self.__start_local_node(with_peers=True)
    
    def _start_loop(self, host):
        self.__start_remote_node(host, with_peers=True)

    def _stop_setup(self):
        self.__stop_local_node()

    def _stop_loop(self, host):
        self.__stop_remote_node(host)

    def __start_local_node(self, with_peers=False):
        start_cmd = "--chain genesis.json --config config.toml --geth --identity ParityUtility"
        shutil.copy(self.FILE_CONFIG, self.datadir)
        shutil.copy(self.FILE_GENESIS, self.datadir)
        shutil.copy(self.FILE_PASSWORD, self.datadir)
        if with_peers:
            shutil.copy(self.FILE_ENODES, self.datadir)
            start_cmd += " --reserved-peers=%s --reserved-only" % os.path.join(self.datadir, os.path.basename(self.FILE_ENODES))
        parity_container = self.local_connections["docker"]["client"].run(
            self.dinr.resolve("parity-node"),
            start_cmd,
            detach=True,
            volumes={
                self.datadir: {
                    "bind": "/home/parity",
                    "mode": "rw"
                }
            },
            ports={
                "8545/tcp":"8545",
                "30303/tcp":"30303",
                "30303/udp":"30303"
            }, name=self.node_name, network=self.network_name)
        self.local_connections["docker"]["containers"][self.node_name] = parity_container
        self.local_connections["web3"] = Web3(HTTPProvider("http://%s:8545" % self.node_name))
        if self.check_web3(self.local_connections["web3"]):
            self.logger.info("Initialized utility node")
        else:
            raise Exception("Can't contact local Geth node. Please abort the deploy.")
        return self.get_enode()
    
    def __stop_local_node(self):
        if self.node_name in self.local_connections["docker"]["containers"]:
            self.local_connections["docker"]["containers"][self.node_name].stop()
            self.local_connections["docker"]["containers"][self.node_name].remove()
            self.logger.info("Stopped utility node")

    def __start_remote_node(self, host, with_peers=False):
        start_cmd = "--chain genesis.json --config config.toml --geth --identity Parity-%s" % host
        ssh_cnx = self.hosts_connections[host]["ssh"]
        ssh_cnx.put(self.FILE_CONFIG, remote=self.datadir)
        ssh_cnx.put(self.FILE_GENESIS, remote=self.datadir)
        ssh_cnx.put(self.FILE_PASSWORD, remote=self.datadir)
        if with_peers:
            ssh_cnx.put(self.FILE_ENODES, remote=self.datadir)
            start_cmd += " --reserved-peers=%s --reserved-only" % os.path.join(self.datadir, os.path.basename(self.FILE_ENODES))
        docker_cnx = self.hosts_connections[host]["docker"]
        parity_container = docker_cnx["client"].run(
            self.dinr.resolve("parity-node"),
            start_cmd,
            detach=True,
            volumes={
                self.datadir: {
                    "bind": "/home/parity",
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
        if self.check_web3(self.hosts_connections[host]["web3"]):
            self.logger.info("[%s]Initialized node" % host)
        else:
            raise Exception("[%s]Can't contact Parity node" % host)
        return self.get_enode(host)

    def __stop_remote_node(self, host):
        containers = self.hosts_connections[host]["docker"]["containers"]
        if self.node_name in containers:
            containers[self.node_name].stop()
            containers[self.node_name].remove()
    
    def __init_genesis(self, genesis_path):
        with open(genesis_path) as base_genesis:
            genesis_dict = json.load(base_genesis)
        accounts_balances = {self.utility_account: {"balance": "0x200000000000000000000000000000000000000000000000000000000000000"}}
        for account in self.accounts:
            {account: {"balance": "0x200000000000000000000000000000000000000000000000000000000000000"}}
        genesis_dict["engine"]["authorityRound"]["params"]["validators"]["list"] = self.accounts
        genesis_dict["accounts"] = accounts_balances
        with open(genesis_path, "w") as genesis_file:
            json.dump(genesis_dict, genesis_file)
        return genesis_dict

    def __write_enodes_file(self, file_path):
        with open(file_path, "w") as enodes_file:
            for enode in self.enodes:
                enodes_file.write("%s\n" % enode)
        self.logger.info("Written enodes file")

    def get_enode(self, host=None):
        if host:
            web3 = self.hosts_connections[host]["web3"]
        else:
            web3 = self.local_connections["web3"]
            host = self.local_connections["ip"]
        requested_enode = web3.parity.enode()
        at_index = requested_enode.find("@")
        port_index = requested_enode.find(":30303")
        return requested_enode[0:at_index+1] + host + requested_enode[port_index:]

    def check_docker_network(self, docker_connection):
        try:
            local_network = docker_connection["client"].networks.create(
                self.network_name,
                driver="bridge",
                check_duplicate=True)
            docker_connection["networks"][self.network_name] = local_network
        except docker.errors.APIError as error:
            if error.status_code == 409:
                self.logger.info("[%s]Network already deployed" % docker_connection["client"].api.base_url)
            else:
                self.logger.error(error)

    def create_local_datadir(self):
        if not os.path.exists(self.datadir):
            os.makedirs(self.datadir)
    
    def create_remote_datadir(self, host):
        mkdir = self.hosts_connections[host]["ssh"].run("mkdir -p %s" % self.datadir)
        if not mkdir.ok:
            raise Exception("[%s]Can't create datadir" % host)
    
    @staticmethod
    def check_web3(web3, attempts=10, delay_between_attempts=1):
        a = 0
        while a < attempts:
            try:
                return web3.version.node
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
    manager.cleanup()
    manager.start()
    time.sleep(120)
    manager.stop()
    manager.deinit()
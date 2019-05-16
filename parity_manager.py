import json
import logging
import os
import requests
import shutil
from threading import Event, Lock
import time
import toml

import docker
from web3 import Web3, HTTPProvider

from deploy_manager import DeployManager
from ethereum_node import EthereumNode
from host_manager import HostManager

class ParityManager(DeployManager):

    # Host dir to be binded at container datadir
    datadir = "/home/ubuntu/parity"
    # Docker container working directory. If the parity image doesn't change, this shouldn't be changed.
    docker_container_datadir = "/home/parity"
    # Docker network that node will join on the host. If it does not exist it will be created. 
    docker_network_name = "benchmark"
    # Docker container name. In the docker_network_name network it can be used as node alias. 
    docker_node_name = "parity-node"
    # Password to encrypt new accounts
    account_password = "password"

    local_datadir = "/root/parity"

    FILE_CONFIG = "./parity/config.toml"
    FILE_GENESIS = "./parity/genesis.json"
    FILE_PASSWORD = os.path.join(local_datadir, "password.txt")
    FILE_ENODES = "./parity/enodes.txt"

    def __init__(self, hosts):
        super().__init__(hosts)
        self.logger = logging.getLogger("ParityManager")
        self.nodes = {}

    def _init_setup(self):
        self.hosts_connections = HostManager.get_hosts_connections(self.hosts)
        self.__init_local_dir()
        with open(self.FILE_CONFIG) as conf_file:
            self.node_config_template = toml.loads(conf_file.read())
        with open(self.FILE_PASSWORD, "w") as pw_file:
            pw_file.write(self.account_password)
    
    def _init_loop(self, host):
        self.check_docker(host)
        self.create_remote_datadir(host)
        self.__upload_config(host)
        self.__upload_genesis(host)
        node = EthereumNode(host, EthereumNode.TYPE_PARITY)
        self.__start_remote_node(node)
        node.account = node.web3.personal.newAccount(self.account_password), self.account_password
        self.__write_host_config(host, node.account[0])
        self.__stop_remote_node(node)
        self.nodes[host] = node
        self.logger.info("[%s]Generated account %s" % (host, node.account[0]))

    def _start_setup(self):
        self.__init_genesis(self.FILE_GENESIS)
        self.__write_enodes_file(self.FILE_ENODES)
    
    def _start_loop(self, host):
        self.__upload_config(host, mining=True)
        self.__upload_password(host)
        self.__upload_enodes(host)
        self.__upload_genesis(host)
        try:
            self.__start_remote_node(self.nodes[host], mining=True, with_peers=True)
        except Exception as e:
            self.logger.error(e)
    
    def _start_teardown(self):
        self.utility_node = self.nodes[self.hosts[0]]
        self.logger.info("Node at %s will serve as utility" % self.hosts[0])

    def _stop_loop(self, host):
        self.__stop_remote_node(self.nodes[host])

    def __init_local_dir(self):
        try:
            shutil.rmtree(self.local_datadir)
            os.makedirs(self.local_datadir)
            self.logger.info("Local datadir (%s) successfully cleaned" % self.local_datadir)
        except FileNotFoundError:
            os.makedirs(self.local_datadir)
            self.logger.info("Created local datadir (%s)" % self.local_datadir)
        except Exception as error:
            self.logger.error(error)

    def __start_remote_node(self, node, mining=False, with_peers=False):
        start_cmd = "--chain genesis.json --config config.toml --geth --identity Parity-%s" % node.host
        if mining:
            start_cmd += " --unlock {0} --password {1}".format(node.account[0], os.path.join(self.docker_container_datadir, "password.txt"))
        if with_peers:
            start_cmd += " --reserved-peers=%s --reserved-only" % os.path.join(self.docker_container_datadir, os.path.basename(self.FILE_ENODES))
        docker_cnx = self.hosts_connections[node.host]["docker"]
        parity_container = docker_cnx["client"].containers.run(
            self.dinr.resolve("parity-node"),
            start_cmd,
            detach=True,
            volumes={
                self.datadir: {
                    "bind": self.docker_container_datadir,
                    "mode": "rw"
                }
            },
            ports={
                "8545/tcp":"8545",
                "30303/tcp":"30303",
                "30303/udp":"30303"
            }, name=self.docker_node_name, network=self.docker_network_name)
        docker_cnx["containers"][self.docker_node_name] = parity_container
        if node.ready():
            self.logger.info("[%s]Initialized node" % node.host)
        else:
            raise Exception("[%s]Can't contact Parity node with account %s" % (node.host, node.account[0]))

    def __stop_remote_node(self, node):
        containers = self.hosts_connections[node.host]["docker"]["containers"]
        if self.docker_node_name in containers:
            containers[self.docker_node_name].stop()
            node.status = EthereumNode.STATUS_STOPPED
            containers[self.docker_node_name].remove()
            self.logger.info("[%s]Node stopped" % node.host)
    
    def __init_genesis(self, genesis_path):
        with open(genesis_path) as base_genesis:
            genesis_dict = json.load(base_genesis)
        accounts = []
        accounts_balances = {}
        for node in self.nodes.values():
            accounts.append(node.account[0])
            accounts_balances[node.account[0]] = {"balance": "0x200000000000000000000000000000000000000000000000000000000000000"}
        genesis_dict["engine"]["authorityRound"]["params"]["validators"]["list"] = accounts
        genesis_dict["accounts"] = accounts_balances
        with open(genesis_path, "w") as genesis_file:
            json.dump(genesis_dict, genesis_file)
        return genesis_dict

    def __write_host_config(self, host, account):
        node_config = self.node_config_template.copy()
        node_config["mining"]["author"] = account
        node_config["mining"]["engine_signer"] = account
        with open(os.path.join(self.local_datadir, "%s.toml" % host), "w") as conf_file:
            conf_file.write(toml.dumps(node_config))

    def __upload_password(self, host):
        self.hosts_connections[host]["ssh"].put(self.FILE_PASSWORD, remote=os.path.join(self.datadir, "password.txt"))
        self.logger.info("[%s]Password file uploaded" % host)

    def __upload_genesis(self, host):
        self.hosts_connections[host]["ssh"].put(self.FILE_GENESIS, remote=os.path.join(self.datadir, "genesis.json"))
        self.logger.info("[%s]Genesis file uploaded" % host)

    def __upload_config(self, host, mining=False):
        if mining:
            conf_file_path = os.path.join(self.local_datadir, "%s.toml" % host)
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
            for node in self.nodes.values():
                enodes_file.write("%s\n" % node.enode)
        self.logger.info("Written enodes file")

    def check_docker(self, host):
        docker_connection = self.hosts_connections[host]["docker"]
        try:
            benchmark_network = docker_connection["client"].networks.create(
                self.docker_network_name,
                driver="bridge",
                check_duplicate=True)
            docker_connection["networks"][self.docker_network_name] = benchmark_network
        except docker.errors.APIError as error:
            if error.status_code == 409:
                self.logger.info("[%s]Network already deployed" % host)
            else:
                self.logger.error(error)
        try:
            parity_node = docker_connection["client"].containers.get(self.docker_node_name)
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("paramiko.transport").setLevel(logging.WARNING)

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
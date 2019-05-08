import docker
import json
import logging
import os
import queue
import sys
from threading import Thread
import time
from web3 import Web3, HTTPProvider
import yaml

from deploy_manager import DeployManager
from host_manager import HostManager

class CaliperManager(DeployManager):

    remote_caliper_dir = "/home/ubuntu/caliper"
    server_container_name = "caliper"
    client_container_name = "zookeeper-client"
    local_datadir = "/home/ubuntu/caliper"
    container_datadir = "/root/caliper"
    reports_dir = "/home/ubuntu/reports"
    tmp_dir = "tmp"

    def __init__(self, bc_manager):
        super().__init__(bc_manager.hosts)
        self.logger = logging.getLogger("CaliperManager")
        self.bc_manager = bc_manager
        self.hosts_addresses = bc_manager.get_etherbases() #TODO Manage the wait time and an eventual timeout
        self.enable_cmd(self.CMD_INIT, self.CMD_START, self.CMD_CLEANUP)
        self.running_in_container = True
        self.is_initialized = False
    
    def parse_conf(self, conf_as_dict): # TODO integrate this function inside kwargs on __init__
        if "RUNNING_IN_CONTAINER" not in conf_as_dict:
            self.running_in_container = False
        if "CALIPER_DATADIR" in conf_as_dict:
            self.local_datadir = conf_as_dict["CALIPER_DATADIR"]
        if "REPORTS_DIR" in conf_as_dict:
            self.reports_dir = conf_as_dict["REPORTS_DIR"]
    
    def get_datadir(self, join_dir=""):
        if self.running_in_container:
            return os.path.join(self.container_datadir, join_dir)
        else:
            return os.path.join(self.local_datadir, join_dir)
    
    def get_local_node_endpoint(self):
        if self.running_in_container:
            return self.bc_manager.local_conf["node_name"]
        else:
            return "localhost"

    def _init(self):
        self.hosts_connections = HostManager.get_hosts_connections(self.hosts_addresses.keys())
        self.local_connections = HostManager.get_local_connections()
        if "docker" in self.local_connections:
            local_docker = self.local_connections["docker"]["client"]
            try:
                local_zookeeper = local_docker.containers.get("zookeeper")
                local_zookeeper.stop()
                local_zookeeper.remove()
                self.logger.info("Previous execution Zookeeper server found, stopped and removed")
            except docker.errors.NotFound:
                self.logger.info("Zookeeper server not found")
            except:
                raise
            try:
                self.logger.info("Deploying Zookeeper server")
                self.local_connections["docker"]["containers"]["zookeeper"] = local_docker.containers.run(
                    self.dinr.resolve("zookeeper"),
                    detach=True,
                    name="zookeeper",
                    network=self.bc_manager.local_conf["network_name"],
                    ports={
                        '2181/tcp': 2181,
                        '2888/tcp': 2888,
                        '3888/tcp': 3888
                    })
                self.logger.info("Zookeeper server deployed")
            except docker.errors.APIError as error:
                if error.status_code == 409:
                    self.logger.warning("Zookeeper port is already being used")
                else:
                    self.logger.error(error)
        else:
            self.logger.error("Can't initialize: error with local docker client")
        self.registry_address = self.deploy_registry(self.get_local_node_endpoint())
        self.is_initialized = True

    def _start(self):
        with open(self.get_datadir("ethereum.json")) as geth_json_file:
            geth_conf = json.load(geth_json_file)
        geth_conf["ethereum"]["url"] = "http://%s:8545" % self.bc_manager.host_conf["node_name"]
        geth_conf["ethereum"]["registry"]["address"] = self.registry_address
        geth_conf["ethereum"]["contractDeployerAddress"] = self.bc_manager.utility_account
        geth_conf["ethereum"]["fromAddressPassword"] = ""
        with open(self.get_datadir("ethereum.json"), "w") as geth_json_file:
            json.dump(geth_conf, geth_json_file)
        remote_file_path = os.path.join(self.remote_caliper_dir, "ethereum.json")
        host_queue = queue.Queue()
        for host in self.hosts_connections.keys():
            host_queue.put(host)
        deployers = []
        for _ in range(min(self.N_DEPLOYER_THREADS, len(self.hosts_connections.keys()))):
            time.sleep(2)
            deployer = Thread(target=self._start_client_thread, args=(host_queue, geth_conf, remote_file_path,))
            deployer.start()
            deployers.append(deployer)
            host_queue.put("") # The empty string is the stop signal for the _start_node_thread
        for deployer in deployers:
            deployer.join()
        self._start_caliper_workload()
        
    
    def _start_client_thread(self, host_queue, geth_conf, remote_file_path):
        host = host_queue.get()
        while host != "":
            connections = self.hosts_connections[host]
            geth_conf = geth_conf.copy()
            geth_conf["ethereum"]["fromAddress"] = self.hosts_addresses[host]
            tmp_file_name = os.path.join(self.tmp_dir, "ethereum-tmp-{0}.json".format(host))
            with open(tmp_file_name, "w") as tmp_file:
                json.dump(geth_conf, tmp_file)
            try:
                connections["ssh"].run("mkdir -p %s" % self.remote_caliper_dir)
                connections["ssh"].put(tmp_file_name, remote=remote_file_path)
                connections["docker"]["containers"][self.client_container_name] = connections["docker"]["client"].containers.run(
                    self.dinr.resolve("caliper-client"),
                    name=self.client_container_name,
                    detach=True,
                    network=self.bc_manager.host_conf["network_name"],
                    environment={
                        "ZOO_SERVER": self.local_connections["ip"],
                        "BLOCKCHAIN": "ethereum",
                        "BC_CONF": "1node"
                    }, volumes={
                        remote_file_path: {
                            "bind":"/caliper/packages/caliper-application/network/ethereum/1node/ethereum.json",
                            "mode":"rw"
                        }
                    })
                self.logger.info("[%s]Zookeeper client deployed" % host)
            except docker.errors.APIError as error:
                self.logger.error("[%s]Error on docker creation of zoo client" % host)
                self.logger.error(error)
            except FileNotFoundError as error:
                self.logger.error(error)
            host = host_queue.get()

    def _start_caliper_workload(self):
        # Adds to the workload conf all the host to monitor
        docker_rapi_hosts = []
        for host in self.hosts_addresses.keys():
            docker_rapi_hosts.append("http://%s:2375/geth-node" % host)
        with open(self.get_datadir("config-ethereum.yaml")) as config_file:
            config_data = yaml.load(config_file)
        config_data["monitor"]["docker"]["name"] = docker_rapi_hosts
        with open(self.get_datadir("config-ethereum.yaml"), "w") as config_file:
            yaml.dump(config_data, config_file, default_flow_style=False)
        self.logger.info("Updated workload configuration")

        self.logger.info("Starting caliper")
        local_docker = self.local_connections["docker"]["client"]
        self.local_connections["docker"]["containers"][self.server_container_name] = local_docker.containers.run(
            self.dinr.resolve("caliper-server"),
            name=self.server_container_name,
            detach=True,
            network=self.bc_manager.local_conf["network_name"],
            environment={
                "BLOCKCHAIN": "ethereum",
                "BC_CONF": "1node",
                "BENCHMARK": "simple"
            }, volumes={
                os.path.join(self.local_datadir, "config-ethereum.yaml"): { # This must point to local host datadir
                    "bind": "/caliper/packages/caliper-application/benchmark/simple/config-ethereum.yaml",
                    "mode": "rw"
                },
                os.path.join(self.local_datadir, "ethereum.json"): { # This must point to local host datadir
                    "bind": "/caliper/packages/caliper-application/network/ethereum/1node/ethereum.json",
                    "mode": "rw"
                },
                self.reports_dir: {
                    "bind": "/caliper/packages/caliper-application/reports",
                    "mode": "rw"
                }
            })
        self.logger.info("Caliper started. Check progress launching 'docker logs -f %s'" % self.server_container_name)
    
    def _cleanup(self):
        local_docker = self.local_connections["docker"]["client"]
        try:
            caliper_server = local_docker.containers.get(self.server_container_name)
            caliper_server.remove(force=True)
            self.logger.info("Caliper container found and removed")
        except docker.errors.APIError as error:
            if error.status_code == 404:
                pass
            else:
                raise
        for host, connections in self.hosts_connections.items():
            docker_client = connections["docker"]["client"]
            try:
                zookeeper_client = docker_client.containers.get(self.client_container_name)
                zookeeper_client.stop()
                zookeeper_client.remove()
                self.logger.info("[{0}]Zookeeper client found, stopped and removed".format(host))
            except docker.errors.APIError as error:
                if error.status_code == 404:
                    pass
                else:
                    raise

    def deploy_registry(self, node):
        web3 = Web3(HTTPProvider("http://%s:8545" % node))
        self.bc_manager.check_web3_cnx(web3)
        with open(self.get_datadir("registry.json")) as registry_info_file:
            registry_data = json.load(registry_info_file)
        Registry = web3.eth.contract(abi=registry_data["abi"], bytecode=registry_data["bytecode"])
        self.logger.info("Creating registry")
        try:
            web3.personal.unlockAccount(self.bc_manager.utility_account, self.bc_manager.utility_account_password)
            registry_contructed = Registry.constructor()
            registry_estimated_gas = registry_contructed.estimateGas()
            registry_tx_hash = registry_contructed.transact({
                "from": self.bc_manager.utility_account,
                "gas": registry_estimated_gas
            })
            registry_creation = web3.eth.waitForTransactionReceipt(registry_tx_hash)
            self.logger.info("Created registry at %s" % registry_creation.contractAddress)
            return registry_creation.contractAddress
        except:
            self.logger.error("Error creating registry")
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from host_manager import HostManager
    from geth_manager import GethManager
    import sys, time
    hosts_file_path = sys.argv[1]
    host_manager = HostManager()
    host_manager.add_hosts_from_file(hosts_file_path)
    hosts = host_manager.get_hosts()
    manager = GethManager(hosts)
    manager.parse_conf(os.environ)
    manager.set_consensus_protocol(GethManager.CLIQUE)
    manager.init()
    manager.cleanup()
    manager.start("clique.json")
    time.sleep(60)
    caliper_manager = CaliperManager(manager)
    caliper_manager.parse_conf(os.environ)
    caliper_manager.init()
    caliper_manager.cleanup()
    caliper_manager.start()
    time.sleep(120)
    caliper_manager.stop()
    caliper_manager.deinit()
    manager.stop()
    manager.deinit()
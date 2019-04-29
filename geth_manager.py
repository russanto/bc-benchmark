import docker
from fabric import Connection
import json
import logging
import os
import queue
import shutil
from threading import Event, Thread
import time
from web3 import Web3, HTTPProvider, WebsocketProvider
import web3.admin

from host_manager import HostManager

# TODO: Implement wait function for bc to be ready

class GethManager:

    ETHASH = "ethash"
    CLIQUE = "clique"

    N_DEPLOYER_THREADS = 4

    CMD_INIT = "init"
    CMD_CLEANUP = "cleanup"
    CMD_START = "start"
    CMD_STOP = "stop"
    CMD_CLOSE = "close"
    CMD_DEINIT = "deinit"

    docker_remote_api_port = 2375

    host_conf = {
        "datadir": "/home/ubuntu/ethereum",
        "network_name": "benchmark",
        "node_name": "geth-node",
        "ssh_username": "ubuntu",
        "account_password": ""
    }

    local_conf = {
        "datadir": "/home/ubuntu/ethereum",
        "container_datadir": "/root/ethereum",
        "network_name": "benchmark",
        "node_name": "geth-node",
        "default_account": "",
        "default_account_password": ""
    }

    def __init__(self, hosts, running_in_container=True): #TODO Use symbolic names for dns resolution in custom docker network
        self.hosts = hosts
        self.running_in_container = running_in_container
        self.is_initialized = False
        self.logger = logging.getLogger("GethManager")
        self.deployed_keys = {}
        self.deployed_keys_available = Event()
        self.consensus_protocol = self.ETHASH 
        self.cmd_queue = queue.Queue()
        cmd_th = Thread(target=self._main_cmd_thread)
        cmd_th.start()

    def parse_conf(self, conf_as_dict):
        if "N_DEPLOYER_THREADS" in conf_as_dict:
            self.N_DEPLOYER_THREADS = int(conf_as_dict["N_DEPLOYER_THREADS"])
        if "LOCAL_NODE_DIR" in conf_as_dict:
            self.set_local_datadir(conf_as_dict["LOCAL_NODE_DIR"])
        if "RUNNING_IN_CONTAINER" not in conf_as_dict:
            self.running_in_container = False

    # Lifecycle methods

    def init(self):
        self.cmd_queue.put({
            "type": self.CMD_INIT
        }) 

    def start(self, genesis_file):
        self.cmd_queue.put({
            "type": self.CMD_START,
            "args": {"genesis_file": genesis_file}
        })

    def stop(self, cleanup=False):
        self.cmd_queue.put({
            "type": self.CMD_STOP,
            "args": {"cleanup": cleanup}
        })

    def cleanup(self):
        self.cmd_queue.put({
            "type": self.CMD_CLEANUP
        })
    
    def deinit(self):
        self.cmd_queue.put({
            "type": self.CMD_DEINIT
        })
        self.cmd_queue.put({"type": self.CMD_CLOSE})

    def get_etherbases(self, wait=True):
        if wait:
            self.deployed_keys_available.wait()
            return self.deployed_keys.copy()
        else:
            if self.deployed_keys_available.is_set():
                return self.deployed_keys.copy()
            else:
                return False
    
    def set_consensus_protocol(self, protocol):
        if protocol == self.ETHASH or protocol == self.CLIQUE:
            self.consensus_protocol = protocol
        else:
            self.consensus_protocol = self.ETHASH
            self.logger.error("Consensus protocol not valid, using ethash as default")
    
    # Topology definition methods

    def full_mesh(self, include_local_node=True):
        enodes = []
        if include_local_node:
            enodes.append(self.get_enode())
        for host in self.hosts:
            web3 = self.host_connections[host]["web3"]
            enode = self.get_enode(host)
            enodes.append(enode)
            self.logger.debug("Added enode: %s" % enode)
            for i in range(len(enodes)-1):
                web3.admin.addPeer(enodes[i])
                self.logger.info("Added node %s to node %s", enodes[i], host)

    # Utility methods. These should not be called from externally.

    def _main_cmd_thread(self):
        cmd = self.cmd_queue.get()
        while cmd["type"] != self.CMD_CLOSE:
            if cmd["type"] == self.CMD_INIT:
                self._init()
            elif cmd["type"] == self.CMD_START:
                self._start(cmd["args"]["genesis_file"])
            elif cmd["type"] == self.CMD_CLEANUP:
                self._cleanup()
            elif cmd["type"] == self.CMD_STOP:
                self._stop(cmd["args"]["cleanup"])
            elif cmd["type"] == self.CMD_DEINIT:
                self._deinit()
            cmd = self.cmd_queue.get()

    def _init(self):
        self._create_local_dir()
        self._init_host_connections()
        local_docker = docker.from_env()
        self.local_connections = HostManager.get_local_connections()
        try:
            local_geth_node = local_docker.containers.get(self.local_conf["node_name"])
            local_geth_node.stop()
            local_geth_node.remove()
            self.logger.info("Geth local node found, stopped and removed")
        except docker.errors.NotFound:
            self.logger.info("Geth local node not found, a new one will be created")
        except:
            raise
        try:
            local_network = local_docker.networks.create(
                self.local_conf["network_name"],
                driver="bridge",
                check_duplicate=True)
            if self.running_in_container:
                local_network.connect("orch-controller") #TODO Avoid embedding this string inside the code
            self.local_connections["docker"]["networks"][self.local_conf["network_name"]] = local_network
        except docker.errors.APIError as error:
            if error.status_code == 409:
                self.logger.info("[LOCAL]Network already deployed")
            else:
                self.logger.error(error)
        self._start_local_node()

    def _start_local_node(self, genesis_file_path=""):
        local_docker = self.local_connections["docker"]["client"]
        self._clean_local_dir(".ethereum/geth")
        if genesis_file_path != "":
            shutil.copyfile(genesis_file_path, self.get_local_datadir("genesis.json"))
            local_docker.containers.run("ethereum/client-go:stable", "init /root/genesis.json", volumes={
                self.local_conf["datadir"]: { # This points always to the controller host datadir
                    "bind": "/root",
                    "mode": "rw"
                }
            })
        local_geth_node = local_docker.containers.run(
            "ethereum/client-go:stable",
            "--rpc --rpcapi admin,eth,miner,personal,web3 --rpcaddr 0.0.0.0 --rpcvhosts=* --rpccorsdomain \"http://remix.ethereum.org\" --nodiscover", detach=True, volumes={
                self.local_conf["datadir"]: { # This points always to the controller host datadir
                    'bind': '/root',
                    'mode': 'rw'
                }
            }, ports={
                '8545/tcp': '8545',
                '8546/tcp': '8546',
                '30303/tcp': '30303',
                '30303/udp': '30303',
            }, name=self.local_conf["node_name"], network=self.local_conf["network_name"])
        self.local_connections["docker"]["containers"][self.local_conf["node_name"]] = local_geth_node
        if self.running_in_container:
            self.local_connections["web3"] = Web3(HTTPProvider("http://%s:8545" % self.local_conf["node_name"]))
        else:
            self.local_connections["web3"] = Web3(HTTPProvider("http://localhost:8545"))
        if self.check_web3_cnx(self.local_connections["web3"]):
            self.logger.info("Initialized local eth node")
        else:
            raise Exception("Can't contact local Geth node. Please abort the deploy.")

    def _init_host_connections(self):
        self.host_connections = {}
        for host in self.hosts:
            self.host_connections[host] = {
                "docker": {
                    "client": docker.DockerClient(base_url='tcp://%s:%d' % (host, self.docker_remote_api_port)),
                    "containers": {},
                    "networks": {}
                },
                "ssh": Connection(host=host, user=self.host_conf["ssh_username"])
            }

    def _init_genesis(self, n_nodes, genesis_file_path):
        self._clean_local_dir(".ethereum/keystore")
        with open(genesis_file_path) as genesis_file:
            genesis_dict = json.load(genesis_file)
        if not "alloc" in genesis_dict or not isinstance(genesis_dict["alloc"], dict):
            genesis_dict["alloc"] = {}
        web3_local = self.local_connections["web3"]
        self.miner_accounts = []
        for i in range(n_nodes+1):
            newAccount = web3_local.personal.newAccount(self.host_conf["account_password"])
            genesis_dict["alloc"][newAccount] = {}
            genesis_dict["alloc"][newAccount]["balance"] = "0x200000000000000000000000000000000000000000000000000000000000000"
            if i == n_nodes and self.local_conf["default_account"] == "":
                self.local_conf["default_account"] = newAccount
                self.local_conf["default_account_password"] = self.host_conf["account_password"]
            else:
                self.miner_accounts.append(newAccount)
            time.sleep(0.05) # To ensure that keyfile names are ordered according to creation time
        if self.consensus_protocol == self.CLIQUE:
            extra_data = "0x0000000000000000000000000000000000000000000000000000000000000000"
            for account in self.miner_accounts:
                extra_data += account[2:]
            extra_data += "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
            genesis_dict["extraData"] = extra_data
        with open(genesis_file_path, "w") as genesis_file:
            json.dump(genesis_dict, genesis_file)
        return genesis_dict
    
    def _copy_genesis(self, host, file_path):
        datadir = self.host_conf["datadir"]
        connection = self.host_connections[host]["ssh"]
        make_datadir = connection.run('mkdir -p ' + datadir)
        if not make_datadir.ok:
            print("Error creating datadir %s" % datadir)
            return
        connection.put(file_path, remote=os.path.join(datadir, "genesis.json"))
    
    def _copy_account_key(self, host, account_key): #TODO Must manage the errors
        remote_path = os.path.join(self.host_conf["datadir"], ".ethereum/keystore")
        ssh_cnx = self.host_connections[host]["ssh"]
        make_keystore_dir = ssh_cnx.run("mkdir -p %s" % remote_path)
        if not make_keystore_dir.ok:
            self.logger.error("[{0}]Error creating keystore dir".format(host))
            return
        ssh_cnx.put(account_key, remote=remote_path)
    
    def _create_local_dir(self):
        if not os.path.exists(self.get_local_datadir()):
            os.makedirs(self.get_local_datadir())

    def _clean_local_dir(self, subdir=""):
        try:
            to_clean = self.get_local_datadir(subdir)
            self.logger.debug("Cleaning %s" % to_clean)
            shutil.rmtree(to_clean)
            self.logger.info("Local %s successfully cleaned" % subdir)
        except FileNotFoundError:
            self.logger.warning("%s not cleaned because not found" % subdir)
        except Exception as error:
            self.logger.error(error)


    def _start(self, genesis_file, include_local_node=True):
        deployers = []
        host_queue = queue.Queue()
        self._init_genesis(len(self.hosts), genesis_file)
        pvt_key_file_list = sorted(os.listdir(self.get_keystore_dir()), reverse=True)
        for host in self.hosts:
            key_file = pvt_key_file_list.pop()
            host_queue.put({"host": host, "etherbase_key_file": key_file})
        for _ in range(min(self.N_DEPLOYER_THREADS, len(self.hosts))):
            deployer = Thread(target=self._start_node_thread, args=(genesis_file, host_queue,))
            deployer.start()
            deployers.append(deployer)
            host_queue.put("") # The empty string is the stop signal for the _start_node_thread
            time.sleep(1)
        for deployer in deployers:
            deployer.join()
        if include_local_node:
            local_node = self.local_connections["docker"]["containers"][self.local_conf["node_name"]]
            local_node.stop()
            local_node.remove()
            self._start_local_node(genesis_file)
        self.deployed_keys_available.set()
        self.full_mesh()
        
    def _start_node_thread(self, genesis_file, host_queue): #TODO set mining threads
        host_data = host_queue.get()
        while host_data != "":
            host = host_data["host"]
            etherbase_key_file = host_data["etherbase_key_file"]
            self.logger.debug("Deploying node at %s" % host)
            self._copy_genesis(host, genesis_file)
            self._copy_account_key(host, os.path.join(self.get_keystore_dir(), etherbase_key_file))
            self._copy_password(host, self.host_conf["account_password"])
            etherbase = etherbase_key_file.split("--")[2]
            docker_client = self.host_connections[host]["docker"]["client"]
            try:
                geth_node = docker_client.containers.get(self.host_conf["node_name"])
                geth_node.stop()
                geth_node.remove()
                self.logger.debug("[{0}]Geth node found, stopped and removed".format(host))
            except docker.errors.NotFound:
                pass
            self._init_node_network(host)
            docker_client.containers.run("ethereum/client-go:stable", "init /root/genesis.json", volumes={
                self.host_conf["datadir"]: {
                    "bind": "/root",
                    "mode": "rw"
                }
            })
            self.logger.debug("[{0}]DB initiated".format(host))
            self.host_connections[host]["docker"]["containers"][self.host_conf["node_name"]] = docker_client.containers.run(
                "ethereum/client-go:stable",
                "--rpc --rpcaddr 0.0.0.0 --rpcvhosts=* --rpcapi admin,eth,miner,personal,web3 --nodiscover --etherbase {0} --unlock {0} --password {1} --mine --minerthreads 2 --gasprice 1".format(etherbase, "/root/password"),
                name=self.host_conf["node_name"],
                volumes={
                    self.host_conf["datadir"]: {
                        "bind": "/root",
                        "mode": "rw"
                    }
                }, ports={
                    '8545/tcp': '8545',
                    '8546/tcp': '8546',
                    '30303/tcp': '30303',
                    '30303/udp': '30303',
                }, detach=True, network=self.host_conf["network_name"])
            self.host_connections[host]["web3"] = Web3(HTTPProvider("http://%s:8545" % host))
            version = self.check_web3_cnx(self.host_connections[host]["web3"])
            if version:
                self.logger.debug("[{0}]Geth node up".format(host))
            else:
                self.logger.error("[{0}]Error deploying node".format(host))
            
            self.deployed_keys[host] = etherbase
            self.logger.info("[{0}]Deployed Geth node with etherbase {1}".format(host, etherbase))
            host_data = host_queue.get()
        
    def _copy_password(self, host, password, password_file_name="password"):
        ssh_cnx = self.host_connections[host]["ssh"]
        ssh_cnx.run("echo {0} > {1}".format(password, os.path.join(self.host_conf["datadir"], password_file_name)))
    
    def _init_node_network(self, host):
        network_name = self.host_conf["network_name"]
        docker_client = self.host_connections[host]["docker"]["client"]
        networks = docker_client.networks.list(names=[network_name])
        if len(networks) == 1:
            self.host_connections[host]["docker"]["networks"][network_name] = networks[0]
            self.logger.info("[{0}]Network already deployed".format(host))
        else:
            for network in networks:
                network.remove()
            self.host_connections[host]["docker"]["networks"][self.host_conf["network_name"]] = docker_client.networks.create(
                self.host_conf["network_name"],
                driver="bridge")
            self.logger.info("[{0}]Network deployed".format(host))
    
    def _cleanup(self):
        for host in self.hosts:
            self._cleanup_host(host)
    
    def _cleanup_host(self, host):
        docker_client = self.host_connections[host]["docker"]["client"]
        try:
            geth_node = docker_client.containers.get(self.host_conf["node_name"])
            geth_node.stop()
            geth_node.remove()
            self.logger.info("[{0}]Geth node found, stopped and removed".format(host))
        except docker.errors.APIError as error:
            if error.status_code == 404:
                pass
            else:
                raise
        ssh = self.host_connections[host]["ssh"]
        ssh.sudo("rm -rf %s" % self.host_conf["datadir"])
        self.logger.info("[{0}]Data cleaned".format(host))

    def _stop(self, cleanup=False):
        for host in self.hosts:
            for _, container in self.host_connections[host]["docker"]["containers"].items():
                container.stop()
                container.remove()
            self.logger.info("[%s]Stopped" % host)
            if cleanup:
                self._cleanup_host(host)
    
    def _deinit(self):
        for _, container in self.local_connections["docker"]["containers"].items():
            container.stop()
            container.remove()
        self.local_connections["docker"]["client"].close()
        for host in self.hosts:
            self.host_connections[host]["docker"]["client"].close()
            self.host_connections[host]["ssh"].close()

    def get_enode(self, host=None):
        if host:
            web3 = self.host_connections[host]["web3"]
        else:
            web3 = self.local_connections["web3"]
            host = self.local_connections["ip"]
        requested_enode = web3.admin.nodeInfo["enode"]
        at_index = requested_enode.find("@")
        port_index = requested_enode.find(":30303")
        return requested_enode[0:at_index+1] + host + requested_enode[port_index:]
    
    def get_local_datadir(self, join_dir=""):
        if self.running_in_container:
            return os.path.join(self.local_conf["container_datadir"], join_dir)
        else:
            return os.path.join(self.local_conf["datadir"], join_dir)
    
    def set_local_datadir(self, datadir):
        self.local_conf["datadir"] = datadir
    
    def get_keystore_dir(self):
        return self.get_local_datadir(".ethereum/keystore")
    
    @staticmethod
    def check_web3_cnx(web3, attempts=10, delay_between_attempts=1):
        a = 0
        while a < attempts:
            try:
                return web3.version.node
            except: #TODO should see if it is worth to continue basing on which exception is raised
                a += 1
                time.sleep(delay_between_attempts)
        return False
            


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from host_manager import HostManager
    import sys
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
    time.sleep(100)
    manager.stop()
    manager.deinit()
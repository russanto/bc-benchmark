import docker
from fabric import Connection
import json
import logging
import os
from threading import Thread
import time
from web3 import Web3, HTTPProvider, WebsocketProvider
import web3.admin

class GethManager:

    docker_remote_api_port = 2375

    host_conf = {
        "datadir": "/home/ubuntu/ethereum",
        "network_name": "benchmark",
        "node_name": "geth-node",
        "ssh_username": "ubuntu"
    }

    local_conf = {
        "datadir": "/home/ubuntu/ethereum",
        "network_name": "benchmark",
        "node_name": "geth-node"
    }

    host_pvt_key_pw = ""

    def __init__(self, hosts): #TODO Use symbolic names for dns resolution in custom docker network
        self.hosts = hosts
        self.is_initialized = False
        self.logger = logging.getLogger("GethManager")

    # Lifecycle methods

    def init(self, running_in_container=True):
        self._init_host_connections()
        local_docker = docker.from_env()
        self.local_connections = {"docker": {"client": local_docker, "containers": {}, "networks": {}}}
        try:
            local_geth_node = local_docker.containers.get(self.local_conf["node_name"])
            local_geth_node.stop()
            local_geth_node.remove()
            self.logger.debug("Geth local node found, stopped and removed")
        except docker.errors.NotFound:
            self.logger.debug("Geth local node not found, a new one will be created")
        except:
            raise
        try:
            local_network = local_docker.networks.create(
                self.local_conf["network_name"],
                driver="bridge",
                check_duplicate=True)
            self.local_connections["docker"]["networks"][self.local_conf["network_name"]] = local_network
        except:
            self.logger.info("[LOCAL]Network already deployed")
        local_geth_node = local_docker.containers.run(
            "ethereum/client-go:stable",
            "--rpc --rpcapi personal,web3 --rpcaddr 0.0.0.0 --nodiscover", detach=True, volumes={
                self.local_conf["datadir"]: {
                    'bind': '/root',
                    'mode': 'rw'
                }
            }, ports={
                '8545/tcp': '8545'
            }, name=self.local_conf["node_name"], network=self.local_conf["network_name"])
        self.local_connections["docker"]["containers"][self.local_conf["node_name"]] = local_geth_node
        if running_in_container:
            self.local_connections["web3"] = Web3(HTTPProvider("http://%s:8545" % local_geth_node.attrs['NetworkSettings']['IPAddress']))
        else:
            self.local_connections["web3"] = Web3(HTTPProvider("http://localhost:8545"))
        self.check_web3_cnx(self.local_connections["web3"], 3, 2)
        self.logger.info("Initialized local eth node")
        

    def start(self, genesis_file, wait=True):
        if wait:
            self._start(genesis_file)
        else:
            start_th = Thread(target=self._start, args=(genesis_file,))
            start_th.start()

    def stop(self, cleanup=False):
        for host in self.hosts:
            for _, container in self.host_connections[host]["docker"]["containers"].items():
                container.stop()
                container.remove()
            if cleanup:
                self.cleanup(host=host)

    def cleanup(self, host=None):
        if host == None:
            for host in self.hosts:
                self._cleanup(host)
        else:
            self._cleanup(host)
    
    def deinit(self):
        for _, container in self.local_connections["docker"]["containers"].items():
            container.stop()
            container.remove()
        self.local_connections["docker"]["client"].close()
        for host in self.hosts:
            for _, network in self.host_connections[host]["docker"]["networks"].items():
                network.remove()
                self.logger.info("[{0}]Network removed".format(host))
            self.host_connections[host]["docker"]["client"].close()
            self.host_connections[host]["ssh"].close()

    # Topology definition methods

    def full_mesh(self): #TODO _start_node function should populate enodes array
        enodes = []
        for host in self.hosts:
            web3 = self.host_connections[host]["web3"]
            enode = self.substitute_enode_ip(web3.admin.nodeInfo["enode"], host)
            enodes.append(enode)
            self.logger.debug("Added enode: %s" % enode)
            for i in range(len(enodes)-1):
                web3.admin.addPeer(enodes[i])
                self.logger.debug("Added node %s to node %s", enodes[i], host)

    # Utility methods. These should not be called from externally.

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
        with open(genesis_file_path) as genesis_file:
            genesis_dict = json.load(genesis_file)
        if not "alloc" in genesis_dict or not isinstance(genesis_dict["alloc"], dict):
            genesis_dict["alloc"] = {}
        for _ in range(n_nodes):
            newAccount = self.local_connections["web3"].personal.newAccount(self.host_pvt_key_pw)
            genesis_dict["alloc"][newAccount] = {}
            genesis_dict["alloc"][newAccount]["balance"] = "0x200000000000000000000000000000000000000000000000000000000000000"
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
        connection.put(file_path, remote=datadir + "/genesis.json")

    def _start(self, genesis_file): #TODO launch multiple parallel threads
        self._init_genesis(len(self.hosts), genesis_file)
        keystore_dir = os.path.join(self.local_conf["datadir"], ".ethereum/keystore")
        pvt_key_file_list = os.listdir(keystore_dir)
        for host in self.hosts:
            self._copy_genesis(host, genesis_file)
            key_file = pvt_key_file_list.pop()
            key_file_address = key_file.split("--")[2]
            self._start_node(host, key_file_address)
            web3 = self.host_connections[host]["web3"]
            with open(os.path.join(keystore_dir, key_file)) as pvt_key_file:
                pvt_key_enc = pvt_key_file.read()
                pvt_key = web3.eth.account.decrypt(pvt_key_enc, self.host_pvt_key_pw)
                web3.personal.importRawKey(pvt_key, self.host_pvt_key_pw)
                self.logger.info("[{0}]Imported {1} private key".format(host, key_file_address))
        self.full_mesh()

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
        
    def _start_node(self, host, etherbase): #TODO set mining threads
        self.logger.debug("Deploying node at %s" % host)
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
            "--rpc --rpcaddr 0.0.0.0 --rpcapi admin,eth,miner,personal,web3 --nodiscover --etherbase {0} --mine --minerthreads 2".format(etherbase),
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
        version = self.check_web3_cnx(self.host_connections[host]["web3"], 4, 1)
        if version:
            self.logger.info("[{0}]Deployed Geth node with etherbase {1}".format(host, etherbase))
        else:
            self.logger.error("[{0}]Error deploying node".format(host))
    
    def _cleanup(self, host):
        self.logger.info("[{0}]Data cleaned".format(host))
        ssh = self.host_connections[host]["ssh"]
        ssh.sudo("rm -rf %s" % self.host_conf["datadir"])

    @staticmethod
    def substitute_enode_ip(enode, new_ip):
        at_index = enode.find("@")
        port_index = enode.find(":30303")
        return enode[0:at_index+1] + new_ip + enode[port_index:]
    
    @staticmethod
    def check_web3_cnx(web3, attempts, delay_between_attempts):
        a = 0
        while a < attempts:
            try:
                return web3.version.node
            except:
                a += 1
                time.sleep(delay_between_attempts)
        return False
            


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from host_manager import HostManager
    host_manager = HostManager("hosts", False)
    hosts = host_manager.get_hosts()
    manager = GethManager(hosts)
    manager.init(False)
    manager.start("genesis.json")
    time.sleep(180)
    manager.stop(cleanup=True)
    manager.deinit()
    host_manager.close()
import docker
from fabric import Connection
import json
import logging
import os
from queue import Queue
import shutil
from threading import Event, Thread
import time
from web3 import Web3, HTTPProvider, WebsocketProvider

from bc_orch_sdk.deploy_manager import DeployManager

from ethereum_node import EthereumNode
from host_manager import HostManager
from bc_orch_sdk.rmq_host_manager_services_provider import RMQHostManagerServicesProvider

# TODO: Implement wait function for bc to be ready

class GethManager(DeployManager):

    ETHASH = "ethash"
    CLIQUE = "clique"

    local_datadir = "/root/geth"
    remote_datadir = "/home/ubuntu/ethereum"

    docker_image_name = 'ethereum/client-go:stable'
    docker_node_name = "geth-node"
    docker_network_name = "benchmark"

    FILE_CLIQUE = "./geth/clique.json"
    FILE_ETHASH = "./geth/genesis.json"

    upload_all_keys = True

    @property
    def local_keystore(self):
        return os.path.join(self.local_datadir, "keystore")

    @property
    def remote_keystore(self):
        return os.path.join(self.remote_datadir, "keystore")

    @property
    def FILE_PASSWORD(self):
        return os.path.join(self.local_datadir, "password.txt")

    account_password = "password"

    def __init__(self, local_node_dir, host_manager_services_provider):
        super().__init__()
        super().register_service_provider(host_manager_services_provider)
        self.local_datadir = local_node_dir
        self.logger = logging.getLogger("GethManager")
        self.consensus_protocol = self.ETHASH
        self.nodes = {}
        self.local_connections = HostManager.get_local_connections()
        self.hosts_connections = {}
        self.__init_local_dir()
        self.__create_password_file()
        self.accounts = []
    
    def set_consensus_protocol(self, protocol):
        if protocol == self.ETHASH or protocol == self.CLIQUE:
            self.consensus_protocol = protocol
        else:
            self.consensus_protocol = self.ETHASH
            self.logger.error("Consensus protocol not valid, using ethash as default")

    # Utility methods. These should not be called from externally.

    def _init_setup(self, hosts):
        ssh_req = super().request_service('ssh', hosts)
        docker_req = super().request_service('docker', hosts, {'images': [self.docker_image_name]})
        ssh_connections = super().wait_service('ssh', ssh_req)
        docker_service = super().wait_service('docker', docker_req)
        for host in hosts:
            self.hosts_connections[host] = {
                'ssh': ssh_connections[host],
                'docker': {
                    'client': docker_service['connections'][host],
                    'containers': {},
                    'networks': {}
                }
            }
        if self.docker_image_name in docker_service['images']:
            self.docker_image_name = docker_service['images'][self.docker_image_name]
        else:
            self.logger.warning("Image %s hasn't been prepared before on hosts", self.docker_image_name)
        self.__start_local_node()
    
    def _init_loop(self, host):
        node = EthereumNode(host, EthereumNode.TYPE_GETH)
        self.nodes[host] = node
        self.accounts.append(self.local_node.web3.personal.newAccount(self.account_password))

    def _init_teardown(self, hosts):
        self.__init_genesis()
    
    def _start_setup(self, hosts, conf):
        self.pvt_key_queue = Queue()
        pvt_key_file_list = os.listdir(os.path.join(self.local_datadir, "keystore"))
        for key in pvt_key_file_list:
            self.pvt_key_queue.put(key)

    def _start_loop(self, host, conf):
        etherbase_key_file = self.pvt_key_queue.get()
        self.logger.debug("Deploying node at %s" % host)
        self.hosts_connections[host]['ssh'].sudo("rm -rf %s" % self.remote_datadir)
        self.__upload_node_files(host, os.path.join(self.local_keystore, etherbase_key_file))
        if self.upload_all_keys:
            all_keys = os.listdir(os.path.join(self.local_datadir, "keystore"))
            all_keys.remove(etherbase_key_file)
            self.__upload_keys(host, all_keys)
        etherbase = etherbase_key_file.split("--")[2]
        docker_client = self.hosts_connections[host]["docker"]["client"]
        try:
            geth_node = docker_client.containers.get(self.docker_node_name)
            geth_node.stop()
            geth_node.remove()
            self.logger.debug("[{0}]Geth node found, stopped and removed".format(host))
        except docker.errors.NotFound:
            pass
        self.__init_node_network(host)
        docker_client.containers.run("ethereum/client-go:stable", "init /root/.ethereum/genesis.json", volumes={
            self.remote_datadir: {
                "bind": "/root/.ethereum",
                "mode": "rw"
            }
        })
        self.logger.debug("[{0}]DB initiated".format(host))
        start_args = "--nodiscover --etherbase {0} --unlock {0} --password {1} --allow-insecure-unlock --nousb".format(etherbase, "/root/.ethereum/password.txt")
        start_args += " --rpc --rpcaddr 0.0.0.0 --rpcvhosts=* --rpcapi admin,eth,miner,personal,net,web3 --rpccorsdomain '*'"
        start_args += " --ws --wsaddr 0.0.0.0 --wsapi admin,eth,miner,personal,net,web3 --wsorigins '*'"
        start_args += " --mine --minerthreads 2 --gasprice 1"
        start_args += " --verbosity 5"
        self.hosts_connections[host]["docker"]["containers"][self.docker_node_name] = docker_client.containers.run(
            "ethereum/client-go:stable",
            start_args,
            name=self.docker_node_name,
            volumes={
                self.remote_datadir: {
                    "bind": "/root/.ethereum",
                    "mode": "rw"
                }
            }, ports={
                '8545/tcp': '8545',
                '8546/tcp': '8546',
                '30303/tcp': '30303',
                '30303/udp': '30303',
            }, detach=True, network=self.docker_network_name)
        self.nodes[host].account = Web3.toChecksumAddress("0x" + etherbase), self.account_password
        if self.nodes[host].ready():
            self.logger.info("[{0}]Deployed Geth node with etherbase {1}".format(host, self.nodes[host].account))
        else:
            self.logger.error("[{0}]Error deploying node".format(host))
        
    def _start_teardown(self, hosts, conf):
        self.utility_node = self.nodes[hosts[0]]
        self.logger.info("Using %s as utility node" % self.utility_node.host)
        self.__full_mesh()
    
    # def _cleanup_loop(self, host):
    #     docker_client = self.hosts_connections[host]["docker"]["client"]
    #     try:
    #         geth_node = docker_client.containers.get(self.docker_node_name)
    #         geth_node.stop()
    #         geth_node.remove()
    #         self.logger.info("[{0}]Geth node found, stopped and removed".format(host))
    #     except docker.errors.APIError as error:
    #         if error.status_code == 404:
    #             pass
    #         else:
    #             raise
    #     ssh = self.hosts_connections[host]["ssh"]
    #     ssh.sudo("rm -rf %s" % self.remote_datadir)
    #     self.logger.info("[{0}]Data cleaned".format(host))

    def _stop_loop(self, host):
        for _, container in self.hosts_connections[host]["docker"]["containers"].items():
            container.stop()
            container.remove()
        self.logger.info("[%s]Stopped" % host)

    def _deinit_setup(self, hosts):
        pvt_key_file_list = os.listdir(os.path.join(self.local_datadir, "keystore"))
        for _ in range(len(hosts)):
            os.remove(os.path.join(self.local_keystore, pvt_key_file_list.pop()))

    def _deinit_loop(self, host):
        del self.nodes[host]

    
    # Private utility methods

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

    def __create_password_file(self):
        with open(self.FILE_PASSWORD, "w") as pw_file:
            pw_file.write(self.account_password)

    def __init_genesis(self):
        if self.consensus_protocol == self.ETHASH:
            genesis_file_path = self.FILE_ETHASH
        else:
            genesis_file_path = self.FILE_CLIQUE
        with open(genesis_file_path) as genesis_file:
            genesis_dict = json.load(genesis_file)
        alloc_accounts = {}
        balance_prototype = {"balance":"0x200000000000000000000000000000000000000000000000000000000000000"}
        for account in self.accounts:
            alloc_accounts[account] = balance_prototype.copy()
        genesis_dict["alloc"] = alloc_accounts
        if self.consensus_protocol == self.CLIQUE:
            extra_data = "0x0000000000000000000000000000000000000000000000000000000000000000"
            for account in self.accounts:
                extra_data += account[2:]
            extra_data += "0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
            genesis_dict["extraData"] = extra_data
        with open(genesis_file_path, "w") as genesis_file:
            json.dump(genesis_dict, genesis_file)
        self.logger.info("Genesis block file written at " + genesis_file_path)

    def __upload_node_files(self, host, pvt_key_file):
        connection = self.hosts_connections[host]["ssh"]
        make_datadir = connection.run('mkdir -p ' + self.remote_datadir)
        if not make_datadir.ok:
            raise Exception("[%s]Error creating datadir %s" % self.remote_datadir)
        if self.consensus_protocol == self.ETHASH:
            genesis_file = self.FILE_ETHASH
        else:
            genesis_file = self.FILE_CLIQUE
        connection.put(genesis_file, remote=os.path.join(self.remote_datadir, "genesis.json"))
        connection.put(self.FILE_PASSWORD, remote=os.path.join(self.remote_datadir, "password.txt"))
        make_keystore_dir = connection.run("mkdir -p %s" % self.remote_keystore)
        if not make_keystore_dir.ok:
            raise Exception("[%s]Error creating keystore dir %s" % (host, self.remote_keystore))
        connection.put(pvt_key_file, remote=os.path.join(self.remote_keystore, os.path.basename(pvt_key_file)))

    def __upload_keys(self, host, keys):
        ssh = self.hosts_connections[host]["ssh"]
        for key in keys:
            ssh.put(os.path.join(self.local_keystore, key), remote=os.path.join(self.remote_keystore, os.path.basename(key)))
        self.logger.info("[%s] All pvt keys uploaded" % host)
    
    def __start_local_node(self):
        local_docker = self.local_connections["docker"]["client"]
        # Removes previous executions geth nodes
        try:
            local_geth_node = local_docker.containers.get(self.docker_node_name)
            local_geth_node.stop()
            local_geth_node.remove()
            self.logger.info("Geth local node found, stopped and removed")
        except docker.errors.NotFound:
            self.logger.info("Geth local node not found, a new one will be created")
        except:
            raise
        # Ensure that the docker network exists
        try:
            local_network = local_docker.networks.create(
                self.docker_network_name,
                driver="bridge",
                check_duplicate=True)
            if HostManager.running_in_container:
                local_network.connect("orch-controller") #TODO Avoid embedding this string inside the code
            self.local_connections["docker"]["networks"][self.docker_network_name] = local_network
        except docker.errors.APIError as error:
            if error.status_code == 409:
                self.logger.info("[LOCAL]Network already deployed")
            else:
                self.logger.error(error)
        local_geth_node = local_docker.containers.run(
            self.docker_image_name,
            "--rpc --rpcapi admin,eth,miner,personal,net,web3 --rpcaddr 0.0.0.0 --rpcvhosts=* --nodiscover",
            detach=True,
            volumes={
                HostManager.resolve_local_path(self.local_datadir): { # This points always to the controller host datadir
                    'bind': '/root/.ethereum',
                    'mode': 'rw'
                }
            }, ports={
                '8545/tcp': '8545',
                '8546/tcp': '8546',
                '30303/tcp': '30303',
                '30303/udp': '30303',
            }, name=self.docker_node_name, network=self.docker_network_name)
        self.local_connections["docker"]["containers"][self.docker_node_name] = local_geth_node
        if HostManager.running_in_container:
            node = EthereumNode(self.docker_node_name, EthereumNode.TYPE_GETH)
        else:
            node = EthereumNode("localhost", EthereumNode.TYPE_GETH)
        if node.ready():
            self.local_node = node
            self.logger.info("Initialized local Geth node")
            return True
        else:
            raise Exception("Can't contact local Geth node. Please abort the deploy.")
        
    def __init_node_network(self, host):
        if self.docker_network_name in self.hosts_connections[host]["docker"]["networks"]:
            self.logger.info("[{0}]Network already deployed".format(host))
            return
        docker_client = self.hosts_connections[host]["docker"]["client"]
        networks = docker_client.networks.list(names=[self.docker_network_name])
        if len(networks) == 1:
            self.hosts_connections[host]["docker"]["networks"][self.docker_network_name] = networks[0]
            self.logger.info("[{0}]Network already deployed".format(host))
        else:
            for network in networks:
                network.remove()
            network = docker_client.networks.create(self.docker_network_name, driver="bridge")
            self.hosts_connections[host]["docker"]["networks"][self.docker_network_name] = network
            self.logger.info("[{0}]Network deployed".format(host))

    def __full_mesh(self):
        for node in self.nodes.values():
            for peer in self.nodes.values():
                if node != peer:
                    node.web3.admin.addPeer(peer.enode)
                    self.logger.debug("Added %s to %s" % (peer.enode, node.enode))
        self.logger.info("Nodes connected in a full mesh network")
            

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("paramiko.transport").setLevel(logging.WARNING)

    from host_manager import HostManager
    import sys

    host_list = ['192.168.99.106','192.168.99.107','192.168.99.108']

    service_provider = RMQHostManagerServicesProvider(None)

    manager = GethManager(os.environ["LOCAL_NODE_DIR"], service_provider)
    manager.set_consensus_protocol(GethManager.CLIQUE)
    manager.init([host_list[0]])
    manager.start({})
    time.sleep(50)
    manager.stop()
    manager.init([host_list[1], host_list[2]])
    manager.start({})
    time.sleep(50)
    manager.stop()
    manager.deinit([host_list[1]])
    manager.start({})
    time.sleep(50)
    manager.stop()
    manager.deinit([host_list[0], host_list[2]])
from fabric import Connection
import logging
from threading import Thread
import time
from web3 import Web3, HTTPProvider, WebsocketProvider
import web3.admin

class GethManager:

    data_dir = "/home/ubuntu/ethereum"
    ssh_username = "ubuntu"

    def __init__(self, hosts):
        self.hosts = hosts
        self.enodes = []
        self.ssh_connections = []
        self.logger = logging.getLogger("GethManager")

    def start(self, genesis_file, wait=True):
        if wait:
            self._start(genesis_file)
        else:
            start_th = Thread(target=self._start, args=(genesis_file,))
            start_th.start()

    def _start(self, genesis_file): #TODO launch multiple parallel threads
        for host in self.hosts:
            self.logger.info("Deploying on %s" % host)
            cnx = Connection(host=host, user=self.ssh_username)
            self.copy_genesis(cnx, genesis_file)
            self.start_node(cnx)
            self.ssh_connections.append(cnx)
            self.logger.info("Deployed %s" % host)
        self.full_mesh()
        

    def copy_genesis(self, connection, file):
        make_datadir = connection.run('mkdir -p ' + self.data_dir)
        if not make_datadir.ok:
            print("Error creating datadir %s" % self.data_dir)
            return
        connection.put(file, remote=self.data_dir + "/genesis.json")
    
    def start_node(self, connection):
        connection.run("docker run -v %s:/root ethereum/client-go init /root/genesis.json" % (self.data_dir), hide=True)
        connection.run("docker run -d -v %s:/root --name ethereum-node -p 8545:8545 -p 8546:8546 -p 30303:30303 -p 30303:30303/udp ethereum/client-go:stable --rpc --rpcaddr 0.0.0.0 --rpcapi admin,eth,miner,web3 --mine --minerthreads=1 --etherbase=0x0000000000000000000000000000000000000001" % (self.data_dir), hide=True)

    def full_mesh(self):
        self.web3_connections = {}
        for cnx in self.ssh_connections:
            web3 = Web3(HTTPProvider("http://%s:8545" % cnx.host))
            self.web3_connections[cnx.host] = web3
            enode = self.substitute_enode_ip(web3.admin.nodeInfo["enode"], cnx.host)
            self.logger.debug("Added enode: %s" % enode)
            self.enodes.append(enode)
            for host, web3_cnx in self.web3_connections.items():
                for enode in self.enodes:
                    web3_cnx.admin.addPeer(enode)
                    self.logger.debug("Added node %s to node %s", enode, host)
    
    def substitute_enode_ip(self, enode, new_ip):
        at_index = enode.find("@")
        port_index = enode.find(":30303")
        return enode[0:at_index+1] + new_ip + enode[port_index:]

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from host_manager import HostManager
    host_manager = HostManager("hosts", False)
    hosts = host_manager.get_hosts()
    manager = GethManager(hosts)
    manager.start("genesis.json")
    host_manager.close()
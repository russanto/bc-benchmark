from fabric import Connection
import logging
from threading import Thread
import time

class GethManager:

    data_dir = "/home/ubuntu/ethereum"
    ssh_username = "ubuntu"

    def __init__(self, hosts):
        self.hosts = hosts
        self.enodes = []

    def start(self, genesis_file):
        for host in self.hosts:
            cnx = Connection(host=host, user=self.ssh_username)
            self.copy_genesis(cnx, genesis_file)
            self.start_node(cnx)

    def copy_genesis(self, connection, file):
        make_datadir = connection.run('mkdir -p ' + self.data_dir)
        if not make_datadir.ok:
            print("Error creating datadir %s" % self.data_dir)
            return
        connection.put(file, remote=self.data_dir + "/genesis.json")
    
    def start_node(self, connection):
        connection.run("docker run -v %s:/root ethereum/client-go init /root/genesis.json" % (self.data_dir), hide=True)
        connection.run("docker run -d -v %s:/root --name ethereum-node -P ethereum/client-go --rpc --rpcaddr 0.0.0.0 --ws --wsaddr 0.0.0.0" % (self.data_dir), hide=True)
        enode_cmd = connection.run("docker run -v %s:/root -t ethereum/client-go attach --exec \"console.log(admin.nodeInfo.enode)\"" % (self.data_dir), hide=True)
        enode = enode_cmd.stdout.split("\n")[1].replace("127.0.0.1", connection.host)
        self.enodes.append(enode)
        

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    from host_manager import HostManager
    host_manager = HostManager("hosts", False)
    manager = GethManager(host_manager.get_hosts())
    manager.start("genesis.json")
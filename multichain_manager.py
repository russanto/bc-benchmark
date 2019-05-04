import docker
import logging
import os

from deploy_manager import DeployManager
from host_manager import HostManager

class MultichainManager(DeployManager):

    BITCOIN = "bitcoin"
    MULTICHAIN = "multichain"

    NODE_TYPE_SEED = "SEED"
    NODE_TYPE_PEER = "PEER"

    conf_dir = "./multichain"

    host_conf = {
        "datadir": "/home/ubuntu/multichain",
        "network_name": "benchmark",
        "container_name": "multichain-node",
        "ssh_username": "ubuntu",
        "node_network_port": 7411,
        "node_rpc_port": 7410
    }

    bc_name = "benchmark"

    def __init__(self, hosts, bc_protocol="multichain"):
        super().__init__(hosts)
        self.logger = logging.getLogger("MultichainManager")
        self.set_bc_protocol(bc_protocol)
    
    def set_bc_protocol(self, bc_protocol):
        if bc_protocol == self.BITCOIN or bc_protocol == self.MULTICHAIN:
            self.bc_protocol = bc_protocol
        else:
            self.logger.warning("{0} blockchain protocol is not supported. Switching to default {1}".format(bc_protocol, self.MULTICHAIN))
            self.bc_protocol = self.MULTICHAIN
    
    def get_datadir(self):
        return os.path.join(self.host_conf["datadir"], self.bc_name)

    def _init(self):
        self.hosts_connections = HostManager.get_hosts_connections(self.hosts)
    
    def _start_setup(self):
        if len(self.hosts) < 1:
            self.logger.warning("Host list is empty. No nodes will be created.")
            return
        self.seed_host = self.hosts[0]
        self._deploy_seed(self.seed_host)
    
    def _start_loop(self, host):
        if host == self.seed_host:
            self.logger.debug("[%s]Skipping node deploy on seed host" % host)
        else:
            self._deploy_node(host, self.seed_host)

    def _stop_setup(self):
        del self.seed_host
    
    def _stop_loop(self, host):
        docker_client = self.hosts_connections[host]["docker"]["client"]
        try:
            node = docker_client.containers.get(self.host_conf["container_name"])
            node.stop()
        except docker.errors.NotFound:
            pass
        self.logger.info("[%s]Successfully stopped" % host)
    
    def _cleanup_loop(self, host):
        docker_client = self.hosts_connections[host]["docker"]["client"]
        try:
            node = docker_client.containers.get(self.host_conf["container_name"])
            node.remove(force=True)
        except docker.errors.NotFound:
            pass
        self.hosts_connections[host]["ssh"].sudo("rm -rf " + self.get_datadir())
        self.logger.info("[%s]Successfully cleaned" % host)
        
    def _deploy_seed(self, host):
        docker_client = self.hosts_connections[host]["docker"]["client"]
        try:
            docker_client.ping()
        except docker.errors.APIError:
            self.logger.error("[%s]Can't contact docker engine. Seed deploy aborted." % host)
            return False
        connection = self.hosts_connections[host]["ssh"]
        datadir = self.get_datadir()
        make_datadir = connection.run('mkdir -p ' + datadir)
        if not make_datadir.ok:
            self.logger.error("[%s]Error creating datadir. Seed deploy aborted." % host)
            return False
        self.logger.debug("[%s][SEED]Created datadir directory" % host)
        connection.put(os.path.join(self.conf_dir, 'params.dat'), remote=datadir)
        self.logger.debug("[%s][SEED]Uploaded params.dat" % host)
        connection.put(os.path.join(self.conf_dir, 'multichain.conf'), remote=datadir)
        self.logger.debug("[%s][SEED]Uploaded multichain.conf" % host)
        self.hosts_connections[host]["docker"]["containers"] = docker_client.containers.run(
            self.dinr.resolve("multichain-node"),
            "multichaind %s -logtimemillis -shrinkdebugfile=0" % self.bc_name,
            detach=True,
            volumes={
                self.host_conf["datadir"]: {
                    "bind": "/root/.multichain",
                    "mode": "rw"
                }
            }, ports={
                "{0}/tcp".format(self.host_conf["node_network_port"]): self.host_conf["node_network_port"],
                "{0}/tcp".format(self.host_conf["node_rpc_port"]): self.host_conf["node_rpc_port"]
            }, environment={
                "CHAIN_NAME": self.bc_name
            }, name=self.host_conf["container_name"])
        self.logger.info("[%s]Seed successfully deployed" % host)
        connection.get(datadir + '/params.dat', os.path.join(self.conf_dir, "compiled-params.dat"))
        self.compiled_params = os.path.join(self.conf_dir, "compiled-params.dat")
        self.logger.info("[%s]Fetched compiled params.dat" % host)
        return True
    
    def _deploy_node(self, host, seed):
        if self.bc_protocol == self.BITCOIN and not hasattr(self, "compiled_params"):
            self.logger.error("[%s]Compiled params not available. Deploy aborted." % host)
        docker_client = self.hosts_connections[host]["docker"]["client"]
        try:
            docker_client.ping()
        except docker.errors.APIError:
            self.logger.error("[%s]Can't contact docker engine. Seed deploy aborted." % host)
            return False
        connection = self.hosts_connections[host]["ssh"]
        datadir = self.get_datadir()
        make_datadir = connection.run('mkdir -p ' + datadir)
        if not make_datadir.ok:
            self.logger.error("[%s]Error creating datadir. Seed deploy aborted." % host)
            return False
        self.logger.debug("[%s]Created datadir directory" % host)
        if self.bc_protocol == self.BITCOIN:
            connection.put(self.compiled_params, remote=os.path.join(datadir, "params.dat"))
            self.logger.debug("[%s]Uploaded params.dat" % host)
        connection.put(os.path.join(self.conf_dir, 'multichain.conf'), remote=datadir)
        self.logger.debug("[%s]Uploaded multichain.conf" % host)
        self.hosts_connections[host]["docker"]["containers"] = docker_client.containers.run(
            self.dinr.resolve("multichain-node"),
            "multichaind {0}@{1}:{2}".format(self.bc_name, seed, self.host_conf["node_network_port"]),
            detach=True,
            volumes={
                self.host_conf["datadir"]: {
                    "bind": "/root/.multichain",
                    "mode": "rw"
                }
            }, ports={
                "{0}/tcp".format(self.host_conf["node_network_port"]): self.host_conf["node_network_port"],
                "{0}/tcp".format(self.host_conf["node_rpc_port"]): self.host_conf["node_rpc_port"]
            }, environment={
                "CHAIN_NAME": self.bc_name
            }, name=self.host_conf["container_name"])
        self.logger.info("[%s]Node successfully deployed" % host)
        return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from host_manager import HostManager
    import sys, time
    hosts_file_path = sys.argv[1]
    host_manager = HostManager()
    host_manager.add_hosts_from_file(hosts_file_path)
    hosts = host_manager.get_hosts()
    manager = MultichainManager(hosts)
    manager.init()
    manager.cleanup()
    manager.start()
    time.sleep(60)
    manager.stop()
    manager.deinit()
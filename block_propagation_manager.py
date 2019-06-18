import logging
import os
import shutil

import docker

from deploy_manager import DeployManager
from host_manager import HostManager

class BlockPropagationManager(DeployManager):

    server_port = 8080
    datadir = "/root/block-propagation"

    docker_network_name = "benchmark"
    docker_container_server_name = "block_propagation_server"
    docker_container_client_name = "block_propagation_client"

    def __init__(self, hosts, container_node="geth"): #geth is the only currently supported
        super().__init__(hosts)
        self.logger = logging.getLogger("BlockPropagationManager")
        self.container_node = container_node

    def _init_setup(self):
        self.__init_datadir()
        self.local_connections = HostManager.get_local_connections()
        self.hosts_connections = HostManager.get_hosts_connections(self.hosts)
        local_docker = self.local_connections["docker"]["client"]
        try:
            local_network = local_docker.networks.create(
                self.docker_network_name,
                driver="bridge",
                check_duplicate=True)
            self.local_connections["docker"]["networks"][self.docker_network_name] = local_network
        except docker.errors.APIError as error:
            if error.status_code == 409:
                self.logger.info("[LOCAL]Network already deployed")
            else:
                self.logger.error(error)

    def _start_setup(self):
        local_docker = self.local_connections["docker"]["client"]
        try:
            previous_execution_container = local_docker.containers.get(self.docker_container_server_name)
            previous_execution_container.stop()
            previous_execution_container.remove()
            self.logger.debug("Previous execution server found, stopped and removed")
        except docker.errors.NotFound:
            pass
        server_container = local_docker.containers.run(
            self.dinr.resolve("bp-server"),
            "-log -nodes %d -csv delays.csv" % len(self.hosts),
            ports={
                "80/tcp": self.server_port
            }, volumes={
                HostManager.resolve_local_path(self.datadir): {
                    "bind":"/go/src/server/delay.csv",
                    "mode":"rw"
                }
            }, detach=True, network=self.docker_network_name, name=self.docker_container_server_name)
        self.local_connections["docker"]["containers"][self.docker_container_server_name] = server_container
        self.logger.info("Deployed server")

    def _start_loop(self, host):
        docker_client = self.hosts_connections[host]["docker"]["client"]
        try:
            previous_execution_container = docker_client.containers.get(self.docker_container_client_name)
            previous_execution_container.stop()
            previous_execution_container.remove()
            self.logger.debug("[{0}]Previous execution container found, stopped and removed".format(host))
        except docker.errors.NotFound:
            pass
        node_container = docker_client.containers.run(
            self.dinr.resolve("bp-client"),
            "{node_name} {container_name} {client} {server}".format_map({
                "node_name": host,
                "container_name": "geth-node",
                "client": self.container_node,
                "server": self.local_connections["ip"] + ":%d" % self.server_port
            }), volumes={
                "/var/run/docker.sock": {
                    "bind": "/var/run/docker.sock",
                    "mode": "rw"
                }
            }, detach=True, name=self.docker_container_client_name)
        self.hosts_connections[host]["docker"]["containers"][self.docker_container_client_name] = node_container
        self.logger.info("[%s]Deployed client" % host)

    def _stop_setup(self):
        for _, container in self.local_connections["docker"]["containers"].items():
            container.stop()
            container.remove()
        self.logger.info("[%s]Stopped log collector")

    def _stop_loop(self, host):
        for _, container in self.hosts_connections[host]["docker"]["containers"].items():
            container.stop()
            container.remove()
        self.logger.info("[%s]Stopped" % host)
    
    def __init_datadir(self):
        try:
            shutil.rmtree(self.datadir)
            os.makedirs(self.datadir)
            self.logger.info("Local datadir (%s) successfully cleaned" % self.datadir)
        except FileNotFoundError:
            os.makedirs(self.datadir)
            self.logger.info("Created local datadir (%s)" % self.datadir)
        except Exception as error:
            self.logger.error(error)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("paramiko.transport").setLevel(logging.WARNING)

    from host_manager import HostManager
    import sys
    
    hosts_file_path = sys.argv[1]
    host_manager = HostManager()
    host_manager.add_hosts_from_file(hosts_file_path)
    hosts = host_manager.get_hosts()
    manager = BlockPropagationManager(hosts)
    manager.init()
    manager.start()
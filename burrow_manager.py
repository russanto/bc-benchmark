import json
import logging
import os
import shutil

import docker

from deploy_manager import DeployManager
from host_manager import HostManager

class BurrowManager(DeployManager):

    local_datadir = "/root/burrow"
    remote_datadir = "/home/ubuntu/burrow"

    docker_network_name = "benchmark"
    docker_node_name = "burrow-node"

    chain_name = "benchmark"

    @property
    def file_spec(self):
        return os.path.join(self.local_datadir, "spec.json")

    @property
    def remote_config_file(self):
        return os.path.join(self.remote_datadir, "config.json")

    @property
    def remote_log_file(self):
        return os.path.join(self.remote_datadir, "burrow.log")

    def __init__(self, hosts, proposal_threshold):
        super().__init__(hosts)
        self.proposal_threshold = proposal_threshold
        self.logger = logging.getLogger("BurrowManager")
        if proposal_threshold > len(hosts):
            self.logger.warning("Given %d as proposal threshold, but only %d validators")

    def _init_setup(self):
        self.local_connections = HostManager.get_local_connections()
        self.hosts_connections = HostManager.get_hosts_connections(self.hosts)
        self.__init_local_dir()
        self.__init_local_network()

    def _start_setup(self):
        local_docker = self.local_connections["docker"]
        spec_string = local_docker["client"].containers.run(
            self.dinr.resolve("burrow-node"),
            "spec -f%d -n %s" % (len(self.hosts), self.chain_name))
        spec_data = json.loads(spec_string)
        spec_data["Params"]["ProposalThreshold"] = self.proposal_threshold
        with open(self.file_spec, "w") as spec_json_file:
            json.dump(spec_data, spec_json_file)
        doc_string = local_docker["client"].containers.run(
            self.dinr.resolve("burrow-node"),
            "configure -s spec.json -j -d --generate-node-keys -n %s" % self.chain_name,
            volumes={
                HostManager.resolve_local_path(self.local_datadir): {
                    "bind": "/home/burrow",
                    "mode": "rw"
                }
            })
        self.config_template = json.loads(doc_string)
        self.config_template["RPC"]["Info"]["ListenHost"] = "0.0.0.0"
        self.config_template["RPC"]["Profiler"]["ListenHost"] = "0.0.0.0"
        self.config_template["RPC"]["GRPC"]["ListenHost"] = "0.0.0.0"
        self.config_template["RPC"]["Metrics"]["ListenHost"] = "0.0.0.0"
    
    def _start_loop(self, host):
        host_index = self.hosts.index(host)
        config = self.config_template.copy()
        config["GenesisDoc"]["Params"]["ProposalThreshold"] = self.proposal_threshold # This is necessary due to a burrow configure bug
        config["Logging"]["RootSink"]["Output"]["OutputType"] = "file"
        config["Logging"]["RootSink"]["Output"]["Path"] = os.path.basename(self.remote_log_file)
        persistent_peers = ""
        tendermint_port = config["Tendermint"]["ListenPort"]
        for i, validator in enumerate(config["GenesisDoc"]["Validators"]):
            if i != host_index:
                if persistent_peers != "":
                    persistent_peers += ","
                persistent_peers += "tcp://%s@%s:%s" % (validator["NodeAddress"].lower(), self.hosts[i], tendermint_port)
        config["Tendermint"]["PersistentPeers"] = persistent_peers
        config_file = os.path.join(self.local_datadir, "config-%s.json" % host)
        with open(config_file, "w") as config_file_descriptor:
            json.dump(config, config_file_descriptor)
        if not self.__init_remote_datadir(host):
            raise Exception("[%s]Failed to initialiaze remote dir" % host)
        self.__copy_validator_files(host, host_index, config_file)
        docker_client = self.hosts_connections[host]["docker"]["client"]
        try:
            burrow_node = docker_client.containers.get(self.docker_node_name)
            burrow_node.stop()
            burrow_node.remove(force=True)
            self.logger.debug("[%s]An already existing burrow node has been removed")
        except docker.errors.NotFound:
            pass
        ports = {config["Tendermint"]["ListenPort"] + "/tcp": config["Tendermint"]["ListenPort"]}
        for _, rpc_config in config["RPC"].items():
            if rpc_config["Enabled"]:
                ports[rpc_config["ListenPort"] + "/tcp"] = rpc_config["ListenPort"]
        burrow_node = docker_client.containers.run(
            self.dinr.resolve("burrow-node"),
            "start -c %s -v %d" % (os.path.basename(self.remote_config_file), host_index),
            detach=True,
            name=self.docker_node_name,
            network=self.docker_network_name,
            ports=ports,
            volumes={
                self.remote_datadir: {
                    "bind": "/home/burrow",
                    "mode": "rw"
                }
            })
        self.hosts_connections[host]["docker"]["containers"][self.docker_node_name] = burrow_node
        self.logger.info("[%s]Node successfully deployed" % host)

    def _stop_loop(self, host):
        for container in self.hosts_connections[host]["docker"]["containers"].values():
            container.stop()
            container.remove(force=True)
        self.logger.info("[%s]Node successfully stopped" % host)
    
    def _deinit_loop(self, host):
        self.hosts_connections[host]["docker"]["client"].close()
        self.hosts_connections[host]["ssh"].close()

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

    def __init_local_network(self):
        try:
            local_network = self.local_connections["docker"]["client"].networks.create(
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
        
    def __init_remote_datadir(self, host):
        ssh_cnx = self.hosts_connections[host]["ssh"]
        ssh_cnx.sudo("rm -rf " + self.remote_datadir)
        mkdir = ssh_cnx.run("mkdir -p " + self.remote_datadir)
        if not mkdir.ok:
            self.logger.error("[%s] Error in creating datadir (%s)" % (host, self.remote_datadir))
            return False
        mkdir = ssh_cnx.run("mkdir -p " + os.path.join(self.remote_datadir, ".keys/data"))
        if not mkdir.ok:
            self.logger.error("[%s] Error in creating key dir (%s) inside datadir" % (host, ".keys/data"))
            return False
        mkdir = ssh_cnx.run("mkdir -p " + os.path.join(self.remote_datadir, ".keys/names"))
        if not mkdir.ok:
            self.logger.error("[%s] Error in creating key dir (%s) inside datadir" % (host, ".keys/names"))
            return False
        return True
    
    def __copy_validator_files(self, host, index, config_file):
        ssh_cnx = self.hosts_connections[host]["ssh"]
        address_file = os.path.join(self.local_datadir, ".keys/names", self.config_template["GenesisDoc"]["Validators"][index]["Name"])
        ssh_cnx.put(address_file, remote=os.path.join(self.remote_datadir, ".keys/names"))
        nodekey_file = os.path.join(self.local_datadir, ".keys/names", "nodekey-" + self.config_template["GenesisDoc"]["Validators"][index]["Name"])
        ssh_cnx.put(nodekey_file, remote=os.path.join(self.remote_datadir, ".keys/names"))
        address_data_file = os.path.join(self.local_datadir, ".keys/data", self.config_template["GenesisDoc"]["Validators"][index]["Address"] + ".json")
        ssh_cnx.put(address_data_file, remote=os.path.join(self.remote_datadir, ".keys/data"))
        nodekey_data_file = os.path.join(self.local_datadir, ".keys/data", self.config_template["GenesisDoc"]["Validators"][index]["NodeAddress"] + ".json")
        ssh_cnx.put(nodekey_data_file, remote=os.path.join(self.remote_datadir, ".keys/data"))
        ssh_cnx.put(config_file, remote=self.remote_config_file)
        self.logger.info("[%s]All validator files upated" % host)
        

if __name__ == "__main__":
    import sys, time

    logging.basicConfig(level=logging.INFO)
    logging.getLogger("paramiko.transport").setLevel(logging.WARNING)

    hosts_file_path = sys.argv[1]
    host_manager = HostManager()
    host_manager.add_hosts_from_file(hosts_file_path)
    hosts = host_manager.get_hosts()
    manager = BurrowManager(hosts, int(len(hosts)*2/3))
    logging.basicConfig(level=logging.INFO)
    manager.init()
    manager.start()
    time.sleep(30)
    manager.stop()
    manager.deinit()
import docker
import json
import logging
import os
import queue
import shutil
import sys
from threading import Thread
import time
from web3 import Web3, HTTPProvider
import yaml

from bc_orch_sdk.deploy_manager import DeployManager
from caliper_blockchain_manager_adapter import CaliperBlockchainManagerAdapter

class CaliperManager(DeployManager):

    DEFAULT_CLIENTS_PER_HOST = 1

    remote_caliper_dir = "/home/ubuntu/caliper"
    remote_network_conf_file = os.path.join(remote_caliper_dir, "benchmark.json")
    docker_server_image = "russanto/bc-orch-caliper:latest"
    docker_client_image = "russanto/bc-orch-caliper:zoo-client"
    docker_container_client_name = 'caliper-client'
    docker_container_control_name = 'caliper-control'
    reports_dir = "/home/ubuntu/reports"
    
    local_datadir = "/root/caliper"

    @property
    def benchmark_file(self):
        return os.path.join(self.local_datadir, 'benchmark.yaml')

    @property
    def network_file(self):
        return os.path.join(self.local_datadir, 'network.json')

    zookeeper_ip = '192.168.99.1'

    def __init__(self, host_manager_services_provider):
        super().__init__(host_manager_services_provider)
        self.logger = logging.getLogger("CaliperManager")
        self.local_docker = {'client': docker.DockerClient(), 'networks': {}, 'containers': {}}
        self.hosts_connections = {}
        self.blockchain_managers = {}
        self.__init_local_dir()
        self.__start_zookeeper_server()

    def register_blockchain_manager(self, identifier, manager_adapter):
        if not isinstance(manager_adapter, CaliperBlockchainManagerAdapter):
            raise Exception("Blockchain manager adapter must be of type CaliperBlockchainManagerAdapter. Given %s" % type(manager_adapter).__name__)
        self.blockchain_managers[identifier] = manager_adapter

    def _init_setup(self, hosts):
        ssh_req = self.request_service('ssh', hosts)
        docker_req = self.request_service('docker', hosts, {'images': [self.docker_client_image]})
        ssh_connections = self.wait_service('ssh', ssh_req)
        docker_service = self.wait_service('docker', docker_req)

        for host in hosts:
            self.hosts_connections[host] = {
                'ssh': ssh_connections[host],
                'docker': {
                    'client': docker_service['connections'][host],
                    'containers': {},
                    'networks': {}
                }
            }
    
    def _init_loop(self, host):
        self.__init_remote_dir(host)

    def _start_setup(self, hosts, conf):
        if 'blockchain' not in conf:
            self.logger.error('blockchain not specified in start configuration')
            raise Exception('blockchain not specified in start configuration')
        if 'benchmark' not in conf:
            self.logger.error('No benchmark provided to start Caliper')
            raise Exception('No benchmark provided to start Caliper')
        if 'network' not in conf:
            self.logger.error('No network provided to start Caliper')
            raise Exception('No network provided to start Caliper')
        with open(self.benchmark_file, 'w') as benchmark_file:
            benchmark_file.write(conf['benchmark'])
        with open(self.network_file, 'w') as network_file:
            network_file.write(conf['network'])
        self.blockchain_managers[conf['blockchain']].init(self.network_file)

    def _start_loop(self, host, conf):
        blockchain = conf['blockchain']
        blockchain_manager = self.blockchain_managers[blockchain]
        network_conf_file = blockchain_manager.get_network_conf_file(host)
        docker_cnx = self.hosts_connections[host]["docker"]
        try:
            self.hosts_connections[host]["ssh"].put(network_conf_file, remote=self.remote_network_conf_file)
            docker_cnx["containers"][self.docker_container_client_name] = docker_cnx["client"].containers.run(
                self.docker_client_image,
                name=self.docker_container_client_name,
                detach=True,
                network=blockchain_manager.docker_network_name,
                environment={
                    "ZOO_SERVER": self.zookeeper_ip,
                    "BLOCKCHAIN": "benchmark",
                    "BC_CONF": "benchmark"
                }, volumes={
                    self.remote_network_conf_file: {
                        "bind":"/caliper/packages/caliper-application/network/benchmark/benchmark/benchmark.json",
                        "mode":"rw"
                    }
                })
            self.logger.info("[%s]Zookeeper client deployed" % host)
        except docker.errors.APIError as error:
            self.logger.error("[%s]Error on docker creation of zoo client" % host)
            self.logger.error(error)
    
    def _start_teardown(self, hosts, conf):
        self._start_caliper_workload(conf['blockchain'])
        self.logger.info("Caliper started. Log available running 'docker logs -f caliper'")

    def _start_caliper_workload(self, blockchain):
        with open(self.benchmark_file) as config_file:
            config_data = yaml.load(config_file)

        # Adds to the workload conf all the host to monitor
        docker_rapi_hosts = []
        for host, docker_names in self.blockchain_managers[blockchain].docker_nodes.items():
            if 'container' in docker_names:
                docker_rapi_hosts.append("http://%s:2375/%s" % (host, docker_names['container']))
            else:
                self.logger.warning('Skipping monitoring on host %s beacuse container name has not given.', host)
        config_data["monitor"]["docker"]["name"] = docker_rapi_hosts

        # Sets clients as zookeeper type checking if a clientsPerHost parameter has been already set
        try:
            clients_per_host = config_data["test"]["clients"]["zoo"]["clientsPerHost"]
        except:
            clients_per_host = self.DEFAULT_CLIENTS_PER_HOST
        config_data["test"]["clients"] = {
            "type": "zookeeper",
            "zoo": {
                "clientsPerHost": clients_per_host,
                "server": "zookeeper:2181"
            }
        }

        with open(self.benchmark_file, "w") as config_file:
            yaml.dump(config_data, config_file, default_flow_style=False)
        self.logger.info("Updated workload configuration")

        network_file = self.blockchain_managers[blockchain].get_utility_network_conf_file(self.network_file)
        shutil.copy(network_file, self.local_datadir)
        network_file = os.path.join(self.local_datadir, os.path.basename(network_file))

        self.logger.info("Starting caliper")
        docker_client = self.local_docker["client"]
        self.local_docker["containers"][self.docker_container_control_name] = docker_client.containers.run(
            'russanto/bc-orch-caliper:latest',
            name=self.docker_container_control_name,
            detach=True,
            network='benchmark',
            environment={
                "BLOCKCHAIN": "benchmark",
                "BC_CONF": "benchmark",
                "BENCHMARK": "simple"
            }, volumes={
                self.benchmark_file: {
                    "bind": "/caliper/packages/caliper-application/benchmark/simple/config-benchmark.yaml",
                    "mode": "rw"
                },
                network_file: {
                    "bind": "/caliper/packages/caliper-application/network/benchmark/benchmark/benchmark.json",
                    "mode": "rw"
                },
                self.reports_dir: {
                    "bind": "/caliper/packages/caliper-application/reports",
                    "mode": "rw"
                }
            })
    
    def _stop_setup(self):
        self.local_docker["containers"][self.docker_container_control_name].wait()

    def _stop_loop(self, host):
        docker_client = self.local_docker["client"]
        try:
            zookeeper_client = docker_client.containers.get(self.docker_container_client_name)
            zookeeper_client.stop()
            zookeeper_client.remove()
            self.logger.info("[{0}]Zookeeper client stopped and removed".format(host))
        except docker.errors.APIError as error:
            if error.status_code == 404:
                pass
            else:
                raise
    
    def _stop_teardown(self):
        self.logger.info("Execution completed")

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
    
    def __start_zookeeper_server(self):
        docker_client = self.local_docker['client']
        try:
            local_zookeeper = docker_client.containers.get("zookeeper")
            local_zookeeper.stop()
            local_zookeeper.remove()
            self.logger.info("Previous execution Zookeeper server found, stopped and removed")
        except docker.errors.NotFound:
            self.logger.info("Zookeeper server not found")
        except:
            raise
        try:
            self.logger.info("Deploying Zookeeper server")
            self.local_docker["containers"]["zookeeper"] = docker_client.containers.run(
                "zookeeper:3.4.11",
                detach=True,
                name="zookeeper",
                network='benchmark',
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
    
    def __init_remote_dir(self, host):
        try:
            rmdir = self.hosts_connections[host]["ssh"].sudo("rm -rf %s" % self.remote_caliper_dir)
            if not rmdir.ok:
                raise Exception("Can't clean designated Caliper dir on host %s", host)
            mkdir = self.hosts_connections[host]["ssh"].run("mkdir -p %s" % self.remote_caliper_dir)
            if not mkdir.ok:
                raise Exception("Can't create Caliper dir on host %s", host)
        except Exception as error:
            self.logger.error(error)
            raise
from fabric import Connection
import logging
import requests
import time
import uuid

class MultichainOpenstack:

    is_controller_deployed = False
    controller_port = 5000

    def __init__(self):
        self.drivers = {}
        self.logger = logging.getLogger("MultichainOpenstack")

    def set_driver(self, label, driver_instance):
        self.drivers[label] = driver_instance

    def deploy(self, network_configuration):
        deploy_id = uuid.uuid4()
        for nodes_group in network_configuration["nodes"]: #TODO deploy parallelly on multiple pops
            nodes_count = int(nodes_group["count"])
            #nodes_flavor = nodes_group["flavor"]
            nodes_pop = nodes_group["pop"]

            controller = self.drivers[nodes_pop].deploy_controller()
            self.drivers[nodes_pop].deploy_nodes(deploy_id, nodes_count)

            # Start multichain network. Polling is a temporary solution.
            self.logger.info("Waiting nodes to be ready")
            started = False
            while not started:
                try:
                    response = requests.get("http://%s:%d/start/multichain/%d" % (controller["public_v4"], self.controller_port, nodes_count))
                    if response.status_code == 403:
                        self.logger.debug("Nodes not yet started")
                        time.sleep(5)
                    else:
                        started = True
                        self.logger.info("Multichain network started")
                except requests.exceptions.ConnectionError:
                    self.logger.debug("Server controller not available") #TODO Improve exception management
                    time.sleep(5)
        return deploy_id

    def dismiss(self):
        pass
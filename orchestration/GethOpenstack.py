import logging
import requests
import time
import uuid

class GethOpenstack:

    controller_port = 5000

    def __init__(self):
        self.drivers = {}
        self.logger = logging.getLogger("GethOpenstack")

    def set_driver(self, label, driver_instance):
        self.drivers[label] = driver_instance

    def deploy(self, network_configuration):
        deploy_id = uuid.uuid4()
        genesis_file = network_configuration["genesis"]
        for nodes_group in network_configuration["nodes"]: #TODO deploy parallelly on multiple pops
            nodes_count = int(nodes_group["count"])
            #nodes_flavor = nodes_group["flavor"]
            nodes_pop = nodes_group["pop"]

            controller = self.drivers[nodes_pop].deploy_controller()
            self.drivers[nodes_pop].deploy_nodes(deploy_id, nodes_count)

            # controller = {"public_v4": "172.30.2.20"}

            # Start multichain network. Polling is a temporary solution.
            self.logger.info("Waiting nodes to be ready")
            url = "http://%s:%d/start/geth/%d" % (controller["public_v4"], self.controller_port, nodes_count)
            started = False
            while not started:
                try:
                    #TODO reuse the same file descriptor remebering to bring the cursor at the beginning for each attempt
                    files = {'genesis': open(genesis_file, 'rb')}
                    response = requests.post(url, files=files)
                    if response.status_code == 412:
                        self.logger.debug("Nodes not yet started")
                        time.sleep(5)
                    elif response.status_code == 403:
                        self.logger.error("Genesis not valid")
                        return
                    else:
                        started = True
                        print(response.json())
                        self.logger.info("Geth network started")
                except requests.exceptions.ConnectionError:
                    self.logger.debug("Server controller not available") #TODO Improve exception management
                    time.sleep(5)
                finally:
                    files["genesis"].close()
        return deploy_id

    def dismiss(self):
        pass
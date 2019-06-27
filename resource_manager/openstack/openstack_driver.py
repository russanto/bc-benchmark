from fabric import Connection
import logging
import os
import time

#TODO: Manage keys and upload them if not present

class OpenstackDriver:

    base_image = "Ubuntu18-Docker-API"

    controller_flavor = "ar1.medium"
    controller_port = 3000

    node_flavor = "ar1.large"

    ssh_key_controller = "ControllerKey"
    ssh_key_nodes = "Deployer"
    ssh_pvt_key_nodes = "Deployer"

    def __init__(self, connection):
        self.controller = None
        self.connection = connection
        self.server_groups = {}
        self.logger = logging.getLogger("OpenstackDriver") #TODO: Point to which connection it refers to

    def deploy_controller(self):
        if self.controller != None:
            return self.controller
        
        self.logger.info("Deploying controller")
        server = self.connection.create_server(
            "BC-Orch-Controller",
            image=self.base_image,
            flavor=self.controller_flavor,
            userdata=self.get_controller_init_script(),
            key_name=self.ssh_key_controller
        )
        self.connection.wait_for_server(server, timeout=300)
        self.connection.add_auto_ip(server, wait=True)
        server = self.connection.get_server(server["id"])
        self.logger.info("Deployed server at %s" % server["public_v4"])
        self.logger.info("Waiting server to upload %s private key" % self.ssh_key_nodes)
        ssh_cnx = Connection(host=server["public_v4"], user="ubuntu")
        ssh_key_uploaded = False
        while not ssh_key_uploaded:
            try:
                ssh_cnx.put(self.ssh_pvt_key_nodes, remote="/home/ubuntu/.ssh/id_rsa")
                ssh_key_uploaded = True
            except FileNotFoundError as error:
                self.logger.error("Node private key file not found.")
                self.logger.error(error)
            except:
                self.logger.debug("Not yet ready")
                time.sleep(5)
        ssh_cnx.close()
        self.controller = server
        return server
    
    def deploy_nodes(self, label, quantity, wait=True, timeout=300):
        # Create server group
        # group = self.connection.create_server_group(label, ["affinity"])
        # group = self.connection.create_server_group(label, ["anti-affinity"])
        # self.logger.info("Created group %s (%s)" % (group["name"], group["id"]))

        # Create node instances
        server = self.connection.create_server(
            label,
            image=self.base_image,
            flavor=self.node_flavor,
            userdata=self.get_nodes_init_script(self.controller["private_v4"]),
            # group=group,
            min_count=quantity,
            max_count=quantity,
            key_name=self.ssh_key_nodes
        )

        if wait:
            self.connection.wait_for_server(server, timeout=timeout)
            self.logger.info("Created %d nodes" % quantity)


    def get_controller_init_script(self):
        script = ""
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts/controller-init-script.sh")) as script_file:
            for line in script_file:
                script += "%s\n" % line
        return script

    def get_nodes_init_script(self, controller_host):
        return "#!/bin/bash\nresult=$(curl -LI http://{0}:{1}/ready/$(curl -s http://169.254.169.254/2009-04-04/meta-data/local-ipv4) -o /dev/null -w '%{{http_code}}' -s)\nwhile [ $result != 200 ]\ndo\nsleep 3\necho wait3\nresult=$(curl -LI http://{0}:{1}/ready/$(curl -s http://169.254.169.254/2009-04-04/meta-data/local-ipv4) -o /dev/null -w '%{{http_code}}' -s)\ndone".format(controller_host, self.controller_port)

if __name__ == "__main__":
    import openstack
    logging.basicConfig(level=logging.INFO)
    openstack_driver = OpenstackDriver(openstack.connect(cloud="openstack"))
    openstack_driver.deploy_controller()
    openstack_driver.deploy_nodes("benchmark",4)
from fabric import Connection
import logging
import requests
import time
import uuid

class MultichainOpenstack:

    is_controller_deployed = False
    controller_port = 5000
    deployer_key_filename = "Deployer"

    def __init__(self, connection):
        self.connection = connection
        self.server_groups = {}
        self.logger = logging.getLogger("MultichainOpenstack")

    def deploy_controller(self):
        server = self.connection.create_server(
            "BC-Orch-Controller",
            image="Ubuntu18-Docker",
            flavor="m1.small",
            userdata=self.get_controller_init_script(),
            key_name="AntonioMac"
        )
        self.connection.wait_for_server(server, timeout=300)
        self.connection.add_auto_ip(server, wait=True)
        server = self.connection.get_server(server["id"])
        print("Deployed server at %s" % server["public_v4"])
        ssh_cnx = Connection(host=server["public_v4"], user="ubuntu")
        ssh_key_uploaded = False
        while not ssh_key_uploaded:
            try:
                ssh_cnx.put("./ssh-keys/" + self.deployer_key_filename, remote="/home/ubuntu/.ssh/id_rsa")
                ssh_key_uploaded = True
            except:
                print("Not yet ready")
                time.sleep(5)
        ssh_cnx.close()
        self.is_controller_deployed = True
        return server


    def deploy(self, network_configuration):
        deploy_id = uuid.uuid4()
        nodes_count = int(network_configuration["nodes"]["count"])

        # Create controller instance
        controller = self.deploy_controller()

        # Start multichain network. It is a temporary solution.
        started = False
        while not started:
            try:
                response = requests.get("http://%s:%d/start/%d" % (controller["public_v4"], self.controller_port, nodes_count))
                if response == "no":
                    print("Already started. No action done.")
                else:
                    started = True
            except requests.exceptions.ConnectionError:
                print("Server controller not available")
                time.sleep(5)

        # Create server group
        group = self.connection.create_server_group("Multichain", ["anti-affinity"])
        self.logger.info("Created group %s (%s)" % (group["name"], group["id"]))

        # Create node instances
        server = self.connection.create_server(
            "Node",
            image="Ubuntu18-Docker",
            flavor="m1.small",
            userdata=self.get_nodes_init_script(controller["private_v4"]),
            group=group,
            min_count=nodes_count,
            max_count=nodes_count,
            key_name="Deployer"
        )
        self.connection.wait_for_server(server, timeout=300)
        return deploy_id

    def dismiss(self):
        pass

    def get_controller_init_script(self):
        return "#!/bin/bash\nlocal_ip=\"$(curl -s http://169.254.169.254/2009-04-04/meta-data/local-ipv4)\"\ndocker run -p 5000:5000 -v /home/ubuntu/.ssh:/root/.ssh -v /var/run/docker.sock:/var/run/docker.sock -d -e LOGGER_HOST=\"$local_ip\" russanto/bc-orch-controller"

    def get_nodes_init_script(self, controller_host):
        return "#!/bin/bash\nresult=\"$(curl -s http://%s:%d/ready/$(curl -s http://169.254.169.254/2009-04-04/meta-data/local-ipv4))\"\nwhile [ \"$result\" != \"understood\" ]\ndo\nsleep 3\necho wait3\nresult=$(curl -s http://%s:%d/ready/$(curl -s http://169.254.169.254/2009-04-04/meta-data/local-ipv4))\ndone" % (controller_host, self.controller_port, controller_host, self.controller_port)
import logging
import openstack
from oslo_utils import encodeutils
import yaml

from Blockchain import Blockchain
from MultichainOpenstack import MultichainOpenstack
from openstack_driver import OpenstackDriver

with open("networks.yaml", "r") as network_config_file:
    network_config = yaml.load(network_config_file)

logging.basicConfig(level=logging.INFO)

multichain = Blockchain("multichain")
openstack_driver = OpenstackDriver(openstack.connect(cloud="openstack"))
multichain_os_adapter = MultichainOpenstack()
multichain_os_adapter.set_driver("insa", openstack_driver)
multichain.add_instance_manager("openstack", multichain_os_adapter)
multichain.deploy(network_config["multichain"], "openstack")
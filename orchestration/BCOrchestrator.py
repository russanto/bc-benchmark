import logging
import openstack
from oslo_utils import encodeutils
import yaml

from Blockchain import Blockchain
from GethOpenstack import GethOpenstack
from MultichainOpenstack import MultichainOpenstack
from openstack_driver import OpenstackDriver

with open("networks.yaml", "r") as network_config_file:
    network_config = yaml.load(network_config_file)

logging.basicConfig(level=logging.INFO)

openstack_driver = OpenstackDriver(openstack.connect(cloud="openstack"))

# multichain = Blockchain("multichain")
# multichain_os_adapter = MultichainOpenstack()
# multichain_os_adapter.set_driver("insa", openstack_driver)
# multichain.add_instance_manager("openstack", multichain_os_adapter)
# multichain.deploy(network_config["multichain"], "openstack")

geth = Blockchain("Geth")
geth_os_adapter = GethOpenstack()
geth_os_adapter.set_driver("insa", openstack_driver)
geth.add_instance_manager("openstack", geth_os_adapter)
geth.deploy(network_config["geth"], "openstack")
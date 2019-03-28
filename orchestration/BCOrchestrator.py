import base64
import openstack
from oslo_utils import encodeutils
import yaml

from Blockchain import Blockchain
from MultichainOpenstack import MultichainOpenstack

with open("networks.yaml", "r") as network_config_file:
    network_config = yaml.load(network_config_file)

multichain = Blockchain("multichain")
multichain_os_adapter = MultichainOpenstack(openstack.connect(cloud="openstack"))
multichain.add_instance_manager("openstack", multichain_os_adapter)
multichain.deploy(network_config["multichain"], "openstack")
import logging
import json
import os

from web3 import Web3, HTTPProvider

from caliper_manager_adapter import CaliperManagerAdapter
from deploy_manager import DeployManager
from geth_manager import GethManager
from parity_manager import ParityManager

class CaliperEthereum(CaliperManagerAdapter):

    FILE_REGISTRY = "./caliper/registry.json"

    temp_dir = "./tmp"

    @property
    def hosts(self):
        return self.manager.hosts

    @property
    def docker_node_name(self):
        return self.manager.docker_node_name

    def __init__(self, ethereum_manager, base_network_file):
        if not isinstance(ethereum_manager, GethManager) and not isinstance(ethereum_manager, ParityManager):
            raise Exception("CaliperEthereum works only with GethManager and ParityManager. Given " + type(ethereum_manager).__name__)
        super().__init__(ethereum_manager)
        self.logger = logging.getLogger("CaliperEthereum")
        self.base_network_file = base_network_file

    def init(self):
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
        self.manager.cmd_events[DeployManager.CMD_START].wait()
        self.__deploy_registry(self.manager.utility_node)
        with open(self.base_network_file) as conf_template_file:
            self.conf_template = json.load(conf_template_file)
        self.conf_template["ethereum"]["url"] = "http://%s:8545" % self.docker_node_name
        self.conf_template["ethereum"]["registry"]["address"] = self.registry_address
        self.conf_template["ethereum"]["contractDeployerAddress"] = self.manager.utility_node.account[0]
        self.conf_template["ethereum"]["contractDeployerAddressPassword"] = self.manager.utility_node.account[1]
        accounts = []
        for node in self.manager.nodes.values():
            accounts.append({"address": node.account[0]})
        self.conf_template["ethereum"]["accounts"] = accounts    

    def get_network_conf_file(self, host="utility"):
        conf_json = self.conf_template.copy()
        if host == "utility":
            node = self.manager.utility_node
            conf_json["ethereum"]["url"] = "http://%s:8545" % node.host
        else:
            node = self.manager.nodes[host]
        conf_json["ethereum"]["fromAddress"] = node.account[0]
        conf_json["ethereum"]["fromAddressPassword"] = node.account[1]
        conf_file_path = os.path.join(self.temp_dir, "cal-eth-%s.json" % host)
        with open(conf_file_path, "w") as geth_json_file:
            json.dump(conf_json, geth_json_file)
        return os.path.abspath(conf_file_path)
    
    def __deploy_registry(self, node):
        with open(self.FILE_REGISTRY) as registry_info_file:
            registry_data = json.load(registry_info_file)
        registry = node.web3.eth.contract(abi=registry_data["abi"], bytecode=registry_data["bytecode"])
        self.logger.info("Creating registry")
        try:
            node.web3.personal.unlockAccount(node.account[0], node.account[1])
            registry_contructed = registry.constructor()
            registry_estimated_gas = registry_contructed.estimateGas()
            registry_tx_hash = registry_contructed.transact({
                "from": node.account[0],
                "gas": registry_estimated_gas
            })
            registry_creation = node.web3.eth.waitForTransactionReceipt(registry_tx_hash)
            self.registry_address = registry_creation.contractAddress
            self.logger.info("Created registry at %s" % registry_creation.contractAddress)
        except:
            self.logger.error("Error creating registry", exc_info=True)
            raise
import logging
import json
import os
from threading import Event

from caliper_blockchain_manager_adapter import CaliperBlockchainManagerAdapter

class RMQCaliperGeth(CaliperBlockchainManagerAdapter):

    temp_dir = './tmp'

    def __init__(self, geth_manager_id, rpc_client):
        self.logger = logging.getLogger("RMQCaliperGeth")
        self.__geth_manager_id = geth_manager_id
        self.__rpc_client = rpc_client
        self.__initialized = Event()
        self.__geth_manager_called = Event()

    def get_network_conf_file(self, host):
        if not self.__initialized.is_set():
            self.logger.error('Caliper adapter for Geth must be initialized before beeing used')
            raise Exception('Caliper adapter for Geth must be initialized before beeing used')
        conf_data = self.network_file_data.copy()
        conf_data["ethereum"]["url"] = "http://%s:8545" % host
        conf_data["ethereum"]["fromAddress"] = self.available_accounts[host][0]['address']
        conf_data["ethereum"]["fromAddressPassword"] = self.available_accounts[host][0]['password']
        network_conf_file_fullpath = os.path.join(self.temp_dir, '%s.json' % host)
        with open('%s.json' % host, 'w') as network_conf_file:
            json.dump(conf_data, network_conf_file)
        return network_conf_file_fullpath
        
    def init(self, base_network_file):
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
        with open(base_network_file) as conf_template_file:
            self.network_file_data = json.load(conf_template_file)
        self.__rpc_client.call(self.__geth_manager_id, 'caliper', {}, self.__on_init_success)
        self.__geth_manager_called.wait()
        if not self.__initialized.is_set():
            self.logger.error("Error while initializing after rpc call")
            raise Exception("Error while initializing after rpc call")

    def __on_init_success(self, status, registry_address, contract_deployer_address, contract_deployer_address_password, available_accounts):
        try:
            self.network_file_data["ethereum"]["registry"]["address"] = registry_address
            self.network_file_data["ethereum"]["contractDeployerAddress"] = contract_deployer_address
            self.network_file_data["ethereum"]["contractDeployerAddressPassword"] = contract_deployer_address_password
            self.available_accounts = available_accounts
            accounts = set()
            for _, accounts_list in available_accounts:
                for account in accounts_list:
                    accounts.add(account)
            configuration_accounts = []
            for account in accounts:
                configuration_accounts.append({'address': account})
            self.network_file_data["ethereum"]["accounts"] = configuration_accounts
            self.__initialized.set()
        except KeyError as identifier:
            self.logger.error('%s not set', str(identifier))
        finally:
            self.__geth_manager_called.set()
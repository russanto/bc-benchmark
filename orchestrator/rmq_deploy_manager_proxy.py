import json
import logging
import uuid

import pika

from bc_orch_sdk.rmq_rpc import RMQRPCClient

class RMQDeployManagerProxy():

    def __init__(self, deploy_manager_id, rpc_client):
        self.logger = logging.getLogger('RMQDeployManagerProxy')
        if not isinstance(rpc_client, RMQRPCClient):
            raise Exception('rpc_client for RMQDeployManagerProxy must be of RMQRPCClient type')
        self.__rpc_client = rpc_client
        self.deploy_manager_id = deploy_manager_id
        
    def init(self, host_list, on_success, on_failure=None):
        return self.__rpc_client.call(self.deploy_manager_id, 'init', {'host_list': host_list}, on_success, on_failure)

    def start(self, conf, on_success, on_failure=None):
        return self.__rpc_client.call(self.deploy_manager_id, 'start', {'conf': conf}, on_success, on_failure)

    def stop(self, on_success, on_failure=None):
        return self.__rpc_client.call(self.deploy_manager_id, 'stop', None, on_success, on_failure)

    def deinit(self, host_list, on_success, on_failure=None):
        return self.__rpc_client.call(self.deploy_manager_id, 'deinit', {'host_list': host_list}, on_success, on_failure)

    def caliper(self, on_success, on_failure=None):
        return self.__rpc_client.call(self.deploy_manager_id, 'caliper', None, on_success, on_failure)
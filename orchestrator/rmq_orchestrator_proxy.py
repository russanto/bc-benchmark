import json
import logging
import os
from threading import Thread
import time
import uuid

import pika

from rmq_host_manager_proxy import RMQHostManagerProxy
from rmq_deploy_manager_proxy import RMQDeployManagerProxy
from bc_orch_sdk.rmq_rpc import RMQRPCClient

class RMQOrchestratorProxy:

    BROADCAST_EXCHANGE = 'broadcast'

    def __init__(self, rabbitmq_host):
        self.rabbitmq_host = rabbitmq_host
        self.logger = logging.getLogger('RMQOrchestrator')
        self.__rpc_client = RMQRPCClient(rabbitmq_host)
        self.__host_manager = RMQHostManagerProxy(self.__rpc_client)
        self.__deploy_managers = {'deploy_manager' : RMQDeployManagerProxy('deploy_manager', self.__rpc_client)}
    
    def host_manager_reserve(self, count):
        return self.__host_manager.reserve(count)
    
    def host_manager_free(self, hosts):
        return self.__host_manager.free(hosts)

    def deploy_manager_init(self, deploy_manager_id, host_list, on_success, on_failure=None):
        return self.__deploy_managers[deploy_manager_id].init(host_list, on_success, on_failure)
    
    def deploy_manager_start(self, deploy_manager_id, conf, on_success, on_failure=None):
        return self.__deploy_managers[deploy_manager_id].start(conf, on_success, on_failure)
    
    def deploy_manager_stop(self, deploy_manager_id, on_success, on_failure=None):
        return self.__deploy_managers[deploy_manager_id].stop(on_success, on_failure)
    
    def deploy_manager_deinit(self, deploy_manager_id, host_list, on_success, on_failure=None):
        return self.__deploy_managers[deploy_manager_id].deinit(host_list, on_success, on_failure)
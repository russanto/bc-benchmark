import json
import logging

import pika

from bc_orch_sdk.a_host_service import AHostService
from bc_orch_sdk.rmq_rpc import RMQRPCServer

class RMQHostManager:

    BROADCAST_EXCHANGE = 'broadcast'
    CMD_QUEUE = 'host_manager_rpc'

    def __init__(self, rmq_host, host_manager):
        self.logger = logging.getLogger('RMQHostManager')
        self.host_manager = host_manager
        self.__services = {}
        self.logger.info("Messaging model initialized")
        self.rpc_server = RMQRPCServer(rmq_host, 'host_manager_rpc')
        self.rpc_server.add_call('reserve', self.__reserve, {'count': int})
        self.rpc_server.add_call('free', self.__free, {'hosts': list})
        self.rpc_server.add_call('service', self.__service, {'service': str, 'hosts': list, 'params': dict})
    
    def register_service(self, key, host_service):
        if not isinstance(host_service, AHostService):
            raise Exception('host_service must be AHostService instance')
        self.__services[key] = host_service
    
    def run(self):
        self.rpc_server.run()

    def __reserve(self, count):
        return {'hosts': self.host_manager.reserve(count)}

    def __service(self, service, hosts, params=None):
        if params:
            return {'service_data': self.__services[service].prepare(hosts, params)}
        else:
            return {'service_data': self.__services[service].prepare(hosts)}
    
    def __free(self, hosts):
        return {'hosts': self.host_manager.free(hosts)}

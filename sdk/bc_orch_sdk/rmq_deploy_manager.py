import json
import logging

import pika

from .deploy_manager import ADeployManager
from .rmq_rpc import RMQRPCServer

class RMQDeployManager:

    def __init__(self, rabbitmq_host, identifier, deploy_manager):
        if not isinstance(deploy_manager, ADeployManager):
            raise Exception("An ADeployManager is required. Given %s" % type(deploy_manager).__name__)
        self.logger = logging.getLogger('RMQDeployManager')
        self.identifier = identifier
        self.deploy_manager = deploy_manager
        rpc_server = RMQRPCServer(rabbitmq_host, identifier)
        rpc_server.add_call('init', self.deploy_manager.init, {'host_list': list})
        rpc_server.add_call('start', self.deploy_manager.start, {'conf': dict})
        rpc_server.add_call('stop', self.deploy_manager.stop)
        rpc_server.add_call('deinit', self.deploy_manager.deinit, {'host_list': list})
        if hasattr(deploy_manager, 'status'):
            rpc_server.add_call('status', self.deploy_manager.status)
        if hasattr(deploy_manager, 'caliper'):
            rpc_server.add_call('caliper', self.deploy_manager.caliper)
        self.__rpc_server = rpc_server
        self.logger.info('Deploy manager %s initialized', identifier)
    
    def run(self):
        self.logger.info('Started %s', self.identifier)
        self.__rpc_server.run()

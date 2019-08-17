import logging
import threading

import docker
from fabric import Connection

from a_host_manager_service_plugin import AHostManagerServicePlugin
from a_services_provider import AServicesProvider
from rmq_rpc_client import RMQRPCClient

class RMQHostManagerServicesProvider(AServicesProvider):

    @property
    def available_services(self):
        return ['ssh', 'docker']

    def __init__(self, connection):
        self.logger = logging.getLogger('RMQHostManagerServicesProvider')
        self.__plugins = {}
        self.__current_request_id = 0
        self.__responses = {}
        self.__requests = {}
        self.__rpc_client = RMQRPCClient(connection, 'host_manager_rpc')

    def register_plugin(self, key, plugin):
        if not isinstance(plugin, AHostManagerServicePlugin):
            raise Exception("Can't register a plugin that is not a AHostManagerServicePlugin")
        if not isinstance(key, str):
            raise Exception("Only string keys are allowed to register plugins")
        if key in self.__plugins:
            raise Exception("Key %s already has a registered plugin. Only one allowed.")
        self.__plugins[key] = plugin

    def request(self, service, hosts, params=None):
        if not isinstance(hosts, list):
            raise Exception("hosts is required to be of list type")
        if service in self.available_services:
            request_id = self.__generate_request()
        else:
            raise Exception("Service %s is not available" % service)
        service_args = {
            'service': service,
            'hosts': hosts
        }
        if params:
            service_args['params'] = params

        def on_successfull_request(data):
            if service in self.__plugins:
                self.__save_request_result(request_id, self.__plugins[service].transform(data['data']))
            else:
                self.__save_request_result(request_id, data['data'])
            self.logger.info('Successfully received and processed request: %d', request_id)

        def on_failing_request(data):
            self.logger.error("Request failed with status code %d", data['status'])

        self.__rpc_client.call('service', service_args, on_successfull_request, on_failure=on_failing_request)
        return request_id


    def service(self, request_id):
        if request_id not in self.__requests:
            raise Exception("Provided request_id is not valid")
        self.__requests[request_id].wait()
        return self.__responses[request_id]

    def __generate_request(self):
        self.__current_request_id += 1
        self.__requests[self.__current_request_id] = threading.Event()
        return self.__current_request_id

    def __save_request_result(self, request_id, result):
        self.__responses[request_id] = result
        self.__requests[request_id].set()

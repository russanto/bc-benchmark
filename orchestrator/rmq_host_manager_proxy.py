import json
import logging
from threading import Event, Lock
import uuid

import pika

from bc_orch_sdk.rmq_rpc import RMQRPCClient

# TODO Manage errors and failures
class RMQHostManagerProxy:

    rpc_host_manager = 'host_manager_rpc'

    def __init__(self, rpc_client):
        self.logger = logging.getLogger('RMQHostManagerProxy')
        if not isinstance(rpc_client, RMQRPCClient):
            raise Exception('rpc_client for RMQHostManagerProxy must be of RMQRPCClient type')
        self.__rpc_client = rpc_client
        self.busy = Lock()
        self.complete = Event()

    def free(self, hosts):
        self.busy.acquire()
        self.complete.clear()
        self.__rpc_client.call(self.rpc_host_manager, 'free', {'hosts': hosts}, self.on_success, self.on_failure)
        self.complete.wait()
        result = self.__result
        self.busy.release()
        return result

    def reserve(self, host_count):
        self.busy.acquire()
        self.complete.clear()
        self.__rpc_client.call(self.rpc_host_manager, 'reserve', {'count': host_count}, self.on_success, self.on_failure)
        self.complete.wait()
        result = self.__result
        self.busy.release()
        return result

    def on_success(self, status, hosts):
        self.__result = hosts
        self.complete.set()
    
    def on_failure(self, status):
        self.complete.set()

if __name__ == "__main__":
    client = RMQRPCClient('localhost')
    proxy = RMQHostManagerProxy(client)
    hosts = proxy.reserve(2)
    print(hosts)
    print(proxy.free([hosts[0]]))
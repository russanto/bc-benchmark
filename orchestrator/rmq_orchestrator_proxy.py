import json
import logging
import os
from threading import Thread
import time
import uuid

import pika

from rmq_host_manager_proxy import RMQHostManagerProxy
from rmq_deploy_manager_proxy import RMQDeployManagerProxy

class RMQOrchestratorProxy:

    BROADCAST_EXCHANGE = 'broadcast'
    REPLY_QUEUE = 'orchestrator_reply'

    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.logger = logging.getLogger('RMQOrchestrator')
        self.requests = {}
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.endpoint))
        self.channel_consumer = self.connection.channel()
        self.channel_producer = self.connection.channel()
        self.channel_producer.exchange_declare(exchange=self.BROADCAST_EXCHANGE, exchange_type='fanout')
        self.channel_consumer.queue_declare(queue=self.REPLY_QUEUE, exclusive=True)
        self.channel_consumer.basic_consume(queue=self.REPLY_QUEUE, on_message_callback=self.__reply_callback, auto_ack=True)
        self.__init_proxies()

    def __init_proxies(self):
        try:
            self.__host_manager = RMQHostManagerProxy(self.channel_producer, self.REPLY_QUEUE)
        except pika.exceptions.ChannelClosedByBroker:
            self.logger.error("HostManager not found")
        try:
            self.__deploy_manager = RMQDeployManagerProxy(self.channel_producer, 'deploy_manager', self.REPLY_QUEUE)
        except pika.exceptions.ChannelClosedByBroker:
            self.logger.error("DeployManager not found")
        

    def listen(self):
        try:
            self.channel_consumer.start_consuming()
        except KeyboardInterrupt:
            self.logger.info("Gracefully stopping")
    
    def host_manager_reserve(self, host_count, on_success, on_failure=None):
        corr_id = self.__host_manager.reserve(host_count)
        self.requests[corr_id] = self.__host_manager.callback_factory(on_success=on_success, on_failure=on_failure)
    
    def host_manager_free(self, host_list, on_success, on_failure=None):
        corr_id = self.__host_manager.free(host_list)
        self.requests[corr_id] = self.__host_manager.callback_factory(on_success=on_success, on_failure=on_failure)

    def deploy_manager_init(self, host_list, on_success, on_failure=None):
        corr_id = self.__deploy_manager.init(host_list)
        self.requests[corr_id] = self.__deploy_manager.callback_factory(on_success=on_success, on_failure=on_failure)
    
    def deploy_manager_start(self, deploy_conf, on_success, on_failure=None):
        corr_id = self.__deploy_manager.start(deploy_conf)
        self.requests[corr_id] = self.__deploy_manager.callback_factory(on_success=on_success, on_failure=on_failure)
    
    def deploy_manager_stop(self, on_success, on_failure=None):
        corr_id = self.__deploy_manager.stop()
        self.requests[corr_id] = self.__deploy_manager.callback_factory(on_success=on_success, on_failure=on_failure)
    
    def deploy_manager_deinit(self, host_list, on_success, on_failure=None):
        corr_id = self.__deploy_manager.deinit(host_list)
        self.requests[corr_id] = self.__deploy_manager.callback_factory(on_success=on_success, on_failure=on_failure)


    # def ping(self):
    #     corr_id = self.__prepare_request()
    #     self.channel_producer.basic_publish(
    #         exchange=self.BROADCAST_EXCHANGE,
    #         routing_key='',
    #         body=json.dumps({'cmd': 'ping'}),
    #         properties=pika.BasicProperties(
    #             reply_to=self.REPLY_QUEUE,
    #             correlation_id=corr_id,
    #             content_type='application/json'
    #     ))
    #     self.logger.info("Ping all sent")

    def __reply_callback(self, channel, method, properties, body):
        if properties.correlation_id not in self.requests:
            self.logger.error("Unknown reply")
            return
        self.requests[properties.correlation_id](body)
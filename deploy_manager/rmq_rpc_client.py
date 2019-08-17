import json
import logging
from threading import Event, Thread
import uuid

import pika

class RMQRPCClient(object):

    def __init__(self, rabbitmq_host, server_key):
        self.logger = logging.getLogger('RMQRPCClient')
        self.rabbitmq_host = rabbitmq_host
        self.server_key = server_key
        self.__success_callbacks = {}
        self.__failure__callbacks = {}

        self.client_ready = Event()

        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.rabbitmq_host))
        self.channel = self.connection.channel()

        self.__consumer_thread = Thread(target=self.__consumer_thread_fcn)
        self.__consumer_thread.start()
        

    def __on_response(self, ch, method, props, body):
        if props.correlation_id not in self.__success_callbacks:
            raise Exception('Received unexpected response')
        data = json.loads(body)
        if data['status'] >= 200 and data['status'] < 300:
            self.__success_callbacks[props.correlation_id](data)
        else:
            if props.correlation_id in self.__failure__callbacks:
                self.__failure__callbacks[props.correlation_id](data)
            else:
                self.logger.warning('Received response with status %d without any failure callback set', data['status'])

    def call(self, cmd, args, on_success, on_failure=None):
        self.client_ready.wait()
        corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key=self.server_key,
            properties=pika.BasicProperties(
                correlation_id=corr_id,
                reply_to=self.response_queue,
                content_type='application/json'),
            body=json.dumps({
                'cmd': cmd,
                'args': args
            })
        )
        self.__success_callbacks[corr_id] = on_success
        if on_failure:
            self.__failure__callbacks[corr_id] = on_failure
        self.logger.debug('Called %s on %s', cmd, self.server_key)

    def wait_exit(self, timeout=None):
        return self.__consumer_thread.join(timeout=timeout)

    def __consumer_thread_fcn(self):
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.rabbitmq_host))
            channel = connection.channel()
            result = channel.queue_declare(queue='', exclusive=True)
            self.response_queue = result.method.queue
            channel.basic_consume(
                queue=self.response_queue,
                on_message_callback=self.__on_response,
                auto_ack=True)
            self.client_ready.set()
            channel.start_consuming()
        except KeyboardInterrupt:
            self.logger.info('Closing because user interrupt')
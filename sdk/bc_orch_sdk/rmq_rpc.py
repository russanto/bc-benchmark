import json
import logging
from threading import Event, Thread
import uuid

import pika

class RMQRPCClient(object):

    def __init__(self, rabbitmq_host):
        self.logger = logging.getLogger('RMQRPCClient')
        self.rabbitmq_host = rabbitmq_host
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
            self.__success_callbacks[props.correlation_id](data['status'], **data['data'])
        else:
            if props.correlation_id in self.__failure__callbacks:
                self.__failure__callbacks[props.correlation_id](data['status'], **data['data'])
            else:
                self.logger.warning('Received response with status %d without any failure callback set', data['status'])

    def call(self, server, cmd, args, on_success, on_failure=None):
        self.client_ready.wait()
        corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key=server,
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
        self.logger.debug('Called %s on %s', cmd, server)

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

class RMQRPCServer:
    def __init__(self, rabbitmq_host, server_key):
        self.logger = logging.getLogger('RMQRPCServer')
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
        self.server_key = server_key

        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=server_key, auto_delete=True)
        self.channel.basic_consume(server_key, self.__on_request, auto_ack=True)

        self.__call_function = {}
        self.__call_args = {}

    def add_call(self, name, function, args=None):
        self.__call_function[name] = function
        if args:
            self.__call_args[name] = args

    def run(self):
        self.channel.start_consuming()

    def __on_request(self, ch, method, props, body):
        msg = json.loads(body.decode('utf-8'))
        if 'cmd' not in msg:
            self.logger.error('Malformed command message received')
            self.__error_reply(props, 400, 'No command provided (cmd key)')
            return
        if msg['cmd'] not in self.__call_function:
            self.logger.error('Unknown command received')
            self.__error_reply(props, 400, 'Unknown command received')
            return
        try:
            if msg['cmd'] in self.__call_args:
                for arg, type_check in self.__call_args[msg['cmd']].items():
                    if arg not in msg['args']:
                        self.logger.error('Argument %s is required for command %s', arg, msg['cmd'])
                        self.__error_reply(props, 400, 'Unknown command received')
                        return
                    if not isinstance(msg['args'][arg], type_check):
                        self.logger.error('Argument %s is required to be of type %s', arg, type_check.__name__)
                        self.__error_reply(props, 400, 'Unknown command received')
                        return
                for arg in msg['args']:
                    if arg not in self.__call_args[msg['cmd']]:
                        self.logger.warning('Discarding argument %s because not required', arg)
                        del msg['args'][arg]
                result = self.__call_function[msg['cmd']](**msg['args'])
            else:
                result = self.__call_function[msg['cmd']]()
            self.__success_reply(props, result)
        except Exception as error:
            self.__error_reply(props, 500, str(error))

    def __success_reply(self, props, data):
        if not isinstance(data, dict):
            self.logger.warning('data is not of dictionary type; any value has been substituted by empty dictionary.')
            data = {}
        self.channel.basic_publish(**self.__json_response(props, {
            'status': 200,
            'data': data
        }))

    def __error_reply(self, props, code, message):
        self.channel.basic_publish(**self.__json_response(props, {
            "status": code,
            'message': message
        }))

    def __json_response(self, props, body):
        return {
            'exchange': '',
            'routing_key': props.reply_to,
            'properties': pika.BasicProperties(
                correlation_id=props.correlation_id,
                content_type='application/json'),
            'body': json.dumps(body)
        }

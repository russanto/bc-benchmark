import json
import logging

import pika

from a_host_service import AHostService

class RMQHostManager:

    BROADCAST_EXCHANGE = 'broadcast'
    CMD_QUEUE = 'host_manager_rpc'

    def __init__(self, endpoint, host_manager):
        self.logger = logging.getLogger('RMQHostManager')
        self.endpoint = endpoint
        self.host_manager = host_manager
        self.__services = {}
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=endpoint))
        self.channel = self.connection.channel()
        self.logger.info("Connected to RabbitMQ at %s", endpoint)
        self.channel.exchange_declare(exchange=self.BROADCAST_EXCHANGE, exchange_type='fanout')
        self.channel.queue_declare(queue=self.CMD_QUEUE, auto_delete=True)
        self.channel.queue_bind(queue=self.CMD_QUEUE, exchange=self.BROADCAST_EXCHANGE)
        self.logger.info("Messaging model initialized")
        #TODO eliminate auto_ack and provide an appropriate acknoledge mechanism
        self.channel.basic_consume(queue=self.CMD_QUEUE, on_message_callback=self.__msg_callback, auto_ack=True)
    
    def register_service(self, key, host_service):
        if not isinstance(host_service, AHostService):
            raise Exception('host_service must be AHostService instance')
        self.__services[key] = host_service

    def start(self):
        self.logger.info("Started with RabbitMQ at %s", self.endpoint)
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.logger.info("Stopping on user request")

    def __msg_callback(self, channel, method, properties, body):
        msg = json.loads(body.decode('utf-8'))
        if 'cmd' not in msg:
            self.logger.error('Malformed command message received')
            self.__error_reply(properties, 400, 'No command provided (cmd key)')
            return
        if msg['cmd'] == 'ping':
            self.logger.info("Ping received")
            self.__pong(properties)
            return
        else:
            self.__cmd_callback(channel, method, properties, msg)
            return

    def __cmd_callback(self, channel, method, properties, msg):
        if msg['cmd'] == 'reserve':
            if 'args' not in msg:
                self.__error_reply(properties, 400, 'No arg dictionary provided')
                return
            if 'host_count' not in msg['args']:
                self.__error_reply(properties, 400, 'Missing argument: host_count')
                return
            host_list = self.__reserve(int(msg['args']['host_count']))
            self.channel.basic_publish(**self.__json_response(properties, {
                'status': 200,
                'data': {'host_list': host_list}
            }))
        elif msg['cmd'] == 'service':
            if 'args' not in msg:
                self.__error_reply(properties, 400, 'No args dictionary provided')
                return
            if 'service' not in msg['args']:
                self.__error_reply(properties, 400, 'No service specified')
                return
            if msg['args']['service'] not in self.__services:
                self.__error_reply(properties, 400, 'Specified service is not supported')
                return
            if 'hosts' not in msg['args']:
                self.__error_reply(properties, 400, 'Missing argument: hosts')
                return
            self.channel.basic_publish(**self.__json_response(properties, {
                'status': 200,
                'data': self.__service(**msg['args'])
            }))
        elif msg['cmd'] == 'free':
            if 'args' not in msg:
                self.__error_reply(properties, 400, 'No args dictionary provided')
                return
            if 'host_list' not in msg['args']:
                self.__error_reply(properties, 400, 'Missing argument: host_list')
                return
            self.__free(msg['args']['host_list'])
            self.channel.basic_publish(**self.__json_response(properties, {
                'status': 200,
                'data': {'host_list': msg['args']['host_list']}
            }))
        else:
            self.logger.error("Command %s not supported", msg['cmd'])

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

    def __pong(self, props):
        self.channel.basic_publish(
            exchange='',
            routing_key=props.reply_to,
            properties=pika.BasicProperties(correlation_id=props.correlation_id),
            body='pong')
        self.logger.info("Sent pong for %s" % props.correlation_id)

    def __reserve(self, host_count):
        return self.host_manager.reserve(host_count)

    def __service(self, service, hosts, params=None):
        if params:
            return self.__services[service].prepare(hosts, params)
        else:
            return self.__services[service].prepare(hosts)
    
    def __free(self, host_list):
        return self.host_manager.free(host_list)

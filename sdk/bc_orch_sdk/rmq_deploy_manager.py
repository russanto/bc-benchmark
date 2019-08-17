import json
import logging

import pika

from .deploy_manager import ADeployManager

class RMQDeployManager:

    def __init__(self, connection, identifier, deploy_manager):
        if not isinstance(deploy_manager, ADeployManager):
            raise Exception("An ADeployManager is required. Given %s" % type(deploy_manager).__name__)
        self.logger = logging.getLogger('RMQDeployManager')
        self.deploy_manager = deploy_manager
        self.connection = connection
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=identifier, auto_delete=True)
        self.logger.info("Messaging model initialized")
        #TODO eliminate auto_ack and provide an appropriate acknoledge mechanism
        self.channel.basic_consume(queue=identifier, on_message_callback=self.__msg_callback, auto_ack=True)
    
    def listen(self):
        self.logger.info("Started serving with RabbitMQ")
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
        if msg['cmd'] == 'init':
            if 'args' not in msg:
                self.__error_reply(properties, 400, 'No args dictionary provided')
                return
            if 'host_list' not in msg['args']:
                self.__error_reply(properties, 400, 'Missing argument: host_list')
                return
            try:
                self.deploy_manager.init(msg['args']['host_list'])
            except:
                self.__error_reply(properties, 500, 'Deploy manager error')
            self.channel.basic_publish(**self.__json_response(properties, {
                'status': 200
            }))
        elif msg['cmd'] == 'start':
            if 'args' not in msg:
                self.__error_reply(properties, 400, 'No args dictionary provided')
                return
            if 'deploy_conf' not in msg['args']:
                self.__error_reply(properties, 400, 'Missing argument: deploy_conf')
                return
            try:
                self.deploy_manager.start(msg['args']['deploy_conf'])
            except:
                self.__error_reply(properties, 500, 'Deploy manager error')
            self.channel.basic_publish(**self.__json_response(properties, {
                'status': 200
            }))
        elif msg['cmd'] == 'stop':
            try:
                self.deploy_manager.stop()
            except:
                self.__error_reply(properties, 500, 'Deploy manager error')
            self.channel.basic_publish(**self.__json_response(properties, {
                'status': 200
            }))
        elif msg['cmd'] == 'deinit':
            if 'args' not in msg:
                self.__error_reply(properties, 400, 'No args dictionary provided')
                return
            if 'host_list' not in msg['args']:
                self.__error_reply(properties, 400, 'Missing argument: host_list')
                return
            try:
                self.deploy_manager.deinit(msg['args']['host_list'])
            except:
                self.__error_reply(properties, 500, 'Deploy manager error')
            self.channel.basic_publish(**self.__json_response(properties, {
                'status': 200
            }))
        else:
            self.logger.error("Command %s not supported", msg['cmd'])

    def __error_reply(self, props, code, message):
        self.channel.basic_publish(**self.__json_response(props, {
            "status": code,
            'message': message
        }))
        self.logger.error("REPLY - Status: %d - Message: %s", code, message)

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

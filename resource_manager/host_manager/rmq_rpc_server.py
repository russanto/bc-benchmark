import json
import logging

import pika

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
        try:
            self.channel.start_consuming()
        except KeyboardInterrupt:
            self.logger.info('Closing because user interrupt')

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
        

    def __success_reply(self, props, data):
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

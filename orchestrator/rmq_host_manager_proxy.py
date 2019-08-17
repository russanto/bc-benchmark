import json
import logging
import uuid

import pika

class RMQHostManagerProxy:

    CMD_QUEUE = 'host_manager_rpc'

    def __init__(self, rmq_channel, reply_queue):
        self.logger = logging.getLogger('RMQHostManagerProxy')
        self.channel = rmq_channel
        self.reply_queue = reply_queue
        self.channel.queue_declare(queue=self.CMD_QUEUE, passive=True)
        self.logger.info("Connected to HostManager through RabbitMQ")
    
    def ping(self):
        pass

    def free(self, host_list):
        corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key=self.CMD_QUEUE,
            properties=pika.BasicProperties(
                correlation_id=corr_id,
                reply_to=self.reply_queue,
                content_type='application/json'),
            body=json.dumps({
                'cmd': 'free',
                'args': {'host_list': host_list}
            })
        )
        return corr_id

    def reserve(self, host_count):
        corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key=self.CMD_QUEUE,
            properties=pika.BasicProperties(
                correlation_id=corr_id,
                reply_to=self.reply_queue,
                content_type='application/json'),
            body=json.dumps({
                'cmd': 'reserve',
                'args': {'host_count': host_count}
            })
        )
        return corr_id

    def callback_factory(self, on_success, on_failure=None):
        def callback(msg):
            try:
                msg_json = json.loads(msg.decode('utf-8'))
                if msg_json['status'] == 200:
                    on_success(msg_json['data']['host_list'])
            except:
                self.logger.error("Error processing reply")
                if on_failure:
                    on_failure()
        return callback
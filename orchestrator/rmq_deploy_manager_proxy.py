import json
import logging
import uuid

import pika

class RMQDeployManagerProxy():

    def __init__(self, rmq_channel, deploy_manager_id, reply_queue):
        self.logger = logging.getLogger('RMQDeployManagerProxy')
        self.channel = rmq_channel
        self.deploy_manager_id = deploy_manager_id
        self.reply_queue = reply_queue
        self.channel.queue_declare(queue=deploy_manager_id, passive=True)
        self.logger.info("Connected to %s through RabbitMQ", deploy_manager_id)

    def init(self, host_list):
        corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key=self.deploy_manager_id,
            properties=pika.BasicProperties(
                correlation_id=corr_id,
                reply_to=self.reply_queue,
                content_type='application/json'),
            body=json.dumps({
                'cmd': 'init',
                'args': {'host_list': host_list}
            })
        )
        return corr_id

    def start(self, deploy_conf):
        corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key=self.deploy_manager_id,
            properties=pika.BasicProperties(
                correlation_id=corr_id,
                reply_to=self.reply_queue,
                content_type='application/json'),
            body=json.dumps({
                'cmd': 'start',
                'args': {'deploy_conf': deploy_conf}
            })
        )
        return corr_id

    def stop(self):
        corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key=self.deploy_manager_id,
            properties=pika.BasicProperties(
                correlation_id=corr_id,
                reply_to=self.reply_queue,
                content_type='application/json'),
            body=json.dumps({
                'cmd': 'stop'
            })
        )
        return corr_id

    def deinit(self, host_list):
        corr_id = str(uuid.uuid4())
        self.channel.basic_publish(
            exchange='',
            routing_key=self.deploy_manager_id,
            properties=pika.BasicProperties(
                correlation_id=corr_id,
                reply_to=self.reply_queue,
                content_type='application/json'),
            body=json.dumps({
                'cmd': 'deinit',
                'args': {'host_list': host_list}
            })
        )
        return corr_id

    def callback_factory(self, on_success, on_failure=None):
        def callback(msg):
            try:
                msg_json = json.loads(msg.decode('utf-8'))
                if msg_json['status'] == 200:
                    on_success()
            except:
                self.logger.error("Error processing reply")
                if on_failure:
                    on_failure()
        return callback
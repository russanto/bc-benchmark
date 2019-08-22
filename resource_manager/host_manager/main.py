import logging
import os
import sys
import time

import pika
import yaml

from host_manager import HostManager
from host_services.docker_host_service import DockerHostService
from host_services.ssh_host_service import SSHHostService
from rmq_host_manager import RMQHostManager

logger = logging.getLogger("HostManager")
if "LOG_LEVEL" in os.environ:
    if os.environ["LOG_LEVEL"] == "DEBUG":
        logging.basicConfig(level=logging.DEBUG)
    elif os.environ["LOG_LEVEL"] == "INFO":
        logging.basicConfig(level=logging.INFO)
logging.getLogger('pika').setLevel(logging.WARNING)

if "RABBITMQ" not in os.environ:
    logger.error("RabbitMQ endpoint not set in environment RABBITMQ")
    sys.exit(1)

host_manager = HostManager()
with open('static_hosts_conf.yaml') as host_conf_file:
    hosts = yaml.load(host_conf_file)
for host in hosts['hosts']:
    host_manager.add_host(host)

rmq_host_manager = RMQHostManager(os.environ["RABBITMQ"], host_manager)
docker_service = DockerHostService('192.168.99.1:5000')
ssh_service = SSHHostService('static_hosts_conf.yaml')
rmq_host_manager.register_service('docker', docker_service)
rmq_host_manager.register_service('ssh', ssh_service)
try:
    rmq_host_manager.run()
except KeyboardInterrupt:
    logger.info('Stopping server')

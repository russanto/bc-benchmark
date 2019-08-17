import logging
import os
import sys
import time

import pika

from docker_host_service import DockerHostService
from host_manager import HostManager
from rmq_host_manager import RMQHostManager
from ssh_host_service import SSHHostService

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
host_manager.add_host('192.168.99.106')
host_manager.add_host('192.168.99.107')
host_manager.add_host('192.168.99.108')

rmq_host_manager = RMQHostManager(os.environ["RABBITMQ"], host_manager)
docker_service = DockerHostService()
ssh_service = SSHHostService()
rmq_host_manager.register_service('docker', docker_service)
rmq_host_manager.register_service('ssh', ssh_service)
rmq_host_manager.start()
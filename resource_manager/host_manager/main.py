import logging
import os
import sys
import time

import pika

from host_manager import HostManager
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
host_manager.add_host('192.168.1.1')
host_manager.add_host('192.168.1.2')

rmq_host_manager = RMQHostManager(os.environ["RABBITMQ"], host_manager)
rmq_host_manager.start()
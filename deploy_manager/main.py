import logging
import os
import sys

import pika

from docker_service_plugin import DockerServicePlugin
from geth_manager import GethManager
from rmq_deploy_manager import RMQDeployManager
from rmq_host_manager_services_provider import RMQHostManagerServicesProvider
from ssh_service_plugin import SSHServicePlugin

logger = logging.getLogger("Orchestrator")
if "LOG_LEVEL" in os.environ:
    if os.environ["LOG_LEVEL"] == "DEBUG":
        logging.basicConfig(level=logging.DEBUG)
    elif os.environ["LOG_LEVEL"] == "INFO":
        logging.basicConfig(level=logging.INFO)
logging.getLogger('pika').setLevel(logging.WARNING)


if "RABBITMQ" not in os.environ:
    logger.error("RabbitMQ endpoint not set in environment RABBITMQ")
    sys.exit(1)

service_provider = RMQHostManagerServicesProvider(os.environ['RABBITMQ'])
service_provider.register_plugin('docker', DockerServicePlugin())
service_provider.register_plugin('ssh', SSHServicePlugin())
dm = GethManager("/Users/antonio/Documents/Universita/INSA/bc-benchmark/tmp", service_provider)
rmq = RMQDeployManager(pika.BlockingConnection(pika.ConnectionParameters(host=os.environ['RABBITMQ'])), "deploy_manager", dm)
rmq.listen()
import logging
import os
import sys

from stub_deploy_manager import StubDeployManager
from rmq_deploy_manager import RMQDeployManager

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

stub = StubDeployManager()
rmq = RMQDeployManager(os.environ['RABBITMQ'], stub)
rmq.listen()
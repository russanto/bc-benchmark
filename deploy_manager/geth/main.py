import logging
import os
import sys

import pika

from bc_orch_sdk.docker_service_plugin import DockerServicePlugin
from bc_orch_sdk.rmq_deploy_manager import RMQDeployManager
from bc_orch_sdk.rmq_host_manager_services_provider import RMQHostManagerServicesProvider
from bc_orch_sdk.rmq_rpc import RMQRPCWaiter
from bc_orch_sdk.ssh_service_plugin import SSHServicePlugin
from geth_manager import GethManager

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

try:
    rpc_waiter = RMQRPCWaiter(os.environ["RABBITMQ"])
    rpc_waiter.wait()
except Exception:
    sys.exit(1)

rmq_geth_manager_identifier = "deploy_manager"
if "RMQ_GETH_MANAGER" in os.environ:
    rmq_geth_manager_identifier = os.environ["RMQ_GETH_MANAGER"]

tmp_dir = "/tmp"
if "GETH_TMP_DIR" in os.environ:
    tmp_dir = os.environ["GETH_TMP_DIR"]

try:
    service_provider = RMQHostManagerServicesProvider(os.environ['RABBITMQ'])
    service_provider.register_plugin('docker', DockerServicePlugin())
    service_provider.register_plugin('ssh', SSHServicePlugin())
    dm = GethManager(tmp_dir, service_provider)
    dm.set_consensus_protocol(dm.CLIQUE)
    rmq = RMQDeployManager(os.environ['RABBITMQ'], rmq_geth_manager_identifier, dm)
    rmq.run()
except pika.exceptions.AMQPConnectionError as error:
    logger.error('Exiting due to connection error with RabbitMQ')
    sys.exit(1)
except KeyboardInterrupt:
    logger.info('Closing due to user interrupt')
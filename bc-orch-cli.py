import argparse
import logging

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BC-Orch-CLI")

def openstack_cli(args):
    import openstack
    from resource_manager.openstack.openstack_driver import OpenstackDriver
    driver = OpenstackDriver(openstack.connect(cloud=args.cloud))
    driver.deploy_controller()
    driver.deploy_nodes(args.name, args.nodes)

def geth_start_cli(args):
    url = "http://%s:%d" % (args.controller, args.controller_port)
    try:
        files = {'genesis': open(args.genesis, 'rb')}
        response = requests.post(url, files=files)
    except FileNotFoundError:
        logger.error("Specifieid genesis file not found. Deploy aborted.")

def geth_stop_cli(args):
    pass

def geth_status_cli(args):
    pass

def benchmark_cli(args):
    logger.warning("Benchmark module not yet implemented")

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--controller", help="Controller endpoint; default is localhost", type=str, default="localhost")
parser.add_argument("-cp", "--controller_port", help="Controller port; default is 3000", type=int, default=3000)
subparsers = parser.add_subparsers(help="module to refer")

openstack_parser = subparsers.add_parser("openstack")
openstack_parser.add_argument("nodes", help="number of nodes to deploy")
openstack_parser.add_argument("-c", "--cloud", help="name of the cloud to use", default="openstack")
openstack_parser.add_argument("-n", "--name", help="name for server group and machines", default="benchmark")
openstack_parser.set_defaults(func=openstack_cli)

deploy_parser = subparsers.add_parser("deploy")
deploy_subparser = deploy_parser.add_subparsers(help="target to deploy")
geth_parser = deploy_subparser.add_parser("geth")
geth_subparsers = geth_parser.add_subparsers(help="start|stop|status are supported")
geth_start_parser = geth_subparsers.add_parser("start")
geth_start_parser.add_argument("--nodes", help="number of nodes to request", required=True)
geth_start_parser.add_argument("-g","--genesis", help="genesis file to use for the deployment", default="genesis.json")
geth_start_parser.set_defaults(func=geth_start_cli)
geth_stop_parser = geth_subparsers.add_parser("stop")
geth_stop_parser.add_argument("deploy_id", help="deploy_id of the deployment to stop")
geth_stop_parser.set_defaults(func=geth_stop_cli)
geth_status_parser = geth_subparsers.add_parser("status")
geth_status_parser.add_argument("deploy_id", help="deploy_id of the deployment to show status")
geth_status_parser.set_defaults(func=geth_status_cli)

benchmark_parser = subparsers.add_parser("benchmark")
benchmark_subparsers = benchmark_parser.add_subparsers(help="tool to employ")

caliper_parser = benchmark_subparsers.add_parser("caliper")
caliper_parser.add_argument("deploy_id", help="deploy id returned by a blockchain deploy", type=str)
caliper_parser.add_argument("-w", "--workload", help="Workload file to submit to Caliper")
caliper_parser.add_argument("-n", "--network", help="Network file relative to the deployed network")

propagation_parser = benchmark_subparsers.add_parser("propagation")
propagation_parser.add_argument("deploy-id", help="deploy id returned by a blockchain deploy; only geth deploy-id are supported.", type=str)


args = parser.parse_args()
args.func(args)


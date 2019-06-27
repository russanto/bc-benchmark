import argparse
import logging

import requests

logging.basicConfig(level=logging.INFO)
logging.getLogger("paramiko.transport").setLevel(logging.WARNING)
logger = logging.getLogger("BC-Orch-CLI")

def openstack_cli(args):
    import openstack
    from resource_manager.openstack.openstack_driver import OpenstackDriver
    driver = OpenstackDriver(openstack.connect(cloud=args.cloud))
    if args.nodes_pub_key:
        if args.nodes_priv_keyfile:
            driver.ssh_pvt_key_nodes = args.nodes_priv_keyfile
            driver.ssh_key_nodes = args.nodes_pub_key
        else:
            raise Exception("Private keyfile must be set if changing nodes public key")
    driver.ssh_key_controller = args.controller_pub_key
    driver.node_flavor = args.flavor_node
    driver.controller_flavor = args.flavor_controller
    driver.deploy_controller()
    driver.deploy_nodes(args.name, args.nodes)

def geth_start_cli(args):
    url = "http://%s:%d/start/geth/%d" % (args.controller, args.controller_port, args.nodes)
    try:
        files = {'genesis': open(args.genesis, 'rb')}
        response = requests.post(url, files=files)
        print(response.json())
    except FileNotFoundError:
        logger.error("Specifieid genesis file not found. Deploy aborted.")

def deploy_stop_cli(args):
    url = "http://%s:%d/stop/%s" % (args.controller, args.controller_port, args.deploy_id)
    try:
        response = requests.get(url)
        print(response.json())
    except:
        logger.error("Something went wrong with the request")


def deploy_status_cli(args):
    url = "http://%s:%d/status/%s" % (args.controller, args.controller_port, args.deploy_id)
    try:
        response = requests.get(url)
        print(response.json())
    except:
        logger.error("Something went wrong with the request")

def caliper_starter_cli(args):
    url = "http://%s:%d/benchmark/start/caliper/%s" % (args.controller, args.controller_port, args.deploy_id)
    try:
        files = {
            'network': open(args.network, 'rb'),
            'benchmark': open(args.workload, 'rb')
        }
        response = requests.post(url, files=files)
        print(response.json())
    except FileNotFoundError as error:
        logger.error(error)

def propagation_start_cli(args):
    url = "http://%s:%d/benchmark/start/block-propagation/%s" % (args.controller, args.controller_port, args.deploy_id)
    try:
        response = requests.post(url)
        print(response.json())
    except FileNotFoundError as error:
        logger.error(error)

parser = argparse.ArgumentParser()
parser.add_argument("-c", "--controller", help="Controller endpoint; default is localhost", type=str, default="localhost")
parser.add_argument("-cp", "--controller_port", help="Controller port; default is 3000", type=int, default=3000)
subparsers = parser.add_subparsers(help="module to refer")

openstack_parser = subparsers.add_parser("openstack")
openstack_parser.add_argument("nodes", help="number of nodes to deploy", type=int)
openstack_parser.add_argument("-c", "--cloud", help="name of the cloud to use", default="openstack")
openstack_parser.add_argument("-n", "--name", help="name for server group and machines", default="benchmark")
openstack_parser.add_argument("--flavor_node", help="flavor to use for nodes hosts. Default: m1.medium", default="m1.medium")
openstack_parser.add_argument("--flavor_controller", help="flavor to use for controller host. Default: m1.large", default="m1.large")
openstack_parser.add_argument("--controller_pub_key", help="Key pair name, already uploaded to openstack, to add to controller", default="ControllerKey")
openstack_parser.add_argument("--nodes_pub_key", help="Key pair name, already uploaded to openstack, to add to nodes. If specified, --nodes_priv_keyfile must be specified, too.")
openstack_parser.add_argument("--nodes_priv_keyfile", help="Private key file to upload to controller in order to connect to nodes.")
openstack_parser.set_defaults(func=openstack_cli)

deploy_parser = subparsers.add_parser("deploy")
deploy_subparser = deploy_parser.add_subparsers(help="target to deploy")
geth_parser = deploy_subparser.add_parser("geth")
geth_subparsers = geth_parser.add_subparsers(help="start|stop|status are supported")
geth_start_parser = geth_subparsers.add_parser("start")
geth_start_parser.add_argument("--nodes", help="number of nodes to request", type=int, required=True)
geth_start_parser.add_argument("-g","--genesis", help="genesis file to use for the deployment", default="genesis.json")
geth_start_parser.set_defaults(func=geth_start_cli)
geth_stop_parser = geth_subparsers.add_parser("stop")
geth_stop_parser.add_argument("deploy_id", help="deploy_id of the deployment to stop")
geth_stop_parser.set_defaults(func=deploy_stop_cli)
geth_status_parser = geth_subparsers.add_parser("status")
geth_status_parser.add_argument("deploy_id", help="deploy_id of the deployment to show status")
geth_status_parser.set_defaults(func=deploy_status_cli)

benchmark_parser = subparsers.add_parser("benchmark")
benchmark_subparsers = benchmark_parser.add_subparsers(help="tool to employ")

caliper_parser = benchmark_subparsers.add_parser("caliper")
caliper_parser.add_argument("deploy_id", help="deploy id returned by a blockchain deploy", type=str)
caliper_parser.add_argument("-w", "--workload", help="Workload file to submit to Caliper")
caliper_parser.add_argument("-n", "--network", help="Network file relative to the deployed network")
caliper_parser.set_defaults(func=caliper_starter_cli)

propagation_parser = benchmark_subparsers.add_parser("propagation")
propagation_parser.add_argument("deploy_id", help="deploy id returned by a blockchain deploy; only geth deploy-id are supported.", type=str)
propagation_parser.set_defaults(func=propagation_start_cli)

args = parser.parse_args()
args.func(args)


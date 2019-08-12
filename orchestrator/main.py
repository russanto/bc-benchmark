import logging
import os
import sys
import time

from rmq_orchestrator_proxy import RMQOrchestratorProxy

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

def on_success():
    logger.info('Op success')

host_list = ['192.168.1.1', '192.168.1.2']

rmq_orchestrator = RMQOrchestratorProxy(os.environ['RABBITMQ'])
rmq_orchestrator.deploy_manager_init(host_list, on_success)
rmq_orchestrator.deploy_manager_start({}, on_success)
rmq_orchestrator.deploy_manager_stop(on_success)
rmq_orchestrator.deploy_manager_deinit(host_list, on_success)
rmq_orchestrator.listen()

# UPLOAD_FOLDER = "/Users/antonio/Documents/Universita/INSA/bc-benchmark/uploads"
# if "UPLOAD_FOLDER" in os.environ:
#     UPLOAD_FOLDER = os.environ["UPLOAD_FOLDER"]
# if not os.path.exists(UPLOAD_FOLDER):
#     os.makedirs(UPLOAD_FOLDER)

# app = Flask("BC-Orch-Controller")
# app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# app.run(host='0.0.0.0')

# @app.route('/ready')
# def get_ready_count():
#     return jsonify({"count": len(host_manager.get_hosts())})

# @app.route('/ready/<string:ip_ready>')
# def notify_ready(ip_ready):
#     host_manager.add_host(ip_ready)
#     return jsonify('understood')

# @app.route('/status/<string:deploy_id>', methods=['GET'])
# def status_deploy(deploy_id):
#     global bc_manager
#     uuidObj = uuid.UUID('urn:uuid:{0}'.format(deploy_id))
#     if uuidObj in bc_manager:
#         deploy_manager = bc_manager[uuidObj]
#         if deploy_manager.current_stage:
#             return jsonify({
#                 "stage": deploy_manager.current_stage,
#                 "completed": deploy_manager.cmd_events[deploy_manager.current_stage].is_set()
#             })
#         else:
#             return jsonify({
#                 "message": "Deploy session not running. Some error occurred between session creation and its initialization."
#             }), 500
#     return jsonify({"message": 'Deploy session not found'}), 404


# @app.route('/start/multichain/<int:nodes_count>/<string:protocol>', methods=['POST'])
# def start_multichain(nodes_count, protocol):
#     global bc_manager
#     if protocol != MultichainManager.BITCOIN and protocol != MultichainManager.MULTICHAIN:
#         return jsonify({"message": 'Only bitcoin and multichain protocol are supported'}), 403
#     if 'params' not in request.files:
#         return jsonify({"message": 'Params file is required in order to start a multichain network'}), 403
#     file = request.files['params']
#     if file.filename == '':
#         return jsonify({"message": 'Empty params file found'}), 403
#     hosts = host_manager.reserve_hosts(nodes_count)
#     if hosts:
#         params_file_path = "./multichain/params.dat"
#         file.save(params_file_path)
#         deploy_id = uuid.uuid4()
#         multichain_manager = MultichainManager(hosts)
#         multichain_manager.set_bc_protocol(protocol)
#         multichain_manager.init()
#         multichain_manager.cleanup()
#         multichain_manager.start()
#         bc_manager[deploy_id] = multichain_manager
#         return jsonify({"message": "Starting network", "deploy_id": deploy_id})
#     else:
#         return jsonify({"message": 'Not enough nodes ready or available'}), 412

# @app.route('/start/geth/<int:nodes_count>', methods=['POST'])
# def start_geth(nodes_count):
#     global bc_manager
#     if 'genesis' not in request.files:
#         return jsonify({"message": 'Genesis is required in order to start the blockchain'}), 403
#     file = request.files['genesis']
#     if file.filename == '':
#         return jsonify({"message": 'Empty json found'}), 403
#     hosts = host_manager.reserve_hosts(nodes_count)
#     if hosts:
#         genesis_file = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
#         file.save(genesis_file)
#         deploy_id = uuid.uuid4()
#         geth_manager = GethManager(hosts)
#         geth_manager.parse_conf(os.environ)
#         with open(genesis_file) as genesis_file_data:
#             genesis_dict = json.load(genesis_file_data)
#             if "clique" in genesis_dict['config']:
#                 geth_manager.set_consensus_protocol(GethManager.CLIQUE)
#                 geth_manager.FILE_CLIQUE = genesis_file
#             else:
#                 geth_manager.FILE_ETHASH = genesis_file
#         geth_manager.init()
#         geth_manager.cleanup()
#         geth_manager.start()
#         bc_manager[deploy_id] = geth_manager
#         return jsonify({"message": "Starting network", "deploy_id": deploy_id})
#     else:
#         return jsonify({"message": 'Not enough nodes ready or available'}), 412

# @app.route('/start/parity/<int:nodes_count>', methods=['POST'])
# def start_parity(nodes_count):
#     global bc_manager
#     if 'genesis' not in request.files:
#         return jsonify({"message": 'Genesis is required in order to start the blockchain'}), 403
#     file = request.files['genesis']
#     if file.filename == '':
#         return jsonify({"message": 'Empty json found'}), 403
#     hosts = host_manager.reserve_hosts(nodes_count)
#     if hosts:
#         genesis_file = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
#         file.save(genesis_file)
#         deploy_id = uuid.uuid4()
#         parity_manager = ParityManager(hosts)
#         parity_manager.FILE_GENESIS = genesis_file
#         parity_manager.init()
#         parity_manager.start()
#         bc_manager[deploy_id] = parity_manager
#         return jsonify({"message": "Starting network", "deploy_id": deploy_id})
#     else:
#         return jsonify({"message": 'Not enough nodes ready or available'}), 412

# @app.route('/start/burrow/<int:nodes_count>/<int:proposal_threshold>', methods=['POST'])
# def start_burrow(nodes_count, proposal_threshold):
#     global bc_manager
#     hosts = host_manager.reserve_hosts(nodes_count)
#     if hosts:
#         deploy_id = uuid.uuid4()
#         burrow_manager = BurrowManager(hosts, proposal_threshold)
#         burrow_manager.init()
#         burrow_manager.start()
#         bc_manager[deploy_id] = burrow_manager
#         return jsonify({"message": "Starting network", "deploy_id": deploy_id})
#     else:
#         return jsonify({"message": 'Not enough nodes ready or available'}), 412

# @app.route('/stop/<string:deploy_id>', methods=['GET', 'POST'])
# def stop_blockchain(deploy_id):
#     global bc_manager
#     uuidObj = uuid.UUID('urn:uuid:{0}'.format(deploy_id))
#     if uuidObj in bc_manager:
#         manager = bc_manager[uuidObj]
#         manager.stop()
#         manager.deinit()
#         host_manager.free_hosts(manager.hosts)
#         return jsonify({"message": 'Nodes stopping and session closed'})
#     return jsonify({"message": 'Deploy session not found'}), 404

# @app.route('/benchmark/start/caliper/<string:deploy_id>', methods=['POST'])
# def start_caliper(deploy_id):
#     global bc_manager
#     if 'benchmark' not in request.files:
#         return jsonify({"message": 'Benchmark file is required in order to start caliper'}), 403
#     file = request.files['benchmark']
#     if file.filename == '':
#         return jsonify({"message": 'Empty benchmark file found'}), 403
#     benchmark_file = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
#     file.save(benchmark_file)

#     if 'network' not in request.files:
#         return jsonify({"message": 'Network file is required in order to start caliper'}), 403
#     file = request.files['network']
#     if file.filename == '':
#         return jsonify({"message": 'Empty network file found'}), 403
#     network_file = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
#     file.save(network_file)

#     uuidObj = uuid.UUID('urn:uuid:{0}'.format(deploy_id))
#     if uuidObj in bc_manager:
#         caliper_deploy_id = uuid.uuid4()
#         ethereum_manager = bc_manager[uuidObj]
#         ethereum_adapter = CaliperEthereum(ethereum_manager, network_file)
#         caliper_manager = CaliperManager(ethereum_adapter, benchmark_file)
#         caliper_manager.parse_conf(os.environ)
#         caliper_manager.init()
#         caliper_manager.cleanup()
#         caliper_manager.start()
#         caliper_manager.stop()
#         caliper_manager.deinit()
#         bc_manager[caliper_deploy_id] = caliper_manager
#         return jsonify({
#             "message": "Caliper configured and started running",
#             "deploy_id": caliper_deploy_id
#         })
#     return jsonify({"message": 'Deploy session not found'}), 404

# @app.route('/benchmark/start/block-propagation/<string:deploy_id>', methods=['POST'])
# def start_block_propagation(deploy_id):
#     global bc_manager
#     uuidObj = uuid.UUID('urn:uuid:{0}'.format(deploy_id))
#     if uuidObj in bc_manager:
#         bp_id = uuid.uuid4()
#         if not isinstance(bc_manager[uuidObj], GethManager):
#             return jsonify({"message": 'Deploy session is not a Geth session'}), 403
#         geth_manager = bc_manager[uuidObj]
#         bp_manager = BlockPropagationManager(geth_manager.hosts)
#         bp_manager.init()
#         bp_manager.start()
#         bc_manager[bp_id] = bp_manager
#         return jsonify({
#             "message": "Block configuration reachable at %s:%d/follow" % (HostManager.get_local_connections(False)['ip'], bp_manager.server_port),
#             "deploy_id": bp_id
#         })
#     return jsonify({"message": 'Deploy session not found'}), 404

    
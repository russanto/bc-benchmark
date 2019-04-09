from flask import Flask, jsonify, request
import logging
import os
import queue
import sys
from threading import Thread
import uuid

from block_benchmark_handler import BlockBenchmarkHandler
from geth_manager import GethManager
from host_manager import HostManager

logger_host = os.environ.get("LOGGER_HOST", "")
if logger_host == "":
    print("[WARNING] Logging block propagation won't work because no logging host has been set")

if "LOG_LEVEL" in os.environ:
    if os.environ["LOG_LEVEL"] == "DEBUG":
        logging.basicConfig(level=logging.DEBUG)
    elif os.environ["LOG_LEVEL"] == "INFO":
        logging.basicConfig(level=logging.INFO)

RUNNING_IN_CONTAINER = True
if "RUNNING_IN_CONTAINER" in os.environ:
    if os.environ["RUNNING_IN_CONTAINER"] == 0 or os.environ["RUNNING_IN_CONTAINER"] == "0":
        RUNNING_IN_CONTAINER = False

UPLOAD_FOLDER = "/root/uploads"
if "UPLOAD_FOLDER" in os.environ:
    UPLOAD_FOLDER = os.environ["UPLOAD_FOLDER"]
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask("BC-Orch-Controller")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

#TODO Implementare prenotazione host
host_manager = HostManager("hosts")
bc_manager = {}

@app.route('/ready')
def get_ready_count():
    return jsonify({"count": len(host_manager.get_hosts())})

@app.route('/ready/<string:ip_ready>')
def notify_ready(ip_ready):
    host_manager.add_host(ip_ready)
    return jsonify('understood')

@app.route('/start/multichain/<int:nodes_count>', methods=['GET', 'POST'])
def start(nodes_count):
    hosts = host_manager.get_hosts(nodes_count, reserve=True)
    if hosts:
        deploy_id = uuid.uuid4()
        bp_manager = BlockBenchmarkHandler(hosts[0:nodes_count], logger_host)
        bp_manager.start()
        bc_manager[deploy_id] = bp_manager
        return jsonify({"message": "Starting benchmark", "deploy_id": deploy_id})
    else:
        return jsonify({"message": 'Not enough nodes ready or available'}), 412
        

@app.route('/start/geth/<int:nodes_count>', methods=['POST'])
def start_geth(nodes_count):
    global bc_manager
    if 'genesis' not in request.files:
        return jsonify({"message": 'Genesis is required in order to start the blockchain'}), 403
    file = request.files['genesis']
    if file.filename == '':
        return jsonify({"message": 'Empty json found'}), 403
    hosts = host_manager.get_hosts(nodes_count, reserve=True)
    if hosts:
        genesis_file = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(genesis_file)
        deploy_id = uuid.uuid4()
        geth_manager = GethManager(hosts, running_in_container=RUNNING_IN_CONTAINER)
        geth_manager.init()
        geth_manager.cleanup()
        geth_manager.start(genesis_file)
        bc_manager[deploy_id] = geth_manager
        return jsonify({"message": "Starting network", "deploy_id": deploy_id})
    else:
        return jsonify({"message": 'Not enough nodes ready or available'}), 412

@app.route('/stop/geth/<string:deploy_id>', methods=['GET', 'POST'])
def stop_geth(deploy_id):
    global bc_manager
    uuidObj = uuid.UUID('urn:uuid:{0}'.format(deploy_id))
    if uuidObj in bc_manager:
        geth_manager = bc_manager[uuidObj]
        geth_manager.stop(cleanup=True)
        geth_manager.deinit()
        host_manager.free_hosts(geth_manager.hosts)
        return jsonify({"message": 'Nodes stopped and session closed'})
    return jsonify({"message": 'Deploy session not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0')
    host_manager.close()
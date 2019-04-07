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

app = Flask("BC-Orch-Controller")
app.config["UPLOAD_FOLDER"] = "/root/uploads"
if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])

#TODO Implementare prenotazione host
host_manager = HostManager("hosts", overwrite=False)
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
        geth_manager = GethManager(hosts[0:nodes_count])
        geth_manager.init(running_in_container=False)
        geth_manager.start(genesis_file, wait=False)
        bc_manager[deploy_id] = geth_manager
        return jsonify({"message": "Starting network", "deploy_id": deploy_id})
    else:
        return jsonify({"message": 'Not enough nodes ready or available'}), 412

@app.route('/stop/geth/<string:deploy_id>', methods=['GET', 'POST'])
def stop_geth(deploy_id):
    if deploy_id in bc_manager:
        geth_manager = bc_manager[deploy_id]
        geth_manager.stop()
        geth_manager.deinit()
        return jsonify({"message": 'Nodes stopped and session closed'})
    return jsonify({"message": 'Deploy session not found'}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0')
    host_manager.close()
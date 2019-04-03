from flask import Flask, jsonify, request
import os
import queue
import sys
from threading import Thread

from block_benchmark_handler import BlockBenchmarkHandler
from geth_manager import GethManager
from host_manager import HostManager

logger_host = os.environ.get("LOGGER_HOST", "")
if logger_host == "":
    print("[WARNING] Logging block propagation won't work because no logging host has been set")

app = Flask("BC-Orch-Controller")
app.config["UPLOAD_FOLDER"] = "/Users/antonio/Documents/Universita/INSA/bc-benchmark/uploads"
if not os.path.exists(app.config["UPLOAD_FOLDER"]):
    os.makedirs(app.config["UPLOAD_FOLDER"])

host_manager = HostManager("hosts")
bp_manager = None
geth_manager = None

@app.route('/ready')
def get_ready_count():
    return jsonify({"count": len(host_manager.get_hosts())})

@app.route('/ready/<string:ip_ready>')
def notify_ready(ip_ready):
    host_manager.add_host(ip_ready)
    return jsonify('understood')

@app.route('/start/multichain/<int:nodes_count>', methods=['GET', 'POST'])
def start(nodes_count):
    global bp_manager
    hosts = host_manager.get_hosts()
    if len(hosts) < nodes_count:
        return jsonify({"message": 'Not enough nodes ready'}), 403
    elif bp_manager != None:
        return jsonify({"message": 'Benchmark already started'}), 403
    else:
        bp_manager = BlockBenchmarkHandler(hosts[0:nodes_count], logger_host)
        bp_manager.start()
        return jsonify({"message": "started"})

@app.route('/start/ethereum/<int:nodes_count>', methods=['POST'])
def upload_file(nodes_count):
    global geth_manager
    hosts = host_manager.get_hosts()
    if len(hosts) < nodes_count:
        return jsonify('Not enough nodes ready')
    elif geth_manager != None:
        return jsonify('Benchmark already started')
    else:
        if 'genesis' not in request.files:
            return jsonify("genesis is required in order to start the network")
        file = request.files['genesis']
        if file.filename == '':
            return jsonify("empty genesis found")
        if file:
            genesis_file = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(genesis_file)
            geth_manager = GethManager(hosts[0:nodes_count])
            geth_manager.start(genesis_file, wait=False)
            return jsonify("Starting network")

if __name__ == '__main__':
    app.run(host='0.0.0.0')
    host_manager.close()
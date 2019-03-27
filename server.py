from flask import Flask
import os
import queue
import sys

from block_benchmark_handler import BlockBenchmarkHandler

nodes_count = int(os.environ.get("NODES_COUNT", 2))
logger_host = os.environ.get("LOGGER_HOST", "")
if logger_host == "":
    print("[WARNING] Logging block propagation won't work because no logging host has been set")

app = Flask("HostWriter")
host_queue = queue.Queue()
writer = BlockBenchmarkHandler(host_queue, nodes_count, logger_host)
writer.start()

@app.route('/ready/<string:ip_ready>')
def show_post(ip_ready):
    host_queue.put(ip_ready)
    return 'understood'

if __name__ == '__main__':
    app.run(host='0.0.0.0')
    host_queue.put("")
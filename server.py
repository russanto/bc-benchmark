from flask import Flask
import os
import queue
import sys
from threading import Thread

from block_benchmark_handler import BlockBenchmarkHandler

logger_host = os.environ.get("LOGGER_HOST", "")
if logger_host == "":
    print("[WARNING] Logging block propagation won't work because no logging host has been set")

app = Flask("HostWriter")
starter = None
writer = None
ready_queue = queue.Queue()
host_queue = queue.Queue()

@app.route('/ready/<string:ip_ready>')
def show_post(ip_ready):
    ready_queue.put(ip_ready)
    return 'understood'

@app.route('/start/<int:nodes_count>')
def start(nodes_count):
    global writer, starter
    if starter == None:
        writer = BlockBenchmarkHandler(host_queue, nodes_count, logger_host)
        writer.start()
        starter = Thread(target=start_deploy)
        starter.start()
        return logger_host
    else:
        return 'no'

def start_deploy():
    ip = ready_queue.get()
    while True:
        host_queue.put(ip)
        if ip == "":
            return
        else:
            ip = ready_queue.get()
    

if __name__ == '__main__':
    app.run(host='0.0.0.0')
    ready_queue.put("")
    if starter != None:
        writer.join()
        starter.join()
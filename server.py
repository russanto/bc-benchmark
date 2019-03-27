from flask import Flask
import queue
import sys

from host_writer import HostWriter

app = Flask("HostWriter")
host_queue = queue.Queue()
writer = HostWriter(host_queue, int(sys.argv[2]))
writer.start()

@app.route('/ready/<string:ip_ready>')
def show_post(ip_ready):
    host_queue.put(ip_ready)
    return 'understood'

if __name__ == '__main__':
    app.run(host='0.0.0.0')
    host_queue.put("")
from flask import Flask

from ssh_node_manager import NodeManager

app = Flask("NodeManagerServer")
manager = NodeManager(3, "./conf/manager.conf")

@app.route('/ready/<string:ip_ready>')
def show_post(ip_ready):
    manager.add_node_ip(ip_ready)
    return 'understood'

if __name__ == '__main__':
    app.run(host='0.0.0.0')
    del manager
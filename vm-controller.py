from http.server import BaseHTTPRequestHandler,HTTPServer
import json
import os
import subprocess
import sys

PORT_NUMBER = 3000
DOCKER_COMPOSE_FOLDER = os.path.dirname(os.path.realpath(__file__)) + '/docker-compose'
BASH_SCRIPTS_FOLDER = os.path.dirname(os.path.realpath(__file__)) + '/bash-scripts'

class requestHandler(BaseHTTPRequestHandler):

    BC_DATADIR = sys.argv[1]

    NODE_NETWORK_PORT = 7411
    NODE_RPC_PORT = 7410

    start_node_cmd = '/start-multichain-node.sh %s %s %s %s'
    start_seed_cmd = 'docker-compose up -d'

    # STARTS THE SEED NODE
    def do_POST(self):
        if not os.path.exists(self.BC_DATADIR):
            os.makedirs(self.BC_DATADIR)
        with open(self.BC_DATADIR + '/params.dat', 'w') as outputlog:
            data = self.rfile.read(int(self.headers['Content-length'])).decode('utf-8')
            outputlog.write(data)
            outputlog.close()
        with open(self.BC_DATADIR + '/multichain.conf', 'w') as conf:
            conf.write('rpcuser=multichainrpc\n')
            conf.write('rpcpassword=multichainpassword\n')
            conf.write('rpcallowip=0.0.0.0/0')
            conf.close()
        result = {}
        result['success'] = self.start_seed()
        self.send_response(200)
        self.send_header('Content-type','application/json')
        self.end_headers()
        self.wfile.write(bytes(json.dumps(result),'utf-8'))
        return
    
    # STARTS A NODE
    # Passi il params.dat e avvia il nodo connettendolo all'ip fornito nell'header
    def do_PUT(self):
        if not os.path.exists(self.BC_DATADIR):
            os.makedirs(self.BC_DATADIR)
        with open(self.BC_DATADIR + '/params.dat', 'w') as outputlog:
            data = self.rfile.read(int(self.headers['Content-length'])).decode('utf-8')
            outputlog.write(data)
            outputlog.close()
        result = {}
        with open(self.BC_DATADIR + '/multichain.conf', 'w') as conf:
            conf.write('rpcuser=multichainrpc\n')
            conf.write('rpcpassword=multichainpassword\n')
            conf.write('rpcallowip=0.0.0.0/0')
            conf.close()
        result['result'] = self.start_node('benchmark', self.BC_DATADIR, self.headers['Seed-ip'], self.headers['Seed-port'])
        self.send_response(200)
        self.send_header('Content-type','application/json')
        self.end_headers()
        self.wfile.write(bytes(json.dumps(result),'utf-8'))
        return

    # Return the params.dat file necessary for multichaind with bitcoin protocol
    def do_GET(self):
        logfilename = self.BC_DATADIR + "/params.dat"             
        with open(logfilename) as pwfile:
            content = pwfile.read()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(bytes(content,'utf-8'))
        return

    
    def start_seed(self):
        start_exec = subprocess.Popen(self.start_seed_cmd, shell=True)
        start_exec.wait()
        return start_exec.returncode
    
    def start_node(self, bc_name, bc_datadir, seed_ip, seed_port):
        start_exec = subprocess.Popen(BASH_SCRIPTS_FOLDER + self.start_node_cmd % (bc_name, bc_datadir, seed_ip, seed_port), shell=True)
        start_exec.wait()
        return start_exec.returncode

try:
    server = HTTPServer(('', PORT_NUMBER), requestHandler)
    print('Started httpserver on port ' , PORT_NUMBER)
    
    server.serve_forever()

except KeyboardInterrupt:
	print('^C received, shutting down the web server')
	server.socket.close()
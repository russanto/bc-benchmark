from http.server import BaseHTTPRequestHandler,HTTPServer
import json
import subprocess
import sys

PORT_NUMBER = 3000

class requestHandler(BaseHTTPRequestHandler):

    VM_VOLUME_FOLDER = '/Users/antonio/Documents/Universita/INSA/MultichainDocker/docker-test/node'

    NODE_NETWORK_PORT = 7411
    NODE_RPC_PORT = 7410

    start_seed_cmd = 'docker run -d -v ' + VM_VOLUME_FOLDER + ':/root/.multichain/benchmark --name multichain-seed russanto:bm-btc-multichain multichaind benchmark'
    start_node_cmd = 'docker run -d -v ' + VM_VOLUME_FOLDER + ':/root/.multichain/benchmark --name multichain-node russanto:bm-btc-multichain multichaind benchmark@%s:%s'
    start_controller_cmd = 'docker run -d -p 8080:8080 -v ' + VM_VOLUME_FOLDER + ':/root/benchmark --name multichain-controller russanto:bm-btc-multichain-controller'
	
    def do_POST(self):
        result = {}
        result['seed'] = self.start_seed()
        # result['controller'] = self.start_controller()
        self.send_response(200)
        self.send_header('Content-type','application/json')
        self.end_headers()
        self.wfile.write(bytes(json.dumps(result),'utf-8'))
        return
    
    # Passi il params.dat e avvia il nodo connettendolo all'ip fornito nell'header
    def do_PUT(self):
        with open(self.VM_VOLUME_FOLDER + '/params.dat', 'w') as outputlog:
            data = self.rfile.read(int(self.headers['Content-length'])).decode('utf-8')
            outputlog.write(data)
            outputlog.close()
        result = {}
        with open(self.VM_VOLUME_FOLDER + '/multichain.conf', 'a') as conf:
            conf.write('rpcuser=multichainrpc\n')
            conf.write('rpcpassword=multichainpassword\n')
            conf.write('rpcallowip=172.17.0.4')
            conf.close()
        result['node'] = self.start_node(self.headers['Seed-ip'])
        result['controller'] = self.start_controller()
        self.send_response(200)
        self.send_header('Content-type','application/json')
        self.end_headers()
        self.wfile.write(bytes(json.dumps(result),'utf-8'))
        return

    
    def start_seed(self):
        start_exec = subprocess.Popen(self.start_seed_cmd, shell=True)
        start_exec.wait()
        return start_exec.returncode
    
    def start_node(self, seed_ip):
        start_exec = subprocess.Popen(self.start_node_cmd % (seed_ip, self.NODE_NETWORK_PORT), shell=True)
        start_exec.wait()
        return start_exec.returncode

    def start_controller(self):
        start_exec = subprocess.Popen(self.start_controller_cmd, shell=True)
        start_exec.wait()
        return start_exec.returncode

try:
    server = HTTPServer(('', PORT_NUMBER), requestHandler)
    print('Started httpserver on port ' , PORT_NUMBER)
    
    server.serve_forever()

except KeyboardInterrupt:
	print('^C received, shutting down the web server')
	server.socket.close()
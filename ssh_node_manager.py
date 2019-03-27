from fabric import Connection
from http.client import HTTPConnection
import ipaddress
import queue
import requests
import sys, time

from ssh_node_deployer import NodeOrganizer

class NodeManager:

    def __init__(self, n_thread, conf_file=""):
        self.conf_file = conf_file
        self.n_thread = n_thread
        self.deploy_queue = queue.Queue()
        self.node_organizer = NodeOrganizer(self.deploy_queue, n_thread, conf_file)
        self.node_organizer.start()
    
    def __del__(self):
        self.deploy_queue.put("")
        for _ in range(self.n_thread):
            self.deploy_queue.put("")
    
    def add_node_ip(self, ip):
        self.deploy_queue.put(ip)

    # def fullfil(self, sleep=0):
    #     for ip in self.nodes_ips:
    #         sys.stdout.write("-----> Starting tx generation on %s:" % str(ip))
    #         sys.stdout.flush()
    #         response = requests.get("http://" + str(ip) + "/fullfil")
    #         print("%d" % response.status_code)
    #         time.sleep(sleep)
    
    # def get_logs(self, label=""):
    #     for ip in self.nodes_ips:
    #         connection = HTTPConnection(str(ip), 8080)
    #         connection.request('GET', '/')
    #         response = connection.getresponse()

    #         if response.status == 200:
    #             with open(self.log_directory + label + '-' + ip + '.log', 'w') as outputlog:
    #                 outputlog.write(response.read().decode('utf-8'))
    #                 print('OK')
    #                 continue
    #             print('Error writing file')
    #         else:
    #             print('Error - HTTP Status: -> %d' % response.status)
    
    # def start(self):
    #     self._start_seed(self.nodes_ssh_connections[0], "SEED")
    #     for index in range(1, len(self.nodes_ssh_connections)):
    #         self._start_node(self.nodes_ssh_connections[index], "NODE" + str(index))

    # def stop(self):
    #     self._stop_seed(self.nodes_ssh_connections[0])
    #     self.nodes_ssh_connections[0].close()
    #     for i in range(1, len(self.nodes_ssh_connections)):
    #         self._stop_node(self.nodes_ssh_connections[i])
    #         self.nodes_ssh_connections[i].close()
    
    # def clean(self):
    #     for cnx in self.nodes_ssh_connections:
    #         self._clean(cnx)

        
    # def _create_seed(self, connection, node_index):
    #     datadir = self._get_datadir()
    #     make_datadir = connection.run('mkdir -p ' + datadir)
    #     if not make_datadir.ok:
    #         print("Error creating datadir %s" % datadir)
    #         return
    #     self._log("Created datadir directory", connection.original_host)
    #     make_composedir = connection.run('mkdir -p ' + self.compose_dir)
    #     if not make_composedir.ok:
    #         print("Error creating compose dir %s" % self.compose_dir)
    #         return
    #     self._log("Created compose directory", connection.original_host)
    #     connection.put(self.manager_conf_directory + 'params.dat', remote=datadir)
    #     self._log("Uploaded params.dat", connection.original_host)
    #     connection.put(self.manager_conf_directory + 'multichain.conf', remote=datadir)
    #     self._log("Uploaded multichain.conf", connection.original_host)
    #     connection.put('docker-compose/multichain-seed.yml', remote=self.compose_dir)
    #     self._log("Uploaded multichain-seed.yml", connection.original_host)
    #     connection.put('bash-scripts/start-multichain-seed.sh', remote=self.compose_dir)
    #     self._log("Uploaded start-multichain-seed.sh", connection.original_host)
    #     seed_creation = connection.run(self.compose_dir + "start-multichain-seed.sh "
    #         + self.bc_name + " "
    #         + datadir + " "
    #         + str(node_index) + " "
    #         + self.log_collector_host + " "
    #         + "80" )
    #     print(seed_creation.stdout)
    #     change_permission_to_params = connection.run("sudo chmod 755 " + datadir + '/params.dat')
    #     print(change_permission_to_params.stdout)
    #     connection.get(datadir + '/params.dat', self.manager_tmp_directory + "compiled-params.dat")

    # def _create_node(self, connection, node_index):
    #     datadir = self._get_datadir()
    #     make_datadir = connection.run('mkdir -p ' + datadir)
    #     if not make_datadir.ok:
    #         print("Error creating datadir %s" % datadir)
    #         return
    #     self._log("Created datadir directory", connection.original_host)
    #     make_composedir = connection.run('mkdir -p ' + self.compose_dir)
    #     if not make_composedir.ok:
    #         print("Error creating compose dir %s" % self.compose_dir)
    #         return
    #     self._log("Created compose directory", connection.original_host)
    #     connection.put(self.manager_tmp_directory + 'compiled-params.dat', remote=datadir + "/params.dat")
    #     self._log("Uploaded params.dat", connection.original_host)
    #     connection.put(self.manager_conf_directory + 'multichain.conf', remote=datadir)
    #     self._log("Uploaded multichain.conf", connection.original_host)
    #     connection.put('docker-compose/multichain-node.yml', remote=self.compose_dir)
    #     self._log("Uploaded multichain-node.yml", connection.original_host)
    #     connection.put('bash-scripts/start-multichain-node.sh', remote=self.compose_dir)
    #     self._log("Uploaded start-multichain-node.sh", connection.original_host)
    #     node_creation = connection.run(self.compose_dir + "start-multichain-node.sh "
    #         + self.bc_name + " "
    #         + self._get_datadir() + " "
    #         + str(self.nodes_ips[0]) + " "
    #         + "7411 "
    #         + str(node_index) + " "
    #         + self.log_collector_host + " "
    #         + "80" )
    #     print(node_creation.stdout)
    
    # def _start_seed(self, connection, node_index):
    #     seed_creation = connection.run(self.compose_dir + "start-multichain-seed.sh "
    #         + self.bc_name + " "
    #         + self._get_datadir() + " "
    #         + str(node_index) + " "
    #         + self.log_collector_host + " "
    #         + "80" )
    #     print(seed_creation.stdout)

    # def _start_node(self, connection, node_index):
    #     node_creation = connection.run(self.compose_dir + "start-multichain-node.sh "
    #         + self.bc_name + " "
    #         + self._get_datadir() + " "
    #         + str(self.nodes_ips[0]) + " "
    #         + "7411 "
    #         + str(node_index) + " "
    #         + self.log_collector_host + " "
    #         + "80" )
    #     print(node_creation.stdout)

    # def _stop_seed(self, cnx):
    #     node_stop = cnx.run("docker-compose -p " + self.bc_name + " -f " + self.compose_dir + "multichain-seed.yml down")
    #     print(node_stop.stdout)
    
    # def _stop_node(self, cnx):
    #     node_stop = cnx.run("docker-compose -p " + self.bc_name + " -f " + self.compose_dir + "multichain-node.yml down")
    #     print(node_stop.stdout)

    # def _clean(self, cnx):
    #     clean_datadir = cnx.run("rm -rf " + self.bc_datadir + self.bc_name)
    #     if clean_datadir.ok:
    #         self._log("Datadir successfully cleaned", cnx.original_host)
    #     else:
    #         self._log("Error cleaning datadir", cnx.original_host)

    # def _log(self, entry, host):
    #     print("[MANAGER][%s] %s" % (host, entry))
    


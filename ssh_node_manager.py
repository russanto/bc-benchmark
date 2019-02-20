from fabric import Connection
import ipaddress

class NodeManager:

    nodes_ips = []
    nodes_ssh_connections = []

    ssh_username = "root"

    bc_datadir = '/root/.multichain/'
    bc_name = 'benchmark'

    compose_dir = '/root/docker-compose/'

    manager_tmp_directory = "./tmp/"
    manager_conf_directory = "./conf/"

    def __init__(self, seed_ip, start_ip, end_ip):
        self.nodes_ips.append(ipaddress.IPv4Address(seed_ip))
        start = ipaddress.IPv4Address(start_ip)
        end = ipaddress.IPv4Address(end_ip)
        for ip_int in range(int(start), int(end) + 1):
            self.nodes_ips.append(ipaddress.IPv4Address(ip_int))
        for ip in self.nodes_ips:
            self.nodes_ssh_connections.append(Connection(
                    host=str(ip),
                    user=self.ssh_username,
                    inline_ssh_env=True
            ))
    
    def add_node_ip(self, ip):
        self.nodes_ips.append(ipaddress.IPv4Address(ip))

    def create(self):
        self._log("Creating seed", str(self.nodes_ips[0]))
        self._create_seed(self.nodes_ssh_connections[0], "SEED")
        for node_index in range(1, len(self.nodes_ips)):
            self._log("Creating node", str(self.nodes_ips[node_index]))
            self._create_node(self.nodes_ssh_connections[node_index], "NODE" + str(node_index))
    
    def start(self):
        self._start_seed(self.nodes_ssh_connections[0], "SEED")
        for index in range(1, len(self.nodes_ssh_connections)):
            self._start_node(self.nodes_ssh_connections[index], "NODE" + str(index))

    def stop(self):
        self._stop_seed(self.nodes_ssh_connections[0])
        for i in range(1, len(self.nodes_ssh_connections)):
            self._stop_node(self.nodes_ssh_connections[i])
    
    def clean(self):
        for cnx in self.nodes_ssh_connections:
            self._clean(cnx)
        
    def _create_seed(self, connection, node_index):
        datadir = self._get_datadir()
        make_datadir = connection.run('mkdir -p ' + datadir)
        if not make_datadir.ok:
            print("Error creating datadir %s" % datadir)
            return
        self._log("Created datadir directory", connection.original_host)
        make_composedir = connection.run('mkdir -p ' + self.compose_dir)
        if not make_composedir.ok:
            print("Error creating compose dir %s" % self.compose_dir)
            return
        self._log("Created compose directory", connection.original_host)
        connection.put(self.manager_conf_directory + 'params.dat', remote=datadir)
        self._log("Uploaded params.dat", connection.original_host)
        connection.put(self.manager_conf_directory + 'multichain.conf', remote=datadir)
        self._log("Uploaded multichain.conf", connection.original_host)
        connection.put('docker-compose/multichain-seed.yml', remote=self.compose_dir)
        self._log("Uploaded multichain-seed.yml", connection.original_host)
        connection.put('bash-scripts/start-multichain-seed.sh', remote=self.compose_dir)
        self._log("Uploaded start-multichain-seed.sh", connection.original_host)
        seed_creation = connection.run(self.compose_dir + "start-multichain-seed.sh "
            + self.bc_name + " "
            + datadir + " "
            + str(node_index) + " "
            + "192.168.20.1 "
            + "80" )
        print(seed_creation.stdout)
        change_permission_to_params = connection.run("sudo chmod 755 " + datadir + '/params.dat')
        print(change_permission_to_params.stdout)
        connection.get(datadir + '/params.dat', self.manager_tmp_directory + "compiled-params.dat")

    def _create_node(self, connection, node_index):
        datadir = self._get_datadir()
        make_datadir = connection.run('mkdir -p ' + datadir)
        if not make_datadir.ok:
            print("Error creating datadir %s" % datadir)
            return
        self._log("Created datadir directory", connection.original_host)
        make_composedir = connection.run('mkdir -p ' + self.compose_dir)
        if not make_composedir.ok:
            print("Error creating compose dir %s" % self.compose_dir)
            return
        self._log("Created compose directory", connection.original_host)
        connection.put(self.manager_tmp_directory + 'compiled-params.dat', remote=datadir + "/params.dat")
        self._log("Uploaded params.dat", connection.original_host)
        connection.put(self.manager_conf_directory + 'multichain.conf', remote=datadir)
        self._log("Uploaded multichain.conf", connection.original_host)
        connection.put('docker-compose/multichain-node.yml', remote=self.compose_dir)
        self._log("Uploaded multichain-node.yml", connection.original_host)
        connection.put('bash-scripts/start-multichain-node.sh', remote=self.compose_dir)
        self._log("Uploaded start-multichain-node.sh", connection.original_host)
        node_creation = connection.run(self.compose_dir + "start-multichain-node.sh "
            + self.bc_name + " "
            + self._get_datadir() + " "
            + str(self.nodes_ips[0]) + " "
            + "7411 "
            + str(node_index) + " "
            + "192.168.20.1 "
            + "80" )
        print(node_creation.stdout)
    
    def _start_seed(self, connection, node_index):
        seed_creation = connection.run(self.compose_dir + "start-multichain-seed.sh "
            + self.bc_name + " "
            + self._get_datadir() + " "
            + str(node_index) + " "
            + "192.168.20.1 "
            + "80" )
        print(seed_creation.stdout)

    def _start_node(self, connection, node_index):
        node_creation = connection.run(self.compose_dir + "start-multichain-node.sh "
            + self.bc_name + " "
            + self._get_datadir() + " "
            + str(self.nodes_ips[0]) + " "
            + "7411 "
            + str(node_index) + " "
            + "192.168.20.1 "
            + "80" )
        print(node_creation.stdout)

    def _stop_seed(self, cnx):
        node_stop = cnx.run("docker-compose -p " + self.bc_name + " -f " + self.compose_dir + "multichain-seed.yml down")
        print(node_stop.stdout)
    
    def _stop_node(self, cnx):
        node_stop = cnx.run("docker-compose -p " + self.bc_name + " -f " + self.compose_dir + "multichain-node.yml down")
        print(node_stop.stdout)

    def _clean(self, cnx):
        clean_datadir = cnx.run("rm -rf " + self.bc_datadir + self.bc_name)
        if clean_datadir.ok:
            self._log("Datadir successfully cleaned", cnx.original_host)
        else:
            self._log("Error cleaning datadir", cnx.original_host)
    
    def _check_connections(self):
        for cnx in self.nodes_ssh_connections:
            if not cnx.is_connected():
                cnx.open()
    
    def _get_datadir(self):
        return self.bc_datadir + self.bc_name

    def _log(self, entry, host):
        print("[MANAGER][%s] %s" % (host, entry))

if __name__ == "__main__":
    import sys, time
    seconds = int(sys.argv[1])
    start_ip = ipaddress.IPv4Address(sys.argv[2])
    end_ip = ipaddress.IPv4Address(sys.argv[3])
    print("-----> Performing a clean run for %d seconds" % seconds)
    
    start = int(start_ip)
    seed = start
    start += 1
    end = int(end_ip)

    manager = NodeManager(str(ipaddress.IPv4Address(seed)), str(ipaddress.IPv4Address(start)), str(ipaddress.IPv4Address(end)))
    manager.clean()
    manager.create()
    time.sleep(seconds)
    manager.stop()
    


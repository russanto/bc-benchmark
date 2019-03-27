from fabric import Connection
import logging
import queue
from threading import Lock, Thread

class NodeOrganizer(Thread):
    def __init__(self, ip_queue, n_deployers, conf_file):
        super().__init__()
        self.ip_queue = ip_queue
        self.seed_queue = queue.Queue(maxsize=1)
        self.deploy_queue = queue.Queue()
        self.seed_deployed = False
        self.n_deployers = n_deployers
        self.conf_file = conf_file
        self.seed_deployer = NodeDeployer(0, self.seed_queue, conf_file)
        self.seed_deployer.start()
        self.threads = []
        for i in range(n_deployers):
            th = NodeDeployer(i+1, self.deploy_queue, conf_file)
            th.start()
            self.threads.append(th)

    def run(self):
        ip = self.ip_queue.get()
        node_count = 0
        while ip != "":
            if not self.seed_deployed:
                self.seed_queue.put({
                    "type": NodeDeployer.NODE_TYPE_SEED,
                    "ip": ip,
                    "id": NodeDeployer.NODE_TYPE_SEED
                })
                self.seed_deployer.join()
                self.seed_ip = ip
                self.seed_deployed = True
            else:
                node_count += 1
                self.deploy_queue.put({
                    "type": NodeDeployer.NODE_TYPE_NODE,
                    "ip": ip,
                    "seed_ip": self.seed_ip,
                    "id": NodeDeployer.NODE_TYPE_NODE + str(node_count)
                })
            ip = self.ip_queue.get()
        for _ in range(len(self.threads)):
            self.deploy_queue.put({})


class NodeDeployer(Thread):

    NODE_TYPE_SEED = "SEED"
    NODE_TYPE_NODE = "NODE"

    default_conf_file = "./conf/manager.conf"

    ssh_username = "root"

    bc_datadir = '/root/.multichain/'
    bc_name = 'benchmark' # You have to change it also in params.dat

    compose_dir = '/root/docker-compose/'

    manager_tmp_directory = "./tmp/"
    manager_conf_directory = "./conf/"

    log_collector_host = "192.168.20.1"
    log_directory = "./logs/"

    def __init__(self, id, ip_queue, conf_file=""):
        super().__init__()
        self.ip_queue = ip_queue
        self.logger = logging.getLogger("Deployer-%d" % id)
        self._parse_conf(conf_file)

    def run(self):
        ip_dict = self.ip_queue.get()
        if ip_dict == {}:
            return
        if ip_dict["type"] == NodeDeployer.NODE_TYPE_SEED:
            connection = Connection(host=str(ip_dict["ip"]), user=self.ssh_username, inline_ssh_env=True)
            self._create_seed(connection, ip_dict["id"])
        else:
            while ip_dict != {}:
                connection = Connection(host=str(ip_dict["ip"]), user=self.ssh_username, inline_ssh_env=True)
                self._create_node(connection, ip_dict["id"], ip_dict["seed_ip"])
                ip_dict = self.ip_queue.get()
    
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
        self._start_seed(connection, node_index)
        change_permission_to_params = connection.run("sudo chmod 755 " + datadir + '/params.dat')
        print(change_permission_to_params.stdout)
        connection.get(datadir + '/params.dat', self.manager_tmp_directory + "compiled-params.dat")

    def _create_node(self, connection, node_index, seed_ip):
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
        self._start_node(connection, node_index, seed_ip)
    
    def _start_seed(self, connection, node_index):
        seed_creation = connection.run(self.compose_dir + "start-multichain-seed.sh "
            + self.bc_name + " "
            + self._get_datadir() + " "
            + str(node_index) + " "
            + self.log_collector_host + " "
            + "80" )
        print(seed_creation.stdout)

    def _start_node(self, connection, node_index, seed_ip):
        node_creation = connection.run(self.compose_dir + "start-multichain-node.sh "
            + self.bc_name + " "
            + self._get_datadir() + " "
            + seed_ip + " "
            + "7411 "
            + str(node_index) + " "
            + self.log_collector_host + " "
            + "80" )
        print(node_creation.stdout)
    
    def _parse_conf(self, conf_file=""):
        filename = self.default_conf_file
        if conf_file != "":
            filename = conf_file
        for line in open(filename):
            stripped = line.strip()
            conf_data = stripped.split('=')
            if conf_data[0] == "username":
                self.ssh_username = conf_data[1]
            elif conf_data[0] == "datadir":
                self.bc_datadir = conf_data[1]
            elif conf_data[0] == "composedir":
                self.compose_dir = conf_data[1]
            elif conf_data[0] == "collector":
                self.log_collector_host = conf_data[1]
            elif conf_data[0] == "logsdir":
                self.log_directory = conf_data[1]
        return
    
    def _get_datadir(self):
        return self.bc_datadir + self.bc_name
    
    def _log(self, entry, host):
        print("[MANAGER][%s] %s" % (host, entry))
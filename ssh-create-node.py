from fabric import Connection
import ipaddress
import sys

# bc_datadir = '/home/centos/.multichain/'
# bc_name = 'benchmark'
# compose_dir = '/home/centos/docker-compose/'

bc_datadir = '/root/.multichain/'
bc_name = 'benchmark'
compose_dir = '/root/docker-compose/'

seed_ip = ipaddress.IPv4Address(sys.argv[1])
start_ip = ipaddress.IPv4Address(sys.argv[2])
end_ip = ipaddress.IPv4Address(sys.argv[3])

def start_seed(connection, node_index):
    datadir = bc_datadir + bc_name
    make_datadir = connection.run('mkdir -p ' + datadir)
    if not make_datadir.ok:
        print("Error creating datadir %s" % datadir)
        return
    print("Created datadir directory")
    make_composedir = connection.run('mkdir -p ' + compose_dir)
    if not make_composedir.ok:
        print("Error creating compose dir %s" % compose_dir)
        return
    print("Created compose directory")
    connection.put('params.dat', remote=datadir)
    print("Uploaded params.dat")
    connection.put('multichain.conf', remote=datadir)
    print("Uploaded multichain.conf")
    connection.put('multichain-seed.yml', remote=compose_dir)
    print("Uploaded multichain-seed.yml")
    connection.put('start-multichain-seed.sh', remote=compose_dir)
    print("Uploaded start-multichain-seed.sh")
    seed_creation = connection.run(compose_dir + "start-multichain-seed.sh "
        + bc_name + " "
        + datadir + " "
        + str(node_index) + " "
        + "192.168.20.1 "
        + "80" )
    print(seed_creation.stdout)
    change_permission_to_params = connection.run("sudo chmod 755 " + datadir + '/params.dat')
    print(change_permission_to_params.stdout)
    connection.get(datadir + '/params.dat', "compiled-params.dat")

def start_node(connection, node_index):
    datadir = bc_datadir + bc_name
    make_datadir = connection.run('mkdir -p ' + datadir)
    if not make_datadir.ok:
        print("Error creating datadir %s" % datadir)
        return
    print("Created datadir directory")
    make_composedir = connection.run('mkdir -p ' + compose_dir)
    if not make_composedir.ok:
        print("Error creating compose dir %s" % compose_dir)
        return
    print("Created compose directory")
    connection.put('compiled-params.dat', remote=datadir + "/params.dat")
    print("Uploaded params.dat")
    connection.put('multichain.conf', remote=datadir)
    print("Uploaded multichain.conf")
    connection.put('multichain-node.yml', remote=compose_dir)
    print("Uploaded multichain-node.yml")
    connection.put('start-multichain-node.sh', remote=compose_dir)
    print("Uploaded start-multichain-node.sh")
    node_creation = connection.run(compose_dir + "start-multichain-node.sh "
        + bc_name + " "
        + datadir + " "
        + str(seed_ip) + " "
        + "7411 "
        + str(node_index) + " "
        + "192.168.20.1 "
        + "80" )
    print(node_creation.stdout)

nodes_connections = []

seed_connection = Connection(
    host=str(seed_ip),
    user='root',
    inline_ssh_env=True
)

node_index = 1
start_seed(seed_connection, node_index)
node_index += 1

for ip_int in range(int(start_ip), int(end_ip) + 1):
    ip = str(ipaddress.IPv4Address(ip_int))
    node_cnx = Connection(
        host=str(ip),
        user='root',
        inline_ssh_env=True)
    start_node(node_cnx, node_index)
    nodes_connections.append(node_cnx)
    node_index += 1
from fabric import Connection
import ipaddress
import sys

bc_datadir = '/root/.multichain/'
bc_name = 'benchmark'
datadir = bc_datadir + bc_name

# compose_dir = '/home/centos/docker-compose/'
compose_dir = '/root/docker-compose/'

seed_ip = ipaddress.IPv4Address(sys.argv[1])
start_ip = ipaddress.IPv4Address(sys.argv[2])
end_ip = ipaddress.IPv4Address(sys.argv[3])

def start_seed(connection, node_index):
    seed_creation = connection.run(compose_dir + "start-multichain-seed.sh "
        + bc_name + " "
        + datadir + " "
        + str(node_index) + " "
        + "192.168.20.1 "
        + "80" )
    print(seed_creation.stdout)

def start_node(connection, node_index):
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
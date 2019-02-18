from fabric import Connection
import ipaddress
import sys

bc_name = 'benchmark'

# compose_dir = '/home/centos/docker-compose/'
compose_dir = '/root/docker-compose/'

seed_ip = ipaddress.IPv4Address(sys.argv[1])
start_ip = ipaddress.IPv4Address(sys.argv[2])
end_ip = ipaddress.IPv4Address(sys.argv[3])

def stop_seed(connection):
    node_creation = connection.run("docker-compose -p " + bc_name + " -f " + compose_dir + "multichain-seed.yml down")
    print(node_creation.stdout)

def stop_node(connection):
    node_creation = connection.run("docker-compose -p " + bc_name + " -f " + compose_dir + "multichain-node.yml down")
    print(node_creation.stdout)

nodes_connections = []

seed_connection = Connection(
    host=str(seed_ip),
    user='root',
    inline_ssh_env=True
)

stop_seed(seed_connection)

for ip_int in range(int(start_ip), int(end_ip) + 1):
    ip = str(ipaddress.IPv4Address(ip_int))
    node_cnx = Connection(
        host=str(ip),
        user='root',
        inline_ssh_env=True)
    stop_node(node_cnx)
    nodes_connections.append(node_cnx)
from ssh_node_manager_hosts import NodeManagerHosts
import ipaddress
import requests
import subprocess
import sys
import time

seconds = int(sys.argv[1])
hosts_filename = sys.argv[2]

start_block_size = 1048576
end_block_size = 10485760
step_block_size = 512000

manager = NodeManagerHosts(hosts_filename)
manager.log_collector_host = sys.argv[3]

while start_block_size <= end_block_size:
    print("-----> Starting benchmark at %d block size" % start_block_size)
    subprocess.run("sed -i -e '21s/maximum-block-size = [0-9]*/maximum-block-size = %d/' ./conf/params.dat" % start_block_size, shell=True)
    subprocess.run("docker run -d -p 80:80 -v $PWD/csv:/root/csv --name benchmark-log-collector russanto/bm-btc-multichain-server /root/server %d /root/csv/%d.csv" % (len(manager.nodes_ips), start_block_size), shell=True)
    manager.clean()
    manager.create()
    manager.fullfil()
    time.sleep(seconds)
    manager.get_logs(str(start_block_size))
    manager.stop()
    subprocess.run("docker stop benchmark-log-collector", shell=True)
    subprocess.run("docker rm benchmark-log-collector", shell=True)
    print("-----> Server stopped")
    start_block_size += step_block_size

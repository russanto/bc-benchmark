import ipaddress
import logging
import subprocess
import sys
import time

from multichain_manager import MultichainManager

class BlockBenchmark:

    csv_save_path = "/home/ubuntu"

    def __init__(self, start_size=1048576, end_size=1048576, step_size=512000):
        self.start_size = start_size
        self.end_size = end_size
        self.step_size = step_size

    def start(self, hosts, log_collector_host, sim_time=120):
        self.manager = MultichainManager(hosts)
        self.manager.log_collector_host = log_collector_host
        self.manager.connect()
        current_size = self.start_size
        while current_size <= self.end_size:
            print("-----> Starting benchmark at %d block size" % current_size)
            subprocess.run("sed -i -e '21s/maximum-block-size = [0-9]*/maximum-block-size = %d/' ./conf/params.dat" % current_size, shell=True)
            subprocess.run("docker run -d -p 80:80 -v %s/csv:/root/csv --name benchmark-log-collector russanto/bm-btc-multichain-server /root/server %d /root/csv/%d.csv" % (self.csv_save_path, len(self.manager.nodes_ips), current_size), shell=True)
            self.manager.clean()
            self.manager.create()
            self.manager.fullfil()
            time.sleep(sim_time)
            self.manager.get_logs(str(current_size))
            self.manager.stop()
            subprocess.run("docker stop benchmark-log-collector", shell=True)
            subprocess.run("docker rm benchmark-log-collector", shell=True)
            print("-----> Server stopped")
            current_size += self.step_size


if __name__ == "__main__":
    from host_manager import HostManager
    host_manager = HostManager("hosts", False)
    mc_benchmark = BlockBenchmark()
    mc_benchmark.start(host_manager.get_hosts(), sys.argv[1])
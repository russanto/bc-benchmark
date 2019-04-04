from threading import Thread
import sys

from block_benchmark import BlockBenchmark

class BlockBenchmarkHandler(Thread):
    def __init__(self, hosts, log_collector_host, sim_time=120):
        super().__init__()
        self.hosts = hosts
        self.logger_host = log_collector_host
        self.simulation_time = sim_time
        self.manager = BlockBenchmark()

    def run(self):
        self.manager.start(self.hosts, self.logger_host, sim_time=self.simulation_time)
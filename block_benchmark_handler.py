from threading import Thread
import sys

from block_benchmark import BlockBenchmark

class BlockBenchmarkHandler(Thread):
    def __init__(self, host_queue, host_to_wait, logger_host):
        super().__init__()
        self.host_queue = host_queue
        self.host_to_wait = host_to_wait
        self.host_count = 0
        self.logger_host = logger_host
        self.simulation_time = 120

    def run(self):
        host_file = open("hosts", "w")
        host = self.host_queue.get()
        while host != "":
            host_file.write("%s\n" % host)
            self.host_count += 1
            if self.host_count == self.host_to_wait:
                self.host_queue.put("")
            host = self.host_queue.get()
        host_file.close()
        if self.host_count > 0:
            benchmark = BlockBenchmark()
            benchmark.start("hosts", self.logger_host, self.simulation_time)
        else:
            print("Execution aborted because no host was ready")
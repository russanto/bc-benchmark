from threading import Thread
import sys

from block_benchmark_docker import BlockBenchmark

class HostWriter(Thread):
    def __init__(self, host_queue, host_to_wait):
        super().__init__()
        self.host_queue = host_queue
        self.host_to_wait = host_to_wait
        self.host_count = 0

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
        benchmark = BlockBenchmark()
        benchmark.start("hosts", sys.argv[1])
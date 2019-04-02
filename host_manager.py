import logging
import queue
import threading

# TODO: Implement checks on received host

class HostManager:
        def __init__(self, host_file, overwrite=True):
                self.overwrite_previous_hosts = overwrite
                self.host_file = host_file
                self.host_file_lock = threading.Lock()
                self.write_queue = queue.Queue()
                self.logger = logging.getLogger("HostManager")
                self.write_thread = threading.Thread(target=self._writer)
                self.write_thread.start()

        def _writer(self):
                if self.overwrite_previous_hosts:
                        host_file = open(self.host_file, "w")
                else:
                        host_file = open(self.host_file, "a")
                host = self.write_queue.get()
                while host != "":
                        with self.host_file_lock:
                                host_file.write("%s\n" % host)
                                self.logger.debug("[WriteHost] Write: " + host + "<--")
                        host = self.write_queue.get()
                host_file.close()
        
        def add_host(self, host):
                self.write_queue.put(host)

        def get_hosts(self):
                hosts = []
                with self.host_file_lock:
                        for line in open(self.host_file, "r"):
                                stripped = line.strip()
                                hosts.append(stripped)
                                self.logger.debug("[ReadHost] Read: " + stripped + "<--")
                return hosts

        def close(self):
                self.write_queue.put("")
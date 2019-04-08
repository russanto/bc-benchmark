import logging
import queue
import threading

# TODO: Implement checks on received host

class HostManager:
        def __init__(self, host_file, overwrite=True):
                self.overwrite_previous_hosts = overwrite
                self.host_file = host_file
                self.host_file_lock = threading.Lock()
                self._hosts = []
                self._reserved_hosts = []
                self.write_queue = queue.Queue()
                self.logger = logging.getLogger("HostManager")
                self._reserving_lock = threading.Lock()
                if not overwrite:
                        self._read_host_file()
                self.write_thread = threading.Thread(target=self._writer)
                self.write_thread.start()
        
        def add_host(self, host):
                self.write_queue.put(host)

        def get_hosts(self, n_hosts=-1, reserve=False):
                with self._reserving_lock:
                        if n_hosts > len(self._hosts):
                                return False
                        if n_hosts == -1:
                                n_hosts = len(self._hosts)
                        if reserve:
                                reserve_list = []
                                for _ in range(n_hosts):
                                        reserved = self._hosts.pop()
                                        self._reserved_hosts.append(reserved)
                                        reserve_list.append(reserved)
                                return reserve_list
                        else:
                                return self._hosts[0:n_hosts]
        
        def free_hosts(self, hosts):
                with self._reserving_lock:
                        for host in hosts:
                                try:
                                        self._reserved_hosts.remove(host)
                                except ValueError:
                                        self.logger.error("Can't free host {0}. It wasn't previously reserved".format(host))
        
        def _read_host_file(self):
            with open(self.host_file) as host_file:
                for line in host_file:
                    stripped = line.strip()
                    self._hosts.append(stripped)
        
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
                        with self._reserving_lock:
                                self._hosts.append(host)
                        host = self.write_queue.get()
                host_file.close()

        def close(self):
                self.write_queue.put("")
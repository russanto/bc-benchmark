import logging
import os
import queue
import sys
import threading
import uuid

import docker
from fabric import Connection

class HostManager:

        DEFAULT_SSH_USERNAME = "ubuntu"

        def __init__(self):
            self._hosts = []
            self._reservations = []
            self._hosts_lock = threading.Lock()
            self._hosts_connections = {}
            self.logger = logging.getLogger("HostManager")
        
        def add_host(self, host):
            with self._hosts_lock:
                self._hosts.append(host)
            self.logger.info("Added host {0}".format(host))

        def add_hosts_from_file(self, hosts_file_path):
            with open(hosts_file_path) as hosts_file:
                hosts = []
                for line in hosts_file:
                    stripped = line.strip()
                    hosts.append(stripped)
            with self._hosts_lock:
                self._hosts.extend(hosts)

        def get_hosts(self):
            with self._hosts_lock:
                return self._hosts.copy()
        
        def reserve(self, n_hosts):
            reserved = []
            with self._hosts_lock:
                if len(self._hosts) < n_hosts or n_hosts < 1:
                    return False
                for _ in range(n_hosts):
                    reserved.append(self._hosts.pop())
                self._reservations.extend(reserved)
            self.logger.info("Reserved %d hosts:", n_hosts)
            for host in reserved:
                self.logger.info('- %s', host)
            return reserved

        def free(self, host_list):
            with self._hosts_lock:
                freed = []
                for host in host_list:
                    try:
                        self._reservations.remove(host)
                        self._hosts.append(host)
                        freed.append(host)
                        self.logger.info("Freed %s", host)
                    except ValueError:
                        self.logger.warning('Host %s was not previously reserved', host)
                return freed
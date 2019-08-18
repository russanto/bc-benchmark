import logging

import yaml

from bc_orch_sdk.a_host_service import AHostService

class SSHHostService(AHostService):
    def __init__(self, static_inventory_file): #TODO check inventory file consistency
        self.logger = logging.getLogger('SSHHostService')
        with open(static_inventory_file) as host_conf_file:
            self.hosts = yaml.load(host_conf_file)['hosts']

    def prepare(self, hosts, params=None):
        prepared_hosts = {}
        for host in hosts:
            if host not in self.hosts:
                self.logger.warning('Requested %s host can\'t be prepared', host)
                continue
            prepared_hosts[host] = {
                'user': self.hosts[host]['username'],
                'key_filename': self.hosts[host]['keyfile']
            }
        return prepared_hosts
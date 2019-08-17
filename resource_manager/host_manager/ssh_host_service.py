from a_host_service import AHostService

class SSHHostService(AHostService):
    def prepare(self, hosts):
        prepared_hosts = {}
        for i, host in enumerate(hosts):
            prepared_hosts[host] = {
                'user': 'docker',
                'key_filename': '/Users/antonio/.docker/machine/machines/node%d/id_rsa' % (i+1)
            }
        return prepared_hosts
from a_host_service import AHostService

class DockerHostService(AHostService):
    def __init__(self, registry_host):
        self.registry_host = registry_host

    def prepare(self, hosts):
        prepared_hosts = {}
        for host in hosts:
            prepared_hosts[host] = {'port': 2375}
        return {'connections': prepared_hosts}
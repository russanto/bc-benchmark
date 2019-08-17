import docker

from bc_orch_sdk.a_host_manager_service_plugin import AHostManagerServicePlugin

class DockerServicePlugin(AHostManagerServicePlugin):
    def transform(self, response_data):
        if 'connections' not in response_data:
            raise Exception('missing connections key in response data')
        if not isinstance(response_data['connections'], dict):
            raise Exception('malformed connections data. Expected connections dictionary')
        connections = {}
        for host, data in response_data['connections'].items():
            connections[host] = docker.DockerClient(base_url='tcp://%s:%d' % (host, data['port']))
        return connections
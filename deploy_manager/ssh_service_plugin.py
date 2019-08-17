from fabric import Connection

from bc_orch_sdk.a_host_manager_service_plugin import AHostManagerServicePlugin

class SSHServicePlugin(AHostManagerServicePlugin):
    def transform(self, response_data):
        connections = {}
        for host, data in response_data.items():
            connections[host] = Connection(host=host, user=data['user'], connect_kwargs={"key_filename": [data['key_filename']]})
        return connections
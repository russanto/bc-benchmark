import uuid

class Blockchain:
    def __init__(self, name):
        self.name = name
        self.instance_managers = {}
        self.deployments = {}

    def add_instance_manager(self, label, manager):
        self.instance_managers[label] = manager

    def deploy(self, network_configuration, manager_label):
        manager_deploy_id = self.instance_managers[manager_label].deploy(network_configuration)
        deploy_id = uuid.uuid4()
        self.deployments[deploy_id] = {
            "manager_deploy_id": manager_deploy_id,
            "manager": manager_label
        }
        return deploy_id

    def dismiss(self, deploy_id):
        deployment = self.deployments.pop(deploy_id, None)
        if deployment != None:
            self.instance_managers[deployment.manager].dismiss(deployment.manager_deploy_id)
        
import uuid

class Blockchain:
    '''
    This class is the higher level of abstraction for a blockchain deploy. It takes the driver instances for
    the compatible platforms and (this is a BIG todo) it uses some strategy to deploy nodes with them.
    Moreover also blockchain topology should be implemented
    '''
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
        
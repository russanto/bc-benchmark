import logging

from a_services_provider import AServicesProvider
from base_deploy_manager import BaseDeployManager

class DeployManager(BaseDeployManager):

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger('DeployManager')
        self.services = {}

    def register_service_provider(self, service_provider):
        if not isinstance(service_provider, AServicesProvider):
            self.logger.error("Service provider must be instance of AServiceProvider")
            raise Exception("Service provider must be instance of AServiceProvider")
        for service in service_provider.available_services:
            self.services[service] = service_provider

    def request_service(self, service, hosts, params=None):
        if service in self.services:
            return self.services[service].request(service, hosts, params)
        else:
            self.logger.error("Service %s has not any registered provider", service)
            raise Exception("Service %s has not any registered provider" % service)

    def wait_service(self, service, request_id):
        if service in self.services:
            return self.services[service].service(request_id)
        else:
            self.logger.error("Service %s has not any registered provider", service)
            raise Exception("Service %s has not any registered provider" % service)

        
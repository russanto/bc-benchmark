import abc

class AServicesProvider(abc.ABC):

    @property
    @abc.abstractmethod
    def available_services(self):
        pass
    
    @abc.abstractmethod
    def request(self, service, params):
        pass

    @abc.abstractmethod
    def service(self, request_id):
        pass
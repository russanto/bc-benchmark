import abc

class AHostService(abc.ABC):
    @abc.abstractmethod
    def prepare(self, hosts, params=None):
        pass
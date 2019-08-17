import abc

class ADeployManager(abc.ABC):

    @abc.abstractmethod
    def init(self, host_list):
        pass

    @abc.abstractmethod
    def start(self, conf):
        pass

    @abc.abstractmethod
    def stop(self):
        pass

    @abc.abstractmethod
    def deinit(self, host_list):
        pass
    

    
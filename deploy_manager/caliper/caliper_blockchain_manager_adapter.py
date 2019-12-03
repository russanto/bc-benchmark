import abc

class CaliperBlockchainManagerAdapter(abc.ABC):

    @abc.abstractmethod
    def init(self, base_network_file):
        pass

    @abc.abstractmethod
    def get_network_conf_file(self, host):
        pass

    @abc.abstractmethod
    def get_utility_network_conf_file(self):
        pass

    @abc.abstractproperty
    def docker_nodes(self):
        pass
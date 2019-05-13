import abc

class CaliperManagerAdapter(abc.ABC):
    def __init__(self, manager):
        self.manager = manager

    @abc.abstractclassmethod
    def init(self):
        pass

    @abc.abstractclassmethod
    def get_network_conf_file(self, host):
        pass

    @abc.abstractproperty
    def hosts(self):
        pass

    @abc.abstractproperty
    def docker_node_name(self):
        pass
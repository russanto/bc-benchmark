import abc

class AHostManagerServicePlugin(abc.ABC):

    @abc.abstractmethod
    def transform(self, response_data):
        pass
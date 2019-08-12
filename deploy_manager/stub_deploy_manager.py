import logging

from a_deploy_manager import ADeployManager

class StubDeployManager(ADeployManager):

    @property
    def id(self):
        return 'stub_dm'

    def __init__(self):
        self.logger = logging.getLogger('StubDeployManager')

    def init(self, host_list):
        self.logger.info('Init called on ' + ', '.join(host_list))

    def start(self, deploy_conf):
        self.logger.info('Start called')

    def stop(self):
        self.logger.info('Stop called')

    def deinit(self, host_list):
        self.logger.info('Deinit called on ' + ', '.join(host_list))

    

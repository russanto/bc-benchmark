import logging

import docker

from bc_orch_sdk.a_host_service import AHostService

class DockerHostService(AHostService):
    def __init__(self, registry_host):
        self.registry_host = registry_host
        self.logger = logging.getLogger('DockerHostService')
        self.docker = docker.DockerClient()

    def prepare(self, hosts, params=None):
        prepared_response = {}
        if params:
            if 'images' in params:
                prepared_images = {}
                for image in params['images']:
                    repository, colon, tag = image.partition(':')
                    if not colon:
                        tag = 'latest'
                        self.logger.warning('No tag specified for repository %s; latest tag will be used.', repository)
                    try:
                        docker_image = self.docker.images.pull(repository, tag=tag)
                        self.logger.info('Pulled image %s successfully', image)
                        _, slash, repository = repository.rpartition('/')
                        registry_repository = self.registry_host + slash + repository
                        docker_image.tag(repository=registry_repository, tag=tag)
                        self.docker.images.push(registry_repository, tag=tag)
                        prepared_images[image] = registry_repository + ':' + tag
                        self.logger.info('Pushed image %s to %s', image, prepared_images[image])
                    except docker.errors.APIError as error:
                        self.logger.error('Error pulling image %s', image)
                        self.logger.error(error)
                prepared_response['images'] = prepared_images
        prepared_hosts = {}
        for host in hosts:
            prepared_hosts[host] = {'port': 2375}
        prepared_response['connections'] = prepared_hosts
        return prepared_response
import logging
import json

import docker

from bc_orch_sdk.a_host_service import AHostService

class DockerHostService(AHostService):
    def __init__(self, registry_host='', public_registry_host=''):
        self.registry_host = registry_host
        if public_registry_host:
            self.public_registry_host = public_registry_host 
        else:
            self.public_registry_host = registry_host
        self.logger = logging.getLogger('DockerHostService')
        if not registry_host:
            self.logger.warning('Image caching with local registry not available because registry_host is empty')
        self.docker = docker.DockerClient()

    def prepare(self, hosts, params=None):
        prepared_response = {}
        if params:
            if 'images' in params:
                prepared_images = {}
                if self.registry_host:
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
                            for log_line in self.docker.images.push(registry_repository, tag=tag, stream=True):
                                log_entry = json.loads(log_line)
                                if 'error' in log_entry:
                                    self.logger.error('Error pushing image %s:%s', registry_repository, tag)
                                    self.logger.error(log_entry['error'])
                                    raise Exception('Error pushing image %s:%s' % (registry_repository, tag))
                            registry_repository = self.public_registry_host + slash + repository
                            prepared_images[image] = registry_repository + ':' + tag
                            self.logger.info('Pushed image %s to %s', image, prepared_images[image])
                        except docker.errors.ImageNotFound:
                            self.logger.error('Image %s:%s not found', repository, tag)
                            raise
                        except docker.errors.APIError as error:
                            self.logger.error('Error pulling image %s', image)
                            self.logger.error(error)
                            raise
                else:
                    for image in params['images']:
                        prepared_images[image] = image
                prepared_response['images'] = prepared_images
        prepared_hosts = {}
        for host in hosts:
            prepared_hosts[host] = {'port': 2375}
        prepared_response['connections'] = prepared_hosts
        return prepared_response
import abc
import logging
from queue import Queue
from threading import Event, Thread
import time

from .a_services_provider import AServicesProvider
from .docker_images_name_resolver import DockerImagesNameResolver

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

class BaseDeployManager(ADeployManager):

    N_DEPLOYER_THREADS = 4
    DEPLOYER_STOP_SIMBOL = "--STOP--"

    CMD_INIT = "init"
    CMD_CLEANUP = "cleanup"
    CMD_START = "start"
    CMD_STOP = "stop"
    CMD_DEINIT = "deinit"
    CMD_CLOSE = "close"

    HOST_STATE_INIZIALIZING = 1
    HOST_STATE_INITIALIZED = 2
    HOST_STATE_STARTING = 3
    HOST_STATE_STARTED = 4
    HOST_STATE_STOPPING = 5
    HOST_STATE_STOPPED = 6
    HOST_STATE_DEINITIALIZING = 7
    HOST_STATE_ERROR = -1

    AVAILABLE_CMDS = {CMD_INIT, CMD_CLEANUP, CMD_START, CMD_STOP, CMD_DEINIT}

    def __init__(self):
        self.hosts = {}
        self.executing_hosts = []
        self.logger = logging.getLogger("BaseDeployManager")
        self.dinr = DockerImagesNameResolver()
        
    def init(self, host_list):
        for host in host_list:
            if host in self.hosts:
                host_list.remove(host)
                self.logger.warning("Skipping host %s initialization because it is already in state %s", host, self.hosts[host])
            else:
                self.hosts[host] = self.HOST_STATE_INIZIALIZING
        if len(host_list) == 0:
            self.logger.error("Can't initialize an empty host list")
            raise Exception("Can't initialize an empty host list")
        self.logger.debug("Called init on " + ', '.join(host_list))
        self.__cmd('init', host_list, {})
        for host in host_list:
            if self.hosts[host] != self.HOST_STATE_ERROR:
                self.hosts[host] = self.HOST_STATE_INITIALIZED

    def start(self, conf):
        if len(self.executing_hosts) > 0:
            self.logger.error("Can't start a new execution while an old one hasn't been stopped")
            raise Exception("Can't start a new execution while an old one hasn't been stopped")
        for host, state in self.hosts.items():
            if state == self.HOST_STATE_INITIALIZED or state == self.HOST_STATE_STOPPED:
                self.executing_hosts.append(host)
                self.hosts[host] = self.HOST_STATE_STARTING
            else:
                self.logger.warning("Host %s can't be started beacuse is not ready. State: %d", host, state)
        if len(self.executing_hosts) == 0:
            self.logger.error("There isn't any initialized host that can be started")
            raise Exception("There isn't any initialized host that can be started")
        self.logger.debug("Called start on " + ', '.join(self.executing_hosts))
        self.__cmd('start', self.executing_hosts, {'conf': conf})
        for host in self.executing_hosts:
            if self.hosts[host] != self.HOST_STATE_ERROR:
                self.hosts[host] = self.HOST_STATE_STARTED
            else:
                self.executing_hosts.remove(host)
        if len(self.executing_hosts) == 0:
            self.logger.error("All host failed starting phase")
            raise Exception("All host failed starting phase")

    def stop(self):
        if len(self.executing_hosts) == 0:
            self.logger.error("Can't call stop command without any host started")
            raise Exception("Can't call stop command without any host started")
        for host in self.executing_hosts:
            self.hosts[host] = self.HOST_STATE_STOPPING
        self.logger.debug("Called stop on " + ', '.join(self.executing_hosts))
        self.__cmd('stop', self.executing_hosts, {})
        for host in self.executing_hosts:
            if self.hosts[host] != self.HOST_STATE_ERROR:
                self.hosts[host] = self.HOST_STATE_STOPPED
        self.executing_hosts.clear()
    
    def deinit(self, host_list):
        for host in host_list:
            if host not in self.hosts:
                self.logger.error("Can't deinitialize uninitialized host %s", host)
                host_list.remove(host)
            elif self.hosts[host] != self.HOST_STATE_INITIALIZED and self.hosts[host] != self.HOST_STATE_STOPPED:
                self.logger.error("Can't deinitialize host %s that is neither in state stopped nor initialized. State: %d", host, self.hosts[host])
                host_list.remove(host)
            else:
                self.hosts[host] = self.HOST_STATE_DEINITIALIZING
        self.logger.debug("Called deinit on " + ', '.join(host_list))
        self.__cmd('deinit', host_list, {})
        for host in host_list:
            if self.hosts[host] != self.HOST_STATE_ERROR:
                del self.hosts[host]

    def __cmd(self, cmd, hosts, args): #TODO: separe args namespaces
        try:
            self.__exec_stage_method(cmd, "setup", hosts, args)
        except Exception as error:
            for host in hosts:
                self.hosts[host] = self.HOST_STATE_ERROR
            self.logger.error("Error on %s setup", cmd)
            self.logger.error(error)
        deployers = []
        host_queue = Queue()
        for host in hosts:
            host_queue.put(host)
        for _ in range(min(self.N_DEPLOYER_THREADS, len(self.hosts))):
            deployer = Thread(target=self.__cmd_loop_thread, args=(cmd, host_queue, args,))
            deployer.start()
            deployers.append(deployer)
            host_queue.put(self.DEPLOYER_STOP_SIMBOL) # The stop signal for the _start_node_thread
            time.sleep(1) # TODO: this should be configurable
        for deployer in deployers:
            deployer.join()
        try:
            self.__exec_stage_method(cmd, "teardown", hosts, args)
        except Exception as error:
            for host in hosts:
                self.hosts[host] = self.HOST_STATE_ERROR
            self.logger.error("Error on %s teardown", cmd)
            self.logger.error(error)
    
    def __cmd_loop_thread(self, cmd, host_queue, args):
        host = host_queue.get()
        while host != self.DEPLOYER_STOP_SIMBOL:
            loop_args = args.copy()
            try:
                self.__exec_stage_method(cmd, "loop", host, loop_args)
            except Exception as error:
                self.hosts[host] = self.HOST_STATE_ERROR
                self.logger.error('Error in loop phase on host %s with command %s', host, cmd)
                self.logger.error(error)
            host = host_queue.get()
    
    def __exec_stage_method(self, cmd, stage, hosts, args):
        stage_method = getattr(self, "_{0}_{1}".format(cmd, stage), self.__exec_stage_not_present)
        if stage_method == self.__exec_stage_not_present:
            stage_method(cmd, stage)
        else:
            stage_method(hosts, **args)
    
    def __exec_stage_not_present(self, cmd, stage):
        # If you don't really need it, you can suppress this log entry implementing the method with pass as body.
        self.logger.debug("{1} stage for {0} command is not defined.".format(cmd, stage))

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

        
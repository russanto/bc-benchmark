import logging
from queue import Queue
from threading import Thread

# TODO: catch SIGINT/SIGKILL signals
# TODO: create events for each stage

class DeployManager:

    N_DEPLOYER_THREADS = 4
    DEPLOYER_STOP_SIMBOL = "--STOP--"

    CMD_INIT = "init"
    CMD_CLEANUP = "cleanup"
    CMD_START = "start"
    CMD_STOP = "stop"
    CMD_DEINIT = "deinit"
    CMD_CLOSE = "close"

    AVAILABLE_CMDS = {CMD_INIT, CMD_CLEANUP, CMD_START, CMD_STOP, CMD_DEINIT, CMD_CLOSE}

    def __init__(self, hosts):
        self.hosts = hosts
        self._enabled_cmds = set()
        self.cmd_queue = Queue()
        self.enable_cmd(self.CMD_INIT)
        self.logger = logging.getLogger("DeployManager")

    def enable_cmd(self, *commands):
        for cmd in commands:
            if cmd in self.AVAILABLE_CMDS:
                self._enabled_cmds.add(cmd)
            else:
                raise ValueError("{0} isn't an available command".format(cmd))
    
    def disable_cmd(self, *commands):
        for cmd in commands:
            if cmd in self.AVAILABLE_CMDS:
                try:
                    self._enabled_cmds.remove(cmd)
                except KeyError:
                    self.logger.debug("{0} was already disabled".format(cmd))
                    pass
            else:
                raise ValueError("{0} isn't an available command".format(cmd))

    def check_enabled(self, cmd, raiseException=False):
        if cmd in self._enabled_cmds:
            return True
        else:
            if raiseException:
                raise ValueError("{0} is not enabled")
            else:
                return False
        
    def init(self, **kwargs):
        self.check_enabled(self.CMD_INIT, raiseException=True)
        self.__cmd_th = Thread(target=self._main_cmd_thread)
        self.__cmd_th.start()
        self.cmd_queue.put({
            "type": self.CMD_INIT,
            "args": kwargs
        })
        self.disable_cmd(self.CMD_INIT)
        self.enable_cmd(self.CMD_START, self.CMD_CLEANUP, self.CMD_DEINIT)
        self.logger.debug("Init enqueued")

    def start(self, **kwargs):
        self.check_enabled(self.CMD_START, raiseException=True)
        self.cmd_queue.put({
            "type": self.CMD_START,
            "args": kwargs
        })
        self.disable_cmd(self.CMD_START, self.CMD_CLEANUP, self.CMD_DEINIT)
        self.enable_cmd(self.CMD_STOP)
        self.logger.debug("Start enqueued")

    def stop(self, **kwargs):
        self.check_enabled(self.CMD_STOP, raiseException=True)
        self.cmd_queue.put({
            "type": self.CMD_STOP,
            "args": kwargs
        })
        self.disable_cmd(self.CMD_STOP)
        self.enable_cmd(self.CMD_START, self.CMD_CLEANUP, self.CMD_DEINIT)
        self.logger.debug("Stop enqueued")

    def cleanup(self, **kwargs):
        self.check_enabled(self.CMD_CLEANUP, raiseException=True)
        self.cmd_queue.put({
            "type": self.CMD_CLEANUP,
            "args": kwargs
        })
        self.logger.debug("Cleanup enqueued")
    
    def deinit(self, **kwargs):
        self.check_enabled(self.CMD_DEINIT, raiseException=True)
        self.cmd_queue.put({
            "type": self.CMD_DEINIT,
            "args": kwargs
        })
        self.cmd_queue.put({"type": self.CMD_CLOSE})
        self.disable_cmd(*self.AVAILABLE_CMDS)
        self.enable_cmd(self.CMD_INIT)
        self.logger.debug("Deinit enqueued")
    
    def _main_cmd_thread(self):
        cmd = self.cmd_queue.get()
        while cmd["type"] != self.CMD_CLOSE:
            self.logger.debug("Executing %s" % cmd["type"])
            cmd_method = getattr(self, "_%s" % cmd["type"], self._cmd)
            if cmd_method == self._cmd:
                cmd_method(cmd["type"], cmd["args"])
            else:
                cmd_method(**cmd["args"])
            cmd = self.cmd_queue.get()
        self.logger.debug("Manager closed")

    def _cmd(self, cmd, args): #TODO: separe args namespaces
        self.__exec_stage_method(cmd, "setup", args)
        deployers = []
        host_queue = Queue()
        for host in self.hosts:
            host_queue.put(host)
        for _ in range(min(self.N_DEPLOYER_THREADS, len(self.hosts))):
            deployer = Thread(target=self.__cmd_loop_thread, args=(cmd, host_queue, args,))
            deployer.start()
            deployers.append(deployer)
            host_queue.put(self.DEPLOYER_STOP_SIMBOL) # The stop signal for the _start_node_thread
            # time.sleep(1) # TODO: this should be configurable
        for deployer in deployers:
            deployer.join()
        self.__exec_stage_method(cmd, "teardown", args)
    
    def __cmd_loop_thread(self, cmd, host_queue, args):
        host = host_queue.get()
        while host != self.DEPLOYER_STOP_SIMBOL:
            args["host"] = host
            self.__exec_stage_method(cmd, "loop", args)
            host = host_queue.get()

    def __exec_stage_method(self, cmd, stage, args):
        try:
            getattr(self, "_{0}_{1}".format(cmd, stage))(**args)
        except AttributeError: # If you don't really need it, you can suppress this warning implementing the method with pass as body.
            self.logger.warning("{1} stage for {0} command is not defined.".format(cmd, stage))
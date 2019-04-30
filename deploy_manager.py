import logging
from queue import Queue
from threading import Thread

# TODO: catch SIGINT/SIGKILL signals
# TODO: create events for each stage

class DeployManager:

    N_DEPLOYER_THREADS = 4

    CMD_INIT = "init"
    CMD_CLEANUP = "cleanup"
    CMD_START = "start"
    CMD_STOP = "stop"
    CMD_DEINIT = "deinit"
    CMD_CLOSE = "close"

    AVAILABLE_CMDS = {CMD_INIT, CMD_CLEANUP, CMD_START, CMD_STOP, CMD_DEINIT, CMD_CLOSE}

    def __init__(self):
        self._enabled_cmds = set()
        self.cmd_queue = Queue()
        self.__cmd_th = Thread(target=self._main_cmd_thread)
        self.__cmd_th.start()
        self.enable_cmd(self.CMD_DEINIT)
        self.logger = logging.getLogger("DeployManager")

    def enable_cmd(self, *commands):
        for cmd in commands:
            if cmd in self.AVAILABLE_CMDS:
                self._enabled_cmds.add(cmd)
            else:
                raise ValueError("{0} isn't an available command".format(cmd))

    def check_enabled(self, cmd, raiseException=False):
        if cmd in self._enabled_cmds:
            return True
        else:
            if raiseException:
                raise ValueError("Only enabled commands can be called")
            else:
                return False
        
    def init(self, **kwargs):
        self.check_enabled(self.CMD_INIT, raiseException=True)
        self.cmd_queue.put({
            "type": self.CMD_INIT,
            "args": kwargs
        })
        self.logger.info("Init enqueued")

    def start(self, **kwargs):
        self.check_enabled(self.CMD_START, raiseException=True)
        self.cmd_queue.put({
            "type": self.CMD_START,
            "args": kwargs
        })
        self.logger.info("Start enqueued")

    def stop(self, **kwargs):
        self.check_enabled(self.CMD_STOP, raiseException=True)
        self.cmd_queue.put({
            "type": self.CMD_STOP,
            "args": kwargs
        })
        self.logger.info("Stop enqueued")

    def cleanup(self, **kwargs):
        self.check_enabled(self.CMD_CLEANUP, raiseException=True)
        self.cmd_queue.put({
            "type": self.CMD_CLEANUP,
            "args": kwargs
        })
        self.logger.info("Cleanup enqueued")
    
    def deinit(self, **kwargs):
        self.check_enabled(self.CMD_DEINIT, raiseException=True)
        self.cmd_queue.put({
            "type": self.CMD_DEINIT,
            "args": kwargs
        })
        self.cmd_queue.put({"type": self.CMD_CLOSE})
        self.logger.info("Deinit enqueued")
    
    def _main_cmd_thread(self):
        cmd = self.cmd_queue.get()
        while cmd["type"] != self.CMD_CLOSE:
            if cmd["type"] == self.CMD_INIT:
                self.logger.info("Executing init")
                if cmd["args"]:
                    self._init(**cmd["args"])
                else:
                    self._init()
            elif cmd["type"] == self.CMD_START:
                self.logger.info("Executing start")
                if cmd["args"]:
                    self._start(**cmd["args"])
                else:
                    self._start()
            elif cmd["type"] == self.CMD_CLEANUP:
                self.logger.info("Executing cleanup")
                if cmd["args"]:
                    self._cleanup(**cmd["args"])
                else:
                    self._cleanup()
            elif cmd["type"] == self.CMD_STOP:
                self.logger.info("Executing stop")
                if cmd["args"]:
                    self._stop(**cmd["args"])
                else:
                    self._stop()
            elif cmd["type"] == self.CMD_DEINIT:
                self.logger.info("Executing deinit")
                if cmd["args"]:
                    self._deinit(**cmd["args"])
                else:
                    self._deinit()
            cmd = self.cmd_queue.get()
        self.logger.info("Manager closed")

    def _init(self):
        pass

    def _start(self):
        pass
    
    def _stop(self):
        pass
    
    def _cleanup(self):
        pass

    def _deinit(self):
        pass
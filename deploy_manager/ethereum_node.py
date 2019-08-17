import logging
import time

from web3 import Web3, HTTPProvider

class EthereumNode:

    TYPE_PARITY = "parity"
    TYPE_GETH = "geth"

    STATUS_STARTED = "started"
    STATUS_STOPPED = "stopped"

    WEB3_PROTOCOL = "http" # TODO Support also the other protocols
    WEB3_PORT = 8545

    def __init__(self, host, node_type):
        self.host = host
        self.web3 = Web3(HTTPProvider("%s://%s:%s" % (self.WEB3_PROTOCOL, host, self.WEB3_PORT)))
        self.enode = ""
        self.account = ("", "") # (account, password)
        self.status = self.STATUS_STOPPED
        self.node_type = node_type
        self.logger = logging.getLogger("EthereumNode(%s)" % host)

    @property
    def status(self):
        return self.__status

    @status.setter
    def status(self, status):
        if status != self.STATUS_STARTED and status != self.STATUS_STOPPED:
            raise ValueError("Allowed statuses can be only %s and %s" % (self.STATUS_STARTED, self.STATUS_STOPPED))
        else:
            self.__status = status

    @property
    def node_type(self):
        return self.__type

    @node_type.setter
    def node_type(self, node_type):
        if node_type != self.TYPE_GETH and node_type != self.TYPE_PARITY:
            raise ValueError("Allowed types can be only %s and %s" % (self.TYPE_GETH, self.TYPE_PARITY))
        else:
            self.__type = node_type

    def ready(self, wait=True, attempts=10, delay_between_attempts=1):
        a = 0
        while a < attempts:
            try:
                if self.node_type == self.TYPE_PARITY:
                    requested_enode = self.web3.parity.enode()
                else:
                    requested_enode = self.web3.admin.nodeInfo["enode"]
                self.status = self.STATUS_STARTED
                at_index = requested_enode.find("@")
                port_index = requested_enode.find(":30303")
                self.enode = requested_enode[0:at_index+1] + self.host + requested_enode[port_index:]
                return True
            except Exception as e: #TODO should see if it is worth to continue basing on which exception is raised
                if wait:
                    a += 1
                    time.sleep(delay_between_attempts)
                    self.logger.debug(e)
                else:
                    break
        self.status = self.STATUS_STOPPED
        return False
from fabric import Connection
from ssh_node_manager import NodeManager
import ipaddress

class NodeManagerHosts(NodeManager):
    def __init__(self, hosts_filename, conf_filename=""):
        self._parse_conf(conf_filename)
        for line in open(hosts_filename):
            stripped = line.strip()
            self.nodes_ssh_connections.append(Connection(
                        host=stripped,
                        user=self.ssh_username,
                        inline_ssh_env=True
            ))
            self.nodes_ips.append(stripped)
            print("Read: " + stripped + "<--")
        
if __name__ == "__main__":
    import sys, time

    seconds = int(sys.argv[1])
    hosts_filename = sys.argv[2]

    print("-----> Performing a clean run for %d seconds" % seconds)

    manager = NodeManagerHosts(hosts_filename)
    manager.clean()
    manager.create()
    time.sleep(seconds)
    manager.stop()
    


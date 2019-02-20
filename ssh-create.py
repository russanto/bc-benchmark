#!/Library/Frameworks/Python.framework/Versions/3.6/bin/python3

from ssh_node_manager import NodeManager
import sys

manager = NodeManager(sys.argv[1], sys.argv[2], sys.argv[3])
manager.create()


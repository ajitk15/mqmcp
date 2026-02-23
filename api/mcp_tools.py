import os
import sys
from langchain_core.tools import tool

# Ensure the root project directory is in the path so we can import server.mqmcpserver
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the robust, fully-featured original MCP Tools
from server.mqmcpserver import (
    search_qmgr_dump as _search_qmgr_dump,
    runmqsc as _runmqsc,
    dspmq as _dspmq,
    dspmqver as _dspmqver
)

@tool
def search_qmgr_dump(search_string: str, object_type: str | None = None) -> str:
    """Search QM dump for a string (Queue Name, Channel Name) to find which Queue Manager hosts an object.
    You MUST run this tool first if you do not know which Queue Manager hosts a specific queue or channel.
    
    Args:
        search_string: String to search (e.g., 'QL.IN.APP1')
        object_type: Optional filter (e.g., 'QLOCAL', 'QUEUES', 'CHANNEL')
    """
    return _search_qmgr_dump(search_string, object_type)

@tool
async def dspmq(qmgr_name: str | None = None) -> str:
    """List all IBM MQ queue managers and their status.
    
    Args:
        qmgr_name: Optional queue manager name to list all QMs running on its host.
    """
    return await _dspmq(qmgr_name)

@tool
async def dspmqver(qmgr_name: str | None = None) -> str:
    """Display IBM MQ version and installation information.
    
    Args:
        qmgr_name: Optional queue manager name to check the installation details of its host.
    """
    return await _dspmqver(qmgr_name)

@tool
async def runmqsc(qmgr_name: str, mqsc_command: str) -> str:
    """Execute a raw MQSC command against a queue manager.
    You must provide BOTH the queue manager name and the MQSC command. 
    Use search_qmgr_dump first if you don't know the queue manager name.
    
    Args:
        qmgr_name: The name of the queue manager.
        mqsc_command: The raw MQSC command (e.g., 'DISPLAY QLOCAL(QL.IN.APP1) CURDEPTH')
    """
    return await _runmqsc(qmgr_name, mqsc_command)

# Provide all tools as a list for easy binding
MQ_TOOLS = [search_qmgr_dump, dspmq, dspmqver, runmqsc]

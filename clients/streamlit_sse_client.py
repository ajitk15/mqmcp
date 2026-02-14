import streamlit as st
import asyncio
import requests
from mcp import ClientSession
from mcp.client.sse import sse_client
from dotenv import load_dotenv

# Load environment variables
# Load environment variables
load_dotenv()

# Cleanup handler for graceful shutdown
def cleanup_on_exit():
    """Cleanup resources on exit - non-blocking"""
    import threading
    
    def do_cleanup():
        try:
            if hasattr(st, 'session_state'):
                for key in list(st.session_state.keys()):
                    # Clear session state objects if needed
                    pass
        except:
            pass
    
    # Run cleanup in background thread (daemon)
    t = threading.Thread(target=do_cleanup, daemon=True)
    t.start()
    t.join(timeout=1)

import atexit
atexit.register(cleanup_on_exit)

# Set up page config
st.set_page_config(page_title="IBM MQ MCP Client (SSE)", page_icon="⚡", layout="wide")

# Validates and sets the server URL and connection status
if "server_url" not in st.session_state:
    st.session_state.server_url = "http://127.0.0.1:8000/sse"
if "connection_status" not in st.session_state:
    st.session_state.connection_status = "unknown"

# Define available tools/operations
OPERATIONS = {
    "Select an operation...": {},
    "--- Infrastructure ---": {"header": True},
    "List Queue Managers": {
        "tool": "dspmq",
        "args": {},
        "description": "List all IBM MQ queue managers and their status."
    },
    "Check MQ Version": {
        "tool": "dspmqver",
        "args": {},
        "description": "Display IBM MQ version and installation details."
    },
    "Show Queue Manager Properties": {
        "tool": "runmqsc",
        "args": {"qmgr_name": "Queue Manager Name"},
        "fixed_args": {"mqsc_command": "DISPLAY QMGR"},
        "description": "View full configuration and properties of a specific QMGR."
    },
    "--- Queues ---": {"header": True},
    "List all Queues": {
        "tool": "runmqsc",
        "args": {"qmgr_name": "Queue Manager Name"},
        "fixed_args": {"mqsc_command": "DISPLAY QLOCAL(*)"},
        "description": "Get a list of all local queues defined on the queue manager."
    },
    "Check Queue Depth": {
        "smart_workflow": "check_depth",
        "tool": "runmqsc", # Placeholder, logic handled in smart_workflow
        "args": {"queue_name": "Queue Name"},
        "description": "Auto-locate queue and check current number of messages (CURDEPTH)."
    },
    "Check Queue Status": {
        "smart_workflow": "check_status",
        "tool": "runmqsc",
        "args": {"queue_name": "Queue Name"},
        "description": "Auto-locate queue and check open input/output counts (QSTATUS)."
    },
    "--- Channels & Listeners ---": {"header": True},
    "Show Channels": {
        "tool": "runmqsc",
        "args": {"qmgr_name": "Queue Manager Name"},
        "fixed_args": {"mqsc_command": "DISPLAY CHANNEL(*)"},
        "description": "Display all channel definitions on the queue manager."
    },
    "Check Channel Status": {
        "tool": "runmqsc",
        "args": {"qmgr_name": "Queue Manager Name", "channel_name": "Channel Name"},
        "mqsc_template": "DISPLAY CHSTATUS({channel_name})",
        "description": "Check if a specific channel is RUNNING, BINDING, or INACTIVE."
    },
     "--- Custom ---": {"header": True},
    "Run Custom MQSC Command": {
        "tool": "runmqsc",
        "args": {"qmgr_name": "Queue Manager Name", "mqsc_command": "MQSC Command"},
        "description": "Execute a raw MQSC command against a queue manager."
    },
    "--- Discovery ---": {"header": True},
    "Find a Queue/Channel": {
        "tool": "search_qmgr_dump",
        "args": {"search_string": "Search Query (e.g. queue name)"},
        "description": "Search across all Queue Managers to find where a Queue or Channel exists."
    }
}

async def call_mcp_tool(server_url, tool_name, arguments):
    """Connect to SSE and call a specific tool"""
    try:
        async with sse_client(server_url) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                if result.content:
                    return result.content[0].text
                return "✅ Command executed (No output)"
    except Exception as e:
        # Handle ExceptionGroups (TaskGroup errors)
        if hasattr(e, 'exceptions'):
            error_msgs = []
            for ex in e.exceptions:
                error_msgs.append(str(ex))
            return f"❌ Error: {'; '.join(error_msgs)}"
        return f"❌ Error: {str(e)}"

async def check_connection(server_url):
    """Check if we can connect to the SSE endpoint"""
    try:
        # Just try to initialize a session to verify connection
        async with sse_client(server_url) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                return True
    except Exception as e:
        print(f"Connection check failed: {e}")
        return False

def extract_qmgrs_from_search(search_output: str) -> list:
    """Parse search_qmgr_dump output to find queue manager names"""
    import re
    # Look for lines like "Queue Manager: QM1 | ..."
    qmgrs = set()
    for line in search_output.split('\n'):
        match = re.search(r'Queue Manager:\s*([A-Z0-9_\.]+)', line, re.IGNORECASE)
        if match:
            qmgrs.add(match.group(1).strip())
    return list(qmgrs)

# CUSTOM CSS
st.markdown("""
<style>
    .stApp { background-color: #ffffff; color: #333333; }
    .top-nav {
        position: fixed; top: 0; left: 0; width: 100%;
        background-color: #4C8C2B; color: white;
        padding: 12px 25px; z-index: 1000;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        display: flex; justify-content: space-between; align-items: center;
    }
    .top-nav h2 { color: white !important; margin: 0 !important; font-size: 20px !important; }
    .block-container { padding-top: 5rem !important; padding-bottom: 5rem !important; }
    .stButton > button {
        background-color: #76BC21 !important; color: white !important;
        border-radius: 6px !important; border: none !important;
        padding: 10px 24px !important; font-weight: 600 !important;
    }
    .stButton > button:hover { background-color: #4C8C2B !important; }
    /* Hide Streamlit default components */
    header {visibility: hidden; height: 0px !important;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .fixed-footer {
        position: fixed; left: 0; bottom: 0; width: 100%;
        background-color: #ffffff; color: #888888;
        text-align: center; padding: 8px 0; font-size: 11px;
        border-top: 1px solid #eeeeee; z-index: 999;
    }
</style>
""", unsafe_allow_html=True)

# Top Nav
st.markdown(f"""
<div class="top-nav">
    <div><h2 style="display: inline; margin-right: 10px;">⚡ IBM MQ MCP Client (Direct)</h2></div>
    <div style="font-weight: 600; font-size: 14px; color: white;"></div>
</div>
<div class="fixed-footer">v2.1 Direct SSE Client | No LLM | Server: {st.session_state.server_url}</div>
""", unsafe_allow_html=True)


# --- Connection Settings (Moved to Main Page) ---
with st.expander("🔌 Connection Settings", expanded=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        server_url = st.text_input("MCP Endpoint URL", value=st.session_state.server_url)
        if server_url != st.session_state.server_url:
            st.session_state.server_url = server_url
            st.rerun()
            
    with col2:
        st.markdown("<br>", unsafe_allow_html=True) # Spacer
        if st.button("Check Connectivity"):
            with st.spinner("Connecting..."):
                is_connected = asyncio.run(check_connection(st.session_state.server_url))
                if is_connected:
                    st.session_state.connection_status = "connected"
                    st.success("Connected!")
                else:
                    st.session_state.connection_status = "error"
                    st.error("Connection Failed")

# Main Operation Selection
st.markdown("""
<div style="background-color: #e8f5e9; border-left: 5px solid #4C8C2B; padding: 15px; border-radius: 8px; margin-bottom: 25px;">
    <span style="color: #2e7d32; font-weight: 600;">Direct Control Mode:</span> 
    <span style="color: #555555;">Execute MCP tools directly without AI interpretation.</span>
</div>
""", unsafe_allow_html=True)

valid_ops = [k for k, v in OPERATIONS.items() if not v.get("header")]
choice = st.selectbox("Select Tool / Operation", valid_ops)

if choice and choice != "Select an operation...":
    op_config = OPERATIONS[choice]
    st.info(f"💡 {op_config['description']}")
    
    # Dynamic Inputs
    tool_args = {}
    if op_config.get("args"):
        # We need to collect inputs
        cols = st.columns(len(op_config["args"]))
        for i, (arg_key, label) in enumerate(op_config["args"].items()):
            with cols[i]:
                tool_args[arg_key] = st.text_input(label, key=f"{choice}_{arg_key}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("🚀 Execute Command", type="primary"):
        # Check params
        missing_params = [k for k, v in tool_args.items() if not v]
        if missing_params:
            st.error(f"⚠️ Missing required parameters: {', '.join(missing_params)}")
        else:
            # Prepare final arguments
            final_args = tool_args.copy()
            
            # Handle fixed args (merged in)
            if "fixed_args" in op_config:
                final_args.update(op_config["fixed_args"])
            
            # Handle templates (e.g. constructing mqsc_command from parts)
            if "mqsc_template" in op_config:
                try:
                    cmd = op_config["mqsc_template"].format(**tool_args)
                    final_args["mqsc_command"] = cmd
                    valid_tool_keys = ["qmgr_name", "mqsc_command"]
                    final_args = {k: v for k, v in final_args.items() if k in valid_tool_keys}
                    
                except KeyError as e:
                    st.error(f"Template error: Missing {e}")
                    st.stop()
            
            # --- Smart Workflow Execution ---
            if "smart_workflow" in op_config:
                workflow_type = op_config["smart_workflow"]
                
                if workflow_type in ["check_depth", "check_status"]:
                    queue_name = tool_args.get("queue_name")
                    command_template = "DISPLAY QLOCAL({queue}) CURDEPTH" if workflow_type == "check_depth" else "DISPLAY QSTATUS({queue}) TYPE(QUEUE) ALL"
                    
                    with st.spinner(f"🔍 Searching for {queue_name}..."):
                        # Step 1: Search
                        st.info(f"**Tool:** `search_qmgr_dump` | **Args:** `{{'search_string': '{queue_name}'}}`")
                        search_res = asyncio.run(call_mcp_tool(st.session_state.server_url, "search_qmgr_dump", {"search_string": queue_name}))
                        
                        # Step 2: Parse QMGRs
                        qmgrs = extract_qmgrs_from_search(search_res)
                        
                        if not qmgrs:
                            st.warning(f"Could not find queue '{queue_name}' on any known queue manager.")
                            st.text(search_res) # Show search output for debugging
                        else:
                            st.success(f"Found on {len(qmgrs)} Queue Manager(s): {', '.join(qmgrs)}")
                            
                            # Step 3: Check Depth/Status on each
                            for qmgr in qmgrs:
                                with st.status(f"Checking {qmgr}...", expanded=True):
                                    cmd = command_template.format(queue=queue_name)
                                    st.write(f"**Tool:** `runmqsc`")
                                    st.code(f"MQSC: {cmd}", language="properties")
                                    res = asyncio.run(call_mcp_tool(st.session_state.server_url, "runmqsc", {
                                        "qmgr_name": qmgr,
                                        "mqsc_command": cmd
                                    }))
                                    st.code(res, language="text")
                st.stop() # End execution after smart workflow

            # Execute standard tool

            # Execute
            with st.spinner(f"Running {op_config['tool']}..."):
                st.info(f"**Tool:** `{op_config['tool']}`\n\n**Args:** `{final_args}`")
                result = asyncio.run(call_mcp_tool(st.session_state.server_url, op_config["tool"], final_args))
                
                if "❌ Error" in result:
                    st.error(result)
                else:
                    st.success("Command Executed Successfully")
                    st.code(result, language="text")

# Add a new section to display qmgr_dump.csv data
st.sidebar.header("Queue Manager Data")
if st.sidebar.button("Load Queue Manager Data"):
    try:
        response = requests.get("http://127.0.0.1:8001/qmgr_dump")
        if response.status_code == 200:
            data = response.json().get("result", [])
            if data:
                st.write("### Queue Manager Data")
                st.dataframe(data)
            else:
                st.warning("No data found in qmgr_dump.csv.")
        else:
            st.error(f"Failed to load data: {response.status_code}")
    except Exception as e:
        st.error(f"Error: {str(e)}")

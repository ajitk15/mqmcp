import streamlit as st
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client
from dotenv import load_dotenv
from tool_logger import get_rest_api_url, should_show_logging

# Load environment variables
load_dotenv()

# Set up page config
st.set_page_config(page_title="IBM MQ MCP Client (SSE)", page_icon="⚡", layout="wide")

# Validates and sets the server URL and connection status
if "server_url" not in st.session_state:
    st.session_state.server_url = "http://127.0.0.1:5000/sse"
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
        "tool": "runmqsc",  # Placeholder, logic handled in smart_workflow
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
            error_msgs = [str(ex) for ex in e.exceptions]
            return f"❌ Error: {'; '.join(error_msgs)}"
        return f"❌ Error: {str(e)}"


async def check_connection(server_url):
    """Check if we can connect to the SSE endpoint"""
    try:
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
    qmgrs = set()
    for line in search_output.split('\n'):
        match = re.search(r'Queue Manager:\s*([A-Z0-9_\.]+)', line, re.IGNORECASE)
        if match:
            qmgrs.add(match.group(1).strip())
    return list(qmgrs)


def render_tool_call(tool_name: str, args: dict, result: str, expanded: bool = True, label: str = ""):
    """Render a standardised 'Tool Called' expander block.
    
    tool_name  - actual MCP tool name, used for REST API URL lookup
    label      - optional display title override (e.g. 'runmqsc on MQQMGR1')
    """
    display = label or tool_name
    with st.expander(f"🔧 Tool Called: `{display}`", expanded=expanded):
        st.markdown(f"**Tool:** `{tool_name}`")
        st.json(args)
        if should_show_logging():
            st.code(get_rest_api_url(tool_name, args), language="text")
        st.markdown("**Output:**")
        if "❌ Error" in result:
            st.error(result)
        else:
            st.code(result, language="text")


def detect_queue_type(queue_name: str) -> tuple[str, str, str]:
    """
    Return (queue_type_label, icon, mqsc_command_template) for the given queue name.
    Queue name should already be normalised (stripped + uppercased).
    """
    if queue_name.startswith("QR"):
        return (
            "Remote Queue", "🌐",
            "DISPLAY QREMOTE({queue})"
        )
    elif queue_name.startswith("QA"):
        return (
            "Alias Queue", "🔀",
            "DISPLAY QALIAS({queue})"   # reveals TARGET
        )
    else:
        label = "Local Queue" if queue_name.startswith("QL") else "Queue"
        return (
            label, "📦",
            "DISPLAY QLOCAL({queue}) CURDEPTH"
        )


# ---------------------------------------------------------------------------
# CUSTOM CSS
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Connection Settings
# ---------------------------------------------------------------------------

with st.expander("🔌 Connection Settings", expanded=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        server_url = st.text_input("MCP Endpoint URL", value=st.session_state.server_url)
        if server_url != st.session_state.server_url:
            st.session_state.server_url = server_url
            st.rerun()
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
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
        cols = st.columns(len(op_config["args"]))
        for i, (arg_key, label) in enumerate(op_config["args"].items()):
            with cols[i]:
                tool_args[arg_key] = st.text_input(label, key=f"{choice}_{arg_key}")

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("🚀 Execute Command", type="primary"):
        # Validate required params
        missing_params = [k for k, v in tool_args.items() if not v]
        if missing_params:
            st.error(f"⚠️ Missing required parameters: {', '.join(missing_params)}")
        else:
            # Prepare final arguments
            final_args = tool_args.copy()

            # Merge fixed args
            if "fixed_args" in op_config:
                final_args.update(op_config["fixed_args"])

            # Apply mqsc_template (constructs mqsc_command from user inputs)
            if "mqsc_template" in op_config:
                try:
                    cmd = op_config["mqsc_template"].format(**tool_args)
                    final_args["mqsc_command"] = cmd
                    final_args = {k: v for k, v in final_args.items() if k in ("qmgr_name", "mqsc_command")}
                except KeyError as e:
                    st.error(f"Template error: Missing {e}")
                    st.stop()

            # --- Smart Workflow Execution ---
            if "smart_workflow" in op_config:
                workflow_type = op_config["smart_workflow"]

                if workflow_type in ["check_depth", "check_status"]:
                    # Normalise: strip whitespace and uppercase to make prefix detection reliable
                    queue_name = tool_args.get("queue_name", "").strip().upper()

                    if workflow_type == "check_depth":
                        queue_type, queue_type_icon, command_template = detect_queue_type(queue_name)
                        st.info(f"{queue_type_icon} **Queue Type Detected:** `{queue_name}` is identified as a **{queue_type}** based on its prefix.")

                        # Remote queues don't store CURDEPTH — explain the limitation
                        if queue_type == "Remote Queue":
                            st.warning(
                                "ℹ️ **Note:** Remote queues don't hold messages locally. "
                                "`DISPLAY QREMOTE` shows routing info (RQMNAME, RNAME, XMITQ). "
                                "To see actual depth, check the transmission queue (XMITQ) on this QMGR, "
                                "or query CURDEPTH on the target queue manager."
                            )
                    else:
                        command_template = "DISPLAY QSTATUS({queue}) TYPE(QUEUE) ALL"

                    with st.spinner(f"🔍 Searching for {queue_name}..."):
                        # Step 1: Search
                        search_args = {"search_string": queue_name}
                        search_res = asyncio.run(call_mcp_tool(st.session_state.server_url, "search_qmgr_dump", search_args))
                        render_tool_call("search_qmgr_dump", search_args, search_res)

                        # Step 2: Parse QMGRs
                        qmgrs = extract_qmgrs_from_search(search_res)

                        if not qmgrs:
                            st.warning(f"Could not find queue '{queue_name}' on any known queue manager.")
                        else:
                            st.success(f"Found on {len(qmgrs)} Queue Manager(s): {', '.join(qmgrs)}")

                            # Step 3: Run MQSC on each QMGR
                            for qmgr in qmgrs:
                                cmd = command_template.format(queue=queue_name)
                                runmqsc_args = {"qmgr_name": qmgr, "mqsc_command": cmd}
                                with st.spinner(f"Running runmqsc on {qmgr}..."):
                                    res = asyncio.run(call_mcp_tool(st.session_state.server_url, "runmqsc", runmqsc_args))
                                render_tool_call("runmqsc", runmqsc_args, res, label=f"runmqsc on {qmgr}")

                st.stop()  # End execution after smart workflow

            # Standard tool execution
            with st.spinner(f"Running {op_config['tool']}..."):
                result = asyncio.run(call_mcp_tool(st.session_state.server_url, op_config["tool"], final_args))

            render_tool_call(op_config["tool"], final_args, result)
            if "❌ Error" not in result:
                st.success("Command Executed Successfully")

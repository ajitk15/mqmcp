import streamlit as st
import asyncio
import os
from dynamic_client import DynamicMQClient

# Set up page config
st.set_page_config(page_title="IBM MQ Guided Assistant", page_icon="🛠️", layout="wide")

# Custom CSS for a professional light theme
st.markdown("""
<style>
    .stApp {
        background-color: #f1f5f9;
        color: #1e293b;
    }
    [data-testid="stChatMessage"] {
        border-radius: 12px;
        margin-bottom: 8px;
        padding: 4px 12px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    [data-testid="stChatMessage"] p, 
    [data-testid="stChatMessage"] li, 
    [data-testid="stChatMessage"] div,
    [data-testid="stChatMessage"] span {
        font-size: 14px !important;
        line-height: 1.4 !important;
    }
    /* Compact the horizontal rules */
    [data-testid="stChatMessage"] hr {
        margin: 8px 0 !important;
        opacity: 0.2;
    }
    .operation-card {
        background-color: white;
        padding: 24px;
        border-radius: 16px;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        margin-bottom: 24px;
        border: 1px solid #e2e8f0;
    }
    .input-label {
        font-weight: 600;
        font-size: 13px;
        color: #334155;
        margin-bottom: 6px;
    }
    .stTextInput input {
        border-radius: 8px;
        border: 1px solid #cbd5e1;
        padding: 10px;
    }
    .stSelectbox div[data-baseweb="select"] {
        border-radius: 12px;
        border: 1px solid #cbd5e1;
    }
</style>
""", unsafe_allow_html=True)

st.title("🛠️ IBM MQ Guided Assistant")

# Define the server script path
script_dir = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(script_dir, "..", "server", "mqmcpserver.py")

async def run_mcp_command(prompt):
    """Execution logic from basic client"""
    client = DynamicMQClient(server_script=SERVER_SCRIPT)
    try:
        await client.connect()
        import builtins
        original_input = builtins.input
        builtins.input = lambda _: ""
        try:
            response = await client.handle_user_input(prompt)
            return response
        finally:
            builtins.input = original_input
            await client.disconnect()
    except Exception as e:
        return f"❌ Error: {str(e)}"

# Define Expanded Predefined Questions
QUESTIONS = {
    "Select an operation...": {},
    "--- Infrastructure ---": {"header": True, "icon": "🏢"},
    "List all Queue Managers": {
        "prompt": "list all queue managers",
        "inputs": [],
        "description": "Show all MQ queue managers on this host and their status."
    },
    "Check MQ Version": {
        "prompt": "dspmqver",
        "inputs": [],
        "description": "Display IBM MQ version, build level, and installation path details."
    },
    "Show Queue Manager Properties": {
        "prompt": "display qmgr for {qmgr}",
        "inputs": ["qmgr"],
        "description": "View full configuration and properties of a specific QMGR."
    },
    "--- Queues ---": {"header": True, "icon": "📥"},
    "List all Queues on a QMGR": {
        "prompt": "list all queues on {qmgr}",
        "inputs": ["qmgr"],
        "description": "Get a list of all local queues defined on the queue manager."
    },
    "Check Queue Depth": {
        "prompt": "what is the depth of {queue} on {qmgr}",
        "inputs": ["qmgr", "queue"],
        "description": "Check current number of messages (CURDEPTH) on a queue."
    },
    "Check Queue Status": {
        "prompt": "status of queue {queue} on {qmgr}",
        "inputs": ["qmgr", "queue"],
        "description": "Check open input/output counts and status."
    },
    "--- Channels & Listeners ---": {"header": True, "icon": "📡"},
    "Show Channels on a QMGR": {
        "prompt": "show channels on {qmgr}",
        "inputs": ["qmgr"],
        "description": "Display all channel definitions on the queue manager."
    },
    "Check Channel Status": {
        "prompt": "channel status of {channel} on {qmgr}",
        "inputs": ["qmgr", "channel"],
        "description": "Check if a specific channel is RUNNING, BINDING, or INACTIVE."
    },
    "Show Listener Status": {
        "prompt": "show listeners on {qmgr}",
        "inputs": ["qmgr"],
        "description": "Check the status of listeners (TCP/IP ports)."
    }
}

# Mapping of headers for the selector
selector_options = []
for k, v in QUESTIONS.items():
    if v.get("header"):
        selector_options.append(f"{v['icon']} {k.strip('- ')}")
    else:
        selector_options.append(k)

valid_choices = [k for k, v in QUESTIONS.items() if not v.get("header")]

# Main UI Logic
col_main, col_spacer = st.columns([2, 1])

with col_main:
    with st.container(border=True):
        choice = st.selectbox("What task would you like to perform?", valid_choices, help="Select an MQ task from the list")
        
        if choice != "Select an operation...":
            config = QUESTIONS[choice]
            st.info(f"💡 **Description:** {config['description']}")
            
            params = {}
            # Dynamic Input Fields in a neat container
            if "inputs" in config and config["inputs"]:
                st.markdown('<p class="input-label">Required Parameters</p>', unsafe_allow_html=True)
                input_container = st.container(border=True)
                with input_container:
                    cols = st.columns(len(config["inputs"]))
                    for i, input_key in enumerate(config["inputs"]):
                        with cols[i]:
                            if input_key == "qmgr":
                                label = "Queue Manager"
                                placeholder = "e.g. QM1"
                            elif input_key == "queue":
                                label = "Queue Name"
                                placeholder = "e.g. APP.QUEUE"
                            elif input_key == "channel":
                                label = "Channel Name"
                                placeholder = "e.g. TO.SERVER"
                            else:
                                label = input_key.capitalize()
                                placeholder = ""
                            
                            params[input_key] = st.text_input(label, placeholder=placeholder, key=f"in_{input_key}_{choice}")

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🚀 Execute MQ Command", type="primary", use_container_width=True):
                if "inputs" in config and all(params.get(k) for k in config["inputs"]):
                    final_prompt = config["prompt"]
                    if params:
                        final_prompt = final_prompt.format(**params)
                    
                    with st.status("Executing Command...", expanded=True) as status:
                        st.write(f"Connecting to IBM MQ...")
                        response = asyncio.run(run_mcp_command(final_prompt))
                        status.update(label="Run Complete!", state="complete", expanded=False)
                    
                    st.chat_message("assistant").markdown(response)
                elif not config.get("inputs"):
                    with st.chat_message("assistant"):
                        with st.spinner("Executing..."):
                            response = asyncio.run(run_mcp_command(config["prompt"]))
                            st.markdown(response)
                else:
                    st.error("⚠️ Please provide all required parameters above.")

# Sidebar info
with st.sidebar:
    st.header("⚡ System Quick Actions")
    if st.button("🔍 Connection Test", use_container_width=True):
        with st.spinner("Checking..."):
            res = asyncio.run(run_mcp_command("dspmq"))
            if "❌" in res:
                st.error("Server Unreachable")
            else:
                st.success("Server Online")
    
    st.divider()
    st.markdown("### 🛠️ Environment")
    st.code(f"Server: {os.path.basename(SERVER_SCRIPT)}", language="text")
    st.markdown("---")
    st.caption("v1.2 Guided MQ Client")

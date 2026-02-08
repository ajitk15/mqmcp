import streamlit as st
import asyncio
import os
from dynamic_client import DynamicMQClient

# Set up page config
st.set_page_config(page_title="IBM MQ Guided Assistant", page_icon="🛠️", layout="wide")

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

# Connectivity Check logic
mcp_status_html = '<span style="color: #ffcccc;">🔘 Checking...</span>'
try:
    res = asyncio.run(run_mcp_command("dspmq"))
    if "❌" in res:
        mcp_status_html = '<span style="color: #ff9999;">🔴 MCP Offline</span>'
    else:
        mcp_status_html = '<span style="color: #ccffcc;">🟢 MCP Online</span>'
except:
    mcp_status_html = '<span style="color: #ff9999;">🔴 MCP Error</span>'

# CUSTOM CSS & GLOBAL UI COMPONENTS
st.markdown(f"""
<style>
    .stApp {{
        background-color: #ffffff;
        color: #333333;
    }}
    
    /* Global Fixed Top Bar */
    .top-nav {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        background-color: #4C8C2B;
        color: white;
        padding: 12px 25px;
        z-index: 1000;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }}
    .top-nav h2 {{
        color: white !important;
        margin: 0 !important;
        font-size: 20px !important;
    }}

    /* Layout adjustments for fixed header */
    .block-container {{
        padding-top: 5rem !important;
        padding-bottom: 5rem !important;
    }}

    /* Primary brand colors */
    h3 {{
        color: #4C8C2B !important;
        font-weight: 700 !important;
    }}

    /* Primary Button color */
    .stButton > button {{
        background-color: #76BC21 !important;
        color: white !important;
        border-radius: 25px !important;
        border: none !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
    }}
    .stButton > button:hover {{
        background-color: #4C8C2B !important;
    }}

    /* Hide Streamlit default components */
    header {{visibility: hidden; height: 0px !important;}}
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    .stApp > header {{display: none !important;}}

    /* Fixed Footer */
    .fixed-footer {{
        position: fixed;
        left: 0;
        bottom: 0;
        width: 100%;
        background-color: #ffffff;
        color: #888888;
        text-align: center;
        padding: 8px 0;
        font-size: 11px;
        border-top: 1px solid #eeeeee;
        z-index: 999;
    }}
</style>

<div class="top-nav">
    <div>
        <h2 style="display: inline; margin-right: 10px;">🛠️ IBM MQ Guided Assistant</h2>
    </div>
    <div style="font-weight: 600; font-size: 14px;">
        {mcp_status_html}
    </div>
</div>

<div class="fixed-footer">
    v1.2 Guided MQ Client | Server: mqmcpserver.py
</div>
""", unsafe_allow_html=True)

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

valid_choices = [k for k, v in QUESTIONS.items() if not v.get("header")]

# Main UI Logic
with st.container(border=True):
    choice = st.selectbox("What task would you like to perform?", valid_choices, help="Select an MQ task from the list")
    
    if choice != "Select an operation...":
        config = QUESTIONS[choice]
        st.info(f"💡 **Description:** {config['description']}")
        
        params = {}
        # Dynamic Input Fields
        if "inputs" in config and config["inputs"]:
            st.markdown('**Required Parameters**')
            cols = st.columns(len(config["inputs"]))
            for i, input_key in enumerate(config["inputs"]):
                with cols[i]:
                    label = input_key.replace("qmgr", "Queue Manager").replace("queue", "Queue").replace("channel", "Channel").capitalize()
                    params[input_key] = st.text_input(label, key=f"in_{input_key}_{choice}")

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

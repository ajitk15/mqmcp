import streamlit as st
import asyncio
import os
import sys
from dynamic_client import DynamicMQClient
from tool_logger import display_tool_call

# Set up page config
st.set_page_config(page_title="IBM MQ Assistant", page_icon="🤖", layout="wide")

# Define the server script path
script_dir = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(script_dir, "..", "server", "mqmcpserver.py")

async def run_mcp_command(prompt, show_tool_call=None):
    """Execution logic from basic client"""
    client = DynamicMQClient(server_script=SERVER_SCRIPT)
    try:
        await client.connect()
        import builtins
        original_input = builtins.input
        builtins.input = lambda _: ""
        try:
            # Monkey-patch the client's _log_tool_call to also display in UI
            if show_tool_call:
                original_log = client._log_tool_call
                def new_log(tool_name, args):
                    original_log(tool_name, args)
                    show_tool_call(tool_name, args)
                client._log_tool_call = new_log
            
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
        padding-bottom: 6rem !important;
    }}

    [data-testid="stChatMessage"] {{
        border-radius: 12px;
        margin-bottom: 8px;
        padding: 4px 12px !important;
        background-color: #f7f9f7 !important;
        border: 1px solid #e1e8e1;
    }}

    /* Pulsing animation for loading */
    @keyframes pulse {{
        0% {{ opacity: 0.6; transform: scale(0.98); }}
        50% {{ opacity: 1; transform: scale(1.01); }}
        100% {{ opacity: 0.6; transform: scale(0.98); }}
    }}
    .thinking-box {{
        background: #ffffff;
        border: 1px solid #e1e8e1;
        border-radius: 10px;
        padding: 12px 20px;
        display: flex;
        align-items: center;
        gap: 12px;
        animation: pulse 2s infinite ease-in-out;
        width: fit-content;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }}
    .thinking-dot {{
        width: 8px;
        height: 8px;
        background: #76BC21;
        border-radius: 50%;
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
        <h2 style="display: inline; margin-right: 10px;">🤖 IBM MQ Assistant</h2>
    </div>
    <div style="font-weight: 600; font-size: 14px;">
        {mcp_status_html}
    </div>
</div>

<div class="fixed-footer">
    v1.2 Basic MQ Client | Server: mqmcpserver.py
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="background-color: #f1f8e9; border-left: 5px solid #76BC21; padding: 15px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <span style="color: #2e7d32; font-weight: 600;">Basic Assistant:</span> 
    <span style="color: #555555;">Fast, predictable, and understands natural language through intelligent pattern matching.</span>
</div>
""", unsafe_allow_html=True)

# Chat interface initialization
if "messages_basic" not in st.session_state:
    st.session_state.messages_basic = [
        {"role": "assistant", "content": "I'm your IBM MQ assistant. I'm connected and ready! Try asking 'list queue managers' or 'what is the depth of MY.QUEUE on QM1?'"}
    ]

# Display chat messages
for message in st.session_state.messages_basic:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
if prompt := st.chat_input("Ask something about IBM MQ..."):
    # Add user message to chat history
    st.session_state.messages_basic.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("""
            <div class="thinking-box">
                <div class="thinking-dot" style="animation-delay: 0s"></div>
                <div class="thinking-dot" style="animation-delay: 0.2s"></div>
                <div class="thinking-dot" style="animation-delay: 0.4s"></div>
                <span>Assistant is processing your request...</span>
            </div>
        """, unsafe_allow_html=True)
        
        # Execute the command with tool logging callback
        full_response = asyncio.run(run_mcp_command(prompt, show_tool_call=display_tool_call))
        message_placeholder.markdown(full_response)
    
    # Add assistant response to chat history
    st.session_state.messages_basic.append({"role": "assistant", "content": full_response})

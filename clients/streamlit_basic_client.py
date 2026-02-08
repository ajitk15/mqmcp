import streamlit as st
import asyncio
import os
import sys
from dynamic_client import DynamicMQClient

# Set up page config
st.set_page_config(page_title="IBM MQ Assistant", page_icon="🤖", layout="wide")

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
    /* Compact the horizontal rules (the --- separators) */
    [data-testid="stChatMessage"] hr {
        margin: 8px 0 !important;
        opacity: 0.2;
    }
    .stChatInputContainer {
        padding-bottom: 20px;
    }
    /* Pulsing animation for loading */
    @keyframes pulse {
        0% { opacity: 0.6; transform: scale(0.98); }
        50% { opacity: 1; transform: scale(1.01); }
        100% { opacity: 0.6; transform: scale(0.98); }
    }
    .thinking-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 12px 20px;
        display: flex;
        align-items: center;
        gap: 12px;
        animation: pulse 2s infinite ease-in-out;
        width: fit-content;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .thinking-dot {
        width: 8px;
        height: 8px;
        background: #3b82f6;
        border-radius: 50%;
    }
    .stMarkdown h1 {
        color: #0f172a;
        font-weight: 800;
    }
</style>
""", unsafe_allow_html=True)

st.title("🤖 IBM MQ Assistant")
st.markdown("""
<div style="background-color: #ffffff; border-left: 5px solid #3b82f6; padding: 15px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <span style="color: #475569; font-weight: 600;">Basic Assistant:</span> 
    <span style="color: #64748b;">Fast, predictable, and understands natural language through intelligent pattern matching.</span>
</div>
""", unsafe_allow_html=True)

# Define the server script path
script_dir = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(script_dir, "..", "server", "mqmcpserver.py")

async def run_mcp_command(prompt):
    """
    Connects to the MCP server, runs the command, and disconnects.
    This is the most reliable way to handle async stdio in Streamlit's 
    stateless/sequential execution model.
    """
    client = DynamicMQClient(server_script=SERVER_SCRIPT)
    try:
        await client.connect()
        # Override built-in input to prevent blocking
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
        return f"❌ Error connecting to MQ Service: {str(e)}"

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
        
        # Execute the command in a new event loop for this interaction
        full_response = asyncio.run(run_mcp_command(prompt))
        message_placeholder.markdown(full_response)
    
    # Add assistant response to chat history
    st.session_state.messages_basic.append({"role": "assistant", "content": full_response})

# Sidebar info
with st.sidebar:
    st.header("System Info")
    st.info(f"Server Script: {os.path.basename(SERVER_SCRIPT)}")
    if st.button("Test Connection"):
        with st.spinner("Testing connection to MCP server..."):
            res = asyncio.run(run_mcp_command("dspmq"))
            if "❌" in res:
                st.error("Connection Failed")
                st.write(res)
            else:
                st.success("Connection Successful!")

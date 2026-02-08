import streamlit as st
import asyncio
import os
import json
from llm_client import LLMToolCaller
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up page config
st.set_page_config(page_title="IBM MQ AI Assistant", page_icon="🧠", layout="wide")

# Custom CSS for a professional light theme
st.markdown("""
<style>
    .stApp {
        background-color: #f8fafc;
        color: #0f172a;
    }
    [data-testid="stChatMessage"] {
        border-radius: 12px;
        margin-bottom: 8px;
        padding: 4px 12px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
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
        border: 1px solid #e0e7ff;
        border-radius: 10px;
        padding: 12px 20px;
        display: flex;
        align-items: center;
        gap: 12px;
        animation: pulse 2s infinite ease-in-out;
        width: fit-content;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    .thinking-dot {
        width: 8px;
        height: 8px;
        background: #6366f1;
        border-radius: 50%;
    }
    .stMarkdown h1 {
        color: #1e1b4b;
        font-weight: 800;
    }
</style>
""", unsafe_allow_html=True)

st.title("🧠 IBM MQ AI Assistant")
st.markdown("""
<div style="background-color: #ffffff; border-left: 5px solid #6366f1; padding: 15px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <span style="color: #4338ca; font-weight: 600;">AI-Powered Assistant:</span> 
    <span style="color: #64748b;">Uses OpenAI's GPT-4 to intelligently decide which tools to call and provides natural, conversational responses.</span>
</div>
""", unsafe_allow_html=True)

# Define the server script path
script_dir = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(script_dir, "..", "server", "mqmcpserver.py")

# OpenAI API Key management
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY", "")

with st.sidebar:
    st.header("Configuration")
    api_key = st.text_input("OpenAI API Key", type="password", value=st.session_state.openai_api_key)
    if api_key:
        st.session_state.openai_api_key = api_key
        os.environ["OPENAI_API_KEY"] = api_key
    else:
        st.warning("Please enter your OpenAI API Key to enable the AI.")

async def run_llm_command(prompt):
    """
    Connects to the MCP server, runs the command using LLM, and disconnects.
    """
    if not st.session_state.openai_api_key:
        return "⚠️ OpenAI API Key is missing. Please provide it in the sidebar."
        
    client = LLMToolCaller(server_script=SERVER_SCRIPT, provider="openai")
    # Pass history if needed, but LLMToolCaller currently manages it internally. 
    # For Streamlit, we might want to sync history if we want the LLM to remember 
    # previous turns across multiple tool calls in the same interaction.
    
    try:
        await client.connect()
        try:
            # Note: We are using a fresh client each time, so multi-turn history 
            # within the LLM session needs to be handled if desired.
            # For now, we'll keep it simple.
            response = await client.handle_user_input(prompt)
            return response
        finally:
            await client.disconnect()
    except Exception as e:
        return f"❌ Error: {str(e)}"

# Chat interface initialization
if "messages_llm" not in st.session_state:
    st.session_state.messages_llm = [
        {"role": "assistant", "content": "I'm your AI-powered IBM MQ assistant. How can I help you today? (e.g., 'Check if all queue managers are running')"}
    ]

# Display chat messages
for message in st.session_state.messages_llm:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
if prompt := st.chat_input("Ask something about IBM MQ..."):
    if not st.session_state.openai_api_key:
        st.error("Please provide an OpenAI API Key in the sidebar.")
    else:
        # Add user message to chat history
        st.session_state.messages_llm.append({"role": "user", "content": prompt})
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
                    <span>AI Assistant is analyzing and calling tools...</span>
                </div>
            """, unsafe_allow_html=True)
            
            full_response = asyncio.run(run_llm_command(prompt))
            message_placeholder.markdown(full_response)
        
        # Add assistant response to chat history
        st.session_state.messages_llm.append({"role": "assistant", "content": full_response})

# Sidebar status info
with st.sidebar:
    st.divider()
    st.header("System Status")
    st.info(f"Server: {os.path.basename(SERVER_SCRIPT)}")
    if st.button("Test Connection"):
        with st.spinner("Testing MCP connection..."):
            # Simple test call
            res = asyncio.run(run_llm_command("List all queue managers"))
            if "❌" in res:
                st.error("Connection Failed")
            else:
                st.success("Connection Successful!")

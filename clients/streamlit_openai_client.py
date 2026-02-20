import streamlit as st
import asyncio
import os
import json
import signal
import atexit
from llm_client import LLMToolCaller
from dotenv import load_dotenv
from tool_logger import get_rest_api_url, should_show_logging

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
                    obj = st.session_state.get(key)
                    if obj and hasattr(obj, 'cleanup'):
                        try:
                            obj.cleanup()
                        except:
                            pass
        except:
            pass
    
    # Run cleanup in background thread (daemon) with short timeout
    t = threading.Thread(target=do_cleanup, daemon=True)
    t.start()
    t.join(timeout=1)  # Wait max 1 second

# Register only atexit handler - don't override Streamlit's signal handlers
atexit.register(cleanup_on_exit)


# Set up page config
st.set_page_config(page_title="IBM MQ AI Assistant", page_icon="🧠", layout="wide")

# Define the server script path
script_dir = os.path.dirname(os.path.abspath(__file__))
SERVER_SCRIPT = os.path.join(script_dir, "..", "server", "mqmcpserver.py")

# API Key management for all providers
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY", "")
if "anthropic_api_key" not in st.session_state:
    st.session_state.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
if "selected_provider" not in st.session_state:
    st.session_state.selected_provider = "openai"

async def run_llm_command(prompt, client):
    """Execution logic for LLM Client - uses persistent client for conversation context"""
    provider = st.session_state.selected_provider
    key_map = {
        "openai": (st.session_state.openai_api_key, "OpenAI"),
        "anthropic": (st.session_state.anthropic_api_key, "Anthropic"),
        "gemini": (st.session_state.gemini_api_key, "Gemini"),
    }
    api_key, label = key_map.get(provider, ("", provider))
    if not api_key:
        return None, f"⚠️ {label} API Key is missing. Please provide it in the sidebar."
    
    try:
        response = await client.handle_user_input(prompt)
        tools_used = client.tools_used
        return tools_used, response
    except Exception as e:
        import traceback
        error_msg = f"❌ Error: {str(e)}"
        st.error(f"{error_msg}\n\n{traceback.format_exc()}")
        return None, error_msg

@st.cache_resource
def get_llm_client(provider="openai"):
    """Get or create a persistent LLM client for the given provider"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    server_script = os.path.join(script_dir, "..", "server", "mqmcpserver.py")
    return LLMToolCaller(server_script=server_script, provider=provider)

@st.cache_resource
def initialize_client(provider="openai"):
    """Initialize client connection for a given provider"""
    client = get_llm_client(provider)
    loop = get_event_loop()
    try:
        loop.run_until_complete(client.connect())
        return client
    except Exception as e:
        st.error(f"Failed to initialize MCP client: {e}")
        return None

@st.cache_resource
def get_event_loop():
    """Get or create an event loop for async operations"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop

# Connectivity Check logic (Shared with LLM for status)
PROVIDER_LABELS = {"openai": "GPT-4", "anthropic": "Claude", "gemini": "Gemini 1.5"}
provider_name = PROVIDER_LABELS.get(st.session_state.selected_provider, "AI")
mcp_status_html = f'<span style="color: #ccffcc;">🟢 {provider_name} Ready</span>'

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

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {{
        background-color: #f8fafc;
        border-right: 1px solid #e2e8f0;
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
        <h2 style="display: inline; margin-right: 10px;">🧠 IBM MQ AI Assistant</h2>
    </div>
    <div style="font-weight: 600; font-size: 14px;">
        {mcp_status_html}
    </div>
</div>

<div class="fixed-footer">
    v1.2 AI OpenAI Client | Server: mqmcpserver.py
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="background-color: #f1f8e9; border-left: 5px solid #76BC21; padding: 15px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <span style="color: #2e7d32; font-weight: 600;">AI-Powered Assistant:</span> 
    <span style="color: #555555;">Uses GPT-4 to intelligently decide which tools to call and provides natural, conversational responses.</span>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("🔑 Configuration")

    # Provider selector
    provider_choice = st.radio(
        "AI Provider",
        options=["openai", "anthropic", "gemini"],
        format_func=lambda x: {"openai": "🧠 OpenAI (GPT-4)", "anthropic": "🐤 Anthropic (Claude)", "gemini": "✨ Google (Gemini)"}[x],
        index=["openai", "anthropic", "gemini"].index(st.session_state.selected_provider)
    )

    # If provider changed, reset the client so it's recreated with new provider
    if provider_choice != st.session_state.selected_provider:
        st.session_state.selected_provider = provider_choice
        st.session_state.pop("llm_client", None)
        st.session_state.client_ready = False
        st.rerun()

    st.divider()

    # Show relevant API key input
    if provider_choice == "openai":
        api_key = st.text_input("🔑 OpenAI API Key", type="password", value=st.session_state.openai_api_key)
        if api_key:
            st.session_state.openai_api_key = api_key
            os.environ["OPENAI_API_KEY"] = api_key
        else:
            st.warning("Please enter your OpenAI API Key.")
    elif provider_choice == "anthropic":
        api_key = st.text_input("🔑 Anthropic API Key", type="password", value=st.session_state.anthropic_api_key)
        if api_key:
            st.session_state.anthropic_api_key = api_key
            os.environ["ANTHROPIC_API_KEY"] = api_key
        else:
            st.warning("Please enter your Anthropic API Key.")
    elif provider_choice == "gemini":
        api_key = st.text_input("🔑 Gemini API Key", type="password", value=st.session_state.gemini_api_key)
        if api_key:
            st.session_state.gemini_api_key = api_key
            os.environ["GEMINI_API_KEY"] = api_key
        else:
            st.warning("Please enter your Gemini API Key.")

    st.divider()
    st.markdown("### 🛠️ Environment")
    st.code(f"Server: mqmcpserver.py", language="text")

# Initialize persistent client on page load
if "llm_client" not in st.session_state:
    st.session_state.llm_client = initialize_client(st.session_state.selected_provider)
    st.session_state.client_ready = st.session_state.llm_client is not None

# Chat interface initialization
if "messages_llm" not in st.session_state:
    st.session_state.messages_llm = [
        {"role": "assistant", "content": "I'm your AI-powered IBM MQ assistant. How can I help you today? (e.g., 'Check status of queue Q1')\n\n**💡 Tip:** I can maintain conversation context, so you can ask follow-up questions and I'll remember the context!"}
    ]

# Display connection status
if not st.session_state.client_ready:
    st.warning("⚠️ MCP client not ready. Please refresh the page.")

# Display chat messages
for message in st.session_state.messages_llm:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Display tools used if available
        if "tools_used" in message and message["tools_used"]:
            with st.expander("🔧 Tools Used (in order)"):
                for idx, tool in enumerate(message["tools_used"], 1):
                    col1, col2 = st.columns([1, 4])
                    with col1:
                        st.markdown(f"**Step {idx}**")
                    with col2:
                        st.markdown(f"**`{tool['name']}`**")
                    
                    if tool.get('args'):
                        st.json(tool['args'], expanded=False)
                    
                    # Show REST endpoint if logging is enabled
                    if should_show_logging():
                        rest_endpoint = get_rest_api_url(tool['name'], tool.get('args', {}))
                        st.code(rest_endpoint, language="text")

# User input
if prompt := st.chat_input("Ask something about IBM MQ..."):
    provider = st.session_state.selected_provider
    key_map = {
        "openai": st.session_state.openai_api_key,
        "anthropic": st.session_state.anthropic_api_key,
        "gemini": st.session_state.gemini_api_key,
    }
    active_key = key_map.get(provider, "")
    if not active_key:
        provider_label = {"openai": "OpenAI", "anthropic": "Anthropic", "gemini": "Gemini"}.get(provider, provider)
        st.error(f"Please provide a {provider_label} API Key in the sidebar.")
    elif not st.session_state.client_ready:
        st.error("MCP client is not ready. Please refresh the page.")
    else:
        # Add user message to chat history
        st.session_state.messages_llm.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            tools_placeholder = st.empty()
            message_placeholder.markdown("""
                <div class="thinking-box">
                    <div class="thinking-dot" style="animation-delay: 0s"></div>
                    <div class="thinking-dot" style="animation-delay: 0.2s"></div>
                    <div class="thinking-dot" style="animation-delay: 0.4s"></div>
                    <span>AI Assistant is analyzing and calling tools...</span>
                </div>
            """, unsafe_allow_html=True)
            
            try:
                loop = get_event_loop()
                # Pass the persistent client to maintain conversation history
                tools_used, full_response = loop.run_until_complete(
                    run_llm_command(prompt, st.session_state.llm_client)
                )
            except Exception as e:
                import traceback
                tools_used = None
                full_response = f"❌ Error: {str(e)}\n\n{traceback.format_exc()}"
            
            message_placeholder.markdown(full_response)
            
            # Display tools used
            if tools_used:
                with tools_placeholder.expander("🔧 Tools Used by AI (in order)"):
                    for idx, tool in enumerate(tools_used, 1):
                        col1, col2 = st.columns([1, 4])
                        with col1:
                            st.markdown(f"**Step {idx}**")
                        with col2:
                            st.markdown(f"**`{tool['name']}`**")
                        
                        if tool.get('args'):
                            st.json(tool['args'], expanded=False)
                        
                        # Show REST endpoint if logging is enabled
                        if should_show_logging():
                            rest_endpoint = get_rest_api_url(tool['name'], tool.get('args', {}))
                            st.code(rest_endpoint, language="text")
        
        # Add assistant response to chat history with tools used
        st.session_state.messages_llm.append({
            "role": "assistant", 
            "content": full_response,
            "tools_used": tools_used
        })

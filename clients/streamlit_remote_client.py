"""
IBM MQ Remote AI Assistant - Streamlit Client

Connects to a remote MCP server via SSE and provides an OpenAI-powered 
conversational interface with tool calling and transparency logging.
"""

import streamlit as st
import asyncio
import os
import json
from dotenv import load_dotenv
from tool_logger import get_rest_api_url, should_show_logging

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import anthropic as anthropic_sdk
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

from mcp import ClientSession
from mcp.client.sse import sse_client

# Load environment variables
load_dotenv()

# Set up page config
st.set_page_config(page_title="IBM MQ Remote AI Assistant", page_icon="🌐", layout="wide")

# Initialize session state
if "mcp_endpoint" not in st.session_state:
    st.session_state.mcp_endpoint = "http://localhost:5000/sse"
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY", "")
if "anthropic_api_key" not in st.session_state:
    st.session_state.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
if "selected_provider" not in st.session_state:
    st.session_state.selected_provider = "openai"
if "connection_status" not in st.session_state:
    st.session_state.connection_status = "unknown"
if "messages_remote" not in st.session_state:
    st.session_state.messages_remote = [
        {"role": "assistant", "content": "I'm your remote IBM MQ AI assistant. Configure the MCP endpoint in the sidebar and ask me anything about your MQ infrastructure!"}
    ]
if "mcp_tools" not in st.session_state:
    st.session_state.mcp_tools = []

async def check_connection(endpoint):
    """Test connection to MCP server"""
    try:
        async with sse_client(endpoint) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                return True, "Connected"
    except Exception as e:
        return False, str(e)

async def get_mcp_tools(endpoint):
    """Fetch available MCP tools from server"""
    try:
        async with sse_client(endpoint) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                return tools_response.tools
    except Exception as e:
        st.error(f"Failed to fetch tools: {e}")
        return []

async def call_mcp_tool(endpoint, tool_name, arguments):
    """Call a specific MCP tool via SSE"""
    try:
        async with sse_client(endpoint) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                if result.content:
                    return result.content[0].text
                return "✅ Command executed (No output)"
    except Exception as e:
        return f"❌ Error: {str(e)}"

def convert_mcp_tools_to_openai_schema(mcp_tools):
    """Convert MCP tools to OpenAI function calling schema"""
    openai_tools = []
    for tool in mcp_tools:
        parameters = tool.inputSchema if hasattr(tool, 'inputSchema') and tool.inputSchema else {"type": "object", "properties": {}}
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or f"Execute {tool.name}",
                "parameters": parameters
            }
        })
    return openai_tools

def convert_mcp_tools_to_anthropic_schema(mcp_tools):
    """Convert MCP tools to Anthropic tool calling schema"""
    anthropic_tools = []
    for tool in mcp_tools:
        input_schema = tool.inputSchema if hasattr(tool, 'inputSchema') and tool.inputSchema else {"type": "object", "properties": {}}
        anthropic_tools.append({
            "name": tool.name,
            "description": tool.description or f"Execute {tool.name}",
            "input_schema": input_schema
        })
    return anthropic_tools

def convert_mcp_tools_to_gemini_declarations(mcp_tools):
    """Convert MCP tools to Gemini FunctionDeclaration list"""
    declarations = []
    for tool in mcp_tools:
        schema = tool.inputSchema if hasattr(tool, 'inputSchema') and tool.inputSchema else {}
        props = schema.get("properties", {})
        required = schema.get("required", [])
        declarations.append(
            genai.protos.FunctionDeclaration(
                name=tool.name,
                description=tool.description or f"Execute {tool.name}",
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties={
                        k: genai.protos.Schema(
                            type=genai.protos.Type.STRING,
                            description=v.get("description", "") if isinstance(v, dict) else ""
                        )
                        for k, v in props.items()
                    },
                    required=required
                ) if props else genai.protos.Schema(type=genai.protos.Type.OBJECT, properties={})
            )
        )
    return declarations

async def handle_ai_conversation(user_message, endpoint, api_key):
    """Handle conversation with OpenAI and execute tool calls"""
    if not api_key:
        return None, "Please provide an OpenAI API key in the sidebar."
    if not HAS_OPENAI:
        return None, "❌ openai library not installed."
    
    # Get available MCP tools
    if not st.session_state.mcp_tools:
        st.session_state.mcp_tools = await get_mcp_tools(endpoint)
    if not st.session_state.mcp_tools:
        return None, "No MCP tools available. Check your MCP endpoint."
    
    openai_tools = convert_mcp_tools_to_openai_schema(st.session_state.mcp_tools)
    
    system_prompt = _get_system_prompt()
    messages = [{"role": "system", "content": system_prompt}]
    for msg in st.session_state.messages_remote[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_message})
    
    try:
        client = OpenAI(api_key=api_key)
        tools_used = []
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            tools=openai_tools,
            tool_choice="auto"
        )
        response_message = response.choices[0].message
        
        while response_message.tool_calls:
            messages.append(response_message)
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                tools_used.append({"name": function_name, "args": function_args})
                tool_result = await call_mcp_tool(endpoint, function_name, function_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": tool_result
                })
            response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                tools=openai_tools,
                tool_choice="auto"
            )
            response_message = response.choices[0].message
        
        return tools_used, response_message.content
    except Exception as e:
        import traceback
        return None, f"❌ Error: {str(e)}\n\n{traceback.format_exc()}"


async def handle_ai_conversation_anthropic(user_message, endpoint, api_key):
    """Handle conversation with Anthropic Claude and execute tool calls via SSE"""
    if not api_key:
        return None, "Please provide an Anthropic API key in the sidebar."
    if not HAS_ANTHROPIC:
        return None, "❌ anthropic library not installed. Run: pip install anthropic"

    if not st.session_state.mcp_tools:
        st.session_state.mcp_tools = await get_mcp_tools(endpoint)
    if not st.session_state.mcp_tools:
        return None, "No MCP tools available. Check your MCP endpoint."

    anthropic_tools = convert_mcp_tools_to_anthropic_schema(st.session_state.mcp_tools)
    system_prompt = _get_system_prompt()

    # Build history — Anthropic uses user/assistant roles only
    history = []
    for msg in st.session_state.messages_remote[-10:]:
        if msg["role"] in ("user", "assistant") and isinstance(msg["content"], str):
            history.append({"role": msg["role"], "content": msg["content"]})
    history.append({"role": "user", "content": user_message})

    try:
        client = anthropic_sdk.Anthropic(api_key=api_key)
        tools_used = []
        max_iterations = 10

        for _ in range(max_iterations):
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2048,
                system=system_prompt,
                tools=anthropic_tools,
                messages=history
            )

            has_tool_use = any(b.type == "tool_use" for b in response.content)
            if not has_tool_use:
                final_text = next((b.text for b in response.content if hasattr(b, "text")), "")
                return tools_used, final_text

            # Append assistant turn
            history.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tools_used.append({"name": block.name, "args": block.input})
                    tool_result = await call_mcp_tool(endpoint, block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": tool_result
                    })
            history.append({"role": "user", "content": tool_results})

        return tools_used, "❌ Max tool calls exceeded."
    except Exception as e:
        import traceback
        return None, f"❌ Error: {str(e)}\n\n{traceback.format_exc()}"


async def handle_ai_conversation_gemini(user_message, endpoint, api_key):
    """Handle conversation with Google Gemini and execute tool calls via SSE"""
    if not api_key:
        return None, "Please provide a Gemini API key in the sidebar."
    if not HAS_GEMINI:
        return None, "❌ google-generativeai library not installed. Run: pip install google-generativeai"

    if not st.session_state.mcp_tools:
        st.session_state.mcp_tools = await get_mcp_tools(endpoint)
    if not st.session_state.mcp_tools:
        return None, "No MCP tools available. Check your MCP endpoint."

    genai.configure(api_key=api_key)
    declarations = convert_mcp_tools_to_gemini_declarations(st.session_state.mcp_tools)
    tool_declarations = [genai.protos.Tool(function_declarations=declarations)]
    system_prompt = _get_system_prompt()

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=system_prompt,
        tools=tool_declarations
    )

    # Build prior history (text only)
    gemini_history = []
    for msg in st.session_state.messages_remote[-10:]:
        if msg["role"] in ("user", "assistant") and isinstance(msg["content"], str):
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})

    chat = model.start_chat(history=gemini_history)

    try:
        tools_used = []
        current_message = user_message
        max_iterations = 10

        for _ in range(max_iterations):
            response = chat.send_message(current_message)
            part = response.candidates[0].content.parts[0]

            if hasattr(part, 'function_call') and part.function_call.name:
                fn = part.function_call
                tool_name = fn.name
                tool_args = dict(fn.args)
                tools_used.append({"name": tool_name, "args": tool_args})
                tool_result = await call_mcp_tool(endpoint, tool_name, tool_args)

                current_message = genai.protos.Content(
                    parts=[genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=tool_name,
                            response={"result": tool_result}
                        )
                    )]
                )
            else:
                return tools_used, part.text

        return tools_used, "❌ Max tool calls exceeded."
    except Exception as e:
        import traceback
        return None, f"❌ Error: {str(e)}\n\n{traceback.format_exc()}"


def _get_system_prompt() -> str:
    """Shared system prompt for all providers"""
    return """You are an IBM MQ expert assistant. Your PRIMARY JOB is to call tools to answer user questions. Do NOT ask users for input.

QUEUE NAMING CONVENTIONS - YOU MUST KNOW THESE:
- QL* = Local Queue (e.g., QL.IN.APP1, QL.OUT.APP2)
- QA* = Alias Queue (e.g., QA.IN.APP1 - points to another queue via TARGET)
- QR* = Remote Queue (e.g., QR.REMOTE.Q - references queue on remote QM)
- Others = System/Application specific queues

MANDATORY RULES - YOU MUST FOLLOW THESE:
1. When a user asks about ANY queue, ALWAYS search for it first using search_qmgr_dump
2. When search results show queue manager info, IMMEDIATELY extract ALL queue manager names
3. **CRITICAL**: If a queue exists on MULTIPLE queue managers, you MUST query ALL of them
4. NEVER ask "which queue manager?" if search results already show it
5. ALWAYS make the next tool call in the SAME iteration - do not wait for user response
6. Queue depth MQSC commands:
   - Local (QL*): DISPLAY QLOCAL(<QUEUE_NAME>) CURDEPTH
   - Remote (QR*): DISPLAY QREMOTE(<QUEUE_NAME>) CURDEPTH
   - Alias (QA*): DISPLAY QALIAS(<QUEUE_NAME>) to see TARGET, then query the TARGET queue
7. COMPLETE THE WORKFLOW - user asks question → search → identify ALL QMs → runmqsc on EACH → return answer

YOU MUST NOT:
- Ask "which queue manager?" when search already found it
- Wait for user input when you can call tools
- Query only ONE queue manager when the queue exists on MULTIPLE queue managers"""

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
        <h2 style="display: inline; margin-right: 10px;">🌐 IBM MQ Remote AI Assistant</h2>
    </div>
    <div style="font-weight: 600; font-size: 14px;">
        {'<span style="color: #ccffcc;">🟢 Connected</span>' if st.session_state.connection_status == "connected" else '<span style="color: #ff9999;">🔴 Disconnected</span>'}
    </div>
</div>

<div class="fixed-footer">
    v1.0 Remote AI Client | SSE + OpenAI
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="background-color: #f1f8e9; border-left: 5px solid #76BC21; padding: 15px; border-radius: 8px; margin-bottom: 25px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <span style="color: #2e7d32; font-weight: 600;">Remote AI Assistant:</span> 
    <span style="color: #555555;">Connect to any MCP server via SSE and use AI-powered natural language to manage your IBM MQ infrastructure.</span>
</div>
""", unsafe_allow_html=True)

# Sidebar Configuration
with st.sidebar:
    st.header("🔌 Connection Settings")
    
    mcp_endpoint = st.text_input(
        "MCP Endpoint (SSE)", 
        value=st.session_state.mcp_endpoint,
        help="Enter the SSE endpoint URL (e.g., http://server:5000/sse)"
    )
    if mcp_endpoint != st.session_state.mcp_endpoint:
        st.session_state.mcp_endpoint = mcp_endpoint
        st.session_state.connection_status = "unknown"
        st.session_state.mcp_tools = []
    
    if st.button("🔄 Test Connection", type="secondary", use_container_width=True):
        with st.spinner("Testing connection..."):
            success, message = asyncio.run(check_connection(st.session_state.mcp_endpoint))
            if success:
                st.session_state.connection_status = "connected"
                st.success(f"✅ {message}")
                st.session_state.mcp_tools = asyncio.run(get_mcp_tools(st.session_state.mcp_endpoint))
                st.info(f"Loaded {len(st.session_state.mcp_tools)} tools")
            else:
                st.session_state.connection_status = "disconnected"
                st.error(f"❌ Connection failed: {message}")
    
    st.divider()
    st.header("🔑 AI Provider")

    provider_choice = st.radio(
        "Select Provider",
        options=["openai", "anthropic", "gemini"],
        format_func=lambda x: {"openai": "🧠 OpenAI (GPT-4)", "anthropic": "🐤 Anthropic (Claude)", "gemini": "✨ Google (Gemini)"}[x],
        index=["openai", "anthropic", "gemini"].index(st.session_state.selected_provider)
    )
    if provider_choice != st.session_state.selected_provider:
        st.session_state.selected_provider = provider_choice
        st.rerun()

    st.divider()
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
    st.markdown("### 📊 Status")
    st.code(f"Endpoint: {st.session_state.mcp_endpoint}", language="text")
    st.code(f"Tools: {len(st.session_state.mcp_tools)}", language="text")

# Display chat messages
for message in st.session_state.messages_remote:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        # Display tools used if available
        if "tools_used" in message and message["tools_used"]:
            with st.expander("🔧 Tools Used by AI"):
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
    provider_label = {"openai": "OpenAI", "anthropic": "Anthropic", "gemini": "Gemini"}.get(provider, provider)

    if not active_key:
        st.error(f"Please provide a {provider_label} API Key in the sidebar.")
    elif st.session_state.connection_status != "connected":
        st.warning("Please test the connection to your MCP endpoint first.")
    else:
        # Add user message to chat history
        st.session_state.messages_remote.append({"role": "user", "content": prompt})
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
                provider = st.session_state.selected_provider
                handler_map = {
                    "openai": (handle_ai_conversation, st.session_state.openai_api_key),
                    "anthropic": (handle_ai_conversation_anthropic, st.session_state.anthropic_api_key),
                    "gemini": (handle_ai_conversation_gemini, st.session_state.gemini_api_key),
                }
                handler, active_key = handler_map[provider]
                tools_used, full_response = asyncio.run(
                    handler(
                        prompt, 
                        st.session_state.mcp_endpoint,
                        active_key
                    )
                )
            except Exception as e:
                import traceback
                tools_used = None
                full_response = f"❌ Error: {str(e)}\n\n{traceback.format_exc()}"
            
            message_placeholder.markdown(full_response)
            
            # Display tools used
            if tools_used:
                with tools_placeholder.expander("🔧 Tools Used by AI"):
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
        st.session_state.messages_remote.append({
            "role": "assistant", 
            "content": full_response,
            "tools_used": tools_used
        })

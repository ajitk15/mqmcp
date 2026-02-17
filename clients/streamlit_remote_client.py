"""
IBM MQ Remote AI Assistant - Streamlit Client

Connects to a remote MCP server via SSE and provides an OpenAI-powered 
conversational interface with tool calling and transparency logging.
"""

import streamlit as st
import asyncio
import os
import json
from openai import OpenAI
from mcp import ClientSession
from mcp.client.sse import sse_client
from dotenv import load_dotenv
from tool_logger import get_rest_api_url, should_show_logging

# Load environment variables
load_dotenv()

# Set up page config
st.set_page_config(page_title="IBM MQ Remote AI Assistant", page_icon="🌐", layout="wide")

# Initialize session state
if "mcp_endpoint" not in st.session_state:
    st.session_state.mcp_endpoint = "http://localhost:5000/sse"
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = os.getenv("OPENAI_API_KEY", "")
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
        # Build parameter schema from inputSchema
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

async def handle_ai_conversation(user_message, endpoint, api_key):
    """Handle conversation with OpenAI and execute tool calls"""
    if not api_key:
        return None, "Please provide an OpenAI API key in the sidebar."
    
    # Get available MCP tools
    if not st.session_state.mcp_tools:
        st.session_state.mcp_tools = await get_mcp_tools(endpoint)
    
    if not st.session_state.mcp_tools:
        return None, "No MCP tools available. Check your MCP endpoint."
    
    # Convert to OpenAI schema
    openai_tools = convert_mcp_tools_to_openai_schema(st.session_state.mcp_tools)
    
    # Build conversation history
    system_prompt = """You are an IBM MQ expert assistant. Your PRIMARY JOB is to call tools to answer user questions. Do NOT ask users for input.

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
- Query only ONE queue manager when the queue exists on MULTIPLE queue managers

EXAMPLE WORKFLOWS:

Example 1 - Single Queue Manager:
User: "What is the current depth of queue QL.OUT.APP3?"
YOU MUST:
1. Call search_qmgr_dump('QL.OUT.APP3') → finds "QL.OUT.APP3 | MQQMGR1 | QLOCAL"
2. Call runmqsc(qmgr_name='MQQMGR1', mqsc_command='DISPLAY QLOCAL(QL.OUT.APP3) CURDEPTH')
3. Return: "The current depth of queue QL.OUT.APP3 on MQQMGR1 is 42"

Example 2 - MULTIPLE Queue Managers (CRITICAL):
User: "What is the current depth of queue QL.IN.APP1?"
YOU MUST:
1. Call search_qmgr_dump('QL.IN.APP1') 
   → Result: "Found on queue managers: MQQMGR1, MQQMGR2"
2. Call runmqsc(qmgr_name='MQQMGR1', mqsc_command='DISPLAY QLOCAL(QL.IN.APP1) CURDEPTH')
   → Result: "CURDEPTH(15)"
3. Call runmqsc(qmgr_name='MQQMGR2', mqsc_command='DISPLAY QLOCAL(QL.IN.APP1) CURDEPTH')
   → Result: "CURDEPTH(8)"
4. Return: "Queue QL.IN.APP1 exists on multiple queue managers:
   - MQQMGR1: current depth is 15
   - MQQMGR2: current depth is 8"

DON'T DO THIS:
✗ Call search_qmgr_dump and then ask "which queue manager?"
✗ Query only MQQMGR1 when queue exists on both MQQMGR1 and MQQMGR2"""
    
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    # Add chat history (limit to last 10 messages to avoid token limits)
    for msg in st.session_state.messages_remote[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Add current user message
    messages.append({"role": "user", "content": user_message})
    
    try:
        client = OpenAI(api_key=api_key)
        tools_used = []
        
        # Initial API call
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            tools=openai_tools,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        
        # Handle tool calls
        while response_message.tool_calls:
            messages.append(response_message)
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                # Record tool usage
                tools_used.append({
                    "name": function_name,
                    "args": function_args
                })
                
                # Call the MCP tool
                tool_result = await call_mcp_tool(endpoint, function_name, function_args)
                
                # Add tool response to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": function_name,
                    "content": tool_result
                })
            
            # Get next response from OpenAI
            response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                tools=openai_tools,
                tool_choice="auto"
            )
            response_message = response.choices[0].message
        
        # Return final response
        return tools_used, response_message.content
        
    except Exception as e:
        import traceback
        return None, f"❌ Error: {str(e)}\n\n{traceback.format_exc()}"

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
                # Load tools
                st.session_state.mcp_tools = asyncio.run(get_mcp_tools(st.session_state.mcp_endpoint))
                st.info(f"Loaded {len(st.session_state.mcp_tools)} tools")
            else:
                st.session_state.connection_status = "disconnected"
                st.error(f"❌ Connection failed: {message}")
    
    st.divider()
    st.header("🔑 OpenAI API Key")
    
    api_key = st.text_input("API Key", type="password", value=st.session_state.openai_api_key)
    if api_key:
        st.session_state.openai_api_key = api_key
        os.environ["OPENAI_API_KEY"] = api_key
    else:
        st.warning("Please enter your OpenAI API Key.")
    
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
    if not st.session_state.openai_api_key:
        st.error("Please provide an OpenAI API Key in the sidebar.")
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
                tools_used, full_response = asyncio.run(
                    handle_ai_conversation(
                        prompt, 
                        st.session_state.mcp_endpoint,
                        st.session_state.openai_api_key
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

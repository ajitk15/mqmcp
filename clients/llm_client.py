#!/usr/bin/env python3
"""
LLM-Based Dynamic Tool Calling Example

This example shows how to use an LLM (OpenAI GPT or Anthropic Claude) to
intelligently decide which MCP tools to call based on natural language input.

This approach is more flexible than pattern matching but requires an API key.

Setup:
1. Install: pip install openai anthropic
2. Set environment variable: OPENAI_API_KEY or ANTHROPIC_API_KEY
3. Run: python llm_client.py
"""

import asyncio
import json
import os
import sys
import atexit
import signal
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
try:
    from metrics_logger import get_metrics_logger, MetricsTracker
except ImportError:
    from .metrics_logger import get_metrics_logger, MetricsTracker

# Load environment variables
load_dotenv()

# Initialize logger
logger = get_metrics_logger("mq-llm-client")

# Try to import LLM libraries
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class LLMToolCaller:
    """
    Uses an LLM to intelligently call MCP tools based on user input.
    Supports both OpenAI and Anthropic.
    """
    
    def __init__(self, server_script=None, provider="openai"):
        if server_script is None:
            # Get the path to the server script relative to this script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            server_script = os.path.join(script_dir, "..", "server", "mqmcpserver.py")
        self.server_script = server_script
        self.session = None
        self.provider = provider
        self.conversation_history = []
        self.tools_used = []  # Track which tools were called
        self._cleanup_done = False  # Track cleanup status
        self._process = None  # Track subprocess for cleanup
        
        # Register cleanup handler
        atexit.register(self.cleanup)
        
        # Tool definitions for LLM
        self.tools_openai = [
            {
                "type": "function",
                "function": {
                    "name": "dspmq",
                    "description": "List all IBM MQ queue managers and their running status (running/stopped)",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "dspmqver",
                    "description": "Get IBM MQ version, build level, and installation path details",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "runmqsc",
                    "description": "Execute an MQSC command on a specific IBM MQ queue manager. Use this for operations like checking queue depth, listing queues, displaying channels, etc.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "qmgr_name": {
                                "type": "string",
                                "description": "Name of the queue manager (e.g., 'QM1', 'PROD_QM')"
                            },
                            "mqsc_command": {
                                "type": "string",
                                "description": "MQSC command to execute. Examples: 'DISPLAY QLOCAL(*)' to list all queues, 'DISPLAY QLOCAL(MYQUEUE) CURDEPTH' to check queue depth, 'DISPLAY CHANNEL(*)' to list channels"
                            }
                        },
                        "required": ["qmgr_name", "mqsc_command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_qmgr_dump",
                    "description": "Search the queue manager dump for a specific string across all columns",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "search_string": {
                                "type": "string",
                                "description": "The string to search for in the queue manager data"
                            }
                        },
                        "required": ["search_string"]
                    }
                }
            },

        ]
        
        self.tools_anthropic = [
            {
                "name": "dspmq",
                "description": "List all IBM MQ queue managers and their running status (running/stopped)",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                }
            },
            {
                "name": "dspmqver",
                "description": "Get IBM MQ version, build level, and installation path details",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                }
            },
            {
                "name": "runmqsc",
                "description": "Execute an MQSC command on a specific IBM MQ queue manager. Use this for operations like checking queue depth, listing queues, displaying channels, etc.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "qmgr_name": {
                            "type": "string",
                            "description": "Name of the queue manager (e.g., 'QM1', 'PROD_QM')"
                        },
                        "mqsc_command": {
                            "type": "string",
                            "description": "MQSC command to execute. Examples: 'DISPLAY QLOCAL(*)' to list all queues, 'DISPLAY QLOCAL(MYQUEUE) CURDEPTH' to check queue depth, 'DISPLAY CHANNEL(*)' to list channels"
                        }
                    },
                    "required": ["qmgr_name", "mqsc_command"]
                }
            },
            {
                "name": "search_qmgr_dump",
                "description": "Search the queue manager dump for a specific string across all columns",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "search_string": {
                            "type": "string",
                            "description": "The string to search for in the queue manager data"
                        }
                    },
                    "required": ["search_string"]
                }
            },

        ]
        
    async def connect(self):
        """Connect to the MCP server"""
        print("🔌 Connecting to MCP server...")
        
        # Verify server script exists
        if not os.path.exists(self.server_script):
            raise FileNotFoundError(f"Server script not found: {self.server_script}")
        
        print(f"   Server script: {self.server_script}")
        
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script]
        )
        
        try:
            self.client_context = stdio_client(server_params)
            read, write = await asyncio.wait_for(self.client_context.__aenter__(), timeout=15.0)
            print("   ✅ Server process started")
            
            # Store process handle for cleanup (access internal _process from context)
            if hasattr(self.client_context, '_process'):
                self._process = self.client_context._process
            
            self.session_context = ClientSession(read, write)
            self.session = await asyncio.wait_for(self.session_context.__aenter__(), timeout=15.0)
            print("   ✅ Session created")
            
            await asyncio.wait_for(self.session.initialize(), timeout=15.0)
            print("✅ Connected to MCP server\n")
        except asyncio.TimeoutError:
            raise Exception("Connection timeout: Server took too long to respond (15s)")
        except Exception as e:
            raise Exception(f"Failed to connect to MCP server: {str(e)}")
        
    async def disconnect(self):
        """Disconnect from the MCP server"""
        try:
            if hasattr(self, 'session_context') and self.session_context:
                await self.session_context.__aexit__(None, None, None)
        except Exception as e:
            print(f"DEBUG: Error closing session: {e}")
        
        try:
            if hasattr(self, 'client_context') and self.client_context:
                await self.client_context.__aexit__(None, None, None)
        except Exception as e:
            print(f"DEBUG: Error closing client: {e}")
    
    def cleanup(self):
        """Force cleanup of resources (synchronous for atexit/signal handlers)"""
        if self._cleanup_done:
            return
        
        print("🧹 Cleaning up MCP client...")
        
        # Try graceful disconnect first
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create a task for async cleanup
                asyncio.create_task(self.disconnect())
            else:
                # Run disconnect synchronously
                loop.run_until_complete(self.disconnect())
        except Exception as e:
            print(f"DEBUG: Error during graceful disconnect: {e}")
        
        # Force terminate subprocess if still running
        if self._process and hasattr(self._process, 'poll'):
            try:
                if self._process.poll() is None:  # Still running
                    print("   ⚠️ Subprocess still running, terminating...")
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=3)
                    except:
                        print("   ⚠️ Subprocess didn't terminate, killing...")
                        self._process.kill()
                        self._process.wait()
                    print("   ✅ Subprocess terminated")
            except Exception as e:
                print(f"DEBUG: Error terminating subprocess: {e}")
        
        self._cleanup_done = True
        print("✅ Cleanup complete")
    
    def __del__(self):
        """Destructor to ensure cleanup on garbage collection"""
        self.cleanup()
            
    async def handle_with_openai(self, user_input: str) -> str:
        """Use OpenAI to handle the request"""
        if not HAS_OPENAI:
            return "❌ OpenAI library not installed. Run: pip install openai"
            
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "❌ OPENAI_API_KEY environment variable not set"
            
        client = openai.OpenAI(api_key=api_key)
        
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })
        
        print("🤖 Asking OpenAI GPT-4...")
        
        system_prompt = """You are an IBM MQ expert assistant. Your PRIMARY JOB is to call tools to answer user questions. Do NOT ask users for input.

QUEUE NAMING CONVENTIONS - YOU MUST KNOW THESE:
- QL* = Local Queue (e.g., QL.IN.APP1, QL.OUT.APP2)
- QA* = Alias Queue (e.g., QA.IN.APP1 - points to another queue via TARGET)
- QR* = Remote Queue (e.g., QR.REMOTE.Q - references queue on remote QM)
- Others = System/Application specific queues

CRITICAL HANDLING FOR ALIAS QUEUES:
When user asks about depth of a QA* (alias) queue:
1. Search for the alias queue to find its TARGET queue name
2. If TARGET is a QL* queue, also search for and query that QL* queue
3. Report BOTH: The alias → target mapping AND the actual depth of the target queue
4. Example: User asks "depth of QA.IN.APP1"
   - Find QA.IN.APP1 → TARGET('QL.IN.APP1')
   - Query QL.IN.APP1 for CURDEPTH
   - Response: "Alias QA.IN.APP1 points to QL.IN.APP1, which has current depth: 42"

MANDATORY RULES - YOU MUST FOLLOW THESE:
1. When a user asks about ANY queue, ALWAYS search for it first using search_qmgr_dump
2. When search results show queue manager info, IMMEDIATELY extract ALL queue manager names
3. **CRITICAL**: If a queue exists on MULTIPLE queue managers, you MUST query ALL of them
4. NEVER ask "which queue manager?" if search results already show it
5. ALWAYS make the next tool call in the SAME iteration - do not wait for user response
6. If querying an ALIAS queue for depth:
   - Query the alias to see its TARGET
   - Then query the TARGET queue (if QL* prefix) for actual depth
7. Queue depth MQSC commands:
   - Local (QL*): DISPLAY QLOCAL(<QUEUE_NAME>) CURDEPTH
   - Remote (QR*): DISPLAY QREMOTE(<QUEUE_NAME>) CURDEPTH
   - Alias (QA*): DISPLAY QALIAS(<QUEUE_NAME>) to see TARGET
8. Queue Status:
   - Command: DISPLAY QSTATUS(<QUEUE_NAME>) TYPE(QUEUE) ALL
   - Purpose: Check Open Input/Output Count (IPPROCS/OPPROCS)
9. Cluster Queues:
   - Command: DISPLAY QLOCAL(<QUEUE_NAME>) CLUSTER
   - If CLUSTER attribute is NOT empty, it is a cluster queue.
   - List ALL Queue Managers found in the initial 'search_qmgr_dump' step as hosting this cluster queue.
10. COMPLETE THE WORKFLOW - user asks question → search → identify ALL QMs → runmqsc on EACH → return answer

YOU MUST NOT:
- Ask "which queue manager?" when search already found it
- Stop at alias queue definition - resolve to target and get actual data
- Wait for user input when you can call tools
- Provide generic MQ command examples instead of actual values
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

Example 3 - Alias Queue (THE KEY DIFFERENCE):
User: "What is the current depth of queue QA.IN.APP1?"
YOU MUST:
1. Call search_qmgr_dump('QA.IN.APP1') → finds "QA.IN.APP1 | MQQMGR1 | QALIAS"
2. Call runmqsc(qmgr_name='MQQMGR1', mqsc_command='DISPLAY QALIAS(QA.IN.APP1)') 
   → Result shows: "TARGET('QL.IN.APP1')"
3. Now search/query the TARGET: Call runmqsc(qmgr_name='MQQMGR1', mqsc_command='DISPLAY QLOCAL(QL.IN.APP1) CURDEPTH')
   → Result shows: "Queue QL.IN.APP1 current depth is 85"
4. Return: "Alias QA.IN.APP1 points to QL.IN.APP1. The target queue has current depth: 85"

DON'T DO THIS:
✗ Call search_qmgr_dump and then ask "which queue manager?"
✗ Return alias definition and stop - always resolve to target
✗ Ask user for confirmation before calling runmqsc
✗ Report "no depth info" for alias - query the target queue instead
✗ Query only MQQMGR1 when queue exists on both MQQMGR1 and MQQMGR2"""
        
        # Multi-turn tool calling loop
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            print(f"   [Iteration {iteration}]")
            
            # Get LLM response
            response = client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": system_prompt},
                    *self.conversation_history
                ],
                tools=self.tools_openai,
                tool_choice="auto"
            )
            
            message = response.choices[0].message
            
            # Check if LLM wants to call a tool
            if message.tool_calls:
                print(f"🔧 GPT-4 decided to call tools...")
                
                # Add assistant message to history
                self.conversation_history.append(message)
                
                # Execute each tool call
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)
                    
                    # Track this tool usage
                    self.tools_used.append({
                        "name": tool_name,
                        "args": tool_args
                    })
                    
                    print(f"   📞 Calling: {tool_name}({tool_args})")
                    
                    # Call the MCP tool
                    with MetricsTracker(logger, tool_name, {"provider": self.provider, "args": tool_args}):
                        result = await self.session.call_tool(tool_name, tool_args)
                    tool_result = result.content[0].text
                    
                    # Add tool result to history
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result
                    })
                
                # Continue loop to allow multi-turn tool calling
                continue
            else:
                # LLM provided a text response (no more tool calls)
                final_message = message.content
                self.conversation_history.append({
                    "role": "assistant",
                    "content": final_message
                })
                
                return final_message
        
        # Fallback if max iterations reached
        return "❌ Maximum tool calls exceeded. Unable to complete request."
            
    async def handle_with_anthropic(self, user_input: str) -> str:
        """Use Anthropic Claude to handle the request"""
        if not HAS_ANTHROPIC:
            return "❌ Anthropic library not installed. Run: pip install anthropic"
            
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return "❌ ANTHROPIC_API_KEY environment variable not set"
            
        client = anthropic.Anthropic(api_key=api_key)
        
        print("🤖 Asking Claude...")
        
        system_prompt = """You are an IBM MQ expert assistant. Your PRIMARY JOB is to call tools to answer user questions. Do NOT ask users for input.

QUEUE NAMING CONVENTIONS - YOU MUST KNOW THESE:
- QL* = Local Queue (e.g., QL.IN.APP1, QL.OUT.APP2)
- QA* = Alias Queue (e.g., QA.IN.APP1 - points to another queue via TARGET)
- QR* = Remote Queue (e.g., QR.REMOTE.Q - references queue on remote QM)
- Others = System/Application specific queues

CRITICAL HANDLING FOR ALIAS QUEUES:
When user asks about depth of a QA* (alias) queue:
1. Search for the alias queue to find its TARGET queue name
2. If TARGET is a QL* queue, also search for and query that QL* queue
3. Report BOTH: The alias → target mapping AND the actual depth of the target queue
4. Example: User asks "depth of QA.IN.APP1"
   - Find QA.IN.APP1 → TARGET('QL.IN.APP1')
   - Query QL.IN.APP1 for CURDEPTH
   - Response: "Alias QA.IN.APP1 points to QL.IN.APP1, which has current depth: 42"

MANDATORY RULES - YOU MUST FOLLOW THESE:
1. When a user asks about ANY queue, ALWAYS search for it first using search_qmgr_dump
2. When search results show queue manager info, IMMEDIATELY extract ALL queue manager names
3. **CRITICAL**: If a queue exists on MULTIPLE queue managers, you MUST query ALL of them
4. NEVER ask "which queue manager?" if search results already show it
5. ALWAYS make the next tool call in the SAME iteration - do not wait for user response
6. If querying an ALIAS queue for depth:
   - Query the alias to see its TARGET
   - Then query the TARGET queue (if QL* prefix) for actual depth
7. Queue depth MQSC commands:
   - Local (QL*): DISPLAY QLOCAL(<QUEUE_NAME>) CURDEPTH
   - Remote (QR*): DISPLAY QREMOTE(<QUEUE_NAME>) CURDEPTH
   - Alias (QA*): DISPLAY QALIAS(<QUEUE_NAME>) to see TARGET
8. Queue Status:
   - Command: DISPLAY QSTATUS(<QUEUE_NAME>) TYPE(QUEUE) ALL
   - Purpose: Check Open Input/Output Count (IPPROCS/OPPROCS)
9. Cluster Queues:
   - Command: DISPLAY QLOCAL(<QUEUE_NAME>) CLUSTER
   - If CLUSTER attribute is NOT empty, it is a cluster queue.
   - List ALL Queue Managers found in the initial 'search_qmgr_dump' step as hosting this cluster queue.
10. COMPLETE THE WORKFLOW - user asks question → search → identify ALL QMs → runmqsc on EACH → return answer

YOU MUST NOT:
- Ask "which queue manager?" when search already found it
- Stop at alias queue definition - resolve to target and get actual data
- Wait for user input when you can call tools
- Provide generic MQ command examples instead of actual values
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

Example 3 - Alias Queue (THE KEY DIFFERENCE):
User: "What is the current depth of queue QA.IN.APP1?"
YOU MUST:
1. Call search_qmgr_dump('QA.IN.APP1') → finds "QA.IN.APP1 | MQQMGR1 | QALIAS"
2. Call runmqsc(qmgr_name='MQQMGR1', mqsc_command='DISPLAY QALIAS(QA.IN.APP1)') 
   → Result shows: "TARGET('QL.IN.APP1')"
3. Now search/query the TARGET: Call runmqsc(qmgr_name='MQQMGR1', mqsc_command='DISPLAY QLOCAL(QL.IN.APP1) CURDEPTH')
   → Result shows: "Queue QL.IN.APP1 current depth is 85"
4. Return: "Alias QA.IN.APP1 points to QL.IN.APP1. The target queue has current depth: 85"

DON'T DO THIS:
✗ Call search_qmgr_dump and then ask "which queue manager?"
✗ Return alias definition and stop - always resolve to target
✗ Ask user for confirmation before calling runmqsc
✗ Report "no depth info" for alias - query the target queue instead
✗ Query only MQQMGR1 when queue exists on both MQQMGR1 and MQQMGR2"""
        
        # Multi-turn tool calling loop for Claude
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            print(f"   [Iteration {iteration}]")
            
            # Get Claude's response
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2048,
                system=system_prompt,
                tools=self.tools_anthropic,
                messages=self.conversation_history
            )
            
            # Check for tool use
            has_tool_use = any(block.type == "tool_use" for block in response.content)
            
            if has_tool_use:
                print(f"🔧 Claude decided to call tools...")
                
                # Add assistant response to history (for tracking tool calls)
                self.conversation_history.append({
                    "role": "assistant",
                    "content": response.content
                })
                
                # Collect tool results
                tool_results = []
                
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        
                        # Track this tool usage
                        self.tools_used.append({
                            "name": tool_name,
                            "args": tool_input
                        })
                        
                        print(f"   📞 Calling: {tool_name}({tool_input})")
                        
                        # Call MCP tool
                        with MetricsTracker(logger, tool_name, {"provider": self.provider, "args": tool_input}):
                            result = await self.session.call_tool(tool_name, tool_input)
                        tool_result = result.content[0].text
                        
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_result
                        })
                
                # Add tool results to history
                self.conversation_history.append({
                    "role": "user",
                    "content": tool_results
                })
                
                # Continue loop to allow multi-turn tool calling
                continue
            else:
                # No tool use, extract text response
                final_message = response.content[0].text
                
                # Add final response to history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": final_message
                })
                
                return final_message
        
        # Fallback if max iterations reached
        return "❌ Maximum tool calls exceeded. Unable to complete request."
            
    async def handle_user_input(self, user_input: str) -> str:
        """Handle user input using the configured LLM provider"""
        print(f"\n💬 User: {user_input}")
        print("-" * 70)
        
        # Reset tools used for this specific request (but keep conversation history)
        self.tools_used = []
        
        if self.provider == "openai":
            return await self.handle_with_openai(user_input)
        elif self.provider == "anthropic":
            return await self.handle_with_anthropic(user_input)
        else:
            return f"❌ Unknown provider: {self.provider}"
            
    async def interactive_mode(self):
        """Run in interactive mode"""
        print("=" * 70)
        print("🤖 LLM-Based MQ Assistant")
        print(f"   Provider: {self.provider.upper()}")
        print("=" * 70)
        print("\nI can help you with IBM MQ operations using natural language!")
        print("Type 'quit' to exit.\n")
        
        while True:
            try:
                user_input = input("\n💬 You: ").strip()
                
                if not user_input:
                    continue
                    
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("\n👋 Goodbye!")
                    break
                    
                # Process the input
                response = await self.handle_user_input(user_input)
                print(f"\n🤖 Assistant:\n{response}")
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                import traceback
                traceback.print_exc()


async def main():
    """Main entry point"""
    
    # Determine which provider to use
    provider = "openai"  # default
    
    if os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        provider = "anthropic"
    
    print(f"\n🔍 Using provider: {provider.upper()}")
    
    if provider == "openai" and not HAS_OPENAI:
        print("❌ OpenAI library not installed. Run: pip install openai")
        return
        
    if provider == "anthropic" and not HAS_ANTHROPIC:
        print("❌ Anthropic library not installed. Run: pip install anthropic")
        return
    
    client = LLMToolCaller(provider=provider)
    
    try:
        await client.connect()
        await client.interactive_mode()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════╗
║  LLM-Based Dynamic Tool Calling                                  ║
║                                                                  ║
║  This uses an LLM (OpenAI GPT-4 or Anthropic Claude) to         ║
║  intelligently decide which MCP tools to call based on your     ║
║  natural language queries.                                      ║
║                                                                  ║
║  Setup:                                                         ║
║  1. pip install openai anthropic                               ║
║  2. Set OPENAI_API_KEY or ANTHROPIC_API_KEY                    ║
║  3. Run this script                                            ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")

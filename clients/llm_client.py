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
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
            }
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
            }
        ]
        
    async def connect(self):
        """Connect to the MCP server"""
        print("🔌 Connecting to MCP server...")
        
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script]
        )
        
        self.client_context = stdio_client(server_params)
        read, write = await self.client_context.__aenter__()
        
        self.session_context = ClientSession(read, write)
        self.session = await self.session_context.__aenter__()
        
        await self.session.initialize()
        print("✅ Connected to MCP server\n")
        
    async def disconnect(self):
        """Disconnect from the MCP server"""
        if self.session_context:
            await self.session_context.__aexit__(None, None, None)
        if self.client_context:
            await self.client_context.__aexit__(None, None, None)
            
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
        
        # Get LLM response
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are an IBM MQ expert assistant. Help users manage their MQ infrastructure using the available tools. Be concise and helpful."},
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
                
                print(f"   📞 Calling: {tool_name}({tool_args})")
                
                # Call the MCP tool
                result = await self.session.call_tool(tool_name, tool_args)
                tool_result = result.content[0].text
                
                # Add tool result to history
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result
                })
            
            # Get final response from LLM
            final_response = client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": "You are an IBM MQ expert assistant. Summarize the results in a clear, concise way."},
                    *self.conversation_history
                ]
            )
            
            final_message = final_response.choices[0].message.content
            self.conversation_history.append({
                "role": "assistant",
                "content": final_message
            })
            
            return final_message
        else:
            # No tool call needed
            self.conversation_history.append({
                "role": "assistant",
                "content": message.content
            })
            return message.content
            
    async def handle_with_anthropic(self, user_input: str) -> str:
        """Use Anthropic Claude to handle the request"""
        if not HAS_ANTHROPIC:
            return "❌ Anthropic library not installed. Run: pip install anthropic"
            
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return "❌ ANTHROPIC_API_KEY environment variable not set"
            
        client = anthropic.Anthropic(api_key=api_key)
        
        print("🤖 Asking Claude...")
        
        # Get Claude's response
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            system="You are an IBM MQ expert assistant. Help users manage their MQ infrastructure using the available tools. Be concise and helpful.",
            tools=self.tools_anthropic,
            messages=[
                {"role": "user", "content": user_input}
            ]
        )
        
        # Process response
        tool_results = []
        
        for block in response.content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                
                print(f"🔧 Claude decided to call: {tool_name}({tool_input})")
                
                # Call MCP tool
                result = await self.session.call_tool(tool_name, tool_input)
                tool_result = result.content[0].text
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": tool_result
                })
        
        # If tools were used, get final response
        if tool_results:
            final_response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2048,
                system="You are an IBM MQ expert assistant. Summarize the results in a clear, concise way.",
                messages=[
                    {"role": "user", "content": user_input},
                    {"role": "assistant", "content": response.content},
                    {"role": "user", "content": tool_results}
                ]
            )
            
            return final_response.content[0].text
        else:
            # No tools used, return text response
            return response.content[0].text
            
    async def handle_user_input(self, user_input: str) -> str:
        """Handle user input using the configured LLM provider"""
        print(f"\n💬 User: {user_input}")
        print("-" * 70)
        
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

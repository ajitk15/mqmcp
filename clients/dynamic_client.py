#!/usr/bin/env python3
"""
Dynamic Tool Calling Based on User Input

This script demonstrates how to dynamically call MCP tools based on natural language
user input. It uses keyword matching and intent detection to determine which tool
to call and what parameters to use.

This is useful for:
- Building chatbots that understand natural language
- Creating AI assistants that can interact with IBM MQ
- Automating MQ operations based on user queries
"""

import asyncio
import os
import re
import sys
from typing import Dict, List, Optional, Tuple
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
logger = get_metrics_logger("mq-dynamic-client")


class DynamicMQClient:
    """
    A client that dynamically calls MCP tools based on user input.
    Uses pattern matching and keyword detection to determine intent.
    """
    
    def __init__(self, server_script=None):
        if server_script is None:
            # Get the path to the server script relative to this script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            server_script = os.path.join(script_dir, "..", "server", "mqmcpserver.py")
        self.server_script = server_script
        self.session = None
        
        # Define patterns for intent detection
        self.intent_patterns = {
            'list_qmgrs': [
                r'list.*queue\s*managers?',
                r'show.*queue\s*managers?',
                r'display.*queue\s*managers?',
                r'what.*queue\s*managers?',
                r'get.*queue\s*managers?',
                r'\bdspmq\b',
            ],
            'check_queue_depth': [
                r'depth.*(?:of|for)\s+([\w\.]+)',
                r'how\s+many.*messages.*(?:in|on)\s+([\w\.]+)',
                r'check.*queue\s+([\w\.]+)',
                r'([\w\.]+)\s+depth',
                r'messages.*(?:in|on)\s+([\w\.]+)',
            ],
            'list_queues': [
                r'list.*queues?',
                r'show.*queues?',
                r'display.*queues?',
                r'what.*queues?',
                r'get.*queues?',
                r'all.*queues?',
            ],
            'list_channels': [
                r'list.*channels?',
                r'show.*channels?',
                r'display.*channels?',
                r'what.*channels?',
                r'get.*channels?',
            ],
            'queue_status': [
                r'queue\s*status.*(?:of|for)\s+([\w\.]+)',
                r'status.*queue\s+([\w\.]+)',
                r'check\s*queue\s*([\w\.]+)',
            ],
            'channel_status': [
                r'channel\s*status.*(?:of|for)\s+([\w\.]+)',
                r'status.*channel\s+([\w\.]+)',
                r'is\s+channel\s+([\w\.]+)\s+running',
            ],
            'listener_status': [
                r'listener\s*status',
                r'show\s*listeners',
                r'list\s*listeners',
            ],
            'qmgr_props': [
                r'properties.*(?:of|for)\s+queue\s*manager',
                r'qmgr\s*info',
                r'display\s*qmgr',
            ],
            'check_version': [
                r'\bversion\b',
                r'\bdspmqver\b',
                r'installation\s*info',
                r'what\s*version',
                r'show\s*version',
                r'mq\s*version',
            ],
        }
        
    async def connect(self):
        """Connect to the MCP server"""
        print("[CONN] Connecting to MCP server...")
        
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script]
        )
        
        self.client_context = stdio_client(server_params)
        read, write = await self.client_context.__aenter__()
        
        self.session_context = ClientSession(read, write)
        self.session = await self.session_context.__aenter__()
        
        await self.session.initialize()
        print("[CONN] Connected to MCP server\n")
        
    async def disconnect(self):
        """Disconnect from the MCP server"""
        if self.session_context:
            await self.session_context.__aexit__(None, None, None)
        if self.client_context:
            await self.client_context.__aexit__(None, None, None)
            
    def detect_intent(self, user_input: str) -> Tuple[str, Optional[Dict]]:
        """
        Detect user intent from natural language input.
        
        Returns:
            Tuple of (intent_name, extracted_parameters)
        """
        user_input_lower = user_input.lower().strip()
        
        # Check each intent pattern
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, user_input_lower, re.IGNORECASE)
                if match:
                    # Extract parameters if captured in pattern
                    params = {}
                    if match.groups():
                        params['entity'] = match.group(1).upper()
                    return intent, params
                    
        return 'unknown', None
        
    def extract_queue_manager(self, user_input: str) -> Optional[str]:
        """
        Extract queue manager name from user input.
        Common patterns: "on QM1", "from QM1", "QM1", etc.
        """
        # Pattern: "on/from/in/for QMGR_NAME"
        match = re.search(r'(?:on|from|in|for)\s+([A-Z0-9_\.]+)', user_input, re.IGNORECASE)
        if match:
            return match.group(1).upper()
            
        # Pattern: standalone word with dots or uppercase (likely queue manager)
        match = re.search(r'\b([A-Z][A-Z0-9_\.]{2,})\b', user_input)
        if match:
            return match.group(1).upper()
            
        return None
        
    async def handle_user_input(self, user_input: str) -> str:
        """
        Process user input and dynamically call the appropriate MCP tool.
        
        Args:
            user_input: Natural language query from user
            
        Returns:
            Response string with results
        """
        print(f"[USER]: {user_input}")
        print("-" * 70)
        
        # Detect intent
        intent, params = self.detect_intent(user_input)
        
        if intent == 'unknown':
            return self._handle_unknown_intent(user_input)
            
        # Extract queue manager if needed
        qmgr = self.extract_queue_manager(user_input)
        
        # Route to appropriate handler
        if intent == 'list_qmgrs':
            return await self._handle_list_qmgrs()
        elif intent == 'check_queue_depth':
            queue_name = params.get('entity', 'UNKNOWN')
            return await self._handle_check_queue_depth(qmgr, queue_name, user_input)
        elif intent == 'list_queues':
            return await self._handle_list_queues(qmgr, user_input)
        elif intent == 'list_channels':
            return await self._handle_list_channels(qmgr, user_input)
        elif intent == 'queue_status':
            queue_name = params.get('entity', 'UNKNOWN')
            return await self._handle_queue_status(qmgr, queue_name, user_input)
        elif intent == 'channel_status':
            channel_name = params.get('entity', 'UNKNOWN')
            return await self._handle_channel_status(qmgr, channel_name, user_input)
            
        elif intent == 'listener_status':
            return await self._handle_listener_status(qmgr, user_input)
            
        elif intent == 'qmgr_props':
            return await self._handle_qmgr_props(qmgr, user_input)
            
        elif intent == 'check_version':
            return await self._handle_check_version()
            
        else:
            return "I'm not sure how to help with that. Try asking to list queue managers or check a queue depth."
            
    async def _handle_list_qmgrs(self) -> str:
        """Handle listing queue managers"""
        print("    Detected intent: List Queue Managers")
        print("    Calling tool: dspmq")
        
        try:
            with MetricsTracker(logger, "dspmq", {"interface": "dynamic_client"}):
                result = await self.session.call_tool("dspmq", {})
            return f"**Tool:** `dspmq`\n**Command:** `dspmq`\n\n**Result:**\n{result.content[0].text}"
        except Exception as e:
            return f"Error: {e}"

    async def _handle_check_version(self) -> str:
        """Handle checking version"""
        print("    Detected intent: Check Version")
        print("    Calling tool: dspmqver")
        
        try:
            with MetricsTracker(logger, "dspmqver", {"interface": "dynamic_client"}):
                result = await self.session.call_tool("dspmqver", {})
            return f"**Tool:** `dspmqver`\n**Command:** `dspmqver`\n\n**Result:**\n{result.content[0].text}"
        except Exception as e:
            return f"Error: {e}"
            
    async def _handle_check_queue_depth(self, qmgr: Optional[str], queue_name: str, user_input: str) -> str:
        """Handle checking queue depth"""
        print(f"    Detected intent: Check Queue Depth")
        print(f"   Queue: {queue_name}")
        
        # If queue manager not detected, ask for it
        if not qmgr:
            return "I need to know which queue manager to check. Please specify it (e.g., 'Check depth of MYQUEUE on QM1')"
            
        print(f"   Queue Manager: {qmgr}")
        print(f"    Calling tool: runmqsc")
        
        mqsc_command = f"DISPLAY QLOCAL({queue_name}) CURDEPTH"
        
        try:
            with MetricsTracker(logger, "runmqsc", {"qmgr": qmgr, "cmd": mqsc_command}):
                result = await self.session.call_tool("runmqsc", {
                    "qmgr_name": qmgr,
                    "mqsc_command": mqsc_command
                })
            return f"**Tool:** `runmqsc`\n**Command:** `runmqsc` ({qmgr}) -> `{mqsc_command}`\n\n**Result:**\n{result.content[0].text}"
        except Exception as e:
            return f"Error: {e}"
            
    async def _handle_list_queues(self, qmgr: Optional[str], user_input: str) -> str:
        """Handle listing all queues"""
        print(f"    Detected intent: List Queues")
        
        if not qmgr:
            return "Please specify the queue manager (e.g., 'List all queues on QM1')"
            
        print(f"   Queue Manager: {qmgr}")
        print(f"    Calling tool: runmqsc")
        
        mqsc_command = "DISPLAY QLOCAL(*)"
        
        try:
            with MetricsTracker(logger, "runmqsc", {"qmgr": qmgr, "cmd": mqsc_command}):
                result = await self.session.call_tool("runmqsc", {
                    "qmgr_name": qmgr,
                    "mqsc_command": mqsc_command
                })
            return f"**Tool:** `runmqsc`\n**Command:** `runmqsc` ({qmgr}) -> `{mqsc_command}`\n\n**Result:**\n{result.content[0].text}"
        except Exception as e:
            return f"Error: {e}"
            
    async def _handle_list_channels(self, qmgr: Optional[str], user_input: str) -> str:
        """Handle listing channels"""
        print(f"    Detected intent: List Channels")
        
        if not qmgr:
            return "Please specify the queue manager (e.g., 'Show channels on QM1')"
            
        print(f"   Queue Manager: {qmgr}")
        print(f"    Calling tool: runmqsc")
        
        mqsc_command = "DISPLAY CHANNEL(*)"
        
        try:
            with MetricsTracker(logger, "runmqsc", {"qmgr": qmgr, "cmd": mqsc_command}):
                result = await self.session.call_tool("runmqsc", {
                    "qmgr_name": qmgr,
                    "mqsc_command": mqsc_command
                })
            return f"**Tool:** `runmqsc`\n**Command:** `runmqsc` ({qmgr}) -> `{mqsc_command}`\n\n**Result:**\n{result.content[0].text}"
        except Exception as e:
            return f"Error: {e}"
            
    async def _handle_queue_status(self, qmgr: Optional[str], queue_name: str, user_input: str) -> str:
        """Handle getting queue status"""
        print(f"    Detected intent: Queue Status")
        print(f"   Queue: {queue_name}")
        
        if not qmgr:
            return "Please specify the queue manager (e.g., 'Status of MYQUEUE on QM1')"
            
        print(f"   Queue Manager: {qmgr}")
        print(f"    Calling tool: runmqsc")
        
        mqsc_command = f"DISPLAY QSTATUS({queue_name})"
        
        try:
            with MetricsTracker(logger, "runmqsc", {"qmgr": qmgr, "cmd": mqsc_command, "queue": queue_name}):
                result = await self.session.call_tool("runmqsc", {
                    "qmgr_name": qmgr,
                    "mqsc_command": mqsc_command
                })
            return f"**Tool:** `runmqsc`\n**Command:** `runmqsc` ({qmgr}) -> `{mqsc_command}`\n\n**Result:**\n{result.content[0].text}"
        except Exception as e:
            return f"Error: {e}"

    async def _handle_channel_status(self, qmgr: Optional[str], channel_name: str, user_input: str) -> str:
        """Handle getting channel status"""
        print(f"    Detected intent: Channel Status")
        print(f"   Channel: {channel_name}")
        if not qmgr:
            return "Please specify the queue manager (e.g., 'Status of channel TO.QM2 on QM1')"
        
        print(f"   Queue Manager: {qmgr}")
        print(f"    Calling tool: runmqsc")
        
        mqsc_command = f"DISPLAY CHSTATUS({channel_name})"
        try:
            with MetricsTracker(logger, "runmqsc", {"qmgr": qmgr, "cmd": mqsc_command, "channel": channel_name}):
                result = await self.session.call_tool("runmqsc", {
                    "qmgr_name": qmgr,
                    "mqsc_command": mqsc_command
                })
            return f"**Tool:** `runmqsc`\n**Command:** `runmqsc` ({qmgr}) -> `{mqsc_command}`\n\n**Result:**\n{result.content[0].text}"
        except Exception as e:
            return f"Error: {e}"

    async def _handle_listener_status(self, qmgr: Optional[str], user_input: str) -> str:
        """Handle listing listener status"""
        print(f"    Detected intent: Listener Status")
        if not qmgr:
            return "Please specify the queue manager (e.g., 'Show listeners on QM1')"
            
        print(f"   Queue Manager: {qmgr}")
        print(f"    Calling tool: runmqsc")
        
        mqsc_command = "DISPLAY LSSTATUS(*)"
        try:
            with MetricsTracker(logger, "runmqsc", {"qmgr": qmgr, "cmd": mqsc_command}):
                result = await self.session.call_tool("runmqsc", {
                    "qmgr_name": qmgr,
                    "mqsc_command": mqsc_command
                })
            return f"**Tool:** `runmqsc`\n**Command:** `runmqsc` ({qmgr}) -> `{mqsc_command}`\n\n**Result:**\n{result.content[0].text}"
        except Exception as e:
            return f"Error: {e}"

    async def _handle_qmgr_props(self, qmgr: Optional[str], user_input: str) -> str:
        """Handle displaying qmgr properties"""
        print(f"    Detected intent: Queue Manager Properties")
        if not qmgr:
            return "Please specify the queue manager (e.g., 'Show qmgr info for QM1')"
            
        print(f"   Queue Manager: {qmgr}")
        print(f"    Calling tool: runmqsc")
        
        mqsc_command = "DISPLAY QMGR"
        try:
            with MetricsTracker(logger, "runmqsc", {"qmgr": qmgr, "cmd": mqsc_command}):
                result = await self.session.call_tool("runmqsc", {
                    "qmgr_name": qmgr,
                    "mqsc_command": mqsc_command
                })
            return f"**Tool:** `runmqsc`\n**Command:** `runmqsc` ({qmgr}) -> `{mqsc_command}`\n\n**Result:**\n{result.content[0].text}"
        except Exception as e:
            return f"Error: {e}"
            
    def _handle_unknown_intent(self, user_input: str) -> str:
        """Handle unknown intents"""
        print("    Detected intent: Unknown")
        return """
[HELP] I didn't understand that request. Here are some examples:

List Queue Managers:
   - "List all queue managers"
   - "Show queue managers"
   - "dspmq"

Check Queue Depth:
   - "What's the depth of MYQUEUE on QM1?"
   - "Check queue MYQUEUE"
   - "How many messages in MYQUEUE?"

List Queues:
   - "List all queues on QM1"
   - "Show queues"

List Channels:
   - "List channels on QM1"
   - "Show all channels"

Queue Status:
   - "Status of MYQUEUE on QM1"
   - "Check MYQUEUE"
"""

    async def interactive_mode(self):
        """Run in interactive mode with continuous user input"""
        print("=" * 70)
        print("      Dynamic MQ Assistant - Natural Language Interface")
        print("=" * 70)
        print("\nI can help you with IBM MQ operations using natural language!")
        print("Type 'help' for examples, 'quit' to exit.\n")
        
        while True:
            try:
                user_input = input("[YOU]: ").strip()
                
                if not user_input:
                    continue
                    
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("Goodbye!")
                    break
                    
                if user_input.lower() == 'help':
                    print(self._handle_unknown_intent(""))
                    continue
                    
                # Process the input
                response = await self.handle_user_input(user_input)
                print(f"[ASSISTANT] Response:\n{response}")
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")


async def main():
    """Main entry point"""
    client = DynamicMQClient()
    
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
║  Dynamic Tool Calling - Natural Language MQ Assistant           ║
║                                                                  ║
║  This demonstrates how to dynamically call MCP tools based on   ║
║  natural language user input using pattern matching and         ║
║  intent detection.                                              ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")

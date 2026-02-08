#!/usr/bin/env python3
"""
Interactive MCP Client for Testing IBM MQ MCP Server

This client allows you to test the MCP server with custom user inputs.
It provides an interactive command-line interface to call the dspmq and runmqsc tools.
"""

import asyncio
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPTestClient:
    """Interactive test client for MCP server"""
    
    def __init__(self, server_script=None):
        if server_script is None:
            # Get the path to the server script relative to this script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            server_script = os.path.join(script_dir, "..", "server", "mqmcpserver.py")
        self.server_script = server_script
        self.session = None
        
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
        
        # Initialize the session
        await self.session.initialize()
        print("✅ Connected to MCP server successfully!\n")
        
    async def disconnect(self):
        """Disconnect from the MCP server"""
        if self.session_context:
            await self.session_context.__aexit__(None, None, None)
        if self.client_context:
            await self.client_context.__aexit__(None, None, None)
        print("\n👋 Disconnected from MCP server")
        
    async def list_tools(self):
        """List all available tools"""
        tools_response = await self.session.list_tools()
        
        print("📋 Available Tools:")
        print("=" * 60)
        for i, tool in enumerate(tools_response.tools, 1):
            print(f"\n{i}. {tool.name}")
            print(f"   Description: {tool.description}")
            if hasattr(tool, 'inputSchema') and tool.inputSchema:
                print(f"   Parameters: {tool.inputSchema.get('properties', {}).keys()}")
        print("=" * 60)
        
    async def call_dspmq(self):
        """Call the dspmq tool"""
        print("\n🔍 Calling dspmq (List Queue Managers)...")
        print("-" * 60)
        
        try:
            result = await self.session.call_tool("dspmq", {})
            
            if result.content and len(result.content) > 0:
                print("✅ Result:")
                print(result.content[0].text)
            else:
                print("⚠️  No content returned")
                
        except Exception as e:
            print(f"❌ Error calling dspmq: {e}")
            
    async def call_dspmqver(self):
        """Call the dspmqver tool"""
        print("\n🔍 Calling dspmqver (Check MQ Version)...")
        print("-" * 60)
        
        try:
            result = await self.session.call_tool("dspmqver", {})
            
            if result.content and len(result.content) > 0:
                print("✅ Result:")
                print(result.content[0].text)
            else:
                print("⚠️  No content returned")
                
        except Exception as e:
            print(f"❌ Error calling dspmqver: {e}")
            
    async def call_runmqsc(self, qmgr_name=None, mqsc_command=None):
        """Call the runmqsc tool"""
        print("\n🔧 Calling runmqsc (Execute MQSC Command)...")
        print("-" * 60)
        
        # Get queue manager name if not provided
        if qmgr_name is None:
            qmgr_name = input("Enter Queue Manager Name (e.g., QM1): ").strip()
            if not qmgr_name:
                print("❌ Queue manager name is required!")
                return
                
        # Get MQSC command if not provided
        if mqsc_command is None:
            print("\nExample commands:")
            print("  - DISPLAY QLOCAL(*)")
            print("  - DISPLAY QLOCAL(MYQUEUE) CURDEPTH")
            print("  - DISPLAY CHANNEL(*)")
            mqsc_command = input("\nEnter MQSC Command: ").strip()
            if not mqsc_command:
                print("❌ MQSC command is required!")
                return
        
        print(f"\n📤 Executing: {mqsc_command}")
        print(f"   On Queue Manager: {qmgr_name}")
        print("-" * 60)
        
        try:
            result = await self.session.call_tool("runmqsc", {
                "qmgr_name": qmgr_name,
                "mqsc_command": mqsc_command
            })
            
            if result.content and len(result.content) > 0:
                print("✅ Result:")
                print(result.content[0].text)
            else:
                print("⚠️  No content returned")
                
        except Exception as e:
            print(f"❌ Error calling runmqsc: {e}")
            
    async def interactive_menu(self):
        """Display interactive menu and handle user choices"""
        while True:
            print("\n" + "=" * 60)
            print("🧪 IBM MQ MCP Server - Interactive Test Client")
            print("=" * 60)
            print("\nChoose an option:")
            print("  1. List available tools")
            print("  2. Call dspmq (List Queue Managers)")
            print("  3. Call dspmqver (Check MQ Version)")
            print("  4. Call runmqsc (Execute MQSC Command)")
            print("  5. Quick test - Check queue depth")
            print("  6. Quick test - List all queues")
            print("  0. Exit")
            print("-" * 60)
            
            choice = input("\nEnter your choice (0-5): ").strip()
            
            if choice == "0":
                print("\n👋 Exiting...")
                break
            elif choice == "1":
                await self.list_tools()
            elif choice == "2":
                await self.call_dspmq()
            elif choice == "3":
                await self.call_dspmqver()
            elif choice == "4":
                await self.call_runmqsc()
            elif choice == "5":
                # Quick test for checking queue depth
                qmgr = input("Enter Queue Manager Name: ").strip()
                queue = input("Enter Queue Name: ").strip()
                if qmgr and queue:
                    await self.call_runmqsc(qmgr, f"DISPLAY QLOCAL({queue}) CURDEPTH")
            elif choice == "6":
                # Quick test for listing all queues
                qmgr = input("Enter Queue Manager Name: ").strip()
                if qmgr:
                    await self.call_runmqsc(qmgr, "DISPLAY QLOCAL(*)")
            else:
                print("❌ Invalid choice! Please enter a number between 0 and 6.")
                
            # Pause before showing menu again
            if choice != "0":
                input("\nPress Enter to continue...")


async def main():
    """Main entry point"""
    print("=" * 60)
    print("🚀 IBM MQ MCP Server - Interactive Test Client")
    print("=" * 60)
    print("\nThis client will help you test the MCP server interactively.")
    print("Make sure the MCP server configuration is correct before testing.\n")
    
    client = MCPTestClient()
    
    try:
        await client.connect()
        await client.interactive_menu()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)

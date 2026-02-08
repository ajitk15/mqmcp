#!/usr/bin/env python3
"""
Simple MCP Client Test Script

A basic script to quickly test the MCP server functionality.
This is a simpler alternative to the interactive client.
"""

import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_mcp_server():
    """Test the MCP server with predefined commands"""
    
    print("=" * 70)
    print("🧪 Testing IBM MQ MCP Server")
    print("=" * 70)
    
    # Get the path to the server script relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    server_script = os.path.join(script_dir, "..", "server", "mqmcpserver.py")
    
    # Configure server parameters
    server_params = StdioServerParameters(
        command="python",
        args=[server_script]
    )
    
    print("\n🔌 Connecting to MCP server...")
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()
            print("✅ Connected successfully!\n")
            
            # List available tools
            print("-" * 70)
            print("📋 Available Tools:")
            print("-" * 70)
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f"  • {tool.name}")
                print(f"    {tool.description}")
            
            # Test 1: Call dspmq
            print("\n" + "=" * 70)
            print("TEST 1: Listing Queue Managers (dspmq)")
            print("=" * 70)
            try:
                result = await session.call_tool("dspmq", {})
                print("✅ Result:")
                print(result.content[0].text)
            except Exception as e:
                print(f"❌ Error: {e}")
            
            # Test 2: Call runmqsc with example command
            print("\n" + "=" * 70)
            print("TEST 2: Running MQSC Command (runmqsc)")
            print("=" * 70)
            
            # You can modify these values for your environment
            qmgr_name = input("\nEnter Queue Manager Name (or press Enter for 'QM1'): ").strip() or "QM1"
            mqsc_command = input("Enter MQSC Command (or press Enter for 'DISPLAY QLOCAL(*)'): ").strip() or "DISPLAY QLOCAL(*)"
            
            print(f"\n📤 Executing: {mqsc_command}")
            print(f"   On: {qmgr_name}")
            print("-" * 70)
            
            try:
                result = await session.call_tool("runmqsc", {
                    "qmgr_name": qmgr_name,
                    "mqsc_command": mqsc_command
                })
                print("✅ Result:")
                print(result.content[0].text)
            except Exception as e:
                print(f"❌ Error: {e}")
            
            print("\n" + "=" * 70)
            print("✅ Testing completed!")
            print("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(test_mcp_server())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()

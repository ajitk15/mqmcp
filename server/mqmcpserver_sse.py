#
# Copyright (c) 2025 IBM Corp.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import httpx
import json
import sys
import asyncio

import os
from typing import Any
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables from .env file
# Try to find .env in current dir or parent dir (to handle different launch paths)
env_path = os.path.join(os.getcwd(), ".env")
if not os.path.exists(env_path):
    # Try one level up if we are in server/ directory
    env_path = os.path.join(os.path.dirname(os.getcwd()), ".env")

load_dotenv(dotenv_path=env_path)

# Configuration from environment variables
URL_BASE = os.getenv("MQ_URL_BASE")
USER_NAME = os.getenv("MQ_USER_NAME")
PASSWORD = os.getenv("MQ_PASSWORD")

# Debugging: Write to stderr instead of stdout (Stdout is reserved for MCP protocol)
sys.stderr.write(f"DEBUG: Loading .env from {env_path}\n")
sys.stderr.write(f"DEBUG: Target MQ URL: {URL_BASE}\n")
sys.stderr.write(f"DEBUG: Target MQ User: {USER_NAME}\n")

if not URL_BASE or not USER_NAME:
    sys.stderr.write("❌ CRITICAL ERROR: MQ_URL_BASE or MQ_USER_NAME is not set in .env\n")

# Initialize FastMCP server
try:
    MCP_PORT = int(os.getenv("MQ_MCP_PORT", 8000))
except ValueError:
    sys.stderr.write("⚠️ Invalid MQ_MCP_PORT in .env, defaulting to 8000\n")
    MCP_PORT = 8000

sys.stderr.write(f"DEBUG: Starting MCP Server on port {MCP_PORT} (SSE)\n")
mcp = FastMCP("mqmcpserver", port=MCP_PORT)

@mcp.tool()
async def dspmq() -> str:
    """List available queue managers and whether they are running or not
    """
    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "token"
    }    
    
    url = URL_BASE + "qmgr/"

    auth = httpx.BasicAuth(username=USER_NAME, password=PASSWORD)
    async with httpx.AsyncClient(verify=False,auth=auth) as client:
        try:            
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return prettify_dspmq(response.content)
        except Exception as err:
            return f"❌ Connection Error: {str(err)}"
                        
# Put the output of for each queue manager on its own line, separated by ---                        
def prettify_dspmq(payload: str) -> str:
    jsonOutput = json.loads(payload.decode("utf-8"))
    prettifiedOutput="\n---\n"
    for x in jsonOutput['qmgr']:
      prettifiedOutput += "name = " + x['name'] + ", running = " + x['state'] + "\n---\n"
    
    return prettifiedOutput
    
@mcp.tool()
async def dspmqver() -> str:
    """Display IBM MQ version and installation information
    """
    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "token"
    }    
    
    url = URL_BASE + "installation"

    auth = httpx.BasicAuth(username=USER_NAME, password=PASSWORD)
    async with httpx.AsyncClient(verify=False,auth=auth) as client:
        try:            
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return prettify_dspmqver(response.content)
        except Exception as err:
            return f"❌ Connection Error: {str(err)}"

def prettify_dspmqver(payload: str) -> str:
    jsonOutput = json.loads(payload.decode("utf-8"))
    prettifiedOutput = "\n---\n"
    for x in jsonOutput['installation']:
        prettifiedOutput += f"Name: {x.get('name', 'N/A')}\n"
        prettifiedOutput += f"Version: {x.get('version', 'N/A')}\n"
        prettifiedOutput += f"Architecture: {x.get('architecture', 'N/A')}\n"
        prettifiedOutput += f"Installation Path: {x.get('installationPath', 'N/A')}\n"
        prettifiedOutput += "---\n"
    
    return prettifiedOutput

@mcp.tool()
async def runmqsc(qmgr_name: str, mqsc_command: str) -> str:
    """Run an MQSC command against a specific queue manager

    Args:
        qmgr_name: A queue manager name   
        mqsc_command: An MQSC command to run on the queue manager   
    """
    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": "a"
    }
    
    data = "{\"type\":\"runCommand\",\"parameters\":{\"command\":\"" + mqsc_command + "\"}}"
    
    url = URL_BASE + "action/qmgr/" + qmgr_name + "/mqsc"

    auth = httpx.BasicAuth(username=USER_NAME, password=PASSWORD)
    async with httpx.AsyncClient(verify=False,auth=auth) as client:
        try:            
            response = await client.post(url, data=data, headers=headers, timeout=30.0)
            response.raise_for_status()
            return prettify_runmqsc(response.content)
        except Exception as err:
            return f"❌ Connection Error: {str(err)}"
            
# Put the output of each MQSC command on its own line, separated by ---
# Deals with both z/OS and distributed queue managers
def prettify_runmqsc(payload: str) -> str:
    jsonOutput = json.loads(payload.decode("utf-8"))
    prettifiedOutput="\n---\n"
    for x in jsonOutput['commandResponse']:
        # z/OS
        if x['text'][0].startswith("CSQN205I"):
            # Remove leading and trailing messages, as they aren't needed. 
            x['text'].pop(0)            
            x['text'].pop()
            for y in x['text']:
                prettifiedOutput += y[15:] + "\n---\n"            
        # Distributed
        else:        
            for line in x['text']:
                if line.strip():
                    prettifiedOutput += line + "\n"
            prettifiedOutput += "---\n"
    
    return prettifiedOutput

async def verify_connectivity():
    """Verify that the MQ REST API is reachable before starting the server"""
    if not URL_BASE or not USER_NAME:
        return
        
    sys.stderr.write(f"DEBUG: Verifying connectivity to {URL_BASE}...\n")
    auth = httpx.BasicAuth(username=USER_NAME, password=PASSWORD)
    async with httpx.AsyncClient(verify=False, auth=auth) as client:
        try:
            # Try to hit the installation endpoint as a lightweight check
            response = await client.get(URL_BASE + "installation", timeout=5.0)
            if response.status_code == 200:
                sys.stderr.write("✅ SUCCESS: MQ REST API is responsive.\n")
            else:
                sys.stderr.write(f"⚠️ WARNING: MQ REST API returned status {response.status_code}. Please check your .env credentials.\n")
        except Exception as e:
            sys.stderr.write(f"❌ CRITICAL: Cannot reach MQ REST API. Ensure 'dspmqweb' is running on the MQ server.\n")
            sys.stderr.write(f"   Error: {str(e)}\n\n")

if __name__ == "__main__":
    # Perform pre-flight connectivity check
    try:
        asyncio.run(verify_connectivity())
    except Exception as e:
        sys.stderr.write(f"DEBUG: Connectivity check skipped or failed: {e}\n")

    # Initialize and run the server on http://127.0.0.1:8000/mcp
    #mcp.run(transport='streamable-http')
    # If using IBM Bob then use one of these
    # mcp.run(transport='stdio')
    # URL is http://127.0.0.1:8000/sse
    mcp.run(transport='sse')
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

import pandas as pd
from pathlib import Path

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

CSV_PATH = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "resources" / "qmgr_dump.csv"

def load_csv():
    """
    Load CSV into dataframe with pipe delimiter
    """
    if not CSV_PATH.exists():
        sys.stderr.write(f"⚠️ WARNING: CSV file not found at {CSV_PATH}\n")
        return pd.DataFrame()

    try:
        # Load CSV with pipe delimiter - no header row in the file
        # Format: hostname | qmgr | object_type | mqsc_command
        df = pd.read_csv(
            CSV_PATH, 
            delimiter="|", 
            skipinitialspace=True,
            header=None,  # No header row in CSV
            names=['hostname', 'qmgr', 'object_type', 'mqsc_command']  # Define column names explicitly
        )
        
        sys.stderr.write(f"✅ CSV loaded successfully: {len(df)} rows, {len(df.columns)} columns\n")
        sys.stderr.write(f"   Columns: {list(df.columns)}\n")
        return df
    except Exception as e:
        sys.stderr.write(f"❌ ERROR loading CSV: {str(e)}\n")
        import traceback
        sys.stderr.write(traceback.format_exc())
        return pd.DataFrame()


# Debugging: Write to stderr instead of stdout (Stdout is reserved for MCP protocol)
sys.stderr.write(f"DEBUG: Loading .env from {env_path}\n")
sys.stderr.write(f"DEBUG: Target MQ URL: {URL_BASE}\n")
sys.stderr.write(f"DEBUG: Target MQ User: {USER_NAME}\n")

if not URL_BASE or not USER_NAME:
    sys.stderr.write("❌ CRITICAL ERROR: MQ_URL_BASE or MQ_USER_NAME is not set in .env\n")

# Initialize FastMCP server
# Use MQ_MCP_HOST/PORT if set (useful if running in SSE mode via import)
mcp_host = os.getenv("MQ_MCP_HOST", "0.0.0.0")
mcp_port = int(os.getenv("MQ_MCP_PORT", 8000))

mcp = FastMCP("mqmcpserver", host=mcp_host, port=mcp_port)


@mcp.resource("qmgr://dump")
def get_qmgr_dump() -> list:
    """
    Return full QMGR dump as JSON
    """
    df = load_csv()

    if df.empty:
        return []

    return df.to_dict(orient="records")


@mcp.tool()
def search_qmgr_dump(search_string: str) -> str:
    """
    Search QMGR dump by any string and return matching records with hostname, queue manager, and object type.
    Returns a formatted string with the most relevant columns for quick identification.
    """

    sys.stderr.write(f"DEBUG: search_qmgr_dump called with search_string: '{search_string}'\n")

    df = load_csv()

    if df.empty:
        sys.stderr.write("DEBUG: CSV is empty. Returning empty result.\n")
        return f"No records found. CSV file may be empty."

    sys.stderr.write(f"DEBUG: CSV loaded with {len(df)} rows\n")
    sys.stderr.write(f"DEBUG: CSV columns: {list(df.columns)}\n")

    # Case-insensitive search across all columns
    mask = df.astype(str).apply(
        lambda row: row.str.contains(
            search_string,
            case=False,
            na=False
        ).any(),
        axis=1
    )

    result = df[mask]

    if result.empty:
        sys.stderr.write(f"DEBUG: No matching records found for '{search_string}'.\n")
        return f"❌ No records found matching '{search_string}'."

    sys.stderr.write(f"DEBUG: Found {len(result)} matching records\n")
    
    # Select relevant columns for display
    display_cols = result[['hostname', 'qmgr', 'object_type']].copy()
    
    # Remove exact duplicates
    display_cols = display_cols.drop_duplicates()
    sys.stderr.write(f"DEBUG: After removing duplicates: {len(display_cols)} unique records\n")
    
    # Format output as readable text with descriptive header
    output_lines = []
    output_lines.append(f"SEARCH RESULTS FOR: {search_string}")
    output_lines.append("=" * 100)
    
    for idx, row in display_cols.iterrows():
        hostname = str(row['hostname']).strip()
        qmgr = str(row['qmgr']).strip()
        obj_type = str(row['object_type']).strip()
        formatted_line = f"Queue Manager: {qmgr} | Hostname: {hostname} | Type: {obj_type}"
        output_lines.append(formatted_line)
        sys.stderr.write(f"DEBUG: Result line: {formatted_line}\n")
    
    output_lines.append("=" * 100)
    output_lines.append(f"SUMMARY: Found '{search_string}' on queue manager(s): {', '.join(display_cols['qmgr'].unique())}")
    
    result_text = "\n".join(output_lines)
    sys.stderr.write(f"DEBUG: Final output:\n{result_text}\n")
    return result_text


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
    # Initialize and run the server
    # Transport can be set via MQ_MCP_TRANSPORT (default: stdio)
    transport = os.getenv("MQ_MCP_TRANSPORT", "stdio")
    
    sys.stderr.write(f"DEBUG: Starting MCP Server with transport={transport}\n")
    mcp.run(transport=transport)
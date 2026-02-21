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

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Environment variables and Logging
# ---------------------------------------------------------------------------
# Try to find .env in cwd or one level up (handles different launch paths)
env_path = os.path.join(os.getcwd(), ".env")
if not os.path.exists(env_path):
    env_path = os.path.join(os.path.dirname(os.getcwd()), ".env")

load_dotenv(dotenv_path=env_path)

# ---------------------------------------------------------------------------
# Configure Logging Setup
# ---------------------------------------------------------------------------
log_level_str = os.getenv("MQ_LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

logging.basicConfig(
    level=log_level,
    stream=sys.stderr,
    format="%(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("mqmcpserver")

logger.debug("Loading .env from %s", env_path)

URL_BASE  = os.getenv("MQ_URL_BASE")
USER_NAME = os.getenv("MQ_USER_NAME")
PASSWORD  = os.getenv("MQ_PASSWORD")

logger.debug("Target MQ URL:  %s", URL_BASE)
logger.debug("Target MQ User: %s", USER_NAME)

if not URL_BASE or not USER_NAME:
    logger.error("CRITICAL: MQ_URL_BASE or MQ_USER_NAME is not set in .env")

# Allowed hostname prefixes for safety (excludes production)
ALLOWED_PREFIXES_STR = os.getenv("MQ_ALLOWED_HOSTNAME_PREFIXES", "lod,loq,lot")
ALLOWED_HOSTNAME_PREFIXES = [p.strip() for p in ALLOWED_PREFIXES_STR.split(",")]

# Standard CSRF token value accepted by IBM MQ REST API (any non-empty value works)
_CSRF_TOKEN = "token"

# ---------------------------------------------------------------------------
# CSV helpers — cached at module level so disk is only read once per startup
# ---------------------------------------------------------------------------
CSV_PATH = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "resources" / "qmgr_dump.csv"

_CSV_CACHE: pd.DataFrame | None = None


def _load_csv_from_disk() -> pd.DataFrame:
    """Read and parse the qmgr_dump CSV from disk."""
    if not CSV_PATH.exists():
        logger.warning("CSV file not found at %s", CSV_PATH)
        return pd.DataFrame()

    try:
        df = pd.read_csv(
            CSV_PATH,
            delimiter="|",
            skipinitialspace=True,
            header=0,
        )
        # Strip whitespace from all string columns and column names
        df.columns = [c.strip() for c in df.columns]
        df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

        df = df.rename(columns={
            "qmname":     "qmgr",
            "objecttype": "object_type",
            "objectdef":  "mqsc_command",
        })
        if "extractedat" in df.columns:
            df["extractedat"] = pd.to_datetime(df["extractedat"], errors="coerce")
        logger.info("CSV loaded successfully: %d rows, %d columns", len(df), len(df.columns))
        logger.debug("Columns: %s", list(df.columns))
        return df
    except Exception:
        logger.exception("ERROR loading CSV")
        return pd.DataFrame()


def load_csv() -> pd.DataFrame:
    """Return the cached CSV dataframe, loading from disk on first call."""
    global _CSV_CACHE
    if _CSV_CACHE is None:
        _CSV_CACHE = _load_csv_from_disk()
    return _CSV_CACHE


# ---------------------------------------------------------------------------
# Hostname allow-list guard
# ---------------------------------------------------------------------------
def is_hostname_allowed(hostname: str) -> tuple[bool, str]:
    """
    Check if a hostname is allowed based on prefix filtering.
    Returns (True, "") if allowed, or (False, "reason message") if blocked.
    """
    hostname_lower = hostname.lower().strip()
    for prefix in ALLOWED_HOSTNAME_PREFIXES:
        if hostname_lower.startswith(prefix.lower()):
            return True, ""

    allowed_list = ", ".join(ALLOWED_HOSTNAME_PREFIXES)
    message = (
        f"🚫 Access to this systems is restricted for safety. "
        f"This query targets hostname '{hostname}' which is not in the allowed list.\n\n"
    )
    return False, message


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------
mcp_host = os.getenv("MQ_MCP_HOST", "0.0.0.0")
mcp_port = int(os.getenv("MQ_MCP_PORT", 8000))
mcp = FastMCP("mqmcpserver", host=mcp_host, port=mcp_port)


@mcp.resource("qmgr://dump")
def get_qmgr_dump() -> list:
    """Return full QMGR dump as JSON."""
    df = load_csv()
    return [] if df.empty else df.to_dict(orient="records")


@mcp.tool()
def search_qmgr_dump(search_string: str, object_type: str | None = None) -> str:
    """
    Search QM dump for a string to find which QM hosts an object.
    
    Args:
        search_string: String to search (e.g., queue name)
        object_type: Optional filter (e.g., 'QLOCAL', 'QUEUES', 'CHANNEL')
    """
    df = load_csv()
    if df.empty:
        return "No records found. CSV file may be empty."

    # 1. Total search across all allowed (and disallowed) columns first to see if it even exists
    total_matches = df[df.astype(str).apply(
        lambda row: row.str.contains(re.escape(search_string), case=False, na=False).any(), axis=1
    )]
    
    if total_matches.empty:
        return f"❌ '{search_string}' not found in the manifest."

    # 2. Apply object_type (or inferred type) filter to ALL matches first
    inf_type = object_type
    if not inf_type:
        s_upper = search_string.upper()
        if s_upper.startswith("QL."): inf_type = "QLOCAL"
        elif s_upper.startswith("QA."): inf_type = "QALIAS"
        elif s_upper.startswith("QR."): inf_type = "QREMOTE"

    type_filtered_matches = total_matches
    if inf_type:
        inf_type_upper = inf_type.upper()
        if inf_type_upper == "QUEUES":
            queue_types = ["QLOCAL", "QREMOTE", "QMODEL", "QALIAS"]
            type_filtered_matches = type_filtered_matches[type_filtered_matches["object_type"].str.upper().isin(queue_types)]
        else:
            type_filtered_matches = type_filtered_matches[type_filtered_matches["object_type"].str.upper() == inf_type_upper]

    if type_filtered_matches.empty:
        found_types = ", ".join(total_matches["object_type"].unique())
        return f"❌ '{search_string}' exists but is not of type '{inf_type}'. (Found types: {found_types})"

    # 3. Check hostname allowance on the type-filtered matches
    is_allowed_series = type_filtered_matches["hostname"].apply(lambda h: is_hostname_allowed(str(h))[0])
    allowed_matches = type_filtered_matches[is_allowed_series]
    restricted_matches = type_filtered_matches[~is_allowed_series]
    
    if allowed_matches.empty:
        return f"🚫 '{search_string}' was found, but only on restricted/production systems. I do not have access to these."

    # 4. Deduplicate and format output for allowed matches
    display_cols = allowed_matches[["hostname", "qmgr", "object_type"]].drop_duplicates()
    output_lines = [f"QM:{r['qmgr']} Host:{r['hostname']} Type:{r['object_type']}" for _, r in display_cols.iterrows()]
    
    # 5. Include restricted matches in the same list but with a clear tag
    if not restricted_matches.empty:
        res_rest_display = restricted_matches[["hostname", "qmgr", "object_type"]].drop_duplicates()
        for _, r in res_rest_display.iterrows():
            output_lines.append(f"QM:{r['qmgr']} [RESTRICTED: {r['hostname']}] Type:{r['object_type']}")

    return "\n".join(output_lines)


@mcp.tool()
async def dspmq() -> str:
    """List available queue managers and whether they are running or not."""
    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": _CSRF_TOKEN,
    }
    url = URL_BASE + "qmgr/"
    auth = httpx.BasicAuth(username=USER_NAME, password=PASSWORD)
    async with httpx.AsyncClient(verify=False, auth=auth) as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return prettify_dspmq(response.content)
        except Exception as err:
            return f"❌ Connection Error: {str(err)}"


def prettify_dspmq(payload: bytes) -> str:
    json_output = json.loads(payload.decode("utf-8"))
    lines = []
    for x in json_output["qmgr"]:
        lines.append(f"name={x['name']}, state={x['state']}")
    return "\n".join(lines)


@mcp.tool()
async def dspmqver() -> str:
    """Display IBM MQ version and installation information."""
    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": _CSRF_TOKEN,
    }
    url = URL_BASE + "installation"
    auth = httpx.BasicAuth(username=USER_NAME, password=PASSWORD)
    async with httpx.AsyncClient(verify=False, auth=auth) as client:
        try:
            response = await client.get(url, headers=headers, timeout=30.0)
            response.raise_for_status()
            return prettify_dspmqver(response.content)
        except Exception as err:
            return f"❌ Connection Error: {str(err)}"


def prettify_dspmqver(payload: bytes) -> str:
    json_output = json.loads(payload.decode("utf-8"))
    lines = ["\n---"]
    for x in json_output["installation"]:
        lines.append(
            f"Name: {x.get('name', 'N/A')}\n"
            f"Version: {x.get('version', 'N/A')}\n"
            f"Architecture: {x.get('architecture', 'N/A')}\n"
            f"Installation Path: {x.get('installationPath', 'N/A')}\n---"
        )
    return "\n".join(lines)


@mcp.tool()
async def runmqsc(qmgr_name: str, mqsc_command: str, hostname: str | None = None) -> str:
    """Run an MQSC command against a specific queue manager.

    Args:
        qmgr_name:    A queue manager name
        mqsc_command: An MQSC command to run on the queue manager
        hostname:     Optional: Host from search_qmgr_dump
    """
    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": _CSRF_TOKEN,
    }

    # Hostname resolution logic
    df = load_csv()
    target_hostname = qmgr_name  # Default fallback (restored to QM name)
    
    if hostname:
        # Use provided hostname directly
        target_hostname = hostname.strip()
        logger.debug("Using explicit hostname from tool call: %s", target_hostname)
        allowed, message = is_hostname_allowed(target_hostname)
        if not allowed:
            return message
    elif not df.empty:
        # Fallback to manifest lookup
        qmgr_matches = df[df["qmgr"].str.upper() == qmgr_name.upper()]
        if not qmgr_matches.empty:
            target_hostname = str(qmgr_matches.iloc[0]["hostname"]).strip()
            allowed, message = is_hostname_allowed(target_hostname)
            if not allowed:
                return message
        else:
            logger.warning("QM %s not found in manifest, using as hostname", qmgr_name)

    # Use json.dumps to safely serialise the command
    data = json.dumps({"type": "runCommand", "parameters": {"command": mqsc_command}})

    # Replace 'localhost' with the actual mapped hostname from CSV
    url_with_host = URL_BASE.replace("localhost", target_hostname)
    url = url_with_host + "action/qmgr/" + qmgr_name + "/mqsc"

    auth = httpx.BasicAuth(username=USER_NAME, password=PASSWORD)
    async with httpx.AsyncClient(verify=False, auth=auth) as client:
        try:
            response = await client.post(url, data=data, headers=headers, timeout=30.0)
            response.raise_for_status()
            return prettify_runmqsc(response.content)
        except Exception as err:
            return f"❌ Connection Error: {str(err)}"


def prettify_runmqsc(payload: bytes) -> str:
    """Format MQSC command response for both z/OS and distributed queue managers."""
    import re
    json_output = json.loads(payload.decode("utf-8"))
    lines = []
    
    # Headers to strip from the beginning of lines
    STRIP_HEADERS = [
        "AMQ8409I: Display Queue details.",
        "AMQ8450I: Display Channel details.",
        "AMQ8420I: Display Queue Manager details."
    ]

    for x in json_output.get("commandResponse", []):
        text_list = x.get("text", [])
        # z/OS responses start with CSQN205I
        if text_list and text_list[0].startswith("CSQN205I"):
            text_list.pop(0)
            if text_list: text_list.pop()
            for y in text_list:
                lines.append(y[15:].strip())
        else:
            for line in text_list:
                line_s = line.strip()
                if not line_s:
                    continue
                
                # 1. Skip echoes (e.g. "1 : DISPLAY ...")
                if line_s[0].isdigit() and " : " in line_s:
                    continue
                
                # 2. Strip known headers from start of line
                for h in STRIP_HEADERS:
                    if line_s.startswith(h):
                        line_s = line_s[len(h):].strip()
                        break
                
                if not line_s:
                    continue
                
                # 3. Handle data-rich lines: Split multi-attribute lines (separated by 2+ spaces)
                # This also fixes the "one long line" problem on some platforms
                parts = [p.strip() for p in re.split(r'\s{2,}', line_s) if p.strip()]
                lines.extend(parts)
    
    if not lines:
        return "✅ Command executed successfully, but no objects matched or no diagnostic output was returned."
    
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Startup connectivity check
# ---------------------------------------------------------------------------
async def verify_connectivity():
    """Verify that the MQ REST API is reachable before starting the server."""
    if not URL_BASE or not USER_NAME:
        return

    logger.debug("Verifying connectivity to %s ...", URL_BASE)
    auth = httpx.BasicAuth(username=USER_NAME, password=PASSWORD)
    async with httpx.AsyncClient(verify=False, auth=auth) as client:
        try:
            response = await client.get(URL_BASE + "installation", timeout=5.0)
            if response.status_code == 200:
                logger.info("SUCCESS: MQ REST API is responsive.")
            else:
                logger.warning(
                    "MQ REST API returned status %d — check .env credentials.",
                    response.status_code,
                )
        except Exception as e:
            logger.error(
                "CRITICAL: Cannot reach MQ REST API. Ensure 'dspmqweb' is running.\n  Error: %s",
                e,
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    transport = os.getenv("MQ_MCP_TRANSPORT", "stdio")
    logger.debug("Starting MCP Server with transport=%s", transport)
    asyncio.run(verify_connectivity())   # #1: actually run the connectivity check
    mcp.run(transport=transport)
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
import sys
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Logging — use the stdlib logger so level is controllable via env var
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    stream=sys.stderr,
    format="%(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("mqmcpserver")

# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------
# Try to find .env in cwd or one level up (handles different launch paths)
env_path = os.path.join(os.getcwd(), ".env")
if not os.path.exists(env_path):
    env_path = os.path.join(os.path.dirname(os.getcwd()), ".env")

load_dotenv(dotenv_path=env_path)
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
        f"🚫 Access to production systems is restricted for safety. "
        f"This query targets hostname '{hostname}' which is not in the allowed list.\n\n"
        f"Allowed hostname prefixes: {allowed_list}\n\n"
        f"Please use non-production environments for queries."
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
def search_qmgr_dump(search_string: str) -> str:
    """
    Search QMGR dump by any string and return matching records with hostname,
    queue manager, and object type.
    """
    logger.debug("search_qmgr_dump called with search_string: '%s'", search_string)
    df = load_csv()

    if df.empty:
        logger.debug("CSV is empty — returning empty result")
        return "No records found. CSV file may be empty."

    logger.debug("CSV contains %d rows", len(df))

    # Case-insensitive search across all columns
    mask = df.astype(str).apply(
        lambda row: row.str.contains(search_string, case=False, na=False).any(),
        axis=1,
    )
    result = df[mask]

    if result.empty:
        logger.debug("No matching records for '%s'", search_string)
        return f"❌ No records found matching '{search_string}'."

    # Filter by allowed hostname prefixes
    logger.debug("Filtering by allowed prefixes: %s", ALLOWED_HOSTNAME_PREFIXES)
    hostname_mask = result["hostname"].apply(lambda h: is_hostname_allowed(str(h))[0])
    result = result[hostname_mask]

    if result.empty:
        allowed_list = ", ".join(ALLOWED_HOSTNAME_PREFIXES)
        return (
            f"❌ No results found for '{search_string}' in allowed environments.\n\n"
            f"🚫 Production systems are excluded for safety.\n\n"
            f"Allowed hostname prefixes: {allowed_list}"
        )

    # Select and deduplicate key columns
    display_cols = result[["hostname", "qmgr", "object_type"]].drop_duplicates()
    logger.debug("Found %d unique records after dedup", len(display_cols))

    output_lines = [
        f"SEARCH RESULTS FOR: {search_string}",
        "=" * 100,
    ]
    for _, row in display_cols.iterrows():
        hostname = str(row["hostname"]).strip()
        qmgr     = str(row["qmgr"]).strip()
        obj_type = str(row["object_type"]).strip()
        line = f"Queue Manager: {qmgr} | Hostname: {hostname} | Type: {obj_type}"
        output_lines.append(line)
        logger.debug("Result line: %s", line)

    output_lines.extend([
        "=" * 100,
        f"SUMMARY: Found '{search_string}' on queue manager(s): {', '.join(display_cols['qmgr'].unique())}",
    ])
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
    lines = ["\n---"]
    for x in json_output["qmgr"]:
        lines.append(f"name = {x['name']}, running = {x['state']}\n---")
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
async def runmqsc(qmgr_name: str, mqsc_command: str) -> str:
    """Run an MQSC command against a specific queue manager.

    Args:
        qmgr_name:    A queue manager name
        mqsc_command: An MQSC command to run on the queue manager
    """
    headers = {
        "Content-Type": "application/json",
        "ibm-mq-rest-csrf-token": _CSRF_TOKEN,
    }

    # Hostname allow-list check using CSV lookup
    df = load_csv()
    if not df.empty:
        qmgr_matches = df[df["qmgr"].str.upper() == qmgr_name.upper()]
        if not qmgr_matches.empty:
            hostname = qmgr_matches.iloc[0]["hostname"]
            allowed, message = is_hostname_allowed(hostname)
            if not allowed:
                return message

    # Use json.dumps to safely serialise the command (handles special characters)
    data = json.dumps({"type": "runCommand", "parameters": {"command": mqsc_command}})

    url_with_qmgr_host = URL_BASE.replace("localhost", qmgr_name)
    url = url_with_qmgr_host + "action/qmgr/" + qmgr_name + "/mqsc"

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
    json_output = json.loads(payload.decode("utf-8"))
    lines = ["\n---"]
    for x in json_output["commandResponse"]:
        # z/OS responses start with CSQN205I
        if x["text"][0].startswith("CSQN205I"):
            x["text"].pop(0)
            x["text"].pop()
            for y in x["text"]:
                lines.append(y[15:] + "\n---")
        else:
            for line in x["text"]:
                if line.strip():
                    lines.append(line)
            lines.append("---")
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
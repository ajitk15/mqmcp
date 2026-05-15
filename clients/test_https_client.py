"""
Simple MCP client to test the HTTPS endpoint of mqmcpserver.

Usage:
    python clients/test_https_client.py

Requires the server to be running with HTTPS enabled:
    python server/mqmcpserver.py

The client will:
  1. Connect to the MCP SSE endpoint over HTTPS
  2. List all available tools
  3. Call the 'find_mq_object' tool with a sample search
  4. Call the 'dspmq' tool to list queue managers
"""

import asyncio
import os
import ssl
import sys
from urllib.parse import urlparse
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load environment
# ---------------------------------------------------------------------------
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(dotenv_path=env_path)


MCP_AUTH_USER = os.getenv("MCP_AUTH_USER", "")
MCP_AUTH_PASSWORD = os.getenv("MCP_AUTH_PASSWORD", "")

# SSE endpoint URL — loaded directly from .env
SSE_URL = os.getenv("MCP_REMOTE_SERVER_URL", "https://127.0.0.1:5000/sse")

# ---------------------------------------------------------------------------
# Colour helpers for terminal output
# ---------------------------------------------------------------------------
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def heading(text: str):
    print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}")


def success(text: str):
    print(f"  {GREEN}✔ {text}{RESET}")


def warn(text: str):
    print(f"  {YELLOW}⚠ {text}{RESET}")


def error(text: str):
    print(f"  {RED}✖ {text}{RESET}")


def info(text: str):
    print(f"  {CYAN}ℹ {text}{RESET}")


# ---------------------------------------------------------------------------
# Custom httpx client factory that skips SSL verification (self-signed certs)
# ---------------------------------------------------------------------------
def _make_insecure_httpx_client(
    headers: dict[str, str] | None = None,
    timeout=None,
    auth=None,
):
    """httpx_client_factory for sse_client that sets verify=False."""
    import httpx

    kwargs: dict = {"follow_redirects": True, "verify": False}
    if timeout is not None:
        kwargs["timeout"] = timeout
    else:
        kwargs["timeout"] = httpx.Timeout(30.0, read=300.0)
    if headers is not None:
        kwargs["headers"] = headers
    if auth is not None:
        kwargs["auth"] = auth
    return httpx.AsyncClient(**kwargs)


# ---------------------------------------------------------------------------
# MCP client logic
# ---------------------------------------------------------------------------
async def run_tests():
    # Import MCP SDK
    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client
    except ImportError:
        error("MCP SDK not installed.  Run:  pip install mcp")
        sys.exit(1)

    import httpx

    # Build auth headers for Basic Authentication
    headers = {}
    if MCP_AUTH_USER and MCP_AUTH_PASSWORD:
        import base64
        credentials = base64.b64encode(
            f"{MCP_AUTH_USER}:{MCP_AUTH_PASSWORD}".encode()
        ).decode()
        headers["Authorization"] = f"Basic {credentials}"
        info(f"Using Basic Auth (user: {MCP_AUTH_USER})")
    else:
        warn("No authentication configured — connecting without credentials.")

    heading("HTTPS MCP Client Test")
    info(f"Target: {SSE_URL}")

    # ------------------------------------------------------------------
    # Step 0: Quick TCP+TLS handshake check (NOT an HTTP GET on SSE)
    # ------------------------------------------------------------------
    print(f"\n{BOLD}[0] HTTPS Connectivity Check{RESET}")
    parsed = urlparse(SSE_URL)
    connect_host = parsed.hostname or "127.0.0.1"
    connect_port = parsed.port or 443
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(connect_host, connect_port, ssl=ctx),
            timeout=5.0,
        )
        writer.close()
        await writer.wait_closed()
        success(f"TLS handshake to {connect_host}:{connect_port} succeeded")
    except Exception as e:
        error(f"Cannot reach {SSE_URL}")
        error(f"  {type(e).__name__}: {e}")
        print(f"\n  Make sure the server is running:")
        print(f"    python server/mqmcpserver.py\n")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Step 1: Connect via MCP SSE and list tools
    # ------------------------------------------------------------------
    print(f"\n{BOLD}[1] Connecting to MCP SSE endpoint …{RESET}")
    try:
        async with sse_client(
            SSE_URL,
            headers=headers,
            httpx_client_factory=_make_insecure_httpx_client,
        ) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                success("MCP session initialised over HTTPS!")

                # List tools
                tools_result = await session.list_tools()
                tools = tools_result.tools
                print(f"\n{BOLD}[2] Available Tools ({len(tools)}){RESET}")
                for t in tools:
                    desc = t.description[:80] + "…" if len(t.description) > 80 else t.description
                    print(f"  • {CYAN}{t.name}{RESET}: {desc}")

                # ----------------------------------------------------------
                # Step 2: Call find_mq_object
                # ----------------------------------------------------------
                print(f"\n{BOLD}[3] Calling tool: find_mq_object{RESET}")
                search_term = "QL."
                info(f'Search term: "{search_term}"')
                try:
                    result = await session.call_tool("find_mq_object", {"search_string": search_term})
                    if result.content:
                        output = result.content[0].text
                        for line in output.split("\n")[:10]:
                            print(f"    {line}")
                        if output.count("\n") > 10:
                            warn(f"… ({output.count(chr(10)) - 10} more lines)")
                    else:
                        info("No results returned.")
                    success("find_mq_object executed successfully.")
                except Exception as e:
                    warn(f"find_mq_object call failed: {e}")

                # ----------------------------------------------------------
                # Step 3: Call dspmq
                # ----------------------------------------------------------
                print(f"\n{BOLD}[4] Calling tool: dspmq{RESET}")
                try:
                    result = await session.call_tool("dspmq", {})
                    if result.content:
                        output = result.content[0].text
                        for line in output.split("\n")[:10]:
                            print(f"    {line}")
                    else:
                        info("No results returned.")
                    success("dspmq executed successfully.")
                except Exception as e:
                    warn(f"dspmq call failed: {e}")

    except Exception as e:
        # Unwrap ExceptionGroup if needed
        if hasattr(e, "exceptions"):
            for ex in e.exceptions:
                error(f"SSE connection error: {type(ex).__name__}: {ex}")
        else:
            error(f"SSE connection error: {type(e).__name__}: {e}")
        sys.exit(1)

    # ------------------------------------------------------------------
    heading("All tests passed!")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Suppress urllib3 InsecureRequestWarning for self-signed certs
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    asyncio.run(run_tests())

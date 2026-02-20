"""
Test configuration and fixtures for MQ MCP tests
"""

import pytest
import asyncio
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

@pytest.fixture
def event_loop():
    """Create an event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def sample_qmgr_data():
    """Sample queue manager dump data for testing"""
    return """extractedat|hostname|qmname|objecttype|objectdef
2026-02-16|lodalhost|MQQMGR1|QLOCAL|DEFINE QLOCAL(QL.IN.APP1) CURDEPTH(15)
2026-02-16|lodalhost|MQQMGR1|QLOCAL|DEFINE QLOCAL(QL.OUT.APP3) CURDEPTH(42)
2026-02-16|lopalhost|MQQMGR2|QLOCAL|DEFINE QLOCAL(QL.IN.APP1) CURDEPTH(8)
2026-02-16|lodalhost|MQQMGR1|QALIAS|DEFINE QALIAS(QA.IN.APP1) TARGET(QL.IN.APP1)
2026-02-16|lodalhost|MQQMGR1|CHANNEL|DEFINE CHANNEL(CH.SVRCONN) CHLTYPE(SVRCONN)"""

@pytest.fixture
def allowed_hostname_prefixes():
    """Allowed hostname prefixes for testing"""
    return ["lod", "loq", "lot"]

@pytest.fixture
def blocked_hostname_prefixes():
    """Blocked hostname prefixes for testing"""
    return ["lop"]

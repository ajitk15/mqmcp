# MQ MCP Test Suite

Comprehensive test suite for the MQ MCP ecosystem covering all major functionality.

## Test Structure

```
tests/
├── conftest.py                    # Test configuration and fixtures
├── test_basic_operations.py       # Basic MQ operations
├── test_hostname_filtering.py     # Production protection tests
├── test_auto_discovery.py         # Multi-queue-manager tests
├── test_tool_logging.py           # Tool transparency tests
└── README.md                      # This file
```

## Test Categories

### 1. Basic Operations (`test_basic_operations.py`)
Tests for common user queries:
- List queue managers
- Check MQ version
- List queues on a queue manager
- Check queue depth (single QM)
- Check queue depth (multiple QMs)
- Check queue status
- List/check channels
- Search functionality

### 2. Hostname Filtering (`test_hostname_filtering.py`)
Tests for production protection:
- Allowed hostnames (lod, loq, lot)
- Blocked hostnames (lop, unknown)
- CSV filtering behavior
- Environment configuration

### 3. Auto-Discovery (`test_auto_discovery.py`)
Tests for automatic queue manager discovery:
- Single queue manager discovery
- **CRITICAL**: Multiple queue manager discovery
- Queue not found scenarios
- Cluster queue handling
- Alias queue resolution
- Ensuring AI doesn't ask "which queue manager?"

### 4. Tool Logging (`test_tool_logging.py`)
Tests for tool transparency:
- Logging enable/disable
- Tool name display
- Arguments display
- REST endpoint display
- Integration in Streamlit apps

## Running Tests

### Install Dependencies
```bash
pip install pytest pytest-asyncio
```

### Run All Tests
```bash
# From project root
pytest tests/

# With verbose output
pytest tests/ -v

# With detailed output
pytest tests/ -vv
```

### Run Specific Test File
```bash
pytest tests/test_basic_operations.py -v
pytest tests/test_auto_discovery.py -v
```

### Run Specific Test
```bash
pytest tests/test_auto_discovery.py::TestAutoDiscovery::test_discover_multiple_queue_managers -v
```

### Run with Coverage
```bash
pip install pytest-cov
pytest tests/ --cov=clients --cov=server --cov-report=html
```

## Key Test Scenarios

### ✅ CRITICAL: Multi-Queue-Manager Depth Check
```python
# User Input: "What is the current depth of queue QL.IN.APP1?"
# Expected Behavior:
# 1. search_qmgr_dump('QL.IN.APP1') → finds MQQMGR1 AND MQQMGR2
# 2. runmqsc(MQQMGR1, 'DISPLAY QLOCAL(QL.IN.APP1) CURDEPTH') → 15
# 3. runmqsc(MQQMGR2, 'DISPLAY QLOCAL(QL.IN.APP1) CURDEPTH') → 8
# 4. Return: "MQQMGR1: depth 15, MQQMGR2: depth 8"
```

### ✅ Hostname Filtering
```python
# Scenario: Queue exists on both dev (lod) and prod (lop) QMs
# Expected: Only dev QM is queried, prod is filtered out
```

### ✅ Alias Queue Resolution
```python
# User Input: "What is the depth of QA.IN.APP1?"
# Expected Behavior:
# 1. Find alias definition → TARGET(QL.IN.APP1)
# 2. Query target queue depth
# 3. Return: "Alias → Target, depth: 85"
```

## Test Data

Tests use sample data defined in `conftest.py`:
- 2 Queue Managers: MQQMGR1 (lodalhost), MQQMGR2 (lopalhost)
- Queue QL.IN.APP1 exists on BOTH queue managers
- Queue QL.OUT.APP3 exists on MQQMGR1 only
- Alias QA.IN.APP1 → QL.IN.APP1 on MQQMGR1

## Expected Test Results

All tests should PASS when:
- ✅ Auto-discovery finds ALL queue managers for a queue
- ✅ AI queries ALL queue managers (not just one)
- ✅ Production hostnames are filtered out
- ✅ Tool logging displays correctly when enabled
- ✅ REST endpoints are constructed correctly

## Continuous Integration

Add to CI/CD pipeline:
```yaml
# .github/workflows/test.yml
- name: Run tests
  run: pytest tests/ -v
```

## Contributing

When adding new features:
1. Add corresponding test cases
2. Ensure all tests pass
3. Update this README if needed

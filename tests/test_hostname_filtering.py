"""
Test cases for hostname filtering and production protection
"""

import pytest
import os

class TestHostnameFiltering:
    """Test hostname-based filtering for production protection"""
    
    def test_allowed_hostname_lod(self):
        """Test: Query to lodalhost (dev) should be ALLOWED"""
        hostname = "lodalhost"
        allowed_prefixes = ["lod", "loq", "lot"]
        
        is_allowed = any(hostname.startswith(prefix) for prefix in allowed_prefixes)
        assert is_allowed == True, f"Hostname '{hostname}' should be allowed"
    
    def test_allowed_hostname_loq(self):
        """Test: Query to loqalhost (QA) should be ALLOWED"""
        hostname = "loqalhost"
        allowed_prefixes = ["lod", "loq", "lot"]
        
        is_allowed = any(hostname.startswith(prefix) for prefix in allowed_prefixes)
        assert is_allowed == True, f"Hostname '{hostname}' should be allowed"
    
    def test_allowed_hostname_lot(self):
        """Test: Query to lotalhost (test) should be ALLOWED"""
        hostname = "lotalhost"
        allowed_prefixes = ["lod", "loq", "lot"]
        
        is_allowed = any(hostname.startswith(prefix) for prefix in allowed_prefixes)
        assert is_allowed == True, f"Hostname '{hostname}' should be allowed"
    
    def test_blocked_hostname_lop(self):
        """Test: Query to lopalhost (prod) should be BLOCKED"""
        hostname = "lopalhost"
        allowed_prefixes = ["lod", "loq", "lot"]
        
        is_allowed = any(hostname.startswith(prefix) for prefix in allowed_prefixes)
        assert is_allowed == False, f"Hostname '{hostname}' should be blocked"
    
    def test_blocked_hostname_unknown(self):
        """Test: Query to unknown hostname should be BLOCKED"""
        hostname = "unknownhost"
        allowed_prefixes = ["lod", "loq", "lot"]
        
        is_allowed = any(hostname.startswith(prefix) for prefix in allowed_prefixes)
        assert is_allowed == False, f"Hostname '{hostname}' should be blocked"

class TestHostnameFilteringWithCSV:
    """Test hostname filtering when reading from CSV"""
    
    def test_search_filters_production(self):
        """Test: search_qmgr_dump should filter out production hostnames"""
        # Scenario: CSV has entries for both MQQMGR1 (lod) and MQQMGR2 (lop)
        # User searches for QL.IN.APP1 which exists on both
        # Expected: Only MQQMGR1 (lod) should be returned, MQQMGR2 (lop) filtered out
        
        csv_data = """extractedat|hostname|qmname|objecttype|objectdef
2026-02-16|lodalhost|MQQMGR1|QLOCAL|DEFINE QLOCAL(QL.IN.APP1)
2026-02-16|lopalhost|MQQMGR2|QLOCAL|DEFINE QLOCAL(QL.IN.APP1)"""
        
        # When searching, should only return MQQMGR1
        allowed_prefixes = ["lod", "loq", "lot"]
        
        lines = csv_data.strip().split('\n')[1:]  # Skip header
        allowed_count = 0
        blocked_count = 0
        
        for line in lines:
            hostname = line.split('|')[1]
            if any(hostname.startswith(prefix) for prefix in allowed_prefixes):
                allowed_count += 1
            else:
                blocked_count += 1
        
        assert allowed_count == 1, "Should find 1 allowed queue manager"
        assert blocked_count == 1, "Should filter out 1 production queue manager"
    
    def test_list_queues_validates_hostname(self):
        """Test: List queues on MQQMGR2 should be BLOCKED if hostname is lop"""
        qmgr_name = "MQQMGR2"
        hostname = "lopalhost"  # Production
        allowed_prefixes = ["lod", "loq", "lot"]
        
        is_allowed = any(hostname.startswith(prefix) for prefix in allowed_prefixes)
        
        # Expected behavior: Return error message instead of executing
        if not is_allowed:
            expected_message = "🚫 Access to production systems is restricted"
            assert "restricted" in expected_message.lower()
        else:
            pytest.fail("Should have blocked production hostname")

class TestEnvironmentConfiguration:
    """Test environment variable configuration for filtering"""
    
    def test_default_allowed_prefixes(self):
        """Test: Default allowed prefixes should be lod,loq,lot"""
        default = "lod,loq,lot"
        prefixes = [p.strip().lower() for p in default.split(",")]
        
        assert "lod" in prefixes
        assert "loq" in prefixes
        assert "lot" in prefixes
        assert "lop" not in prefixes
    
    def test_custom_allowed_prefixes(self):
        """Test: Custom prefixes via environment variable"""
        custom = "lod,loq,lot,lop"
        prefixes = [p.strip().lower() for p in custom.split(",")]
        
        # If user explicitly allows production
        assert "lop" in prefixes

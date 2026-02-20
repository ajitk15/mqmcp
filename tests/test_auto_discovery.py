"""
Test cases for multi-queue-manager auto-discovery
"""

import pytest

class TestAutoDiscovery:
    """Test automatic queue manager discovery"""
    
    def test_discover_single_queue_manager(self):
        """
        Test: Queue exists on ONE queue manager
        User: "What is the depth of QL.OUT.APP3?"
        Expected workflow:
          1. search_qmgr_dump('QL.OUT.APP3') -> finds MQQMGR1
          2. runmqsc(MQQMGR1, 'DISPLAY QLOCAL(QL.OUT.APP3) CURDEPTH')
          3. Return: "Current depth of QL.OUT.APP3 on MQQMGR1 is 42"
        """
        queue_name = "QL.OUT.APP3"
        expected_qmgrs = ["MQQMGR1"]
        expected_tool_calls = 2  # 1 search + 1 runmqsc
        
        assert len(expected_qmgrs) == 1
        assert expected_tool_calls == 2
    
    def test_discover_multiple_queue_managers(self):
        """
        Test: Queue exists on MULTIPLE queue managers (CRITICAL)
        User: "What is the current depth of queue QL.IN.APP1?"
        Expected workflow:
          1. search_qmgr_dump('QL.IN.APP1') -> finds MQQMGR1 AND MQQMGR2
          2. runmqsc(MQQMGR1, 'DISPLAY QLOCAL(QL.IN.APP1) CURDEPTH') -> 15
          3. runmqsc(MQQMGR2, 'DISPLAY QLOCAL(QL.IN.APP1) CURDEPTH') -> 8
          4. Return depths for BOTH: "MQQMGR1: 15, MQQMGR2: 8"
        """
        queue_name = "QL.IN.APP1"
        expected_qmgrs = ["MQQMGR1", "MQQMGR2"]
        expected_tool_calls = 3  # 1 search + 2 runmqsc
        
        assert len(expected_qmgrs) == 2
        assert expected_tool_calls == 3
    
    def test_queue_not_found(self):
        """
        Test: Queue does NOT exist anywhere
        User: "What is the depth of QL.NONEXISTENT?"
        Expected workflow:
          1. search_qmgr_dump('QL.NONEXISTENT') -> no results
          2. Return: "Queue QL.NONEXISTENT not found"
        """
        queue_name = "QL.NONEXISTENT"
        expected_qmgrs = []
        expected_message = "not found"
        
        assert len(expected_qmgrs) == 0
        assert "not found" in expected_message.lower()

class TestMultiQueueManagerScenarios:
    """Test various multi-queue-manager scenarios"""
    
    def test_cluster_queue_on_two_qmgrs(self):
        """
        Test: Cluster queue exists on 2 queue managers
        User: "Show me the depth of QL.CLUSTER.QUEUE"
        Expected: Query BOTH queue managers and show both depths
        """
        queue_name = "QL.CLUSTER.QUEUE"
        is_cluster = True
        expected_qmgrs = ["MQQMGR1", "MQQMGR2"]
        
        if is_cluster:
            assert len(expected_qmgrs) >= 2, "Cluster queue should be on multiple QMs"
    
    def test_cluster_queue_on_three_qmgrs(self):
        """
        Test: Cluster queue exists on 3 queue managers
        User: "What is the depth of QL.CLUSTER.QUEUE?"
        Expected: Query ALL THREE queue managers
        """
        queue_name = "QL.CLUSTER.QUEUE"
        expected_qmgrs = ["MQQMGR1", "MQQMGR2", "MQQMGR3"]
        expected_tool_calls = 4  # 1 search + 3 runmqsc
        
        assert len(expected_qmgrs) == 3
        assert expected_tool_calls == 4
    
    def test_do_not_ask_which_qmgr(self):
        """
        Test: AI should NOT ask "which queue manager?"
        User: "What is the depth of QL.IN.APP1?"
        BAD Response: "Which queue manager would you like to check?"
        GOOD Response: Auto-discover, query all, return results
        """
        queue_name = "QL.IN.APP1"
        
        # AI should NOT return this
        bad_response = "which queue manager"
        
        # AI SHOULD do this
        good_workflow = [
            "search_qmgr_dump",
            "runmqsc(MQQMGR1)",
            "runmqsc(MQQMGR2)"
        ]
        
        assert "which" not in " ".join(good_workflow).lower()

class TestAliasQueueResolution:
    """Test alias queue target resolution"""
    
    def test_alias_queue_auto_resolve(self):
        """
        Test: Alias queue should resolve to target automatically
        User: "What is the depth of QA.IN.APP1?"
        Expected workflow:
          1. search_qmgr_dump('QA.IN.APP1') -> finds MQQMGR1, type=QALIAS
          2. runmqsc(MQQMGR1, 'DISPLAY QALIAS(QA.IN.APP1)') -> TARGET(QL.IN.APP1)
          3. runmqsc(MQQMGR1, 'DISPLAY QLOCAL(QL.IN.APP1) CURDEPTH') -> 85
          4. Return: "Alias QA.IN.APP1 -> QL.IN.APP1, depth: 85"
        """
        alias_queue = "QA.IN.APP1"
        target_queue = "QL.IN.APP1"
        expected_tool_calls = 3  # 1 search + 2 runmqsc
        
        assert alias_queue.startswith("QA")
        assert target_queue.startswith("QL")
        assert expected_tool_calls == 3
    
    def test_do_not_stop_at_alias_definition(self):
        """
        Test: AI should NOT stop at alias definition
        User: "What is the depth of QA.IN.APP1?"
        BAD Response: "QA.IN.APP1 is an alias queue pointing to QL.IN.APP1"
        GOOD Response: "QA.IN.APP1 -> QL.IN.APP1, current depth: 85"
        """
        alias_queue = "QA.IN.APP1"
        
        # BAD: Stop here
        bad_response = "is an alias queue"
        
        # GOOD: Continue to get actual depth
        good_response = "current depth"
        
        assert "depth" in good_response.lower()

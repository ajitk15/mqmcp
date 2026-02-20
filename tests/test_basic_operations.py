"""
Test cases for basic MQ operations
"""

import pytest
from clients.dynamic_client import DynamicMQClient

class TestBasicOperations:
    """Test basic MQ commands and operations"""
    
    def test_list_queue_managers_intent(self):
        """Test: User asks 'list all queue managers'"""
        user_input = "list all queue managers"
        # Expected: dspmq tool should be called
        assert "list" in user_input.lower()
        assert "queue manager" in user_input.lower()
    
    def test_check_version_intent(self):
        """Test: User asks 'what is the MQ version?'"""
        user_input = "what is the MQ version?"
        # Expected: dspmqver tool should be called
        assert "version" in user_input.lower()
    
    def test_show_queue_managers_status(self):
        """Test: User asks 'show me all queue managers and their status'"""
        user_input = "show me all queue managers and their status"
        # Expected: dspmq tool should be called
        assert "queue manager" in user_input.lower()
        assert "status" in user_input.lower()

class TestQueueQueries:
    """Test queue-related queries"""
    
    def test_list_queues_on_qmgr(self):
        """Test: User asks 'list all queues on MQQMGR1'"""
        user_input = "list all queues on MQQMGR1"
        # Expected: search or runmqsc should be called with MQQMGR1
        assert "list" in user_input.lower()
        assert "queue" in user_input.lower()
        assert "MQQMGR1" in user_input
    
    def test_check_queue_depth_single_qm(self):
        """Test: User asks 'what is the depth of QL.OUT.APP3?'"""
        user_input = "what is the depth of QL.OUT.APP3?"
        # Expected: 
        # 1. search_qmgr_dump('QL.OUT.APP3') finds MQQMGR1
        # 2. runmqsc(MQQMGR1, 'DISPLAY QLOCAL(QL.OUT.APP3) CURDEPTH')
        assert "depth" in user_input.lower()
        assert "QL.OUT.APP3" in user_input
    
    def test_check_queue_depth_multiple_qm(self):
        """Test: User asks 'what is the current depth of queue QL.IN.APP1?'"""
        user_input = "what is the current depth of queue QL.IN.APP1?"
        # Expected (CRITICAL):
        # 1. search_qmgr_dump('QL.IN.APP1') finds MQQMGR1 AND MQQMGR2
        # 2. runmqsc(MQQMGR1, 'DISPLAY QLOCAL(QL.IN.APP1) CURDEPTH')
        # 3. runmqsc(MQQMGR2, 'DISPLAY QLOCAL(QL.IN.APP1) CURDEPTH')
        # 4. Return depths for BOTH queue managers
        assert "depth" in user_input.lower()
        assert "QL.IN.APP1" in user_input
    
    def test_check_alias_queue_depth(self):
        """Test: User asks 'what is the depth of QA.IN.APP1?'"""
        user_input = "what is the depth of QA.IN.APP1?"
        # Expected:
        # 1. search_qmgr_dump('QA.IN.APP1') finds MQQMGR1, type=QALIAS
        # 2. runmqsc(MQQMGR1, 'DISPLAY QALIAS(QA.IN.APP1)') -> TARGET(QL.IN.APP1)
        # 3. runmqsc(MQQMGR1, 'DISPLAY QLOCAL(QL.IN.APP1) CURDEPTH')
        assert "depth" in user_input.lower()
        assert "QA.IN.APP1" in user_input
    
    def test_check_queue_status(self):
        """Test: User asks 'status of queue QL.IN.APP1'"""
        user_input = "status of queue QL.IN.APP1"
        # Expected: DISPLAY QSTATUS command
        assert "status" in user_input.lower()
        assert "QL.IN.APP1" in user_input

class TestChannelQueries:
    """Test channel-related queries"""
    
    def test_list_channels(self):
        """Test: User asks 'show channels on MQQMGR1'"""
        user_input = "show channels on MQQMGR1"
        # Expected: DISPLAY CHANNEL(*) on MQQMGR1
        assert "channel" in user_input.lower()
        assert "MQQMGR1" in user_input
    
    def test_check_channel_status(self):
        """Test: User asks 'channel status of CH.SVRCONN on MQQMGR1'"""
        user_input = "channel status of CH.SVRCONN on MQQMGR1"
        # Expected: DISPLAY CHSTATUS(CH.SVRCONN)
        assert "channel" in user_input.lower()
        assert "status" in user_input.lower()
        assert "CH.SVRCONN" in user_input

class TestSearchQueries:
    """Test search functionality"""
    
    def test_find_queue(self):
        """Test: User asks 'where is QL.IN.APP1?'"""
        user_input = "where is QL.IN.APP1?"
        # Expected: search_qmgr_dump('QL.IN.APP1')
        # Should return all queue managers hosting this queue
        assert "where" in user_input.lower()
        assert "QL.IN.APP1" in user_input
    
    def test_find_channel(self):
        """Test: User asks 'find channel CH.SVRCONN'"""
        user_input = "find channel CH.SVRCONN"
        # Expected: search_qmgr_dump('CH.SVRCONN')
        assert "find" in user_input.lower()
        assert "CH.SVRCONN" in user_input
    
    def test_search_generic(self):
        """Test: User asks 'search for APP1'"""
        user_input = "search for APP1"
        # Expected: search_qmgr_dump('APP1')
        # Should return all objects containing APP1
        assert "search" in user_input.lower()
        assert "APP1" in user_input

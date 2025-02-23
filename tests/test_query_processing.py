import pytest
from typing import Dict, List, Optional
from tests.test_agent_tools import MockResourceQueryTools, RANK_HIERARCHY, TEST_CASES
from src.query_tools.base import BaseResourceQueryTools
from unittest.mock import Mock
import json

# Add this at the top of the file
pytestmark = pytest.mark.filterwarnings("ignore::pytest.PytestCollectionWarning")

# Mock database for testing
class MockDB:
    pass

@pytest.fixture
def query_tools():
    """Simple fixture without any DB dependencies"""
    return MockResourceQueryTools()

# Single source of test cases
QUERY_TEST_CASES = {
    "basic": [
        (
            "consultants in London",
            {"rank": "Consultant", "location": "London"}
        ),
        (
            "Senior Consultants in Manchester",
            {"rank": "Senior Consultant", "location": "Manchester"}
        ),
    ],
    "hierarchy": [
        (
            "all consultants below MC",
            {"ranks": ["Principal Consultant", "Senior Consultant", "Consultant", 
                      "Consultant Analyst", "Analyst"]}
        ),
        (
            "people below Principal Consultant",
            {"ranks": ["Senior Consultant", "Consultant", "Consultant Analyst", "Analyst"]}
        ),
    ],
    "combined": [
        (
            "AWS Engineers below MC in Manchester",
            {
                "ranks": ["Principal Consultant", "Senior Consultant", "Consultant", 
                         "Consultant Analyst", "Analyst"],
                "location": "Manchester",
                "skills": ["AWS Engineer"]
            }
        ),
    ]
}

class TestQueryProcessing:
    """Single test class for all query processing"""
    
    @pytest.fixture
    def tools(self):
        """Fixture to provide MockResourceQueryTools instance"""
        return MockResourceQueryTools()
    
    @pytest.mark.parametrize("query,expected", TEST_CASES["basic"])
    def test_basic_queries(self, tools, query, expected):
        """Test basic query construction"""
        assert tools.construct_query(query) == expected

    @pytest.mark.parametrize("query,expected", TEST_CASES["hierarchy"])
    def test_hierarchy_queries(self, tools, query, expected):
        """Test hierarchy-based queries"""
        assert tools.construct_query(query) == expected

    @pytest.mark.parametrize("query,expected", [
        (
            "all consultants below MC",
            {"ranks": ["Principal Consultant", "Senior Consultant", "Consultant", 
                      "Consultant Analyst", "Analyst"]}
        ),
        (
            "consulting resources in London",
            {"ranks": ["Principal Consultant", "Managing Consultant", "Senior Consultant", 
                      "Consultant", "Consultant Analyst"], 
             "location": "London"}
        ),
    ])
    def test_rank_queries(self, tools, query, expected):
        """Test different types of rank-based queries"""
        assert tools.construct_query(query) == expected

class TestQueryConstruction:
    """Test the query construction logic"""
    
    @pytest.mark.parametrize("input_query,expected_query", [
        # Basic rank queries
        (
            "Consultants in London",
            {
                "rank": "Consultant",
                "location": "London"
            }
        ),
        # Generic consultant queries
        (
            "all consultants below MC",
            {
                "ranks": ["Principal Consultant", "Senior Consultant", "Consultant", 
                          "Consultant Analyst", "Analyst"]
            }
        ),
        # Location-only queries
        (
            "people in Manchester",
            {
                "location": "Manchester"
            }
        ),
        # Skill queries
        (
            "Frontend Developers in Bristol",
            {
                "location": "Bristol",
                "skills": ["Frontend Developer"]
            }
        ),
    ])
    def test_query_construction(self, query_tools, input_query, expected_query):
        """Test that queries are constructed correctly before any DB interaction"""
        # Get the constructed query without executing it
        constructed_query = query_tools.construct_query(input_query)
        assert constructed_query == expected_query

    @pytest.mark.parametrize("input_query,expected_ranks", [
        ("below MC", ["Principal Consultant", "Senior Consultant", "Consultant", 
                     "Consultant Analyst", "Analyst"]),
        ("below Partner", ["Associate Partner", "Consulting Director", "Managing Consultant",
                          "Principal Consultant", "Senior Consultant", "Consultant", 
                          "Consultant Analyst", "Analyst"]),
        ("below Principal Consultant", ["Senior Consultant", "Consultant", 
                                      "Consultant Analyst", "Analyst"]),
    ])
    def test_rank_hierarchy_resolution(self, query_tools, input_query, expected_ranks):
        """Test that rank hierarchy is correctly resolved"""
        # Extract just the rank name from the query
        rank = input_query.replace("below ", "").strip()
        ranks = query_tools.get_ranks_below(rank)
        assert ranks == expected_ranks

    @pytest.mark.parametrize("input_query,expected_interpretation", [
        # Test generic vs specific consultant interpretation
        (
            "consultants in London",
            {"rank": "Consultant"}  # Specific rank
        ),
        (
            "all consultants",
            {"ranks": ["Principal Consultant", "Managing Consultant", "Senior Consultant", 
                      "Consultant", "Consultant Analyst"]}  # Generic
        ),
        (
            "consulting resources",
            {"ranks": ["Principal Consultant", "Managing Consultant", "Senior Consultant", 
                      "Consultant", "Consultant Analyst"]}  # Generic
        ),
    ])
    def test_consultant_interpretation(self, query_tools, input_query, expected_interpretation):
        """Test that 'consultant' is correctly interpreted based on context"""
        constructed_query = query_tools.construct_query(input_query)
        # Check only the rank-related parts of the query
        for key in expected_interpretation:
            assert constructed_query[key] == expected_interpretation[key]

class TestRankQueries:
    """Test cases for rank-based queries"""
    
    @pytest.fixture
    def tools(self):
        return MockResourceQueryTools()

    @pytest.mark.parametrize("query,expected", [
        (
            "all consultants below MC",
            {"ranks": ["Principal Consultant", "Senior Consultant", "Consultant", 
                      "Consultant Analyst", "Analyst"]}
        ),
        (
            "consulting resources in London",
            {"ranks": ["Principal Consultant", "Managing Consultant", "Senior Consultant", 
                      "Consultant", "Consultant Analyst"],
             "location": "London"}
        ),
    ])
    def test_rank_queries(self, tools, query, expected):
        assert tools.construct_query(query) == expected

class TestLocationQueries:
    """Test cases for location-based queries"""
    
    @pytest.mark.parametrize("query,expected_location", [
        ("people in London", "London"),
        ("consultants in Manchester", "Manchester"),
        ("resources in Bristol", "Bristol"),
        ("employees in Belfast", "Belfast"),
    ])
    def test_location_queries(self, query_tools, query, expected_location):
        # First translate the query to JSON
        json_query = query_tools.translate_query(query)
        
        # Then use the JSON for people query
        result = query_tools.query_people(json_query)
        
        # Success case: we got results
        if "| Name | Location | Rank |" in result:
            assert expected_location in result
        # No results case: verify the query was correct
        else:
            structured_query = json.loads(json_query)
            assert structured_query.get('location') == expected_location

class TestEdgeCases:
    """Test edge cases and potential ambiguous queries"""
    
    @pytest.fixture
    def tools(self):
        return MockResourceQueryTools()

    @pytest.mark.parametrize("query,expected", TEST_CASES["edge_cases"])
    def test_edge_cases(self, tools, query, expected):
        result = tools.construct_query(query)
        assert result == expected

class TestNonResourceQueries:
    """Test handling of non-resource related queries"""
    
    @pytest.fixture
    def tools(self):
        return MockResourceQueryTools()
    
    @pytest.mark.parametrize("query,expected_message", [
        (
            "what's the weather today?",
            "Sorry, I cannot help with that query. I can only assist with resource management related questions."
        ),
        (
            "tell me a joke",
            "Sorry, I cannot help with that query. I can only assist with resource management related questions."
        ),
        (
            "what time is it?",
            "Sorry, I cannot help with that query. I can only assist with resource management related questions."
        ),
        (
            "help me with my taxes",
            "Sorry, I cannot help with that query. I can only assist with resource management related questions."
        )
    ])
    def test_non_resource_queries(self, tools, query, expected_message):
        """Test that non-resource queries return the standard error message"""
        result = tools.handle_non_resource_query(query)
        assert result == expected_message
        # Verify that query construction returns empty for non-resource queries
        assert tools.construct_query(query) == {}

    @pytest.mark.parametrize("query", [
        "find consultants in London",
        "available developers in Manchester",
        "senior engineers with AWS skills"
    ])
    def test_valid_resource_queries(self, tools, query):
        """Test that valid resource queries are processed normally"""
        # First verify non-resource handler returns empty string
        assert tools.handle_non_resource_query(query) == ""
        # Then verify query construction returns non-empty result
        assert tools.construct_query(query) != {}
        assert isinstance(tools.construct_query(query), dict)

@pytest.fixture(autouse=True)
def mock_firebase(monkeypatch):
    """Mock Firebase for all tests"""
    from tests.mock_utils import mock_fetch_employees
    monkeypatch.setattr('firebase_utils.fetch_employees', mock_fetch_employees)
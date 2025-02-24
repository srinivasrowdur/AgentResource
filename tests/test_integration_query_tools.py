import pytest
from typing import Dict, List, Optional
from src.agent_tools import ResourceQueryTools
from firebase_utils import initialize_firebase
from llama_index.core import Settings
from tests.test_agent_tools import TEST_CASES

@pytest.fixture
def llm_client():
    """Initialize LLM client for testing"""
    Settings.llm = None  # Replace with your actual LLM initialization
    return Settings.llm

@pytest.fixture
def mock_cred_path():
    """Provide a mock credential path for testing"""
    return "tests/mock_firebase_credentials.json"

@pytest.fixture
def firebase_db(mock_cred_path):
    """Initialize Firebase DB for testing"""
    db, _ = initialize_firebase(mock_cred_path)
    return db

@pytest.fixture
def availability_db(mock_cred_path):
    """Initialize availability DB for testing"""
    _, availability_db = initialize_firebase(mock_cred_path)
    return availability_db

@pytest.fixture
def query_tools(firebase_db, availability_db, llm_client):
    """Create ResourceQueryTools instance with real dependencies"""
    return ResourceQueryTools(firebase_db, availability_db, llm_client)

class TestIntegrationQueryProcessing:
    """Integration tests for query processing with actual LLM"""
    
    @pytest.mark.integration
    @pytest.mark.parametrize("query,expected", TEST_CASES["basic"])
    def test_basic_queries(self, query_tools, query, expected):
        """Test basic query construction with real LLM"""
        result = query_tools.construct_query(query)
        assert all(key in result for key in expected.keys())
        assert all(result[key] == expected[key] for key in expected.keys())

    @pytest.mark.integration
    @pytest.mark.parametrize("query,expected", TEST_CASES["hierarchy"])
    def test_hierarchy_queries(self, query_tools, query, expected):
        """Test hierarchy-based queries with real LLM"""
        result = query_tools.construct_query(query)
        assert "ranks" in result
        assert set(result["ranks"]) == set(expected["ranks"])

    @pytest.mark.integration
    def test_complex_queries(self, query_tools):
        """Test more complex queries that require LLM understanding"""
        queries = [
            (
                "find me experienced cloud engineers in London who can lead projects",
                {"location": "London", "skills": ["Cloud Engineer"], "rank": "Senior Consultant"}
            ),
            (
                "who are our technical architects across all locations",
                {"skills": ["Solution Architect"]}
            ),
            (
                "show me all frontend and backend developers below principal level",
                {
                    "skills": ["Frontend Developer", "Backend Developer"],
                    "ranks": ["Senior Consultant", "Consultant", "Consultant Analyst", "Analyst"]
                }
            )
        ]
        
        for query, expected in queries:
            result = query_tools.construct_query(query)
            assert all(key in result for key in expected.keys())
            for key, value in expected.items():
                if isinstance(value, list):
                    assert set(result[key]) == set(value)
                else:
                    assert result[key] == value

    @pytest.mark.integration
    def test_query_with_database(self, query_tools):
        """Test full query flow including database interaction"""
        query = "Frontend Developers in London"
        
        # First test query construction
        structured_query = query_tools.construct_query(query)
        assert "skills" in structured_query
        assert "Frontend Developer" in structured_query["skills"]
        assert structured_query["location"] == "London"
        
        # Then test actual database query
        result = query_tools.query_people(json.dumps(structured_query))
        assert isinstance(result, str)
        assert "| Name | Location | Rank |" in result  # Table header should be present
        assert "London" in result  # Location should be in results
        assert "Frontend Developer" in result  # Skill should be in results
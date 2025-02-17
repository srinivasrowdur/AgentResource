import pytest
from typing import Dict, List, Optional
from src.query_tools.base import BaseResourceQueryTools

class TestBaseQueryTools:
    """Test base class functionality only"""
    
    def test_rank_hierarchy(self):
        """Test rank hierarchy structure"""
        tools = BaseResourceQueryTools()
        assert 'Partner' in tools.RANK_HIERARCHY
        assert tools.RANK_HIERARCHY['Partner'] < tools.RANK_HIERARCHY['Consultant']

    def test_standard_skills(self):
        """Test standard skills initialization"""
        tools = BaseResourceQueryTools()
        assert "Frontend Developer" in tools.standard_skills
        assert "Backend Developer" in tools.standard_skills

class TestBaseQueryTools(BaseResourceQueryTools):
    """Concrete implementation for testing base class"""
    def query_people(self, query_str: str) -> str:
        return str(self.construct_query(query_str))

@pytest.mark.parametrize("query,expected", [
    (
        "consultants in London",
        {"rank": "Consultant", "location": "London"}
    ),
    (
        "Senior Consultants in Manchester",
        {"rank": "Senior Consultant", "location": "Manchester"}
    ),
    (
        "all consultants",
        {"ranks": [
            'Principal Consultant', 'Managing Consultant', 'Senior Consultant',
            'Consultant', 'Consultant Analyst'
        ]}
    ),
    (
        "Frontend Developers in Bristol",
        {"location": "Bristol", "skills": ["Frontend Developer"]}
    ),
])
def test_shared_query_construction(query, expected):
    tools = TestBaseQueryTools()
    assert tools.construct_query(query) == expected 
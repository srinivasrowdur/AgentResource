import pytest
from tests.test_agent_tools import MockResourceQueryTools, TEST_CASES

@pytest.fixture
def query_tools():
    return MockResourceQueryTools()

class TestAvailabilityQueries:
    @pytest.fixture
    def tools(self):
        return MockResourceQueryTools()

    @pytest.mark.parametrize("query,expected", TEST_CASES["availability"])
    def test_availability_parsing(self, tools, query, expected):
        result = tools.construct_query(query)
        assert result == expected 
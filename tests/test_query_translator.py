import pytest
from src.query_tools.query_translator import QueryTranslator

@pytest.fixture
def translator():
    return QueryTranslator()

def test_rank_queries(translator):
    # Test basic rank query
    assert translator.translate_query("consultants in London") == {
        "locations": ["London"],
        "ranks": ["Consultant"],
        "skills": list(translator.all_skills)
    }

    # Test ranks below query
    result = translator.translate_query("below PC")
    assert result["ranks"] == [
        "Senior Consultant", "Consultant", "Consultant Analyst", "Analyst"
    ]
    assert set(result["locations"]) == set(translator.all_locations)

    # Test ranks above query
    result = translator.translate_query("above consultant")
    assert result["ranks"] == [
        "Partner", "Associate Partner", "Consulting Director",
        "Managing Consultant", "Principal Consultant", "Senior Consultant"
    ]

def test_location_queries(translator):
    # Test specific location
    result = translator.translate_query("engineers in Oslo")
    assert result["locations"] == ["Oslo"]

    # Test no location specified
    result = translator.translate_query("all consultants")
    assert set(result["locations"]) == set(translator.all_locations)

def test_skill_queries(translator):
    # Test specific skill with related skills
    result = translator.translate_query("cloud engineers")
    assert set(result["skills"]) == {
        "Cloud Engineer", "AWS Engineer", "Solution Architect", "DevOps Engineer"
    }

    # Test skill plurals
    result = translator.translate_query("frontend developers")
    assert set(result["skills"]) == {"Frontend Developer", "Full Stack Developer"}

def test_complex_queries(translator):
    # Test combination of rank, location, and skill
    result = translator.translate_query("cloud engineers below PC in Oslo")
    assert result == {
        "locations": ["Oslo"],
        "ranks": ["Senior Consultant", "Consultant", "Consultant Analyst", "Analyst"],
        "skills": ["Cloud Engineer", "AWS Engineer", "Solution Architect", "DevOps Engineer"]
    }

    # Test with rank alias
    result = translator.translate_query("MC in London")
    assert result == {
        "locations": ["London"],
        "ranks": ["Managing Consultant"],
        "skills": list(translator.all_skills)
    }

def test_empty_query(translator):
    # Test empty query returns all options
    result = translator.translate_query("")
    assert set(result["locations"]) == set(translator.all_locations)
    assert set(result["ranks"]) == set(translator.RANK_LEVELS.keys())
    assert set(result["skills"]) == translator.all_skills
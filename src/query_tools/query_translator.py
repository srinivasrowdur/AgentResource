from typing import Dict, List, Set, Optional
import json
from src.settings import Settings

class QueryTranslator:
    """Comprehensive query translator for resource management system"""

    # Rank hierarchy and aliases
    RANK_HIERARCHY = {
        'Partner': ['Par', 'partner'],
        'Associate Partner': ['AP', 'associate partner'],
        'Consulting Director': ['CD', 'consulting director'],
        'Managing Consultant': ['MC', 'management consultant', 'managing consultant'],
        'Principal Consultant': ['PC', 'principal consultant'],
        'Senior Consultant': ['SC', 'senior consultant'],
        'Consultant': ['C', 'consultant'],
        'Consultant Analyst': ['CA', 'consultant analyst'],
        'Analyst': ['A', 'analyst']
    }

    RANK_LEVELS = {
        'Partner': 1,
        'Associate Partner': 2,
        'Consulting Director': 2,
        'Managing Consultant': 3,
        'Principal Consultant': 4,
        'Senior Consultant': 5,
        'Consultant': 6,
        'Consultant Analyst': 7,
        'Analyst': 8
    }

    # Location groupings
    LOCATIONS = {
        'Britain': ['London', 'Bristol', 'Manchester'],
        'Northern Ireland': ['Belfast'],
        'Nordics': ['Oslo', 'Copenhagen', 'Stockholm']
    }

    # Skill relationships mapping
    SKILL_RELATIONSHIPS = {
        'Frontend Developer': ['Full Stack Developer'],
        'Backend Developer': ['Full Stack Developer'],
        'AWS Engineer': ['Cloud Engineer', 'Solution Architect'],
        'Cloud Engineer': ['AWS Engineer', 'Solution Architect', 'DevOps Engineer'],
        'DevOps Engineer': ['Cloud Engineer'],
        'Data Engineer': [],
        'Solution Architect': ['Cloud Engineer'],
        'Business Analyst': [],
        'Product Manager': ['Digital Consultant'],
        'Agile Coach': ['Scrum Master', 'Project Manager'],
        'Scrum Master': ['Agile Coach'],
        'Project Manager': ['Agile Coach', 'Scrum Master'],
        'Digital Consultant': ['Product Manager']
    }

    def __init__(self):
        # Create reverse mappings for ranks
        self.rank_aliases = {}
        for rank, aliases in self.RANK_HIERARCHY.items():
            for alias in aliases:
                self.rank_aliases[alias.lower()] = rank

        # Flatten location list
        self.all_locations = []
        for locations in self.LOCATIONS.values():
            self.all_locations.extend(locations)

        # Get all unique skills
        self.all_skills = set(self.SKILL_RELATIONSHIPS.keys())

    def translate_query(self, query: str) -> Dict:
        """Translate natural language query to structured JSON"""
        # Check if query is about availability
        if isinstance(query, str) and any(word in query.lower() for word in ['available', 'availability', 'week']):
            # Extract employee numbers from previous results if they exist
            emp_numbers = []
            lines = query.split('\n')
            for line in lines:
                if '|' in line and 'EMP' in line:
                    parts = line.split('|')
                    emp_id = next((part.strip() for part in parts if 'EMP' in part), None)
                    if emp_id:
                        emp_numbers.append(emp_id)
            
            # Extract week numbers
            weeks = []
            query_lower = query.lower()
            if 'week' in query_lower:
                import re
                week_nums = re.findall(r'week\s*(\d+)', query_lower)
                weeks.extend(int(num) for num in week_nums)
                
            if emp_numbers and weeks:
                return {
                    'employee_numbers': emp_numbers,
                    'weeks': sorted(weeks)
                }

        prompt = '''You are an AI assistant that generates structured JSON responses for queries related to job ranks, locations, and skills within a consulting firm. Follow these guidelines strictly.

1. RANK HIERARCHY & ALIASES (Recognise in Queries, but Exclude from JSON Output)
The firm's rank hierarchy is structured as follows, from highest to lowest:

1. Partner (Alias: Par)
2. Associate Partner / Consulting Director (Aliases: AP, CD) - These are at the same rank level
3. Management Consultant (Alias: MC)
4. Principal Consultant (Alias: PC)
5. Senior Consultant (Alias: SC)
6. Consultant (Alias: C)
7. Consultant Analyst (Alias: CA)
8. Analyst (Alias: A)

RULES FOR RANKS:
- Recognise abbreviations (AP, MC, SC, etc.) in queries but do not include them in JSON output
- For "ranks below X", return only lower ranks
- For "ranks above X", return only higher ranks
- For single rank queries, return only that rank
- If no rank mentioned, return all ranks
- For "Management Consultant" or "MC", return exactly "Managing Consultant" rank
- For "All Consultants":
  - By default, return all ranks in the firm
  - For singular "Consultant", return only mid-level Consultant rank
- For "above" or "below" rank queries, treat Associate Partner (AP) and Consulting Director (CD) as equal:
  - "Above MC" → Partner, Associate Partner, Consulting Director
  - "Below AP" or "Below CD" → Management Consultant and all lower ranks

2. RECOGNISED LOCATIONS
The following locations are recognised:

- Britain: London, Bristol, Manchester
- Northern Ireland: Belfast
- Nordics: Oslo, Copenhagen, Stockholm

RULES FOR LOCATIONS:
- For "Britain" queries, include only London, Bristol, Manchester (excluding Belfast)
- For "Nordics" queries, include only Oslo, Copenhagen, Stockholm
- If no location specified, return all locations
- If location does not exist in database, return {}

3. SKILL CATEGORIES & FLEXIBLE MAPPING
Technical Skills:
- Frontend Developer → May relate to Full Stack Developer
- Backend Developer → May relate to Full Stack Developer
- AWS Engineer → May relate to Cloud Engineer, Solution Architect
- Cloud Engineer → May relate to AWS Engineer, Solution Architect, DevOps Engineer
- DevOps Engineer → May relate to Cloud Engineer
- Data Engineer → Standalone
- Solution Architect → May relate to Cloud Engineer

Business/Management Skills:
- Business Analyst → Standalone
- Product Manager → May relate to Digital Consultant
- Agile Coach → May relate to Scrum Master, Project Manager
- Scrum Master → May relate to Agile Coach
- Project Manager → May relate to Agile Coach, Scrum Master
- Digital Consultant → May relate to Product Manager

RULES FOR SKILLS:
- If no skill mentioned, return all skills
- Treat plurals and singulars as same (e.g., "Cloud Engineers" = "Cloud Engineer")
- Include all relevant related skills in matches

4. QUERY UNDERSTANDING & FOLLOW-UP HANDLING
- If no rank mentioned, return all ranks
- If no skill mentioned, return all skills
- If no location mentioned, return all locations
- Treat plurals and singulars as same
- For follow-up queries referencing "same skills" or "same location", maintain context
  Example:
  - First Query: "Management consultants in Bristol with frontend skills"
  - Follow-up: "Anyone with the same skills in Bristol above MC"
  - Response: Include Frontend & Full Stack Developer skills, with Partner, AP, CD ranks in Bristol

5. JSON RESPONSE FORMAT
Response must be in structured JSON format:
{
  "locations": ["<Location(s)>"],
  "ranks": ["<Rank(s)>"],
  "skills": ["<Skill(s)>"],
  "employee_numbers": ["<Employee IDs>"],  // Only for availability queries
  "weeks": [<Week Numbers>]  // Only for availability queries
}

Query: {query}'''
        
        formatted_prompt = prompt.format(query=query)
        response = Settings.llm.complete(formatted_prompt, temperature=0.1).text.strip()
        
        # Clean and parse JSON
        if not response.startswith('{'):
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                response = response[start:end]
            else:
                return {}
        
        try:
            structured_query = json.loads(response)
            validated_query = self.validate_query(structured_query)
            return validated_query
        except json.JSONDecodeError:
            return {}

    def validate_query(self, query: dict) -> dict:
        """Validate and clean up the query response"""
        valid_query = {}
        
        # Validate locations
        if 'locations' in query:
            valid_locations = [loc for loc in query['locations'] 
                             if loc in self.all_locations]
            if valid_locations:
                valid_query['locations'] = valid_locations
        
        # Validate ranks
        if 'ranks' in query:
            valid_ranks = [r for r in query['ranks'] 
                         if r in self.RANK_LEVELS]
            if valid_ranks:
                valid_query['ranks'] = valid_ranks
        
        # Validate skills
        if 'skills' in query:
            valid_skills = [s for s in query['skills'] 
                          if s in self.all_skills]
            if valid_skills:
                valid_query['skills'] = valid_skills
        
        return valid_query

    def translate_query_to_json(self, query: str) -> str:
        """Convert query to JSON string"""
        try:
            result = self.translate_query(query)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({'error': str(e)})
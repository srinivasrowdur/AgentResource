from llama_index.core.tools import FunctionTool
from llama_index.core import Settings
from typing import List, Dict, Optional, Union
import json
from firebase_utils import (
    fetch_employees, 
    fetch_availability, 
    fetch_availability_batch,
)
from datetime import datetime, timedelta
from src.query_tools.base import BaseResourceQueryTools

def preprocess_query(query: str) -> Dict[str, any]:
    """Preprocess and validate the query"""
    query = query.lower().strip()
    
    # Common patterns to extract
    patterns = {
        'rank_keywords': ['partner', 'consultant', 'associate', 'principal', 'senior', 'managing'],
        'location_keywords': ['london', 'manchester', 'bristol', 'belfast'],
        'time_keywords': ['week', 'available', 'availability'],
        'skill_keywords': ['developer', 'engineer', 'architect', 'analyst', 'manager', 'coach']
    }
    
    # Extract basic query type
    query_type = 'availability' if any(word in query for word in patterns['time_keywords']) else 'people'
    
    # Extract potential filters
    filters = {
        'rank': any(word in query for word in patterns['rank_keywords']),
        'location': any(word in query for word in patterns['location_keywords']),
        'skills': any(word in query for word in patterns['skill_keywords'])
    }
    
    return {
        'type': query_type,
        'filters': filters,
        'raw_query': query
    }

# Organization hierarchy (from highest to lowest rank)
RANK_HIERARCHY = {
    'Partner': 1,
    'Associate Partner': 2,
    'Consulting Director': 2,  # Same level as Associate Partner
    'Principal Consultant': 3,
    'Managing Consultant': 4,  # MC
    'Senior Consultant': 5,
    'Consultant': 6,
    'Consultant Analyst': 7,
    'Analyst': 8
}

class ResourceQueryTools(BaseResourceQueryTools):
    """Production version with Firebase integration"""
    
    def __init__(self, db, availability_db, llm_client):
        super().__init__()
        self.db = db
        self.availability_db = availability_db
        self.llm = llm_client

    def construct_query(self, query_str: str) -> dict:
        """Convert natural language to structured query"""
        try:
            prompt = '''You are an intelligent query parser for employee searches. Your task is to extract and map information from natural language queries into structured JSON objects. Always ensure that your output is valid JSON.

AVAILABLE DATA:
1. Ranks (from highest to lowest):
   - Partner
   - Associate Partner
   - Consulting Director
   - Managing Consultant
   - Principal Consultant
   - Senior Consultant
   - Consultant
   - Consultant Analyst
   - Analyst

2. Locations:
   - UK: London, Manchester, Bristol, Belfast
   - Nordics: Copenhagen, Stockholm, Oslo

3. Skills:
   - Frontend Developer
   - Backend Developer
   - Full Stack Developer
   - AWS Engineer
   - Cloud Engineer
   - DevOps Engineer
   - Data Engineer
   - Solution Architect
   - Business Analyst
   - Product Manager
   - Agile Coach
   - Scrum Master
   - Project Manager
   - Digital Consultant

MAPPING RULES:
1. Location Mapping:
   - For "outside UK" or "outside the UK":
     {{"locations": ["Copenhagen", "Stockholm", "Oslo"]}}
   - For "in UK" or "in the UK":
     {{"locations": ["London", "Manchester", "Bristol", "Belfast"]}}
   - For specific city:
     {{"location": "City"}}  # Use exact city name

2. Rank Mapping:
   - For "all consultants" or similar:
     {{"ranks": ["Principal Consultant", "Managing Consultant", "Senior Consultant", "Consultant", "Consultant Analyst"]}}
   - For specific rank (handle plural forms):
     {{"rank": "Exact Rank"}}  # Use exact rank name

3. Skills Mapping:
   - For skill matches (including synonyms):
     {{"skills": ["Exact Skill"]}}  # Use exact skill name
   - Examples:
     "frontend engineer" -> {{"skills": ["Frontend Developer"]}}
     "AWS resource" -> {{"skills": ["AWS Engineer"]}}

GENERAL INSTRUCTIONS:
- Identify keywords in the natural language query that correspond to ranks, locations, and skills
- Correct for variations in wording (e.g., plural vs singular forms, synonyms, and different phrasing)
- If the query includes multiple elements (e.g. a rank and a location), include all relevant keys in the resulting JSON
- Always produce valid JSON as your output
- Handle informal language (e.g. "devs" -> "Developer", "resources" -> match to appropriate rank/skill)
- For ambiguous queries, use the most specific interpretation based on available data

EXAMPLE QUERIES AND OUTPUTS:
1. "consultants in London" -> 
   {{"rank": "Consultant", "location": "London"}}

2. "partners outside UK" -> 
   {{"rank": "Partner", "locations": ["Copenhagen", "Stockholm", "Oslo"]}}

3. "frontend developers in Oslo" -> 
   {{"skills": ["Frontend Developer"], "location": "Oslo"}}

4. "all consultants in UK" -> 
   {{"ranks": ["Principal Consultant", "Managing Consultant", "Senior Consultant", "Consultant", "Consultant Analyst"], 
    "locations": ["London", "Manchester", "Bristol", "Belfast"]}}

5. "AWS engineers in Manchester" -> 
   {{"skills": ["AWS Engineer"], "location": "Manchester"}}

6. "available senior consultants" ->
   {{"rank": "Senior Consultant"}}

Query: {query}'''
            
            formatted_prompt = prompt.format(query=query_str)
            response = self.llm.complete(formatted_prompt, temperature=0.1).text.strip()
            
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
            
        except Exception:
            return {}

    def validate_query(self, query: dict) -> dict:
        """Validate and clean up the LLM response"""
        valid_query = {}
        
        # Location validation
        if 'location' in query and isinstance(query['location'], str):
            if query['location'] in self.locations:
                valid_query['location'] = query['location']
        
        # Handle location arrays for UK/non-UK queries
        if 'locations' in query and isinstance(query['locations'], list):
            valid_locations = [loc for loc in query['locations'] if loc in self.locations]
            if valid_locations:
                # Convert to 'in' query for Firestore
                valid_query['location_in'] = valid_locations
        
        # Rank validation
        if 'rank' in query and isinstance(query['rank'], str):
            if query['rank'] in self.RANK_HIERARCHY:
                valid_query['rank'] = query['rank']
        
        # Ranks validation
        if 'ranks' in query and isinstance(query['ranks'], list):
            valid_ranks = [r for r in query['ranks'] if r in self.RANK_HIERARCHY]
            if valid_ranks:
                valid_query['ranks'] = valid_ranks
        
        # Skills validation
        if 'skills' in query and isinstance(query['skills'], list):
            valid_skills = [s for s in query['skills'] if s in self.standard_skills]
            if valid_skills:
                valid_query['skills'] = valid_skills
        
        return valid_query

    def query_people(self, query: str) -> str:
        """Query people based on JSON query"""
        try:
            # Handle string input (from translator)
            if isinstance(query, str):
                try:
                    structured_query = json.loads(query)
                except json.JSONDecodeError:
                    return "Error: Invalid JSON query format"
            else:
                structured_query = query

            # Execute query
            results = fetch_employees(self.db, structured_query)
            if not results:
                return f"No employees found matching: {structured_query}"
            
            # Format results
            table = "| Name | Location | Rank | Skills | Employee ID |\n"
            table += "|------|----------|------|---------|-------------|\n"
            
            for emp in results:
                skills = ", ".join(emp.get('skills', []))
                table += f"| {emp['name']} | {emp['location']} | {emp['rank']} | {skills} | {emp['employee_number']} |\n"
            
            return table
        except Exception as e:
            return f"Error executing query: {str(e)}"

    def get_ranks_below(self, rank: str) -> List[str]:
        """Get all ranks below the specified rank"""
        if rank.lower() == 'mc':
            rank = 'Managing Consultant'
        target_level = self.RANK_HIERARCHY.get(rank)
        if not target_level:
            return []
        return sorted([r for r, level in self.RANK_HIERARCHY.items() 
                      if level > target_level],
                     key=lambda x: self.RANK_HIERARCHY[x])

    def is_rank_below(self, rank1: str, rank2: str) -> bool:
        """Check if rank1 is below rank2"""
        return self.RANK_HIERARCHY.get(rank1, 0) < self.RANK_HIERARCHY.get(rank2, 0)
    
    def is_rank_above(self, rank1: str, rank2: str) -> bool:
        """Check if rank1 is above rank2"""
        return self.RANK_HIERARCHY.get(rank1, 0) > self.RANK_HIERARCHY.get(rank2, 0)
    
    def is_fully_available(self, pattern: str, status: str) -> bool:
        """Check if someone is truly fully available"""
        pattern = pattern.strip() if pattern else ""
        status = status.strip() if status else ""
        return pattern == "Generally available" and status == "Available"

    def translate_skill_query(self, skill_query: str) -> Optional[str]:
        """Use LLM to translate skill query to standard form"""
        prompt = f"""Given this request: "{skill_query}"
        Map it to ONE of our standard skills:
        {', '.join(sorted(self.standard_skills))}
        
        Rules:
        1. Return EXACTLY ONE skill from the list above
        2. Match variations like:
           - "frontend engineer" → "Frontend Developer"
           - "UI developer" → "Frontend Developer"
           - "AWS resource" → "AWS Engineer"
        3. Return the EXACT skill name with correct capitalization
        4. If no match, return "None"
        
        Examples:
        Input: "frontend engineer" → Output: Frontend Developer
        Input: "AWS resource" → Output: AWS Engineer
        Input: "random skill" → Output: None
        """
        
        response = Settings.llm.complete(prompt)
        normalized = response.text.strip()
        
        if normalized in self.standard_skills:
            return normalized
        return None

    def extract_employee_name(self, query: str) -> Optional[str]:
        """Extract employee name from phrases like 'similar to John Smith' or 'like Jane Doe'"""
        for phrase in ["similar to", "like"]:
            if phrase in query:
                # Get text after the phrase and clean it
                name = query.split(phrase)[1].strip()
                return name.title()  # Convert "john smith" to "John Smith"
        return None

    def get_employee_skills(self, db, name: str) -> List[str]:
        """Get skills for an employee by their name"""
        # Query employee by name
        employees = fetch_employees(db, {"name": name})
        if employees and len(employees) > 0:
            return employees[0].get('skills', [])
        return []

    def query_availability(self, employee_numbers: Union[str, List[str]], weeks: Optional[List[int]] = None) -> str:
        """First get employees matching criteria, then check their availability"""
        try:
            # Get employees first if we have a query string
            if isinstance(employee_numbers, dict) and "query_str" in employee_numbers:
                results = self.query_people(employee_numbers["query_str"])
                if isinstance(results, str) and "No matching employees found" not in results:
                    employee_numbers = [line.split("|")[-2].strip() for line in results.split("\n")[2:] if "|" in line]

            if isinstance(employee_numbers, str):
                employee_numbers = [employee_numbers]
            
            if not weeks:
                weeks = list(range(1, 9))
            
            # Use existing fetch_availability_batch function
            results = fetch_availability_batch(self.db, employee_numbers, weeks)
            
            # Format as markdown table
            # Create header only for requested weeks
            week_headers = [f"Week {w}" for w in weeks]
            table = f"| Name | Pattern | {' | '.join(week_headers)} |\n"
            table += f"|------|---------|{'|'.join(['---'] * len(week_headers))}|"
            
            for emp_id, data in results.items():
                name = data["employee_data"].get("name", "Unknown")
                pattern = data["availability"].get("pattern_description", "")
                
                # Get weekly status only for requested weeks
                week_status = []
                for week_num in weeks:
                    week_key = f"week_{week_num}"
                    status = data["weeks"].get(week_key, {}).get("status", "Unknown")
                    week_status.append(status)
                
                # Add row to table
                table += f"\n| {name} | {pattern} | {' | '.join(week_status)} |"
            
            return table
            
        except Exception as e:
            return f"Error querying availability: {str(e)}"

    def query_available_people(self,
                         skills: Optional[List[str]] = None,
                         location: Optional[str] = None,
                         rank: Optional[str] = None,
                         rank_below: Optional[str] = None,
                         rank_above: Optional[str] = None,
                         employee_numbers: Optional[List[str]] = None,
                         weeks: Optional[List[int]] = None) -> str:
        """Query people with their availability in one go"""
        try:
            # First get matching people
            if employee_numbers:
                # If we have specific employee numbers, use those
                filters = {'employee_numbers': employee_numbers}
            else:
                # Otherwise use other filters
                filters = {}
                if skills:
                    filters['skills'] = skills
                if location:
                    filters['location'] = location
                if rank:
                    filters['rank'] = rank
                
            people_results = self.query_people(**filters)
            if "No employees found" in people_results:
                return people_results
            
            # Extract employee numbers and details
            emp_numbers = []
            emp_details = {}
            for line in people_results.split('\n'):
                if '|' in line and 'EMP' in line:
                    parts = [p.strip() for p in line.split('|')]
                    emp_id = parts[-2]
                    emp_rank = parts[3]
                    
                    # Apply rank filters
                    if rank_below and not self.is_rank_below(emp_rank, rank_below):
                        continue
                    if rank_above and not self.is_rank_above(emp_rank, rank_above):
                        continue
                        
                    emp_details[emp_id] = {
                        'name': parts[1],
                        'location': parts[2],
                        'rank': emp_rank,
                        'skills': parts[4]
                    }
                    emp_numbers.append(emp_id)
            
            if not emp_numbers:
                return "No employees found matching the rank criteria."
            
            # Get availability in one query
            availability = self.query_availability(emp_numbers, weeks)
            
            # Filter for fully available people
            fully_available = []
            availability_details = {}
            
            for line in availability.split('\n'):
                if '|' in line:
                    parts = [p.strip() for p in line.split('|')]
                    if len(parts) < 4:  # Skip header/separator lines
                        continue
                        
                    name = parts[1]
                    pattern = parts[2]
                    status = parts[3]
                    
                    # Store availability details for all matching people
                    emp_id = next((id for id, details in emp_details.items() 
                                 if details['name'] == name), None)
                    if emp_id:
                        availability_details[emp_id] = {
                            'pattern': pattern,
                            'status': status
                        }
                        
                        if self.is_fully_available(pattern, status):
                            fully_available.append(emp_details[emp_id])
            
            # Format the response
            response = "Found matching employees:\n"
            response += "\n".join([line for line in people_results.split('\n') 
                                 if any(emp['name'] in line for emp in emp_details.values())])
            
            response += "\n\nAvailability Status:\n"
            for emp_id, emp in emp_details.items():
                avail = availability_details.get(emp_id, {})
                pattern = avail.get('pattern', 'Unknown')
                status = avail.get('status', 'Unknown')
                is_available = self.is_fully_available(pattern, status)
                
                response += f"\n{'✓' if is_available else '❌'} {emp['name']} ({emp['rank']}):\n"
                response += f"  - Pattern: {pattern}\n"
                response += f"  - Status: {status}\n"
            
            response += "\n"
            if fully_available:
                response += "FULLY AVAILABLE PEOPLE:\n"
                for emp in sorted(fully_available, 
                                key=lambda x: (self.RANK_HIERARCHY.get(x['rank'], 0), x['name']), 
                                reverse=True):
                    response += f"✓ {emp['name']} ({emp['rank']}, {emp['location']})\n"
            else:
                response += "❌ No fully available people found.\n"
            
            return response
            
        except Exception as e:
            return f"Error querying available people: {str(e)}"

    def get_ranks_tool(self, query_str: str) -> str:
        """Tool interface for rank queries"""
        # Handle both string and dict inputs
        if isinstance(query_str, dict):
            query_str = query_str.get('query_str', '')
        
        query_lower = str(query_str).lower()
        
        if "below" in query_lower:
            # Special handling for MC
            if "mc" in query_lower:
                ranks = self.get_ranks_below("Managing Consultant")
                return f"Ranks below Managing Consultant (MC):\n- " + "\n- ".join(ranks)
            # Handle other ranks
            for rank in self.RANK_HIERARCHY.keys():
                if rank.lower().replace(' ', '') in query_lower:
                    ranks = self.get_ranks_below(rank)
                    return f"Ranks below {rank}:\n- " + "\n- ".join(ranks)
        
        return "Please specify a rank query like 'below MC' or 'below Partner'"

    def get_tools(self):
        """Get the tools for the agent"""
        return [
            FunctionTool.from_defaults(
                fn=self.translate_query,
                name="QueryTranslator",
                description="""
                Translates natural language queries into structured JSON format.
                ALWAYS use this tool first to translate user queries.
                
                Input: A natural language query as a string
                Output: A JSON formatted query
                
                EXAMPLE INPUTS AND OUTPUTS:
                1. Input: "consultants in London"
                   Output: {"rank":"Consultant","location":"London"}
                
                2. Input: "all consultants"
                   Output: {"ranks":["Principal Consultant","Managing Consultant","Senior Consultant","Consultant","Consultant Analyst"]}
                
                3. Input: "Frontend Developers in Oslo"
                   Output: {"skills":["Frontend Developer"],"location":"Oslo"}
                """
            ),
            FunctionTool.from_defaults(
                fn=self.query_people,
                name="PeopleQuery",
                description="""
                Queries employees using a structured JSON query.
                ONLY use this after getting JSON from QueryTranslator.
                
                Input must be a valid JSON query with these possible fields:
                - rank: single rank name
                - ranks: array of rank names
                - location: location name
                - skills: array of skill names
                """
            ),
            FunctionTool.from_defaults(
                fn=self.get_ranks_tool,
                name="RankQuery",
                description="""
                Get information about rank hierarchy.
                
                WHEN TO USE:
                - When you need to understand which ranks are below another rank
                - When you need to verify the rank hierarchy
                - Before making complex rank-based queries
                
                RANK HIERARCHY (highest to lowest):
                Partner > Associate Partner = Consulting Director > Managing Consultant (MC) >
                Principal Consultant > Senior Consultant > Consultant > Consultant Analyst > Analyst
                
                EXAMPLE QUERIES:
                - "below MC" -> returns all ranks below Managing Consultant
                - "below Partner" -> returns all ranks below Partner
                
                Use this tool to understand rank relationships before making PeopleQuery calls.
                """
            ),
            FunctionTool.from_defaults(
                fn=self.query_availability,
                name="AvailabilityQuery",
                description="""
                Check availability for specific employees.
                
                WHEN TO USE:
                - After finding employees with PeopleQuery
                - When you need to check availability for specific weeks
                
                Input should be a list of employee IDs and week numbers.
                """
            )
        ]

    def translate_query(self, query_str: str) -> str:
        """Translate natural language query to JSON structure"""
        try:
            if not isinstance(query_str, str):
                return "Error: Query must be a string"
            
            # Get structured query
            structured_query = self.construct_query(query_str)
            if not structured_query:
                return "Error: Could not parse query structure"
            
            # Return formatted JSON
            return json.dumps(structured_query, indent=2)
            
        except Exception as e:
            return f"Error translating query: {str(e)}"
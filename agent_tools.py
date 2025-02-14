from llama_index.core.tools import FunctionTool
from llama_index.core import Settings
from typing import List, Dict, Optional, Union
import json
from firebase_utils import fetch_employees, fetch_availability, fetch_availability_batch
from datetime import datetime, timedelta

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

class ResourceQueryTools:
    def __init__(self, db, availability_db):
        self.db = db
        self.availability_db = availability_db
        
        # Keep only the standard/canonical forms
        self.standard_skills = {
            "Frontend Developer",
            "Backend Developer",
            "Full Stack Developer",
            "AWS Engineer",
            "GCP Engineer",
            "Cloud Engineer",
            "Architect",
            "Product Manager",
            "Agile Coach",
            "Business Analyst"
        }

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

    def query_people(self, 
                    skills: Optional[List[str]] = None,
                    location: Optional[str] = None,
                    rank: Optional[str] = None,
                    name: Optional[str] = None,
                    employee_number: Optional[str] = None) -> str:
        """Query people data efficiently"""
        try:
            # Debug print
            print(f"Original query: skills={skills}, location={location}, rank={rank}")
            
            # Translate skills if provided
            if skills:
                normalized_skills = []
                for skill in skills:
                    translated = self.translate_skill_query(skill)
                    if translated:
                        normalized_skills.append(translated)
                    else:
                        print(f"Warning: Could not translate skill '{skill}'")
                
                # Only update skills if we got valid translations
                if normalized_skills:
                    skills = normalized_skills
                    print(f"Translated skills: {skills}")
                else:
                    return "I couldn't understand the requested skill. Please use terms like 'Frontend Developer', 'Backend Developer', 'AWS Engineer', etc."
            
            # Build server-side filters first
            filters = {}
            
            if employee_number:
                filters['employee_number'] = employee_number
            
            if rank:
                filters['rank'] = rank.title()
            
            if location:
                filters['location'] = location.title()
            
            if name:
                filters['name'] = name
            
            if skills:
                # Add skills to server-side filters
                filters['skills'] = skills[0]  # Use first skill for initial filter
            
            # Get filtered data from server
            print(f"Executing query with filters: {filters}")
            employees = fetch_employees(self.db, filters)
            print(f"Query returned {len(employees)} results")
            
            # Apply additional skills filters in memory if needed
            if skills and len(skills) > 1:
                employees = [emp for emp in employees 
                           if all(skill in emp["skills"] for skill in skills)]
            
            # Format results
            if not employees:
                return "No employees found matching your criteria."
            
            table = "| Name | Location | Rank | Skills | Employee ID |\n"
            table += "|------|----------|------|---------|-------------|\n"
            
            for emp in sorted(employees, key=lambda x: (x["rank"]["official_name"], x["name"])):
                skills_str = ", ".join(emp["skills"])
                table += f"| {emp['name']} | {emp['location']} | {emp['rank']['official_name']} | {skills_str} | {emp['employee_number']} |\n"
            
            return table
            
        except Exception as e:
            print(f"Debug - Error in query_people: {str(e)}")
            return f"Error querying employees: {str(e)}"

    def query_availability(self, 
                         employee_numbers: Union[str, List[str]],
                         weeks: Optional[List[int]] = None) -> str:
        """Query availability efficiently for multiple employees"""
        try:
            if isinstance(employee_numbers, str):
                employee_numbers = [employee_numbers]
            
            if not weeks:
                weeks = list(range(1, 9))
            
            # Fetch all data in batches
            results = fetch_availability_batch(self.db, employee_numbers, weeks)
            
            # Format as markdown table
            table = "| Name | Pattern | Week 1 | Week 2 | Week 3 | Week 4 | Week 5 | Week 6 | Week 7 | Week 8 |\n"
            table += "|------|---------|---------|---------|---------|---------|---------|---------|---------|---------|"
            
            for emp_id, data in results.items():
                name = data["employee_data"].get("name", "Unknown")
                pattern = data["availability"].get("pattern_description", "")
                
                # Get weekly status
                week_status = []
                for week_num in range(1, 9):
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
                         weeks: Optional[List[int]] = None) -> str:
        """Query people with their availability in one go"""
        try:
            # First get matching people
            people_results = self.query_people(skills=skills, location=location, rank=rank)
            if "No employees found" in people_results:
                return people_results
            
            # Extract employee numbers
            emp_numbers = []
            for line in people_results.split('\n'):
                if '|' in line and 'EMP' in line:
                    emp_numbers.append(line.split('|')[-2].strip())
            
            # Get availability in one query
            availability = self.query_availability(emp_numbers, weeks)
            
            return f"Found matching employees:\n{people_results}\n\nAvailability:\n{availability}"
        except Exception as e:
            return f"Error querying available people: {str(e)}"

    def get_tools(self) -> List[FunctionTool]:
        """Get the tools for the agent to use"""
        return [
            FunctionTool.from_defaults(
                fn=self.query_available_people,
                name="QueryAvailablePeople",
                description="""
                Query people and their availability in one go.
                Use this for questions about who is available.
                
                Parameters:
                - skills: List of skills to filter by (e.g., ['Frontend Developer'])
                - location (optional): Office location
                - rank (optional): Job title
                - weeks: List of week numbers to check (e.g., [1] for week 1)
                
                Example: {'skills': ['Frontend Developer'], 'weeks': [1]}
                """
            ),
            FunctionTool.from_defaults(
                fn=self.query_people,
                name="PeopleQuery",
                description="Use only for queries that don't involve availability"
            ),
            FunctionTool.from_defaults(
                fn=self.query_availability,
                name="AvailabilityQuery",
                description="Use only when you already have employee numbers"
            )
        ]
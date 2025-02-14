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
    def __init__(self, db, _):  # Second parameter kept for compatibility
        self.db = db
        self.llm = Settings.llm

    def validate_query(self, query: str) -> bool:
        """Basic query validation"""
        if not query or len(query.strip()) < 3:
            return False
        return True

    def _semantic_match(self, query: str, category: str) -> str:
        """Use LLM to understand and match query semantically"""
        prompts = {
            "skill": """
            Given the input '{query}', map it to the most appropriate skill from our standard skills list:
            - Full Stack Developer (includes: fullstack, full-stack, full stack dev)
            - Backend Developer (includes: backend, back-end, server-side)
            - Frontend Developer (includes: frontend, front-end, UI developer)
            - AWS Engineer (includes: cloud engineer, aws specialist)
            - GCP Engineer (includes: google cloud, cloud platform)
            - Architect (includes: solution architect, technical architect)
            - Business Analyst (includes: BA, business analytics)
            - Product Manager (includes: PM, product owner)
            - Agile Coach (includes: scrum master, agile trainer)
            
            Return ONLY the exact skill name from the list above, or None if no match.
            """,
            "rank": """
            Match '{query}' to exactly one of these ranks:
            Partner
            Associate Partner
            Principal Consultant
            Managing Consultant
            Senior Consultant
            Consultant

            Rules:
            1. Return ONLY the exact rank name from the list above
            2. Do not add any explanation or extra text
            3. Do not add quotes
            4. If no match found, return None

            For example:
            'partner' matches to: Partner
            'sc' matches to: Senior Consultant
            'associate' matches to: Associate Partner
            'unknown' matches to: None
            """,
            "location": """
            Given the input '{query}', return EXACTLY ONE of these location names:
            - London
            - Manchester
            - Bristol
            - Belfast

            Return ONLY the exact location name, nothing else.
            """
        }

        prompt = prompts.get(category, "").format(query=query)
        response = self.llm.complete(prompt)
        
        # Clean up the response
        result = response.text.strip().replace('"', '').replace("'", "")
        
        # If result is too long, it's probably an explanation rather than a match
        if len(result.split()) > 3:
            print("Response too long, defaulting to None")
            return "None"
        
        return result

    def _find_employee_by_name(self, name: str, employees: List[dict]) -> List[dict]:
        """Find employee by name using various matching strategies"""
        if not name:
            return employees

        name = name.lower().strip()
        
        # Try exact match first
        matches = [emp for emp in employees if emp["name"].lower() == name]
        if matches:
            return matches

        # Try contains match
        matches = [emp for emp in employees if name in emp["name"].lower()]
        if matches:
            return matches

        return []

    def query_people(self, 
                    skills: Optional[List[str]] = None,
                    location: Optional[str] = None,
                    rank: Optional[str] = None,
                    name: Optional[str] = None,
                    employee_number: Optional[str] = None) -> str:
        """Query people data efficiently"""
        try:
            # Debug print
            print(f"PeopleQuery called with: employee_number={employee_number}, location={location}, rank={rank}, name={name}, skills={skills}")
            
            # Build server-side filters first
            filters = {}
            
            if employee_number:
                filters['employee_number'] = employee_number
                print(f"Searching by employee number: {employee_number}")
                
            if rank:
                filters['rank'] = rank.title()
                
            if location:
                filters['location'] = location.title()
                
            if name:
                filters['name'] = name
                
            # Get filtered data from server
            print(f"Executing query with filters: {filters}")
            employees = fetch_employees(self.db, filters)
            print(f"Query returned {len(employees)} results")
            
            # Apply skills filter in memory if needed
            if skills:
                employees = [emp for emp in employees if any(skill in emp["skills"] for skill in skills)]
            
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

    def get_tools(self) -> List[FunctionTool]:
        """Get the tools for the agent to use"""
        return [
            FunctionTool.from_defaults(
                fn=self.query_people,
                name="PeopleQuery",
                description="""
                Query people data to get employee details including their employee_number.
                MUST be used before querying availability by name.
                
                Parameters:
                - name (optional): Name of the employee to search for (e.g. ['Alice', 'Bob'])
                - rank (optional): Official job title to filter by. Valid ranks are:
                  * Partner
                  * Associate Partner  
                  * Principal Consultant
                  * Managing Consultant
                  * Senior Consultant
                  * Consultant
                - skills (optional): Technical/business expertise to filter by (e.g. ['Backend Developer', 'AWS Engineer'])
                - location (optional): Office location to filter by (London, Manchester, Bristol, Belfast)
                
                IMPORTANT: Use 'rank' parameter ONLY for job titles, not skills.
                Example: Use {'rank': 'Consultant'}, NOT {'skills': ['Consultant']}
                
                Returns JSON string of matching employees with their employee_numbers.
                """
            ),
            FunctionTool.from_defaults(
                fn=self.query_availability,
                name="AvailabilityQuery",
                description="""
                Query availability data using employee_number (NOT names).
                REQUIRES employee_number from PeopleQuery first.
                
                Parameters:
                - employee_number: Single employee ID or list of employee IDs
                - weeks (optional): List of week numbers to query (1-8)
                
                Returns weekly availability data for each employee.
                """
            )
        ]
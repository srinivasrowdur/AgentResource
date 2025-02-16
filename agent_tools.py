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
        
        # Define rank hierarchy (lowest to highest)
        self.RANK_HIERARCHY = {
            'Partner': 8,
            'Associate Partner': 7,
            'Consulting Director': 7,
            'Managing Consultant': 6,
            'Principal Consultant': 5,
            'Senior Consultant': 4,
            'Consultant': 3,
            'Consultant Analyst': 2,
            'Analyst': 1
        }
        
        # Keep standard skills
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

    def get_tools(self) -> List[FunctionTool]:
        """Get the tools for the agent to use"""
        return [
            FunctionTool.from_defaults(
                fn=self.query_available_people,
                name="QueryAvailablePeople",
                description="""
                ONLY use this for questions about employee availability and scheduling.
                Do NOT use for general questions or explanations.
                
                Parameters:
                - skills: List of skills to filter by (e.g., ['Frontend Developer'])
                - weeks: List of week numbers to check
                - rank_below/rank_above: For rank filtering
                - employee_numbers: For specific people
                """
            ),
            FunctionTool.from_defaults(
                fn=self.query_people,
                name="PeopleQuery",
                description="ONLY use for finding specific employees. Do NOT use for general explanations."
            ),
            FunctionTool.from_defaults(
                fn=self.query_availability,
                name="AvailabilityQuery",
                description="ONLY use for checking specific employee availability."
            )
        ]
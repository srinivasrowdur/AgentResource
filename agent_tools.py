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

class ResourceQueryTools:
    def __init__(self, db, availability_db):
        self.db = db
        self.availability_db = availability_db
        
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

    def get_ranks_below(self, rank: str) -> List[str]:
        """Get all ranks below the specified rank"""
        if rank.lower() == 'mc':
            rank = 'Managing Consultant'
        target_level = RANK_HIERARCHY.get(rank)
        if not target_level:
            return []
        # Return ranks strictly below the target level (higher number = lower rank)
        return sorted([r for r, level in RANK_HIERARCHY.items() 
                      if level > target_level],
                     key=lambda x: RANK_HIERARCHY[x])  # Sort by hierarchy

    def is_rank_below(self, rank1: str, rank2: str) -> bool:
        """Check if rank1 is below rank2"""
        return RANK_HIERARCHY.get(rank1, 0) < RANK_HIERARCHY.get(rank2, 0)
    
    def is_rank_above(self, rank1: str, rank2: str) -> bool:
        """Check if rank1 is above rank2"""
        return RANK_HIERARCHY.get(rank1, 0) > RANK_HIERARCHY.get(rank2, 0)
    
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

    def query_people(self, query_str: str = None) -> str:
        """Query people based on filters"""
        try:
            query = {}
            if isinstance(query_str, str):
                query_lower = query_str.lower()
                
                # Helper to check query context
                is_hierarchy_query = any(word in query_lower for word in ["below", "above", "under"])
                is_generic_consultant_query = (
                    "consultant" in query_lower and 
                    (is_hierarchy_query or "all" in query_lower or "resources" in query_lower)
                )
                
                # Handle rank filtering with context awareness
                if is_generic_consultant_query:
                    # When used generically, get all consulting ranks based on context
                    if "mc" in query_lower or "managing" in query_lower:
                        query["ranks"] = self.get_ranks_below("Managing Consultant")
                    elif "principal" in query_lower:
                        query["ranks"] = self.get_ranks_below("Principal Consultant")
                    elif "partner" in query_lower:
                        query["ranks"] = self.get_ranks_below("Partner")
                    else:
                        # If no specific level mentioned, include all consulting ranks
                        query["ranks"] = [r for r in RANK_HIERARCHY.keys() 
                                        if "Consultant" in r and r != "Consulting Director"]
                elif "consultant" in query_lower:
                    # When used specifically (e.g., "Consultants in London")
                    if not any(mod in query_lower for mod in ["senior", "principal", "managing", "analyst"]):
                        query["rank"] = "Consultant"
                elif "below" in query_lower:
                    # Handle other "below" queries for non-consultant ranks
                    if "mc" in query_lower:
                        query["ranks"] = self.get_ranks_below("Managing Consultant")
                    else:
                        for rank in RANK_HIERARCHY.keys():
                            if rank.lower().replace(' ', '') in query_lower:
                                query["ranks"] = self.get_ranks_below(rank)
                                break
                elif "partner" in query_lower and "associate" not in query_lower:
                    query["rank"] = "Partner"
                
                # Handle location
                if "london" in query_lower:
                    query["location"] = "London"
                elif "manchester" in query_lower:
                    query["location"] = "Manchester"
                elif "bristol" in query_lower:
                    query["location"] = "Bristol"
                elif "belfast" in query_lower:
                    query["location"] = "Belfast"
                
                # Handle skill matching
                if "similar to" in query_lower or "like" in query_lower:
                    # Extract employee name after "similar to" or "like"
                    # Then look up their skills and add to query
                    employee_name = self.extract_employee_name(query_lower)
                    if employee_name:
                        employee_skills = self.get_employee_skills(self.db, employee_name)
                        if employee_skills:
                            query["skills"] = employee_skills
            
            elif isinstance(query_str, dict):
                query = query_str

            print(f"Original query: skills={query.get('skills')}, location={query.get('location')}, rank={query.get('rank')}")
            
            # Build filters dictionary
            filters = {}
            
            # Handle multiple ranks
            if 'ranks' in query:
                filters['ranks'] = query['ranks']
            elif 'rank' in query:
                filters['rank'] = query['rank']

            if 'location' in query and query['location']:
                filters['location'] = query['location']

            # Handle skills translation
            if 'skills' in query and query['skills']:
                if not isinstance(query['skills'], list):
                    query['skills'] = [query['skills']]
                
                valid_skills = []
                for skill in query['skills']:
                    if skill in self.standard_skills:
                        valid_skills.append(skill)
                    else:
                        print(f"Warning: Could not translate skill '{skill}'")
                
                if not valid_skills:
                    return "I couldn't understand the requested skill. Please use terms like 'Frontend Developer', 'Backend Developer', 'AWS Engineer', etc."
                
                filters['skills'] = valid_skills

            print(f"Executing query with filters: {filters}")
            
            # Execute query
            results = fetch_employees(self.db, filters)
            
            if not results:
                return "No matching employees found."
            
            # Format results as a markdown table
            table = "| Name | Location | Rank | Skills | Employee ID |\n"
            table += "|------|----------|------|---------|-------------|\n"
            
            for emp in results:
                skills_str = ", ".join(emp.get('skills', []))
                table += f"| {emp['name']} | {emp['location']} | {emp['rank']} | {skills_str} | {emp['employee_number']} |\n"
            
            return table

        except Exception as e:
            return f"Error querying people: {str(e)}"

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
                                key=lambda x: (RANK_HIERARCHY.get(x['rank'], 0), x['name']), 
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
            for rank in RANK_HIERARCHY.keys():
                if rank.lower().replace(' ', '') in query_lower:
                    ranks = self.get_ranks_below(rank)
                    return f"Ranks below {rank}:\n- " + "\n- ".join(ranks)
        
        return "Please specify a rank query like 'below MC' or 'below Partner'"

    def get_tools(self) -> List[FunctionTool]:
        """Get all tools"""
        return [
            FunctionTool.from_defaults(
                fn=self.query_people,
                name="PeopleQuery",
                description="""Query people based on location, rank, and skills.
                   IMPORTANT: The word 'consultant' is interpreted based on context:
                    
                    1. Generic/Collective Usage (returns multiple ranks):
                       - "all consultants below MC"
                       - "consulting resources in London"
                       - "consultants below Principal"
                    
                    2. Specific Rank Usage (returns only Rank 6):
                       - "Consultants in London"
                       - "available Consultants"
                       - "Frontend Developer Consultants"
                    
                    RANKS (from highest to lowest):
                    1. Partner
                    2. Associate Partner/Consulting Director
                    3. Principal Consultant
                    4. Managing Consultant (MC)
                    5. Senior Consultant
                    6. Consultant
                    7. Consultant Analyst
                    8. Analyst
                    
                    Examples:
                    - 'all consultants below MC'     # Returns ALL consulting ranks below MC
                    - 'Consultants in London'        # Returns ONLY rank 6 in London
                    - 'consulting resources in UK'    # Returns ALL consulting ranks
                    - 'partners in Manchester'        # Returns ONLY rank 1"""
            ),
            FunctionTool.from_defaults(
                fn=self.query_availability,
                name="AvailabilityQuery",
                description="""Check availability for specific employees.
                   Input should be a list of employee IDs and week numbers."""
            ),
            FunctionTool.from_defaults(
                fn=self.get_ranks_tool,
                name="RankQuery",
                description="""Get information about ranks. Examples:
                   IMPORTANT: We have a strict rank hierarchy:
                   Partner > Associate Partner = Consulting Director > Principal Consultant > 
                   Managing Consultant (MC) > Senior Consultant > Consultant > 
                   Consultant Analyst > Analyst
                   
                   Input: 'below MC' -> Returns all ranks below Managing Consultant
                   Input: 'below Partner' -> Returns all ranks below Partner
                   Note: 'MC' is shorthand for 'Managing Consultant'"""
            )
        ]
class MockResourceQueryTools:
    def __init__(self):
        self.locations = [
            "London", "Manchester", "Bristol", "Belfast",
            "Copenhagen", "Stockholm", "Oslo"
        ]
        self.standard_skills = {
            "Frontend Developer",
            "Backend Developer",
            "AWS Engineer",
            "Full Stack Developer",
            "Cloud Engineer",
            "Architect",
            "Product Manager",
            "Agile Coach",
            "Business Analyst"
        }

    def handle_non_resource_query(self, query: str) -> str:
        """Handle queries not related to resource management"""
        resource_keywords = [
            "consultant", "developer", "engineer", "resource", 
            "london", "manchester", "available", "skill"
        ]
        
        query_lower = query.lower()
        if any(keyword in query_lower for keyword in resource_keywords):
            return ""
            
        return "Sorry, I cannot help with that query. I can only assist with resource management related questions."

def mock_fetch_employees():
    """Mock function to return test employee data"""
    return [
        {
            "name": "John Doe",
            "location": "London",
            "rank": "Consultant",
            "skills": ["Frontend Developer"],
            "employee_number": "E001"
        },
        {
            "name": "Jane Smith",
            "location": "Manchester",
            "rank": "Senior Consultant",
            "skills": ["Backend Developer"],
            "employee_number": "E002"
        },
        {
            "name": "Alice Johnson",
            "location": "Bristol",
            "rank": "Consultant",
            "skills": ["Full Stack Developer"],
            "employee_number": "E003"
        },
        {
            "name": "Bob Wilson",
            "location": "Oslo",
            "rank": "Principal Consultant",
            "skills": ["Cloud Engineer"],
            "employee_number": "E004"
        },
        {
            "name": "Carol Brown",
            "location": "Stockholm",
            "rank": "Managing Consultant",
            "skills": ["Architect"],
            "employee_number": "E005"
        },
        {
            "name": "David Miller",
            "location": "Belfast",
            "rank": "Senior Consultant",
            "skills": ["AWS Engineer"],
            "employee_number": "E006"
        }
    ]
from typing import Dict, List, Optional

class MockFirebase:
    def __init__(self):
        self.data = {
            'employees': [
                {
                    'name': 'John Smith',
                    'location': 'London',
                    'rank': {'level': 6, 'official_name': 'Consultant'},
                    'skills': ['AWS Engineer', 'Frontend Developer'],
                    'employee_number': 'EMP001'
                },
                # Add more mock data as needed
            ]
        }

MOCK_EMPLOYEES = [
    {
        'id': '1',
        'name': 'John Smith',
        'location': 'London',
        'rank': 'Consultant',
        'skills': ['Frontend Developer', 'AWS Engineer']
    },
    {
        'id': '2',
        'name': 'Jane Doe',
        'location': 'London',
        'rank': 'Senior Consultant',
        'skills': ['Backend Developer', 'Cloud Engineer']
    }
]

def mock_fetch_employees(db, filters: Dict) -> List[Dict]:
    """Mock implementation for testing"""
    results = MOCK_EMPLOYEES.copy()
    
    # Apply filters
    if 'location' in filters:
        results = [e for e in results if e['location'] == filters['location']]
    if 'rank' in filters:
        results = [e for e in results if e['rank'] == filters['rank']]
    if 'ranks' in filters:
        results = [e for e in results if e['rank'] in filters['ranks']]
    if 'skills' in filters:
        results = [e for e in results if any(s in e['skills'] for s in filters['skills'])]
        
    return results

def mock_fetch_availability(db, employee_id, week):
    """Mock implementation of fetch_availability"""
    return {'status': 'Available'}

def mock_fetch_availability_batch(db, employee_numbers, weeks):
    """Mock implementation of fetch_availability_batch"""
    return {
        emp_id: {
            'employee_data': {'name': 'John Smith'},
            'availability': {'pattern_description': 'Generally available'},
            'weeks': {f'week_{w}': {'status': 'Available'} for w in weeks}
        }
        for emp_id in employee_numbers
    } 
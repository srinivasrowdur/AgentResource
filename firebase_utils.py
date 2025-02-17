import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
from typing import List, Dict
import random
import names

def initialize_firebase(cred_path):
    """Initialize Firebase with credentials"""
    if not firebase_admin._apps:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    return firestore.client()

def clean_collections(db):
    """Clean up all collections"""
    collections = ['employees', 'availability']
    for collection_name in collections:
        docs = db.collection(collection_name).stream()
        for doc in docs:
            # Delete subcollections
            for subcoll in doc.reference.collections():
                for subdoc in subcoll.stream():
                    subdoc.reference.delete()
            # Delete main document
            doc.reference.delete()

def create_sample_data(db):
    """Create 100 sample employees with varied ranks, skills, and availability"""
    
    # Updated locations with Scandinavian cities
    locations = {
        "London": 0.25,      # 25% in London
        "Manchester": 0.15,  # 15% in Manchester
        "Bristol": 0.15,    # 15% in Bristol
        "Belfast": 0.15,    # 15% in Belfast
        "Copenhagen": 0.1,   # 10% in Copenhagen
        "Stockholm": 0.1,    # 10% in Stockholm
        "Oslo": 0.1         # 10% in Oslo
    }
    
    # Updated rank hierarchy (PC above MC)
    ranks = [
        {"official_name": "Partner", "level": 1},
        {"official_name": "Associate Partner", "level": 2},
        {"official_name": "Consulting Director", "level": 2},
        {"official_name": "Principal Consultant", "level": 3},  # Level 3
        {"official_name": "Managing Consultant", "level": 4},   # Level 4 (below PC)
        {"official_name": "Senior Consultant", "level": 5},
        {"official_name": "Consultant", "level": 6},
        {"official_name": "Consultant Analyst", "level": 7},
        {"official_name": "Analyst", "level": 8}
    ]

    # Updated pyramid structure (PC gets more allocation than MC)
    rank_weights = [
        0.10,  # Partner (10%)
        0.08,  # Associate Partner (8%)
        0.07,  # Consulting Director (7%)
        0.15,  # Principal Consultant (15%) - Increased
        0.12,  # Managing Consultant (12%) - Decreased
        0.20,  # Senior Consultant (20%)
        0.15,  # Consultant (15%)
        0.08,  # Consultant Analyst (8%)
        0.05   # Analyst (5%)
    ]

    skills = {
        "technical": [
            "Frontend Developer",
            "Backend Developer",
            "Full Stack Developer",
            "AWS Engineer",
            "Cloud Engineer",
            "DevOps Engineer",
            "Data Engineer",
            "Solution Architect"
        ],
        "business": [
            "Business Analyst",
            "Product Manager",
            "Agile Coach",
            "Scrum Master",
            "Project Manager",
            "Digital Consultant"
        ]
    }

    # Availability patterns
    availability_patterns = {
        "fully_available": {
            "weights": [0.8, 0.15, 0.05],  # Available, Partial, Not Available
            "description": "Generally available"
        },
        "partially_available": {
            "weights": [0.3, 0.5, 0.2],
            "description": "Mixed availability"
        },
        "mostly_unavailable": {
            "weights": [0.1, 0.3, 0.6],
            "description": "Limited availability"
        },
        "future_available": {
            "weights": [0.0, 0.2, 0.8],
            "description": "Available in future"
        }
    }

    pattern_weights = [0.4, 0.3, 0.2, 0.1]  # Distribution of availability patterns
    
    try:
        # Generate 100 employees
        for i in range(100):
            emp_id = f"EMP{str(i+1).zfill(3)}"
            
            # Select location based on distribution
            location = random.choices(list(locations.keys()), 
                                   weights=list(locations.values()))[0]
            
            # Select rank based on distribution
            rank = random.choices(ranks, weights=rank_weights)[0]
            
            # Select 2-4 skills based on rank level
            num_skills = random.randint(2, 4)
            technical_weight = 0.7 if rank["level"] > 5 else 0.3  # More technical for junior roles
            
            selected_skills = []
            for _ in range(num_skills):
                skill_type = "technical" if random.random() < technical_weight else "business"
                skill = random.choice(skills[skill_type])
                if skill not in selected_skills:  # Avoid duplicates
                    selected_skills.append(skill)
            
            # Create employee document
            employee_data = {
                "employee_number": emp_id,
                "name": names.get_full_name(),
                "location": location,
                "rank": rank,
                "skills": selected_skills
            }
            
            # Add to Firestore
            emp_ref = db.collection('employees').document(emp_id)
            emp_ref.set(employee_data)
            
            # Create availability pattern
            pattern_type = random.choices(list(availability_patterns.keys()), 
                                       weights=pattern_weights)[0]
            pattern = availability_patterns[pattern_type]
            
            # Create availability document
            avail_ref = db.collection('availability').document(emp_id)
            avail_ref.set({
                "employee_number": emp_id,
                "pattern_description": pattern["description"]
            })
            
            # Create weekly availability for next 8 weeks
            weeks_collection = avail_ref.collection('weeks')
            statuses = ['Available', 'Partially Available', 'Not Available']
            
            for week_num in range(1, 9):
                # Future availability pattern becomes more available in later weeks
                if pattern_type == 'future_available':
                    if week_num <= 2:
                        status = 'Not Available'
                    elif week_num <= 4:
                        status = random.choices(statuses, weights=[0.2, 0.5, 0.3])[0]
                    else:
                        status = random.choices(statuses, weights=[0.6, 0.3, 0.1])[0]
                else:
                    status = random.choices(statuses, weights=pattern["weights"])[0]
                
                weeks_collection.document(f"week_{week_num}").set({
                    "status": status,
                    "notes": f"Week {week_num} - {status}",
                    "week_number": week_num
                })
        
        print(f"Successfully created 100 sample employees with availability")
        return 100
        
    except Exception as e:
        print(f"Error creating sample data: {str(e)}")
        return 0

def fetch_employees(db, filters: Dict) -> List[Dict]:
    """Fetch employees matching the given filters"""
    try:
        # Start with base query
        query = db.collection('employees')
        
        # Apply filters using where() instead of filter()
        if 'location' in filters:
            query = query.where('location', '==', filters['location'])
            
        if 'rank' in filters:
            query = query.where('rank.official_name', '==', filters['rank'])
            
        if 'ranks' in filters:
            query = query.where('rank.official_name', 'in', filters['ranks'])
            
        if 'skills' in filters:
            query = query.where('skills', 'array_contains_any', filters['skills'])
        
        # Execute query
        docs = query.stream()
        
        # Convert to list of dicts and add document ID
        results = []
        for doc in docs:
            employee = doc.to_dict()
            if 'rank' in employee and isinstance(employee['rank'], dict):
                employee['rank'] = employee['rank']['official_name']
            employee['id'] = doc.id
            results.append(employee)
            
        if not results:
            print(f"No results found for filters: {filters}")
            
        return results
    except Exception as e:
        print(f"Error fetching employees: {str(e)}")
        return []

def fetch_availability(db, employee_number: str) -> dict:
    """Fetch availability for an employee"""
    try:
        avail_ref = db.collection('availability').document(employee_number)
        avail_doc = avail_ref.get()
        
        if not avail_doc.exists:
            print(f"No availability found for employee {employee_number}")
            return None
            
        avail_data = avail_doc.to_dict()
        
        # Fetch weeks subcollection
        weeks_collection = avail_ref.collection('weeks')
        weeks_docs = weeks_collection.stream()
        
        weeks_data = {}
        for week_doc in weeks_docs:
            weeks_data[week_doc.id] = week_doc.to_dict()
            
        avail_data['weeks'] = weeks_data
        return avail_data
        
    except Exception as e:
        print(f"Error fetching availability: {str(e)}")
        return None

def fetch_availability_batch(db, employee_numbers: List[str], weeks: List[int]) -> Dict:
    """Fetch availability for multiple employees"""
    try:
        results = {}
        for emp_num in employee_numbers:
            # Get employee data
            emp_query = db.collection('employees').where('employee_number', '==', emp_num)
            emp_docs = emp_query.stream()
            emp_data = next((doc.to_dict() for doc in emp_docs), None)
            
            if not emp_data:
                continue
                
            # Get availability data
            avail_data = fetch_availability(db, emp_num)
            if not avail_data:
                continue
                
            # Format weeks data
            weeks_data = {}
            for week in weeks:
                week_key = f"week_{week}"
                if week_key in avail_data.get('weeks', {}):
                    weeks_data[week_key] = avail_data['weeks'][week_key]
                else:
                    weeks_data[week_key] = {'status': 'Unknown'}
            
            results[emp_num] = {
                'employee_data': emp_data,
                'availability': {
                    'pattern_description': avail_data.get('pattern_description', '')
                },
                'weeks': weeks_data
            }
            
        return results
    except Exception as e:
        print(f"Error fetching batch availability: {str(e)}")
        return {}

def create_employees(db):
    """Create sample employees"""
    locations = ["London", "Manchester", "Bristol", "Belfast"]
    ranks = [
        {"official_name": "Partner", "level": 1},
        {"official_name": "Associate Partner", "level": 2},
        {"official_name": "Principal Consultant", "level": 3},
        {"official_name": "Managing Consultant", "level": 4},
        {"official_name": "Senior Consultant", "level": 5},
        {"official_name": "Consultant", "level": 6}
    ]
    skills = [
        "Full Stack Developer",
        "Backend Developer",
        "Frontend Developer",
        "AWS Engineer",
        "GCP Engineer",
        "Architect",
        "Business Analyst",
        "Product Manager",
        "Agile Coach"
    ]

    created_employees = []
    
    for i in range(50):
        emp_id = f"EMP{str(i+1).zfill(3)}"
        employee_data = {
            "employee_number": emp_id,
            "name": names.get_full_name(),
            "location": random.choice(locations),
            "rank": random.choice(ranks),
            "skills": random.sample(skills, k=random.randint(2, 4))
        }
        
        db.collection('employees').document(emp_id).set(employee_data)
        created_employees.append(employee_data)
    
    return created_employees

def create_availability(db, employees):
    """Create availability records"""
    patterns = {
        'fully_available': {
            'weights': [0.8, 0.15, 0.05],
            'description': 'Generally available'
        },
        'partially_available': {
            'weights': [0.3, 0.5, 0.2],
            'description': 'Mixed availability'
        },
        'mostly_unavailable': {
            'weights': [0.1, 0.3, 0.6],
            'description': 'Limited availability'
        },
        'future_available': {
            'weights': [0.0, 0.0, 1.0],
            'description': 'Available in future'
        }
    }
    
    statuses = ['Available', 'Partially Available', 'Not Available']
    
    for emp_data in employees:
        emp_id = emp_data['employee_number']
        pattern_type = random.choice(list(patterns.keys()))
        pattern = patterns[pattern_type]
        
        # Create availability document
        availability_ref = db.collection('availability').document(emp_id)
        availability_ref.set({
            'employee_number': emp_id,
            'pattern_description': pattern['description']
        })
        
        # Create weekly availability
        weeks_collection = availability_ref.collection('weeks')
        for week_num in range(1, 9):
            if pattern_type == 'future_available' and week_num <= 2:
                status = 'Not Available'
                notes = 'Unavailable until week 3'
            else:
                status = random.choices(statuses, weights=pattern['weights'])[0]
                notes = f"Week {week_num} - {status}"

            weeks_collection.document(f"week_{week_num}").set({
                'status': status,
                'notes': notes,
                'week_number': week_num
            }) 

def reset_database(db):
    """Clean and recreate sample data"""
    try:
        # Clean existing data
        clean_collections(db)
        
        # Create new sample data
        count = create_sample_data(db)
        
        print(f"Database reset complete. Created {count} sample employees.")
        return True
    except Exception as e:
        print(f"Error resetting database: {str(e)}")
        return False 
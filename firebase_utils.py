import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
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
    """Create sample employees and availability data"""
    # First clean existing data
    clean_collections(db)
    
    # Create employees
    employees = create_employees(db)
    
    # Create availability
    create_availability(db, employees)
    
    return len(employees)

def fetch_employees(db, filters: Dict = None) -> List[Dict]:
    """Fetch employees with optional filters"""
    try:
        # Start with base query
        query = db.collection('employees')
        
        # Apply filters if provided
        if filters:
            if 'rank' in filters:
                query = query.where('rank.official_name', '==', filters['rank'])
            if 'location' in filters:
                query = query.where('location', '==', filters['location'])
            if 'name' in filters:
                query = query.where('name', '==', filters['name'])
        
        # Execute query
        docs = query.stream()
        
        # Debug print the query
        print(f"Firebase Query: collection='employees' filters={filters}")
        
        return [doc.to_dict() for doc in docs]
        
    except Exception as e:
        print(f"Error fetching employees: {str(e)}")
        return []

def fetch_availability(db, employee_number: str) -> dict:
    """Fetch availability for an employee"""
    try:
        avail_ref = db.collection('availability').document(employee_number)
        avail_doc = avail_ref.get()
        
        if not avail_doc.exists:
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
    """Fetch availability for multiple employees efficiently"""
    try:
        batch_size = 10
        results = {}
        
        for i in range(0, len(employee_numbers), batch_size):
            batch = employee_numbers[i:i + batch_size]
            
            # Batch get employees and availability
            emp_refs = [db.collection('employees').document(emp_id) for emp_id in batch]
            emp_docs = db.get_all(emp_refs)
            
            avail_refs = [db.collection('availability').document(emp_id) for emp_id in batch]
            avail_docs = db.get_all(avail_refs)
            
            for emp_id, emp_doc, avail_doc in zip(batch, emp_docs, avail_docs):
                if not emp_doc.exists or not avail_doc.exists:
                    continue
                    
                emp_data = emp_doc.to_dict()
                avail_data = avail_doc.to_dict()
                
                # Get weeks data - Fix the week query
                weeks_ref = avail_doc.reference.collection('weeks')
                # Convert week numbers to week_1, week_2 format
                week_docs = {
                    f"week_{week}": weeks_ref.document(f"week_{week}").get()
                    for week in weeks
                }
                
                weeks_data = {}
                for week_key, doc in week_docs.items():
                    if doc.exists:
                        weeks_data[week_key] = doc.to_dict()
                    else:
                        weeks_data[week_key] = {"status": "Unknown", "notes": "No data"}
                
                results[emp_id] = {
                    "employee_data": emp_data,
                    "availability": avail_data,
                    "weeks": weeks_data
                }
        
        return results
        
    except Exception as e:
        print(f"Error in batch fetch: {str(e)}")
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
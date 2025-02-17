import os
from dotenv import load_dotenv
from firebase_utils import initialize_firebase, reset_database, fetch_employees, fetch_availability_batch
from collections import Counter
import pandas as pd

def verify_distribution(db):
    """Verify the distribution of employees across locations, ranks, and availability"""
    
    # Fetch all employees
    all_employees = fetch_employees(db, {})
    
    # Basic distributions
    locations = Counter(emp['location'] for emp in all_employees)
    ranks = Counter(emp['rank'] for emp in all_employees)
    
    # Create DataFrames
    location_df = pd.DataFrame([
        {'Location': loc, 'Count': count, 'Percentage': count/len(all_employees)*100}
        for loc, count in locations.items()
    ])
    
    rank_df = pd.DataFrame([
        {'Rank': rank, 'Count': count, 'Percentage': count/len(all_employees)*100}
        for rank, count in ranks.items()
    ])
    
    # Fetch availability for all employees
    employee_numbers = [emp['employee_number'] for emp in all_employees]
    availability_data = fetch_availability_batch(db, employee_numbers, list(range(1, 9)))
    
    # Analyze availability patterns by location
    availability_by_location = {}
    for emp in all_employees:
        location = emp['location']
        emp_id = emp['employee_number']
        if emp_id in availability_data:
            pattern = availability_data[emp_id]['availability']['pattern_description']
            availability_by_location.setdefault(location, []).append(pattern)
    
    # Create availability DataFrame
    availability_rows = []
    for location, patterns in availability_by_location.items():
        pattern_counts = Counter(patterns)
        total = len(patterns)
        row = {
            'Location': location,
            'Generally Available (%)': pattern_counts['Generally available'] / total * 100,
            'Mixed Availability (%)': pattern_counts['Mixed availability'] / total * 100,
            'Limited Availability (%)': pattern_counts['Limited availability'] / total * 100,
            'Future Available (%)': pattern_counts['Available in future'] / total * 100
        }
        availability_rows.append(row)
    
    availability_df = pd.DataFrame(availability_rows)
    
    # Print all distributions
    print("\n=== Location Distribution ===")
    print(location_df.to_string(index=False))
    
    print("\n=== Rank Distribution ===")
    print(rank_df.to_string(index=False))
    
    print("\n=== Availability Distribution by Location ===")
    print(availability_df.to_string(index=False))
    
    # Sample queries with availability
    print("\n=== Sample Queries with Availability ===")
    queries = [
        ("Available Consultants in London", {'rank': 'Consultant', 'location': 'London'}),
        ("Partners in Copenhagen", {'rank': 'Partner', 'location': 'Copenhagen'}),
        ("Senior Consultants in Oslo", {'rank': 'Senior Consultant', 'location': 'Oslo'})
    ]
    
    for description, filters in queries:
        results = fetch_employees(db, filters)
        print(f"\n{description}: {len(results)} employees found")
        for emp in results:
            emp_id = emp['employee_number']
            if emp_id in availability_data:
                pattern = availability_data[emp_id]['availability']['pattern_description']
                week1_status = availability_data[emp_id]['weeks'].get('week_1', {}).get('status', 'Unknown')
                print(f"- {emp['name']} ({emp['rank']}) - {pattern} - Week 1: {week1_status}")

def main():
    # Load environment variables
    load_dotenv()
    
    # Initialize Firebase
    try:
        print("Initializing Firebase...")
        db = initialize_firebase(os.getenv('FIREBASE_CREDENTIALS_PATH'))
        print("✅ Firebase initialized successfully")
        
        # Reset database with 100 sample employees
        print("\nResetting database...")
        if reset_database(db):
            print("✅ Database reset successful!")
            
            # Verify distribution
            print("\nVerifying data distribution...")
            verify_distribution(db)
        else:
            print("❌ Database reset failed")
            
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 
from typing import Dict, List
from abc import ABC, abstractmethod

class BaseResourceQueryTools(ABC):
    """Base class for resource query tools with shared logic"""
    
    RANK_HIERARCHY = {
        'Partner': 1,
        'Associate Partner': 2,
        'Consulting Director': 2,
        'Managing Consultant': 3,
        'Principal Consultant': 4,
        'Senior Consultant': 5,
        'Consultant': 6,
        'Consultant Analyst': 7,
        'Analyst': 8
    }

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

    def get_ranks_below(self, rank: str) -> List[str]:
        """Shared rank hierarchy logic"""
        if rank.lower() == 'mc':
            rank = 'Managing Consultant'
        target_level = self.RANK_HIERARCHY.get(rank)
        if not target_level:
            return []
        return sorted([r for r, level in self.RANK_HIERARCHY.items() 
                      if level > target_level],
                     key=lambda x: self.RANK_HIERARCHY[x])

    def construct_query(self, query_str: str) -> Dict:
        """Shared query construction logic"""
        query = {}
        if isinstance(query_str, str):
            query_lower = query_str.lower()
            
            # Parse weeks
            if "week" in query_lower:
                weeks = []
                if "next" in query_lower:
                    parts = query_lower.split("next")[1].split()
                    if parts and parts[0].isdigit():
                        num_weeks = int(parts[0])
                        weeks = list(range(1, num_weeks + 1))
                elif "weeks" in query_lower:
                    parts = query_lower.split("weeks")[1].split()
                    for part in parts:
                        if part.isdigit():
                            weeks.append(int(part))
                elif "week" in query_lower:
                    parts = query_lower.split("week")[1].split()
                    if parts and parts[0].isdigit():
                        weeks.append(int(parts[0]))
                
                if weeks:
                    query["weeks"] = sorted(weeks)
            
            # Handle ranks
            is_hierarchy_query = any(word in query_lower for word in ["below", "above", "under"])
            is_all_consultants = "all consultants" in query_lower and not is_hierarchy_query
            is_consulting_resources = "consulting resources" in query_lower
            
            if is_all_consultants or is_consulting_resources:
                # Use hardcoded order for "all consultants" and "consulting resources"
                query['ranks'] = [
                    'Principal Consultant', 'Managing Consultant', 'Senior Consultant',
                    'Consultant', 'Consultant Analyst'
                ]
            elif is_hierarchy_query:
                # Use hierarchy-based ordering for "below X" queries
                if "mc" in query_lower or "management consultant" in query_lower:
                    query["ranks"] = self.get_ranks_below("Managing Consultant")
                else:
                    # Check for other ranks
                    for rank in self.RANK_HIERARCHY.keys():
                        if rank.lower() in query_lower:
                            query["ranks"] = self.get_ranks_below(rank)
                            break
            elif "senior consultant" in query_lower:
                query["rank"] = "Senior Consultant"
            elif "consultant" in query_lower and not any(mod in query_lower 
                for mod in ["principal", "managing", "analyst"]):
                query["rank"] = "Consultant"
            elif "below" in query_lower and "above" in query_lower:
                # Handle complex range queries
                below_rank = None
                above_rank = None
                
                if "mc" in query_lower:
                    below_rank = "Managing Consultant"
                else:
                    for rank in self.RANK_HIERARCHY.keys():
                        if rank.lower().replace(' ', '') in query_lower.split("below")[1]:
                            below_rank = rank
                            break
                
                for rank in self.RANK_HIERARCHY.keys():
                    if rank.lower().replace(' ', '') in query_lower.split("above")[1]:
                        above_rank = rank
                        break
                
                if below_rank and above_rank:
                    all_ranks = sorted(self.RANK_HIERARCHY.keys(), 
                                     key=lambda x: self.RANK_HIERARCHY[x])
                    start_idx = all_ranks.index(below_rank)
                    end_idx = all_ranks.index(above_rank)
                    query["ranks"] = all_ranks[start_idx+1:end_idx]
            
            # Handle location
            for location in self.locations:
                if location.lower() in query_lower:
                    query["location"] = location
            
            # Handle skills
            for skill in self.standard_skills:
                if skill.lower() in query_lower:
                    query.setdefault("skills", []).append(skill)
            
        return query

    @abstractmethod
    def query_people(self, query_str: str) -> str:
        """Must be implemented by concrete classes"""
        pass
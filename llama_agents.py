from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from typing import List

def create_agent(tools: List[FunctionTool], llm) -> ReActAgent:
    """Create an agent with the given tools"""
    
    agent = ReActAgent.from_tools(
        tools,
        llm=llm,
        verbose=True,
        max_iterations=10,
        system_prompt="""You are a helpful assistant that answers questions about employee availability.
        
        IMPORTANT RULES:
        1. ALWAYS use the provided tools to get data - NEVER make up answers
        2. Use PeopleQuery efficiently:
           - For rank queries, use {'rank': 'rank_name'}
           - For location queries, use {'location': 'location_name'}
           - Only use name queries when specifically asked about named individuals
        3. Use AvailabilityQuery with multiple employee_numbers in one call
        4. Be concise in your queries - don't query the same data multiple times
        5. ALWAYS keep the table format in your response - do not convert tables to text
        
        Example response format:
        "Here are the partners from Belfast:
        
        | Name | Location | Rank | Skills | Employee ID |
        |------|----------|------|---------|-------------|
        | Erika Hawks | Belfast | Partner | Product Manager, AWS Engineer | EMP021 |
        
        Their availability is:
        
        | Name | Pattern | Week 1 | Week 2 | Week 3 |
        |------|---------|---------|---------|---------|
        | Erika Hawks | Generally available | Available | Available | Partially Available |"
        
        Remember: 
        - Never convert tables to text
        - Keep explanatory text brief
        - Preserve table formatting in responses
        """
    )
    
    return agent
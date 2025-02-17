from llama_index.core.tools import FunctionTool
from llama_index.core.agent import ReActAgent
from llama_index.core.callbacks import CallbackManager
from typing import List, Optional, Dict, Any
from llama_index.llms.openai import OpenAI
from llama_index.core.llms import MessageRole
from llama_index.core.tools import BaseTool

def create_agent(tools: List[BaseTool], llm: Any, chat_history: Optional[List[Dict]] = None) -> ReActAgent:
    """Create an agent with the given tools and LLM"""
    
    # Define the agent's system prompt
    system_prompt = """You are a helpful Resource Management Assistant. 
    
    IMPORTANT: Always follow this sequence when handling queries about employees:
    1. FIRST use QueryTranslator to convert the natural language query into JSON
    2. THEN use PeopleQuery with the JSON result to find employees
    3. ONLY use RankQuery if you need to understand rank relationships
    4. Use AvailabilityQuery last, and only for availability questions
    
    Example Flow:
    User: "Show me all consultants in London"
    1. Use QueryTranslator to get JSON format
    2. Use PeopleQuery with that JSON to get results
    
    Complex Example:
    User: "Who are the senior people available in London next week?"
    1. Use QueryTranslator to convert to JSON
    2. Use PeopleQuery with JSON to find people
    3. Use AvailabilityQuery to check their schedule
    
    ALWAYS:
    - Start with QueryTranslator for any employee search
    - Use the JSON output from QueryTranslator as input to PeopleQuery
    - Explain what you're doing at each step
    """
    
    # Create the agent
    agent = ReActAgent.from_tools(
        tools=tools,
        llm=llm,
        system_prompt=system_prompt,
        verbose=True
    )
    
    return agent
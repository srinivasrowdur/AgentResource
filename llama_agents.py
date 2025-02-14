from llama_index.core.tools import FunctionTool
from llama_index.core.agent import ReActAgent
from llama_index.core.callbacks import CallbackManager
from typing import List
from llama_index.llms.openai import OpenAI

def create_agent(tools: List[FunctionTool], llm: OpenAI) -> ReActAgent:
    """Create an agent with the given tools"""
    
    system_prompt = """You are a helpful resource management assistant.

    Important rules:
    1. For questions about available people:
       - ALWAYS use QueryAvailablePeople with:
         * skills (e.g., {'skills': ['Frontend Developer']})
         * weeks (e.g., {'weeks': [1]} for week 1)
         * location (optional)
         * rank (optional)
       Example: "Are any frontend devs available in week 1?"
       → Use QueryAvailablePeople({'skills': ['Frontend Developer'], 'weeks': [1]})

    2. For other queries:
       - Use PeopleQuery for finding people without availability
       - Use AvailabilityQuery only when you already have employee numbers

    Remember:
    - ALWAYS use QueryAvailablePeople for availability questions
    - Let the tools handle skill translations
    - Never try to use non-existent tools
    """
    
    return ReActAgent.from_tools(
        tools,
        llm=llm,
        verbose=True,
        system_prompt=system_prompt
    )
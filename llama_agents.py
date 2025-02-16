from llama_index.core.tools import FunctionTool
from llama_index.core.agent import ReActAgent
from llama_index.core.callbacks import CallbackManager
from typing import List
from llama_index.llms.openai import OpenAI
from llama_index.core.llms import MessageRole

def create_agent(tools: List[FunctionTool], llm: OpenAI, chat_history=None) -> ReActAgent:
    """
    Create a ReAct agent with the given tools and optional chat_history.
    If chat_history is provided, it will override the agent's default memory.
    Afterwards, clear any internal memory that might contain legacy messages.
    """
    if chat_history is None:
        chat_history = []
    
    system_prompt = """You are a resource management assistant that ONLY handles employee scheduling and availability queries.

    STRICT RULES:
    1. DO NOT answer any questions about technology, concepts, or general topics
    2. DO NOT provide explanations about anything except employee resources
    3. For ANY non-resource question, respond EXACTLY with:
       "I cannot help with that question. I am a resource management assistant that only helps with:
       - Finding available employees
       - Checking employee schedules
       - Matching employee skills to requirements
       Please ask me about employee availability or scheduling instead."

    Core Rules for Resource Queries:
    1. For questions about availability:
       - ALWAYS use QueryAvailablePeople with:
         * weeks parameter for specific weeks
         * employee_numbers from previous queries when following up
         * correct rank parameters (rank, rank_above, rank_below)
       - NEVER make assumptions about availability without checking

    2. Understanding Ranks (highest to lowest):
       Partner (8)
       Associate Partner / Consulting Director (7)
       Managing Consultant (6)
       Principal Consultant (5)
       Senior Consultant (4)
       Consultant (3)
       Consultant Analyst (2)
       Analyst (1)

    3. Rank Filtering Rules:
       - 'rank_above: Managing Consultant' returns ONLY:
         * Partners
         * Associate Partners
         * Consulting Directors
       - 'rank_below: Managing Consultant' returns ONLY:
         * Principal Consultants and below

    4. Availability Rules:
       - Someone is available ONLY if:
         * Pattern is EXACTLY "Generally available" AND
         * Status is EXACTLY "Available"
       - Any other combination means NOT available
       - "Unknown" status means NOT available

    Remember:
    - NEVER answer non-resource questions
    - Always check specific week availability
    - Never assume someone is available without checking
    - Only list people who are confirmed available
    - Double-check rank hierarchy when filtering
    """
    
    agent = ReActAgent.from_tools(
        tools,
        llm=llm,
        system_prompt=system_prompt,
        verbose=True,
        chat_history=chat_history
    )
    
    # Clear legacy internal memory:
    if hasattr(agent, "memory") and hasattr(agent.memory, "chat_history"):
        fixed_history = []
        for msg in agent.memory.chat_history:
            # Check if the message is a dict or an object with a "role" attribute
            if isinstance(msg, dict):
                role = msg.get("role", "").lower()
                if role not in ["system", "user", "assistant"]:
                    print(f"Fixing legacy role in memory (dict): {role} -> assistant")
                    msg["role"] = "assistant"
                fixed_history.append(msg)
            else:
                # Assume it's a ChatMessage-like object
                if hasattr(msg, "role"):
                    if msg.role.lower() not in ["system", "user", "assistant"]:
                        print(f"Fixing legacy role in memory (object): {msg.role} -> {MessageRole.ASSISTANT}")
                        msg.role = MessageRole.ASSISTANT
                fixed_history.append(msg)
        agent.memory.chat_history = fixed_history
    else:
        print("Agent has no memory.chat_history attribute to fix.")
    
    return agent
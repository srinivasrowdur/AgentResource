from typing import Optional
from langchain.llms.base import BaseLLM

class Settings:
    """Global settings for the application"""
    
    # LLM client instance
    llm: Optional[BaseLLM] = None
    
    @classmethod
    def initialize_llm(cls, llm_client: BaseLLM):
        """Initialize the LLM client"""
        cls.llm = llm_client
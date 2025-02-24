import streamlit as st
import pytest
import sys
from pathlib import Path
from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from firebase_utils import initialize_firebase, reset_database
from src.agent_tools import ResourceQueryTools
from llama_agents import create_agent
import os
from dotenv import load_dotenv
import re
from llama_index.core.llms import ChatMessage, MessageRole
from openai import OpenAI as OpenAIClient
import argparse

# Load environment variables
load_dotenv()

# Clear Streamlit caches
st.cache_resource.clear()
st.cache_data.clear()

# Check for required environment variables
if not os.getenv('FIREBASE_CREDENTIALS_PATH'):
    st.error("Firebase credentials path not set. Please set FIREBASE_CREDENTIALS_PATH in .env file")
    st.stop()

if not os.getenv('OPENAI_API_KEY'):
    st.error("OpenAI API key not set. Please set OPENAI_API_KEY in .env file")
    st.stop()

def main():
    # Add command line argument parsing
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset-db", action="store_true", help="Reset database with sample data")
    args = parser.parse_args()

    try:
        # Initialize Firebase
        db = initialize_firebase(os.getenv('FIREBASE_CREDENTIALS_PATH'))
        
        # Reset database if requested and not already done
        if args.reset_db and not st.session_state.get('db_reset'):
            if reset_database(db):
                st.success("Database reset complete!")
                st.session_state.db_reset = True
            else:
                st.error("Failed to reset database")
                st.stop()

        # Initialize OpenAI without caching
        try:
            # Create a client to check models
            client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
            
            # Initialize LLM settings with GPT-4
            llm = OpenAI(
                model="gpt-4",
                api_key=os.getenv("OPENAI_API_KEY"),
                temperature=0.1
            )
            Settings.llm = llm
        except Exception as e:
            st.error(f"Error initializing OpenAI: {str(e)}")
            st.stop()

        def initialize_tools():
            """Initialize tools with proper dependencies"""
            # Load environment variables
            load_dotenv()
            
            # Initialize Firebase
            db = initialize_firebase(os.getenv('FIREBASE_CREDENTIALS_PATH'))
            
            # Initialize LLM client
            llm = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            
            # Create tools with all required dependencies
            return ResourceQueryTools(
                db=db,
                availability_db=db,  # Using same db for both
                llm_client=llm
            )

        # Use the initialization function
        tools = initialize_tools()

        def format_agent_response(response: str) -> str:
            """Format agent response to preserve tables"""
            # Split into text and table parts
            parts = re.split(r'(\|.*\|(?:\n\|.*\|)*)', response)
            
            formatted_parts = []
            has_table = False
            
            for part in parts:
                if part.strip():
                    if part.startswith('|') and '|' in part:
                        has_table = True
                        formatted_parts.append(part.strip())
                    else:
                        formatted_parts.append(part.strip())
            
            return "\n\n".join(formatted_parts)

        # Initialize session state
        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "last_employee_number" not in st.session_state:
            st.session_state.last_employee_number = None

        def handle_query(prompt: str):
            # Legacy implementation using a single consolidated call via our agent.
            if not prompt:
                 return

            # Add the user message to session state.
            st.session_state.messages.append({"role": "user", "content": prompt})

            # Create a placeholder for the assistant's response.
            with st.chat_message("assistant"):
                 message_placeholder = st.empty()

                 with st.spinner("Thinking..."):
                      # Force update API key and create fresh LLM instance using 40-mini.
                      api_key = os.getenv("OPENAI_API_KEY")
                      os.environ["OPENAI_API_KEY"] = api_key
                      llm = OpenAI(
                           model="gpt-4",
                           api_key=api_key,
                           temperature=0.1
                      )
                      Settings.llm = llm

                      # Build sanitized chat history from the last 5 messages.
                      sanitized_history = []
                      for msg in st.session_state.messages[-5:]:
                           current_role = "user" if msg.get("role", "").lower() == "user" else "assistant"
                           sanitized_history.append({"role": current_role, "content": msg["content"]})

                      # Build chat history (ChatMessage objects) using sanitized history.
                      from llama_index.core.llms import ChatMessage, MessageRole
                      chat_history = []
                      for msg in sanitized_history:
                           role = MessageRole.USER if msg["role"] == "user" else MessageRole.ASSISTANT
                           chat_history.append(ChatMessage(role=role, content=msg["content"]))

                      # Create tools and agent using the legacy approach.
                      current_agent = create_agent(tools.get_tools(), llm, chat_history=sanitized_history)
                      response = current_agent.chat(prompt, chat_history=chat_history)

                      formatted_response = format_agent_response(response.response)
                      message_placeholder.markdown(formatted_response)

                      st.session_state.messages.append({
                           "role": "assistant",
                           "content": formatted_response,
                           "context": response.response
                      })

                      st.rerun()

        # Streamlit UI
        st.title("Resource Management Assistant")

        # Sample questions section
        st.markdown("### Sample Questions")
        col1, col2 = st.columns(2)

        # Handle sample question buttons
        if col1.button("🔍 Show me all consultants in London"):
            handle_query("Show me all consultants in London")
            st.rerun()

        if col2.button("📅 Who is available in week 2?"):
            handle_query("Who is available in week 2?")
            st.rerun()

        st.markdown("---")

        # Clear Chat History button
        if st.button("Clear Chat History"):
            st.session_state.messages = []
            st.rerun()

        # Display chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(format_agent_response(message["content"]))

        # Handle chat input
        if prompt := st.chat_input("Ask about employee availability..."):
            handle_query(prompt)
            st.rerun()

    except Exception as e:
        st.error(f"Error in main function: {str(e)}")
        st.stop()

if __name__ == "__main__":
    main()
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

def run_tests():
    """Run all tests and return True if all pass"""
    # Get the root directory
    root_dir = Path(__file__).parent
    
    # Run pytest programmatically
    test_result = pytest.main([
        str(root_dir / "tests"),  # Test directory
        "-v",                     # Verbose output
        "--no-header",           # No header
        "-W", "ignore::pytest.PytestCollectionWarning"  # Ignore collection warnings
    ])
    
    return test_result == pytest.ExitCode.OK

def main():
    # Add command line argument parsing
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument("--reset-db", action="store_true", help="Reset database with sample data")
    args = parser.parse_args()

    # Only run tests on initial startup, not on reruns
    if not args.skip_tests and not st.session_state.get('tests_run'):
        if run_tests():
            st.session_state.tests_run = True
        else:
            st.error("⚠️ Tests failed! Please check the test output in the console.")
            st.stop()
            sys.exit(1)

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
            
            # Initialize tools and agent
            tools = ResourceQueryTools(db, availability_db, llm).get_tools()
            agent = create_agent(tools, llm, st.session_state.messages if 'messages' in st.session_state else None)
            
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
            """Handle user query and update chat history"""
            try:
                # Add user message to chat history
                st.session_state.messages.append({"role": "user", "content": prompt})
                
                # Get agent response
                response = agent.chat(prompt)
                
                # Add assistant response to chat history
                st.session_state.messages.append({"role": "assistant", "content": response})
                
            except Exception as e:
                st.error(f"Error processing query: {str(e)}")

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
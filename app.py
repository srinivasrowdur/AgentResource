import streamlit as st
from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from firebase_utils import initialize_firebase
from agent_tools import ResourceQueryTools
from llama_agents import create_agent
import os
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

# Check for required environment variables
if not os.getenv('FIREBASE_CREDENTIALS_PATH'):
    st.error("Firebase credentials path not set. Please set FIREBASE_CREDENTIALS_PATH in .env file")
    st.stop()

if not os.getenv('OPENAI_API_KEY'):
    st.error("OpenAI API key not set. Please set OPENAI_API_KEY in .env file")
    st.stop()

# Initialize OpenAI
Settings.llm = OpenAI(model="gpt-4", api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Firebase
try:
    db = initialize_firebase(os.getenv('FIREBASE_CREDENTIALS_PATH'))
except Exception as e:
    st.error(f"Error initializing Firebase: {str(e)}")
    st.error("Please check your Firebase credentials file path")
    st.stop()

# Initialize tools and agent
tools = ResourceQueryTools(db, db)
agent = create_agent(tools.get_tools(), Settings.llm)

def format_agent_response(response: str) -> str:
    """Format agent response to preserve tables"""
    # Split response into parts (text and tables)
    parts = re.split(r'(\|.*\|(?:\n\|.*\|)*)', response)
    
    formatted_parts = []
    for part in parts:
        if part.strip():
            if part.startswith('|') and '|' in part:
                # This is a table - preserve formatting
                formatted_parts.append(part)
            else:
                # This is regular text - wrap in paragraph
                formatted_parts.append(part.strip())
    
    return "\n\n".join(formatted_parts)

# Streamlit UI
st.title("Resource Management Assistant")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(format_agent_response(message["content"]))

# Chat input
if prompt := st.chat_input("Ask about employee availability..."):
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Get agent response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = agent.chat(prompt)
            formatted_response = format_agent_response(response.response)
            st.markdown(formatted_response)
            st.session_state.messages.append({"role": "assistant", "content": formatted_response}) 
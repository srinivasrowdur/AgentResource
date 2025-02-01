import streamlit as st
from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from firebase_utils import initialize_firebase
from agent_tools import ResourceQueryTools
from llama_agents import create_agent
import os
from dotenv import load_dotenv
import re
from llama_index.core.llms import ChatMessage, MessageRole

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
Settings.llm = OpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))

# Initialize Firebase
try:
    db = initialize_firebase(os.getenv('FIREBASE_CREDENTIALS_PATH'))
except Exception as e:
    st.error(f"Error initializing Firebase: {str(e)}")
    st.error("Please check your Firebase credentials file path")
    st.stop()

# Initialize tools and agent
@st.cache_resource
def get_agent():
    tools = ResourceQueryTools(db, db)
    agent = create_agent(tools.get_tools(), Settings.llm)
    return agent

agent = get_agent()

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

def handle_query(prompt: str):
    """Handle query and update session state"""
    if not prompt:
        return
        
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Create a placeholder for the assistant's response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        with st.spinner("Thinking..."):
            # Build chat history context
            chat_history = []
            for msg in st.session_state.messages[-5:]:  # Last 5 messages for context
                role = MessageRole.USER if msg["role"] == "user" else MessageRole.ASSISTANT
                chat_history.append(ChatMessage(
                    role=role,
                    content=msg["content"]
                ))
                if "context" in msg:  # Add any stored context
                    chat_history.append(ChatMessage(
                        role=MessageRole.SYSTEM,
                        content=f"Context: {msg['context']}"
                    ))
            
            # Get assistant response
            response = agent.chat(prompt, chat_history=chat_history)
            
            # Format and display response
            formatted_response = format_agent_response(response.response)
            message_placeholder.markdown(formatted_response)
            
            # Store response
            st.session_state.messages.append({
                "role": "assistant", 
                "content": formatted_response,
                "context": response.response if "consultants" in prompt.lower() or "availability" in prompt.lower() else None
            })

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

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(format_agent_response(message["content"]))

# Handle chat input
if prompt := st.chat_input("Ask about employee availability..."):
    handle_query(prompt)
    st.rerun() 
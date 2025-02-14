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
from openai import OpenAI as OpenAIClient

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

# Initialize OpenAI without caching
try:
    # Create a client to check models
    client = OpenAIClient(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Initialize LLM settings
    Settings.llm = OpenAI(
        model="gpt-4o-mini",
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.1
    )
except Exception as e:
    st.error(f"Error initializing OpenAI: {str(e)}")
    st.stop()

# Initialize Firebase
try:
    db = initialize_firebase(os.getenv('FIREBASE_CREDENTIALS_PATH'))
except Exception as e:
    st.error(f"Error initializing Firebase: {str(e)}")
    st.error("Please check your Firebase credentials file path")
    st.stop()

# Remove global agent creation
# tools = ResourceQueryTools(db, db)
# agent = create_agent(tools.get_tools(), Settings.llm)

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
    """Handle query and update session state"""
    if not prompt:
        return
        
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Create a placeholder for the assistant's response
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        thinking_placeholder = st.empty()
        
        with st.spinner("Thinking..."):
            # Force update OpenAI settings
            api_key = os.getenv("OPENAI_API_KEY")
            os.environ["OPENAI_API_KEY"] = api_key
            
            # Create fresh LLM instance and update global settings
            llm = OpenAI(
                model="gpt-4o-mini",
                api_key=api_key,
                temperature=0.1
            )
            Settings.llm = llm
            
            # Create fresh tools and agent
            tools = ResourceQueryTools(db, db)
            current_agent = create_agent(tools.get_tools(), llm)
            
            # Build chat history context with last employee number
            chat_history = []
            
            # Add system context about the last interaction
            if len(st.session_state.messages) > 0:
                last_msg = st.session_state.messages[-1]
                if "EMP" in last_msg["content"]:
                    # Extract the last mentioned employee details
                    emp_match = re.search(r'(\w+ \w+).*?EMP\d{3}', last_msg["content"])
                    if emp_match:
                        chat_history.append(ChatMessage(
                            role=MessageRole.SYSTEM,
                            content=f"The last response mentioned {emp_match.group(1)}. Use their employee number to look up details."
                        ))
            
            # Add recent message history
            for msg in st.session_state.messages[-5:]:
                role = MessageRole.USER if msg["role"] == "user" else MessageRole.ASSISTANT
                chat_history.append(ChatMessage(
                    role=role,
                    content=msg["content"]
                ))
            
            # Get response using fresh agent
            response = current_agent.chat(prompt, chat_history=chat_history)
            
            # Update last employee number if response mentions one
            if "EMP" in response.response:
                emp_match = re.search(r'EMP\d{3}', response.response)
                if emp_match:
                    st.session_state.last_employee_number = emp_match.group(0)
            
            # Format and display response
            formatted_response = format_agent_response(response.response)
            message_placeholder.markdown(formatted_response)
            
            # Store response with context
            st.session_state.messages.append({
                "role": "assistant", 
                "content": formatted_response,
                "context": response.response,
                "last_employee": st.session_state.last_employee_number
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
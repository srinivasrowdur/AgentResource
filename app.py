import streamlit as st
from llama_index.core import Settings
from llama_index.llms.openai import OpenAI
from firebase_utils import initialize_firebase
from agent_tools import ResourceQueryTools
from llama_agents import create_agent
import os
from dotenv import load_dotenv
import re
from llama_index.core.callbacks import LlamaDebugHandler, CallbackManager
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
    return create_agent(tools.get_tools(), Settings.llm)

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
                # Ensure table is properly formatted
                formatted_parts.append(part.strip())
            else:
                # Format text part
                formatted_parts.append(part.strip())
    
    # If no table found in response but it looks like it should have one,
    # try to convert text to table format
    if not has_table and any(keyword in response.lower() for keyword in ['emp', 'available', 'consultant', 'partner']):
        lines = response.split('\n')
        if len(lines) > 1:
            # Attempt to format as table
            table_lines = []
            for line in lines:
                if line.strip() and not line.startswith(('Here', 'The', 'These')):
                    parts = line.split(' - ')
                    if len(parts) >= 2:
                        table_lines.append(f"| {' | '.join(parts)} |")
            
            if table_lines:
                header = "| Name | Details |"
                separator = "|------|---------|"
                formatted_parts.append(f"{header}\n{separator}\n" + "\n".join(table_lines))
    
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
        thinking_placeholder = st.empty()
        
        with st.spinner("Thinking..."):
            # Create a container for thoughts
            thoughts_container = thinking_placeholder.container()
            thoughts = []
            
            # Create callback to capture thoughts
            class ThoughtCallback(LlamaDebugHandler):
                def on_event(self, event_type: str, payload: dict) -> None:
                    if event_type == "agent_step":
                        if "thought" in payload:
                            thought = payload["thought"].strip()
                            if thought and not thought.startswith("I can answer without"):
                                thoughts.append(thought)
                                thoughts_container.info(f"💭 Step {len(thoughts)}: {thought}")
            
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
            
            # Create new agent with callback and context
            callback_manager = CallbackManager([ThoughtCallback()])
            tools = ResourceQueryTools(db, db)
            agent_with_callback = create_agent(tools.get_tools(), Settings.llm, callback_manager)
            
            # Get assistant response with context
            response = agent_with_callback.chat(
                prompt,
                chat_history=chat_history
            )
            
            # Store any relevant context for future use
            context = None
            if "consultants" in prompt.lower() or "availability" in prompt.lower():
                context = response.response  # Store the response as context
            
            # Format and display final response
            formatted_response = format_agent_response(response.response)
            message_placeholder.markdown(formatted_response)
            st.session_state.messages.append({
                "role": "assistant", 
                "content": formatted_response,
                "thoughts": thoughts,
                "context": context
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
        if message["role"] == "assistant":
            if "thoughts" in message and message["thoughts"]:
                with st.container():
                    st.write("🤔 **My Thinking Process:**")
                    for i, thought in enumerate(message["thoughts"], 1):
                        st.info(f"💭 Step {i}: {thought}")
            st.markdown(format_agent_response(message["content"]))
        else:
            st.markdown(message["content"])

# Handle chat input
if prompt := st.chat_input("Ask about employee availability..."):
    handle_query(prompt)
    st.rerun() 
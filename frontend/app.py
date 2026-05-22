import streamlit as st
import requests
import os
from datetime import datetime
import base64
from audio_recorder_streamlit import audio_recorder

# PAGE CONFIG
st.set_page_config(
    page_title="AgentForge AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CUSTOM CSS
st.markdown("""
<style>

    .stChatInputContainer {
        padding-bottom: 20px;
    }

    .agent-box {
        padding: 10px;
        border-radius: 10px;
        background-color: #1e1e1e;
        margin-bottom: 10px;
    }

</style>
""", unsafe_allow_html=True)

# SESSION STATE
if "messages" not in st.session_state:
    st.session_state.messages = []

if "selected_agent" not in st.session_state:
    st.session_state.selected_agent = "None"

if "retrieved_chunks" not in st.session_state:
    st.session_state.retrieved_chunks = []

# SIDEBAR
with st.sidebar:

    st.title("📂 Document Upload")

    doc_type = st.radio(
        "Select Document Type",
        ["Resume", "Research Paper"],
        help="""
        Resume:
        Career guidance + ATS analysis

        Research Paper:
        Research summarization + RAG
        """
    )

    uploaded_file = st.file_uploader(
        f"Upload your {doc_type} (PDF)",
        type=["pdf"]
    )

    st.divider()

    st.subheader("🧠 Agent Observability")

    st.write(
        "Selected Agent:",
        st.session_state.selected_agent
    )

    st.write(
        "Retrieved Research Chunks:",
        len(st.session_state.retrieved_chunks)
    )

    if st.session_state.retrieved_chunks:

        with st.expander("View Retrieved Chunks"):

            for idx, chunk in enumerate(
                st.session_state.retrieved_chunks
            ):

                st.markdown(
                    f"""
                    <div class="agent-box">
                    <b>Chunk {idx+1}</b><br>
                    {chunk[:500]}...
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    st.divider()

    if st.button(
        "🗑️ Clear Chat History",
        use_container_width=True
    ):

        st.session_state.messages = []

        st.rerun()

# MAIN AREA
st.title("🤖 AgentForge AI")

st.markdown("""
Multi-Agent AI Career & Research Assistant

Features:
- Resume Analysis
- Research Paper RAG
- Career Guidance
- AI Interview Preparation
- Long-Term Memory
- Multi-Agent Routing
""")

# DISPLAY CHAT HISTORY
for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])
        
        if "chunks" in message and message["chunks"]:
            with st.expander("📚 Source Citations"):
                for idx, chunk in enumerate(message["chunks"]):
                    st.markdown(f"**Source {idx+1}**\n\n{chunk}")
                    
        if "audio_response_b64" in message:
            audio_bytes = base64.b64decode(message["audio_response_b64"])
            # Don't autoplay history
            st.audio(audio_bytes, format="audio/mp3")
            
        if "timestamp" in message:
            st.caption(f"_{message['timestamp']}_")

# CHAT INPUT
user_input = st.chat_input(
    "Ask something..."
)

# AUDIO INPUT
st.markdown("Or speak your message:")
audio_bytes = audio_recorder(text="Record", icon_size="2x")

# USER MESSAGE
if user_input or audio_bytes:

    current_time = datetime.now().strftime("%I:%M %p")
    
    audio_data_b64 = None
    if audio_bytes:
        audio_data_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        if not user_input:
            user_input = "🎤 *Voice Message*"

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_input,
            "timestamp": current_time
        }
    )

    with st.chat_message("user"):

        st.markdown(user_input)
        st.caption(f"_{current_time}_")

    payload = {
        "message": user_input,
        "doc_type": doc_type,
        "audio_data": audio_data_b64
    }

    # SAVE UPLOADED FILE
    if uploaded_file is not None:

        save_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "backend",
                "uploaded_document.pdf"
            )
        )

        with open(save_path, "wb") as f:

            f.write(
                uploaded_file.getbuffer()
            )

        payload["resume_path"] = save_path

    # BACKEND REQUEST
    spinner_msg = "🧠 Research Agent analyzing paper..." if doc_type == "Research Paper" else "📄 Resume Agent reviewing ATS score..."
    with st.spinner(spinner_msg):

        audio_response_b64 = None
        
        try:

            response = requests.post(
                "http://127.0.0.1:8000/chat",
                json=payload
            )

            data = response.json()

            agent_response = data.get(
                "response",
                "No response from agent."
            )
            
            audio_response_b64 = data.get("audio_response", None)

            # OBSERVABILITY
            st.session_state.selected_agent = data.get(
                "selected_agent",
                "Unknown"
            )

            st.session_state.retrieved_chunks = data.get(
                "retrieved_chunks",
                []
            )

        except Exception as e:

            agent_response = f"""
            Error connecting to backend:
            {str(e)}
            """

    # SAVE ASSISTANT MESSAGE
    assistant_time = datetime.now().strftime("%I:%M %p")
    assistant_msg = {
        "role": "assistant",
        "content": agent_response,
        "timestamp": assistant_time
    }
    
    if audio_response_b64:
        assistant_msg["audio_response_b64"] = audio_response_b64
    
    if st.session_state.retrieved_chunks:
        assistant_msg["chunks"] = st.session_state.retrieved_chunks
        
    st.session_state.messages.append(assistant_msg)

    # DISPLAY RESPONSE
    with st.chat_message("assistant"):

        st.markdown(agent_response)
        
        if audio_response_b64:
            audio_bytes = base64.b64decode(audio_response_b64)
            st.audio(audio_bytes, format="audio/mp3", autoplay=True)
        
        if st.session_state.retrieved_chunks:
            with st.expander("📚 Source Citations"):
                for idx, chunk in enumerate(st.session_state.retrieved_chunks):
                    st.markdown(f"**Source {idx+1}**\n\n{chunk}")
                    
        st.caption(f"_{assistant_time}_")
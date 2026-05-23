from fastapi import FastAPI
from pydantic import BaseModel
import base64
import tempfile
import os

# Add ffmpeg to PATH dynamically for Windows
ffmpeg_path = r"C:\Users\Abhinand Prameesh\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin"
if os.path.exists(ffmpeg_path) and ffmpeg_path not in os.environ["PATH"]:
    os.environ["PATH"] = ffmpeg_path + os.pathsep + os.environ["PATH"]

import whisper
import edge_tts
import asyncio

from agent import llm
import json

from research_agent import store_research_paper
from workflow import app_workflow

from vector_memory import (
    store_memory,
    retrieve_memory
)

from profile_memory import (
    save_profile,
    load_profile
)

app = FastAPI()

# Load Whisper model globally to save time
print("Loading Whisper model...")
try:
    whisper_model = whisper.load_model("base")
    print("Whisper model loaded!")
except Exception as e:
    print(f"Warning: Failed to load whisper model. Audio transcription might fail: {e}")
    whisper_model = None

# INPUT MODEL
class UserInput(BaseModel):

    message: str | None = None
    audio_data: str | None = None
    resume_path: str | None = None
    doc_type: str = "Resume"

# CHAT ENDPOINT
@app.post("/chat")
async def chat(user_input: UserInput):

    try:
        # Handle Audio Input
        if user_input.audio_data and whisper_model:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
                audio_bytes = base64.b64decode(user_input.audio_data)
                temp_audio.write(audio_bytes)
                temp_audio_path = temp_audio.name
            
            # Transcribe with Whisper (Offloaded to CPU worker thread)
            result = await asyncio.to_thread(whisper_model.transcribe, temp_audio_path)
            user_input.message = result["text"].strip()
            
            # Cleanup temp file
            os.remove(temp_audio_path)
        
        if not user_input.message:
            return {"response": "Please provide a message or audio input."}

        # Load persistent user profile
        profile_data = load_profile()

        # Retrieve semantic memories (Offloaded to DB worker thread)
        relevant_memories = await asyncio.to_thread(
            retrieve_memory,
            user_input.message
        )

        memory_context = "\n".join(
            relevant_memories
        )

        memory_context = f"""
        These are important memories from previous conversations:

        {memory_context}

        Use them only if relevant.
        """

        # Document handling
        resume_text = ""

        if user_input.resume_path:
            
            if user_input.doc_type == "Research Paper":
                # Store research paper embeddings only (Offloaded to DB worker thread)
                try:
                    await asyncio.to_thread(store_research_paper, user_input.resume_path)
                except:
                    pass
            else:
                # Store resume embeddings (optional) and extract text
                try:
                    await asyncio.to_thread(store_research_paper, user_input.resume_path)
                except:
                    pass
                
                from tools import analyze_resume

                # Offload heavy PDF parsing to thread pool
                resume_text = await asyncio.to_thread(
                    analyze_resume.invoke,
                    {"file_path": user_input.resume_path}
                )

                # Dynamically extract career interest and skills from resume using LLM
                try:
                    extraction_response = await asyncio.to_thread(
                        llm.invoke,
                        f"""
                        You are an expert profile extractor.
                        Analyze the following resume text and extract two key details in JSON format:
                        1. "career_interest": A highly specific career focus (e.g. "Computer Vision Engineer", "MLOps Professional", "NLP Specialist") based on their projects/experience.
                        2. "skills": A list of their top technical skills (maximum 10).

                        Return ONLY a raw valid JSON object with the keys "career_interest" and "skills".
                        Do not wrap in markdown or backticks.

                        Resume Text:
                        {resume_text}
                        """
                    )
                    extracted_data = json.loads(extraction_response.content.strip("`").replace("json", "").strip())
                    profile_data["resume_uploaded"] = True
                    profile_data["career_interest"] = extracted_data.get("career_interest", "AI Research Internships")
                    profile_data["skills"] = extracted_data.get("skills", [])
                except Exception as ex:
                    profile_data["resume_uploaded"] = True
                    profile_data["career_interest"] = "AI Research Internships"
                    profile_data["skills"] = []
                
                save_profile(profile_data)

        # Run LangGraph workflow (Offloaded to workflow worker thread)
        workflow_result = await asyncio.to_thread(
            app_workflow.invoke,
            {
                "user_input": f"""
                User Profile:
                {profile_data}

                Previous Relevant Memories:
                {memory_context}

                Current User Message:
                {user_input.message}
                """,

                "resume_text": resume_text
            }
        )

        response_text = workflow_result["response"]

        # Store important semantic memory
        important_memory = f"""
        User Query:
        {user_input.message}

        AI Response:
        {response_text}
        """

        # Offload DB write
        await asyncio.to_thread(store_memory, important_memory)

        # Generate Audio Response with Edge-TTS
        audio_response_b64 = None
        if user_input.audio_data or "interview" in workflow_result.get("selected_agent", "").lower():
            # Generate audio if the user spoke to us OR if it's the interview agent
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_mp3:
                temp_mp3_path = temp_mp3.name
            
            # Voice can be changed: en-US-AriaNeural, en-US-GuyNeural, en-GB-SoniaNeural, etc.
            communicate = edge_tts.Communicate(response_text, "en-US-AriaNeural")
            await communicate.save(temp_mp3_path)
            
            with open(temp_mp3_path, "rb") as f:
                audio_response_b64 = base64.b64encode(f.read()).decode("utf-8")
            
            os.remove(temp_mp3_path)

        return {
            "response": response_text,
            "selected_agent": workflow_result.get("selected_agent", "Unknown"),
            "retrieved_chunks": workflow_result.get("retrieved_chunks", []),
            "audio_response": audio_response_b64
        }

    except Exception as e:

        return {
            "response": f"Error: {str(e)}"
        }
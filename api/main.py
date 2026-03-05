from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
import uuid

from models import ChatRequest, ChatResponse
from agent import process_chat
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(
    title="IBM MQ AI Gateway",
    description="A UI-agnostic REST API for interacting with IBM MQ via LangGraph and LLMs.",
    version="1.0.0"
)

# Enable CORS for frontend applications (React, Angular, UI testing apps)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session tracking. For a production app, use Redis or a Database.
# Dictionary mapping: session_id -> list of Langchain BaseMessages
SESSIONS = {}

@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "message": "MQ AI Gateway is running."}

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint.
    Takes a session_id and user message string.
    Returns the AI's response along with a list of tools it used.
    """
    try:
        session_id = request.session_id
        if not session_id:
            session_id = str(uuid.uuid4())
            
        # Retrieve history or start fresh
        history = SESSIONS.get(session_id, [])
        
        # Add new user message
        history.append(HumanMessage(content=request.message))
        
        # Run graph
        reply_mgs, tools_used = await process_chat(history)
        
        # Assuming the AI responded, store the final AI message too
        from langchain_core.messages import AIMessage
        history.append(AIMessage(content=reply_mgs))
        
        # Save back to memory
        SESSIONS[session_id] = history
        
        
        return ChatResponse(
            reply=reply_mgs,
            tools_used=tools_used
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


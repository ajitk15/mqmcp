from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
import uuid

from models import ChatRequest, ChatResponse
from agent import process_chat
from fastapi.staticfiles import StaticFiles
import os
import sys
import time

# Ensure we can import utils
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
from utils.logger import get_api_logger
logger = get_api_logger()

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
    logger.info("Health check endpoint accessed")
    return {"status": "ok", "message": "MQ AI Gateway is running."}

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint.
    Takes a session_id and user message string.
    Returns the AI's response along with a list of tools it used.
    """
    start_time = time.time()
    try:
        session_id = request.session_id
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info("Generated new session_id", extra={"context": {"session_id": session_id}})
            
        logger.info("Received chat request", extra={"context": {"session_id": session_id, "message_length": len(request.message)}})
            
        # Retrieve history or start fresh
        history = SESSIONS.get(session_id, [])
        
        # Add new user message
        history.append(HumanMessage(content=request.message))
        
        # Run graph
        reply_mgs, tools_used = await process_chat(history, session_id=session_id)
        
        # Assuming the AI responded, store the final AI message too
        from langchain_core.messages import AIMessage
        history.append(AIMessage(content=reply_mgs))
        
        # Save back to memory
        SESSIONS[session_id] = history
        
        duration_ms = (time.time() - start_time) * 1000
        logger.info("Successfully processed chat request", extra={
            "metrics": {"execution_time_ms": duration_ms, "tools_used_count": len(tools_used)}, 
            "context": {"session_id": session_id, "tools_used": tools_used}
        })
        
        return ChatResponse(
            reply=reply_mgs,
            tools_used=tools_used
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"Chat request failed: {str(e)}", extra={"metrics": {"execution_time_ms": duration_ms}, "context": {"session_id": getattr(request, 'session_id', 'unknown')}})
        raise HTTPException(status_code=500, detail=str(e))


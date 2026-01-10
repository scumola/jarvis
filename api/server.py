"""
Jarvis FastAPI Server - Multi-user AI assistant with memory.

Provides REST API endpoints for:
- Authentication (API key-based)
- Chat interactions with conversation memory
- Session management
- Memory inspection
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import yaml
from pathlib import Path

from api.auth import get_current_user
from api.session_manager import SessionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load config
config_path = Path(__file__).parent.parent / "config" / "config.yaml"
with open(config_path) as f:
    config = yaml.safe_load(f)

# Create FastAPI app
app = FastAPI(
    title="Jarvis API",
    description="Multi-user AI assistant with persistent memory and conversation context",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize session manager (will be set in startup event)
session_manager: Optional[SessionManager] = None


# Request/Response Models

class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(description="User message to send to Jarvis")
    stream: bool = Field(default=False, description="Stream response (not yet implemented)")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str = Field(description="Jarvis' response")
    actions_taken: List[Dict[str, Any]] = Field(description="List of actions/tools executed")
    verification: Optional[Dict[str, Any]] = Field(default=None, description="Verification result if applicable")
    session_id: str = Field(description="Session identifier")


class UserInfo(BaseModel):
    """User information response model."""
    user_id: int
    username: str
    display_name: Optional[str]
    role: str


class SessionInfo(BaseModel):
    """Session information response model."""
    session_id: str
    username: str
    role: str
    message_count: int
    created_at: str
    last_activity: str


class MemoryItem(BaseModel):
    """Memory item response model."""
    id: int
    text: str
    type: str
    confidence: float
    importance: float
    decay_score: float
    created_at: Optional[str]


class MemoriesResponse(BaseModel):
    """Response model for memories endpoint."""
    memories: List[MemoryItem]
    count: int


# API Endpoints

@app.get("/")
async def root():
    """Root endpoint - API status."""
    return {
        "service": "Jarvis API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/v1/me", response_model=UserInfo)
async def get_user_info(current_user: Dict = Depends(get_current_user)):
    """
    Get current authenticated user information.

    Returns user ID, username, display name, and role.
    """
    return UserInfo(
        user_id=current_user['id'],
        username=current_user['username'],
        display_name=current_user.get('display_name'),
        role=current_user['role']
    )


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    Send a message to Jarvis and get a response.

    This endpoint maintains conversation context per user. Each user has
    a dedicated Orchestrator instance with persistent conversation history.

    Args:
        request: ChatRequest with message
        current_user: Authenticated user from dependency

    Returns:
        ChatResponse with Jarvis' reply and actions taken
    """
    user_id = current_user['id']
    username = current_user['username']
    user_role = current_user['role']

    logger.info(f"Chat request from user {username} (ID: {user_id}): {request.message[:50]}...")

    # Get or create user session
    session = session_manager.get_or_create_session(user_id, username, user_role)

    try:
        # Process message through orchestrator
        result = session.orchestrator.process_user_input(
            user_input=request.message,
            user_id=user_id  # NEW: Pass user_id for memory isolation
        )

        # Save conversation history
        session_manager.save_session(user_id)

        logger.info(f"Chat response to user {username}: {len(result['response'])} chars, {len(result['actions_taken'])} actions")

        return ChatResponse(
            response=result['response'],
            actions_taken=result['actions_taken'],
            verification=result.get('verification'),
            session_id=session.session_id
        )

    except Exception as e:
        logger.error(f"Error processing message for user {username}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@app.get("/api/v1/session", response_model=SessionInfo)
async def get_session_info(current_user: Dict = Depends(get_current_user)):
    """
    Get current session information.

    Returns session ID, message count, and activity timestamps.
    """
    user_id = current_user['id']

    session_info = session_manager.get_session_info(user_id)

    if not session_info:
        # No active session yet, create one to return info
        session = session_manager.get_or_create_session(
            user_id,
            current_user['username'],
            current_user['role']
        )
        session_info = session_manager.get_session_info(user_id)

    return SessionInfo(**session_info)


@app.post("/api/v1/session/reset")
async def reset_session(current_user: Dict = Depends(get_current_user)):
    """
    Reset conversation history for current user.

    Clears all conversation messages but preserves long-term memories.
    """
    user_id = current_user['id']
    username = current_user['username']

    session_manager.reset_session(user_id)

    logger.info(f"Reset conversation history for user {username}")

    return {
        "status": "success",
        "message": "Conversation history cleared"
    }


@app.get("/api/v1/memories", response_model=MemoriesResponse)
async def get_memories(
    query: Optional[str] = None,
    limit: int = 10,
    current_user: Dict = Depends(get_current_user)
):
    """
    Retrieve user's memories.

    If query is provided, performs semantic search. Otherwise returns recent memories.

    Args:
        query: Optional search query for semantic search
        limit: Maximum number of memories to return (default 10)
        current_user: Authenticated user

    Returns:
        MemoriesResponse with list of memories
    """
    user_id = current_user['id']
    username = current_user['username']

    logger.info(f"Memory request from user {username}: query='{query}', limit={limit}")

    # Get or create session to access memory manager
    session = session_manager.get_or_create_session(
        user_id,
        username,
        current_user['role']
    )

    try:
        if query:
            # Semantic search
            memories = session.orchestrator.memory_manager.retrieve_memories(
                user_id=user_id,
                query=query,
                k=limit
            )
        else:
            # Get recent memories
            memories = session.orchestrator.memory_manager.metadata_store.filter_memories(
                user_id=user_id,
                limit=limit
            )

        # Convert to response format
        memory_items = [
            MemoryItem(
                id=m.id,
                text=m.memory_text,
                type=str(m.memory_type),
                confidence=m.confidence,
                importance=m.importance,
                decay_score=m.decay_score,
                created_at=m.created_at.isoformat() if m.created_at else None
            )
            for m in memories
        ]

        return MemoriesResponse(
            memories=memory_items,
            count=len(memory_items)
        )

    except Exception as e:
        logger.error(f"Error retrieving memories for user {username}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving memories: {str(e)}")


@app.get("/api/v1/stats")
async def get_stats(current_user: Dict = Depends(get_current_user)):
    """
    Get memory system statistics for current user.

    Returns counts and averages for the user's memory bank.
    """
    user_id = current_user['id']
    username = current_user['username']

    # Get or create session
    session = session_manager.get_or_create_session(
        user_id,
        username,
        current_user['role']
    )

    try:
        # Get all memories for user
        all_memories = session.orchestrator.memory_manager.metadata_store.filter_memories(
            user_id=user_id,
            limit=None
        )

        total_count = len(all_memories)

        if total_count == 0:
            return {
                'total_memories': 0,
                'by_type': {},
                'avg_confidence': 0.0,
                'avg_decay_score': 0.0
            }

        # Aggregate stats
        by_type = {}
        total_confidence = 0.0
        total_decay = 0.0

        for memory in all_memories:
            mem_type = str(memory.memory_type)
            if mem_type not in by_type:
                by_type[mem_type] = 0
            by_type[mem_type] += 1

            total_confidence += memory.confidence
            total_decay += memory.decay_score

        stats = {
            'total_memories': total_count,
            'by_type': by_type,
            'avg_confidence': round(total_confidence / total_count, 2),
            'avg_decay_score': round(total_decay / total_count, 2),
            'user_id': user_id,
            'username': username
        }

        return stats

    except Exception as e:
        logger.error(f"Error getting stats for user {username}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error getting statistics: {str(e)}")


# Background Tasks

async def cleanup_sessions_task():
    """
    Background task to periodically clean up inactive sessions.

    Runs every 5 minutes.
    """
    while True:
        await asyncio.sleep(300)  # 5 minutes
        try:
            logger.debug("Running session cleanup...")
            session_manager.cleanup_inactive_sessions()
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}", exc_info=True)


# Application Lifecycle Events

@app.on_event("startup")
async def startup_event():
    """Initialize services on application startup."""
    global session_manager

    logger.info("Starting Jarvis API server...")

    # Initialize session manager
    session_manager = SessionManager(config, config['memory'])
    logger.info("Session manager initialized")

    # Start background cleanup task
    asyncio.create_task(cleanup_sessions_task())
    logger.info("Session cleanup task started")

    logger.info("Jarvis API server started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on application shutdown."""
    logger.info("Shutting down Jarvis API server...")

    # Save all active sessions
    if session_manager:
        for user_id in list(session_manager.sessions.keys()):
            try:
                session_manager.save_session(user_id)
            except Exception as e:
                logger.error(f"Error saving session during shutdown: {e}", exc_info=True)

    logger.info("Jarvis API server shutdown complete")


# Run server
if __name__ == "__main__":
    import uvicorn

    # Get API config
    api_config = config.get('api', {})
    host = api_config.get('host', '0.0.0.0')
    port = api_config.get('port', 8000)

    logger.info(f"Starting Jarvis API server on {host}:{port}")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )

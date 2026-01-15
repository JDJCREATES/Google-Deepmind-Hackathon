"""
Session Control API

Endpoints for managing on-demand simulation sessions and budget monitoring.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.session_manager import session_manager
from app.services.budget_manager import budget_manager
from app.utils.logging import get_agent_logger

logger = get_agent_logger("SessionAPI")

router = APIRouter(prefix="/api/session", tags=["session"])


class SessionStartRequest(BaseModel):
    duration_minutes: Optional[int] = 10


@router.post("/start")
async def start_session(request: SessionStartRequest):
    """
    Start a new simulation session.
    
    Sessions run for a fixed duration to control costs.
    """
    # Check budget first
    if not budget_manager.can_make_request():
        raise HTTPException(
            status_code=429,
            detail={
                "error": "daily_budget_exceeded",
                "message": "Daily API budget exceeded. Please try again tomorrow.",
                "budget_stats": budget_manager.get_stats()
            }
        )
    
    session_info = await session_manager.start_session(request.duration_minutes)
    
    logger.info(f"✅ Session started via API: {session_info['session_id']}")
    
    return {
        "status": "started",
        "session": session_info,
        "budget": budget_manager.get_stats()
    }


@router.post("/stop")
async def stop_session():
    """Stop the active session."""
    result = await session_manager.stop_session()
    
    return {
        "status": "stopped",
        "session": result,
        "budget": budget_manager.get_stats()
    }


@router.get("/status")
async def get_session_status():
    """Get current session and budget status."""
    return {
        "session": session_manager.get_session_info(),
        "budget": budget_manager.get_stats()
    }


@router.get("/budget")
async def get_budget_stats():
    """Get detailed budget statistics."""
    return budget_manager.get_stats()

"""
API Router for hypothesis market and reasoning endpoints.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.graphs import run_hypothesis_market
from app.reasoning import DecisionPolicy, FrameworkDriftDetector
from app.utils.logging import get_agent_logger

router = APIRouter(prefix="/hypothesis", tags=["Hypothesis"])
logger = get_agent_logger("API_Hypothesis")

# Shared state access (in real app would be DB/Cache)
from app.graphs.nodes import drift_detector


class InvestigationRequest(BaseModel):
    signal_id: str
    signal_type: str
    description: str
    data: Dict[str, Any]


class InvestigationResponse(BaseModel):
    status: str
    belief_state: Optional[Dict[str, Any]] = None
    action: Optional[str] = None
    drift_alert: Optional[Dict[str, Any]] = None


@router.post("/run", response_model=InvestigationResponse)
async def run_investigation(request: InvestigationRequest):
    """
    Trigger a full hypothesis-driven investigation.
    """
    try:
        logger.info(f"🕵️‍♂️ API triggered investigation: {request.signal_id}")
        
        final_state = await run_hypothesis_market(
            signal_id=request.signal_id,
            signal_type=request.signal_type,
            signal_description=request.description,
            signal_data=request.data,
        )
        
        belief_state = final_state.get("belief_state")
        belief_dict = belief_state.to_dict() if belief_state else None
        
        return {
            "status": "COMPLETED",
            "belief_state": belief_dict,
            "action": final_state.get("selected_action"),
            "drift_alert": final_state.get("drift_alert"),
        }
        
    except Exception as e:
        logger.error(f"Investigation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drift/status")
async def get_drift_status():
    """Get current framework drift statistics."""
    stats = drift_detector.get_stats()
    current_alert = drift_detector.detect_drift()
    
    return {
        "stats": stats,
        "active_alert": current_alert.to_dict() if current_alert else None
    }


@router.get("/policy/current")
async def get_current_policy():
    """Get the current decision policy."""
    # In a real app, this would fetch from StrategicMemory
    # For now, we return a fresh reference or singleton
    policy = DecisionPolicy.create_initial()
    return {
        "version": policy.version,
        "framework_weights": policy.framework_weights,
        "confidence_threshold_act": policy.confidence_threshold_act,
        "insights": policy.policy_insights
    }

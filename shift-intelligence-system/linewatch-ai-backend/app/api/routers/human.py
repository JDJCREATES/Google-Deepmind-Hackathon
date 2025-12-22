"""
API Router for Human-in-the-Loop (HITL) interactions.
"""
from fastapi import APIRouter, HTTPException, Path, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4

from app.utils.logging import get_agent_logger
from app.services.websocket import manager

router = APIRouter(prefix="/human", tags=["HITL"])
logger = get_agent_logger("API_Human")

# In-memory store for pending approvals (would be DB in prod)
# Key: approval_id, Value: Dict
PENDING_APPROVALS: Dict[str, Dict[str, Any]] = {}


class ApprovalRequest(BaseModel):
    """Request sent to human for approval."""
    id: str
    agent_name: str
    action_type: str
    description: str
    severity: str
    target_resource: Optional[str] = None
    created_at: datetime
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED
    
    
class ApprovalResponse(BaseModel):
    """Human response to request."""
    approved: bool
    feedback: Optional[str] = None
    modified_parameters: Optional[Dict[str, Any]] = None


@router.get("/inbox", response_model=List[ApprovalRequest])
async def get_inbox():
    """Get all pending approval requests."""
    return [
        ApprovalRequest(**item) 
        for item in PENDING_APPROVALS.values() 
        if item["status"] == "PENDING"
    ]


@router.post("/inbox/{approval_id}/approve")
async def approve_request(
    approval_id: str = Path(..., title="The ID of the approval request"),
    feedback: Optional[str] = Body(None)
):
    """Approve a pending request."""
    if approval_id not in PENDING_APPROVALS:
        raise HTTPException(status_code=404, detail="Request not found")
        
    request = PENDING_APPROVALS[approval_id]
    if request["status"] != "PENDING":
        raise HTTPException(status_code=400, detail="Request already processed")
        
    # Update status
    request["status"] = "APPROVED"
    request["resolved_at"] = datetime.now()
    request["feedback"] = feedback
    
    # Notify system via WebSocket
    await manager.broadcast({
        "type": "human_decision",
        "data": {
            "approval_id": approval_id,
            "decision": "APPROVED",
            "feedback": feedback,
            "agent": request["agent_name"]
        }
    })
    
    logger.info(f"✅ Human APPROVED request {approval_id}")
    return {"status": "approved"}


@router.post("/inbox/{approval_id}/reject")
async def reject_request(
    approval_id: str = Path(..., title="The ID of the approval request"),
    feedback: Optional[str] = Body(None)
):
    """Reject a pending request."""
    if approval_id not in PENDING_APPROVALS:
        raise HTTPException(status_code=404, detail="Request not found")
        
    request = PENDING_APPROVALS[approval_id]
    if request["status"] != "PENDING":
        raise HTTPException(status_code=400, detail="Request already processed")
        
    # Update status
    request["status"] = "REJECTED"
    request["resolved_at"] = datetime.now()
    request["feedback"] = feedback or "Rejected by supervisor"
    
    # Notify system via WebSocket
    await manager.broadcast({
        "type": "human_decision",
        "data": {
            "approval_id": approval_id,
            "decision": "REJECTED",
            "feedback": request["feedback"],
            "agent": request["agent_name"]
        }
    })
    
    logger.info(f"❌ Human REJECTED request {approval_id}")
    return {"status": "rejected"}


async def create_approval_request(
    agent_name: str, 
    action: str, 
    description: str,
    severity: str = "MEDIUM"
) -> str:
    """Internal helper to create a new approval request."""
    approval_id = f"REQ-{uuid4().hex[:8]}"
    
    request = {
        "id": approval_id,
        "agent_name": agent_name,
        "action_type": action,
        "description": description,
        "severity": severity,
        "created_at": datetime.now(),
        "status": "PENDING"
    }
    
    PENDING_APPROVALS[approval_id] = request
    
    # Notify frontend new item in inbox
    await manager.broadcast({
        "type": "inbox_update",
        "data": {"count": len([x for x in PENDING_APPROVALS.values() if x["status"] == "PENDING"])}
    })
    
    return approval_id

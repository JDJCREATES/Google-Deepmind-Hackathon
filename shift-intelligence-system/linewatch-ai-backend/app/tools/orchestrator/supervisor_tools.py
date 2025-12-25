"""
Supervisor coordination tools for Master Orchestrator.

These tools allow the Master Orchestrator to directly influence the physical
supervisor on the factory floor, enabling proactive issue investigation
and verification.
"""
from typing import Dict, Any, Optional
from datetime import datetime

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.utils.logging import get_agent_logger
from app.services.simulation import simulation as sim_service

logger = get_agent_logger("SupervisorTools")


class SupervisorAlertInput(BaseModel):
    """Input schema for alerting supervisor."""
    location_x: int = Field(description="X coordinate to check (0-1200)")
    location_y: int = Field(description="Y coordinate to check (0-500)")
    reason: str = Field(description="Reason for alert/check", min_length=5)
    priority: str = Field(
        default="HIGH",
        description="Priority level (CRITICAL/HIGH/MEDIUM)"
    )


@tool(args_schema=SupervisorAlertInput)
async def alert_supervisor_to_check(
    location_x: int,
    location_y: int,
    reason: str,
    priority: str = "HIGH"
) -> Dict[str, Any]:
    """
    Alert the floor supervisor to physically check a location.
    
    This command overrides the supervisor's default monitoring loop
    and dispatches them to the specified coordinates immediately.
    Use this for:
    - Verifying visual anomalies
    - Checking on specific lines/machines
    - Investigating safety concerns
    - Proactive bottleneck inspection
    
    Args:
        location_x: Target X coordinate
        location_y: Target Y coordinate
        reason: Justification for dispatch
        priority: Request priority
        
    Returns:
        Status dictionary indicating if dispatch met.
    """
    logger.info(f"🚨 Master Agent dispatching Supervisor to ({location_x}, {location_y})")
    
    # Execute dispatch on simulation
    success = sim_service.dispatch_supervisor_to_location(
        target_x=location_x,
        target_y=location_y,
        reason=reason
    )
    
    timestamp = datetime.now().isoformat()
    
    if success:
        return {
            "status": "DISPATCHED",
            "message": f"Supervisor is moving to check {reason}",
            "timestamp": timestamp,
            "target": {"x": location_x, "y": location_y}
        }
    else:
        return {
            "status": "BUSY",
            "message": "Supervisor is currently busy with another task",
            "timestamp": timestamp,
            "current_status": sim_service.supervisor["status"]
        }

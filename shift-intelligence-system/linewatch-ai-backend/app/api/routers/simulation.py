"""
API Router for controlling the background simulation.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.services.simulation import simulation
from app.utils.logging import get_agent_logger

router = APIRouter(prefix="/simulation", tags=["Simulation"])
logger = get_agent_logger("API_Sim")


class SimulationControl(BaseModel):
    action: str  # "start" or "stop"


class ManualEvent(BaseModel):
    event_type: str
    severity: str = "HIGH"
    details: Optional[Dict[str, Any]] = None


@router.post("/start")
async def start_simulation():
    """Start the background simulation loop."""
    if simulation.is_running:
        return {"status": "already_running"}
    
    await simulation.start()
    return {"status": "started"}


@router.post("/stop")
async def stop_simulation():
    """Stop the background simulation loop."""
    if not simulation.is_running:
        return {"status": "not_running"}
    
    await simulation.stop()
    return {"status": "stopped"}


@router.post("/event")
async def inject_event(event: ManualEvent):
    """
    Manually inject an event into the simulation.
    Useful for demos to trigger specific scenarios.
    """
    if not simulation.is_running:
        raise HTTPException(status_code=400, detail="Simulation must be running to inject events")
        
    result = await simulation.inject_event(event.event_type, event.severity)
    return {"status": "injected", "event": result}


@router.get("/status")
async def get_status():
    """Get current simulation status."""
    return {
        "running": simulation.is_running,
        "uptime_minutes": int(simulation.total_uptime_minutes),
        "tick_rate": simulation.tick_rate
    }


@router.get("/layout")
async def get_layout():
    """Get static floor layout configuration."""
    from app.services.layout_service import layout_service
    return layout_service.get_layout()

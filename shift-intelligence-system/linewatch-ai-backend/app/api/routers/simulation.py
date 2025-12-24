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


# =============================================================================
# AI AGENT PRODUCTION CONTROL ENDPOINTS
# =============================================================================

class SetLineProductRequest(BaseModel):
    """Request model for setting a line's product type."""
    line_id: int
    product_type: str


@router.post("/set_line_product")
async def set_line_product(request: SetLineProductRequest):
    """
    AI Agent API: Assign a product type to a production line.
    
    This allows AI agents to dynamically control what each production line manufactures
    based on production targets and scheduling decisions.
    
    Args:
        request.line_id: The production line ID (1-20)
        request.product_type: Product type key (e.g., "widget_a", "gizmo_x")
    
    Returns:
        Status with result or error message
    """
    result = simulation.set_line_product(request.line_id, request.product_type)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/production_schedule")
async def get_production_schedule():
    """
    AI Agent API: Get current production assignments for all lines.
    
    Returns a dict mapping line_id to:
    - product_type: Current product being produced
    - product_name: Human-readable product name
    - is_running: Whether the line is currently active
    - fill_level: Progress towards next large box (0-100%)
    - health: Machine health (0-100%)
    """
    return simulation.get_production_schedule()


@router.get("/warehouse_inventory")
async def get_warehouse_inventory():
    """
    AI Agent API: Get current warehouse inventory by product type.
    
    Returns a dict mapping product_type to count of completed large boxes.
    """
    return simulation.get_warehouse_inventory()


@router.get("/product_catalog")
async def get_product_catalog():
    """
    AI Agent API: Get available product types.
    
    Returns the full product catalog with names, colors, and production parameters.
    """
    return simulation.get_product_catalog()


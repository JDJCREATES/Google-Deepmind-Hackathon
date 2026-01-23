"""
API Router for controlling the background simulation.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.services.simulation import simulation
from app.services.rate_limiter import rate_limiter
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
async def start_simulation(request: Request):
    """Start the background simulation loop. Rate limited: 5 minutes per IP per day."""
    ip = request.client.host
    
    # Check if IP has remaining time
    can_run, remaining = rate_limiter.check_daily_limit(ip)
    if not can_run:
        raise HTTPException(status_code=429, detail="Daily limit exceeded. Try again tomorrow!")
    
    if simulation.is_running:
        return {"status": "already_running", "remaining_seconds": remaining}
    
    # Record session start
    rate_limiter.start_session(ip)
    simulation._current_ip = ip
    
    await simulation.start()
    logger.info(f"Simulation started by {ip} ({remaining}s remaining)")
    
    return {"status": "started", "remaining_seconds": remaining}


@router.post("/stop")
async def stop_simulation():
    """Stop the background simulation loop."""
    if not simulation.is_running:
        return {"status": "not_running"}
    
    await simulation.stop()
    return {"status": "stopped"}


@router.post("/event")
async def inject_event(event: ManualEvent, request: Request):
    """Manually inject an event. Rate limited: 30s cooldown between injections."""
    ip = request.client.host
    
    # Check inject cooldown
    can_inject, cooldown = rate_limiter.check_inject_cooldown(ip)
    if not can_inject:
        raise HTTPException(status_code=429, detail=f"Wait {cooldown}s before injecting again.")
    
    if not simulation.is_running:
        raise HTTPException(status_code=400, detail="Simulation must be running")
    
    rate_limiter.record_inject(ip)
    result = await simulation.inject_event(event.event_type, event.severity)
    logger.info(f"Event '{event.event_type}' injected by {ip}")
    
    return {"status": "injected", "event": result}


@router.get("/status")
async def get_status():
    """Get current simulation status."""
    return {
        "running": simulation.is_running,
        "uptime_minutes": int(simulation.total_uptime_minutes),
        "tick_rate": simulation.tick_rate
    }


@router.get("/usage")
async def get_usage(request: Request):
    """Get rate limit usage stats for the requesting IP. Used by frontend timer."""
    ip = request.client.host
    return rate_limiter.get_usage_stats(ip)


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



# =============================================================================
# AI AGENT SUPERVISOR & FATIGUE ENDPOINTS
# =============================================================================

@router.get("/operator_status")
async def get_operator_status():
    """
    AI Agent API: Get current operator status including fatigue levels.
    
    Returns a list of operators with their current state:
    - id: Operator ID
    - name: Operator name
    - status: Current status (idle, moving, working, on_break, etc.)
    - fatigue: Fatigue level (0-100%)
    - on_break: Whether operator is currently on break
    - break_requested: Whether operator has requested a break
    - x, y: Current position
    """
    return [{
        "id": op["id"],
        "name": op["name"],
        "status": op["status"],
        "current_action": op["current_action"],
        "fatigue": op["fatigue"],
        "on_break": op["on_break"],
        "break_requested": op["break_requested"],
        "x": op["x"],
        "y": op["y"]
    } for op in simulation.operators]


class RequestBreakRequest(BaseModel):
    """Request model for requesting an operator break."""
    operator_id: str


@router.post("/request_break")
async def request_break(request: RequestBreakRequest):
    """
    AI Agent API: Request a break for a specific operator.
    
    The supervisor will be dispatched to relieve the operator if available.
    
    Args:
        operator_id: The ID of the operator who needs a break
    
    Returns:
        Status dict with result or error
    """
    operator = next((op for op in simulation.operators if op["id"] == request.operator_id), None)
    
    if not operator:
        return {"success": False, "error": f"Operator {request.operator_id} not found"}
    
    if operator["on_break"]:
        return {"success": False, "error": f"{operator['name']} is already on break"}
    
    if operator["break_requested"]:
        return {"success": False, "error": f"{operator['name']} has already requested a break"}
    
    # Mark operator as requesting break
    operator["break_requested"] = True
    
    return {
        "success": True,
        "message": f"Break requested for {operator['name']}. Supervisor will be dispatched.",
        "operator": {
            "id": operator["id"],
            "name": operator["name"],
            "fatigue": operator["fatigue"]
        }
    }


@router.get("/supervisor_status")
async def get_supervisor_status():
    """
    AI Agent API: Get current supervisor status.
    
    Returns supervisor state including:
    - status: Current status (idle, moving_to_operator, relieving, returning)
    - current_action: Description of current action
    - assigned_operator_id: ID of operator being relieved (if any)
    - x, y: Current position
    """
    return {
        "id": simulation.supervisor["id"],
        "name": simulation.supervisor["name"],
        "status": simulation.supervisor["status"],
        "current_action": simulation.supervisor["current_action"],
        "assigned_operator_id": simulation.supervisor["assigned_operator_id"],
        "x": simulation.supervisor["x"],
        "y": simulation.supervisor["y"]
    }

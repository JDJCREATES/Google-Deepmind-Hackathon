"""
Maintenance Dispatch Tools.

Tools for the Maintenance Agent to dispatch crews to fix equipment.
"""
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from app.services.simulation import simulation
from app.utils.logging import get_agent_logger

logger = get_agent_logger("MaintenanceTools")

class DispatchCrewInput(BaseModel):
    """Input for dispatching maintenance crew."""
    machine_id: int = Field(description="ID of the machine to repair (e.g., 1, 2, 3)")
    priority: str = Field(description="Priority of the repair (LOW, MEDIUM, HIGH, CRITICAL)", default="HIGH")

@tool("dispatch_maintenance_crew", args_schema=DispatchCrewInput)
def dispatch_maintenance_crew(machine_id: int, priority: str = "HIGH") -> str:
    """
    Dispatch the maintenance crew to a specific machine to fix a breakdown.
    
    This command sends the physical crew to the machine's location.
    The crew will:
    1. Travel to the machine (takes time)
    2. Perform repairs (takes 5s)
    3. Return to base
    
    Use this when a failure is detected by sensors or visual inspection.
    """
    logger.info(f"🔧 Maintenance Agent requesting crew dispatch to Line {machine_id} ({priority})")
    
    success = simulation.dispatch_maintenance_crew(machine_id)
    
    if success:
        return f"SUCCESS: Maintenance Crew dispatched to Line {machine_id}. ETA 10-20s."
    else:
        return f"FAILURE: Could not dispatch crew to Line {machine_id}. Crew may be busy or machine ID invalid."

"""
Production control tools for LineWatch AI.

This module provides tools for the Production Agent to actively control
production line parameters (speed, product mix, etc.).
"""
from typing import Dict, Any
from datetime import datetime

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.utils.logging import get_agent_logger

logger = get_agent_logger("ProductionControlTools")

class SetSpeedInput(BaseModel):
    """Input schema for setting production line speed."""
    line_number: int = Field(description="Production line number (1-20)", ge=1, le=20)
    speed_percent: float = Field(
        description="Target speed percentage (0-200). >100 increases risk.", 
        ge=0.0, 
        le=200.0
    )
    reason: str = Field(description="Reason for speed change", min_length=5)


@tool(args_schema=SetSpeedInput)
async def set_production_speed(
    line_number: int, 
    speed_percent: float,
    reason: str
) -> Dict[str, Any]:
    """
    Set target production speed for a specific line.
    
    Control lever to balance Throughput (OEE) vs Risk (Safety/Health).
    - 100%: Normal operation.
    - >100%: Increases Output but exponentially increases Degradation & Safety Risk.
    - <100%: Safer, extends machine life, but lowers OEE.
    - 0%: Stops the line.
    
    Args:
        line_number: Line to control (1-20)
        speed_percent: Target percentage (0-200)
        reason: Justification for the change
        
    Returns:
        Status dictionary
    """
    logger.info(f"⚙️ Setting Line {line_number} speed to {speed_percent}% ({reason})")
    
    try:
        from app.services.simulation import simulation
        
        success = simulation.set_line_speed(line_number, speed_percent)
        
        if success:
            return {
                "status": "SUCCESS",
                "line_number": line_number,
                "new_speed_percent": speed_percent,
                "timestamp": datetime.now().isoformat(),
                "note": "Speed updated. Monitor for health impact if >100%."
            }
        else:
             return {
                "status": "FAILED",
                "reason": "Simulation refused update (invalid line or state)"
            }
            
    except Exception as e:
        logger.error(f"❌ Error setting speed for Line {line_number}: {e}")
        return {"status": "ERROR", "error": str(e)}

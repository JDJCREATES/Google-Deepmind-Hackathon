"""
Maintenance monitoring and scheduling tools for LineWatch AI.

This module provides tools for the Maintenance Agent to monitor equipment health,
schedule preventive maintenance, and create work orders.
"""
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.state.context import shared_context
from app.models.domain import Alert, AlertSeverity
from app.utils.logging import get_agent_logger


logger = get_agent_logger("MaintenanceTools")


# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class MaintenanceScheduleInput(BaseModel):
    """Input schema for scheduling maintenance."""
    line_number: int = Field(description="Line number", ge=1, le=20)
    window_description: str = Field(description="Maintenance window (e.g., '2hr', 'shift_change')")


class WorkOrderInput(BaseModel):
    """Input schema for creating work orders."""
    line_number: int = Field(description="Line number", ge=1, le=20)
    issue: str = Field(description="Issue description", min_length=10)
    priority: str = Field(description="CRITICAL/HIGH/MEDIUM/LOW")


# ============================================================================
# MAINTENANCE TOOLS
# ============================================================================

@tool
async def check_all_equipment_health() -> Dict[str, Any]:
    """Get equipment health scores for all 20 production lines."""
    logger.info("🔧 Checking equipment health for all lines")
    
    try:
        department = await shared_context.get_department()
        
        health_report = {
            "timestamp": datetime.now().isoformat(),
            "critical_lines": [],  # Health < 30
            "degraded_lines": [],  # Health < 60
            "healthy_lines": [],   # Health >= 60
            "average_health": 0.0,
        }
        
        total_health = 0.0
        
        for line_num in range(1, 21):
            line = department.get_line(line_num)
            if not line:
                continue
            
            health = line.health_score
            total_health += health
            
            line_data = {
                "line": line_num,
                "health": health,
                "status": line.status.value,
            }
            
            if health < 30:
                health_report["critical_lines"].append(line_data)
            elif health < 60:
                health_report["degraded_lines"].append(line_data)
            else:
                health_report["healthy_lines"].append(line_data)
        
        health_report["average_health"] = round(total_health / 20, 2)
        
        logger.info(
            f"✅ Health check: {len(health_report['critical_lines'])} critical, "
            f"avg health {health_report['average_health']:.1f}"
        )
        
        return health_report
        
    except Exception as e:
        logger.error(f"❌ Error checking equipment health: {e}")
        raise


@tool(args_schema=MaintenanceScheduleInput)
async def schedule_maintenance(
    line_number: int,
    window_description: str
) -> Dict[str, Any]:
    """Schedule maintenance for a production line."""
    logger.info(f"📅 Scheduling maintenance for Line {line_number}")
    
    try:
        # Parse window (simplified)
        if "2hr" in window_description or "2 hour" in window_description:
            scheduled_time = datetime.now() + timedelta(hours=2)
            duration_hours = 2
        elif "shift" in window_description:
            scheduled_time = datetime.now() + timedelta(hours=4)
            duration_hours = 1
        else:
            scheduled_time = datetime.now() + timedelta(hours=1)
            duration_hours = 1
        
        result = {
            "line_number": line_number,
            "scheduled_start": scheduled_time.isoformat(),
            "scheduled_end": (scheduled_time + timedelta(hours=duration_hours)).isoformat(),
            "duration_hours": duration_hours,
            "window": window_description,
            "status": "SCHEDULED",
        }
        
        logger.info(f"✅ Maintenance scheduled for Line {line_number}: {scheduled_time}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error scheduling maintenance: {e}")
        raise


@tool(args_schema=WorkOrderInput)
async def create_work_order(
    line_number: int,
    issue: str,
    priority: str
) -> Dict[str, Any]:
    """Create work order for maintenance technicians."""
    logger.info(f"📋 Creating {priority} work order for Line {line_number}")
    
    try:
        work_order = {
            "work_order_id": f"WO-{line_number}-{int(datetime.now().timestamp())}",
            "line_number": line_number,
            "issue": issue,
            "priority": priority,
            "created_at": datetime.now().isoformat(),
            "status": "OPEN",
            "assigned_technician": None,
        }
        
        logger.info(f"✅ Work order created: {work_order['work_order_id']}")
        
        return work_order
        
    except Exception as e:
        logger.error(f"❌ Error creating work order: {e}")
        raise

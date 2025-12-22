"""
Vision integration tools for staffing - alerts and monitoring.

This module connects the Staffing Agent to the vision system
for real-time workforce visibility and alert handling.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.state.context import shared_context
from app.services.vision_service import vision_service
from app.utils.logging import get_agent_logger


logger = get_agent_logger("StaffingVisionTools")


# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class AcknowledgeAlertInput(BaseModel):
    """Input schema for acknowledging vision alerts."""
    alert_id: str = Field(description="Alert ID to acknowledge")
    action_taken: str = Field(description="What was done to address alert")


# ============================================================================
# VISION TOOLS FOR STAFFING
# ============================================================================

@tool
async def get_recent_vision_alerts(
    minutes: int = 30,
    line_filter: Optional[int] = None
) -> Dict[str, Any]:
    """
    Get recent alerts from the vision system relevant to staffing.
    
    Retrieves:
    - Empty station alerts (no operator at line)
    - PPE violations (staffing should address)
    - Unauthorized area access
    - Fatigue indicators (slowed movement patterns)
    
    Args:
        minutes: Look back window (default 30)
        line_filter: Optional - filter by line number
        
    Returns:
        List of vision alerts with staffing relevance
    """
    logger.info(f"👁️ Getting vision alerts for staffing (last {minutes}min)")
    
    try:
        violations = await shared_context.safety_violations
        
        # Filter by time
        cutoff = datetime.now() - timedelta(minutes=minutes)
        recent = [
            v for v in violations.values()
            if v.detected_at > cutoff
        ]
        
        # Filter by line if specified
        if line_filter:
            recent = [v for v in recent if line_filter in v.affected_lines]
        
        # Categorize for staffing relevance
        staffing_relevant = {
            "empty_stations": [],
            "ppe_violations": [],
            "fatigue_indicators": [],
            "unauthorized_access": [],
            "other": [],
        }
        
        for v in recent:
            if "empty" in v.violation_type.value.lower() or "unmanned" in v.description.lower():
                staffing_relevant["empty_stations"].append({
                    "violation_id": v.violation_id,
                    "line": v.affected_lines[0] if v.affected_lines else None,
                    "detected_at": v.detected_at.isoformat(),
                    "description": v.description,
                })
            elif "ppe" in v.violation_type.value.lower():
                staffing_relevant["ppe_violations"].append({
                    "violation_id": v.violation_id,
                    "line": v.affected_lines[0] if v.affected_lines else None,
                    "detected_at": v.detected_at.isoformat(),
                    "description": v.description,
                })
            elif "fatigue" in v.description.lower() or "slow" in v.description.lower():
                staffing_relevant["fatigue_indicators"].append({
                    "violation_id": v.violation_id,
                    "line": v.affected_lines[0] if v.affected_lines else None,
                    "detected_at": v.detected_at.isoformat(),
                    "description": v.description,
                })
            elif "unauthorized" in v.description.lower():
                staffing_relevant["unauthorized_access"].append({
                    "violation_id": v.violation_id,
                    "detected_at": v.detected_at.isoformat(),
                    "description": v.description,
                })
            else:
                staffing_relevant["other"].append({
                    "violation_id": v.violation_id,
                    "detected_at": v.detected_at.isoformat(),
                    "description": v.description,
                })
        
        total = sum(len(v) for v in staffing_relevant.values())
        
        logger.info(f"✅ Found {total} staffing-relevant alerts")
        
        return {
            "timestamp": datetime.now().isoformat(),
            "lookback_minutes": minutes,
            "total_alerts": total,
            "alerts": staffing_relevant,
            "action_needed": (
                len(staffing_relevant["empty_stations"]) > 0 or
                len(staffing_relevant["ppe_violations"]) > 0
            ),
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting vision alerts: {e}")
        raise


@tool
async def get_all_lines_occupancy() -> Dict[str, Any]:
    """
    Get visual occupancy count for all production lines.
    
    Uses camera system to verify actual staff presence vs assigned.
    Essential for identifying coverage gaps.
    
    Returns:
        Occupancy by line with gap analysis
    """
    logger.info("👀 Getting occupancy for all lines")
    
    try:
        department = await shared_context.get_department()
        employees = await shared_context.employees
        
        occupancy = {
            "timestamp": datetime.now().isoformat(),
            "lines": {},
            "understaffed_lines": [],
            "overstaffed_lines": [],
            "optimal_lines": [],
        }
        
        for line_num in range(1, 21):
            line = department.get_line(line_num)
            if not line:
                continue
            
            # Get visual count
            visual = await vision_service.get_line_occupancy(line_num)
            
            # Get assigned count
            assigned = len([
                e for e in employees.values()
                if e.assigned_line == line_num and not e.on_break
            ])
            
            # Optimal is 3 operators per line (5 lines = 20 lines / 4 = 5 main operators needed)
            optimal = 3  # 3 operators optimal per line
            minimum = 2  # 2 minimum
            
            status = "OPTIMAL"
            if visual < minimum:
                status = "CRITICAL"
                occupancy["understaffed_lines"].append(line_num)
            elif visual < optimal:
                status = "SUBOPTIMAL"
            elif visual > optimal + 1:
                status = "OVERSTAFFED"
                occupancy["overstaffed_lines"].append(line_num)
            else:
                occupancy["optimal_lines"].append(line_num)
            
            occupancy["lines"][str(line_num)] = {
                "visual_count": visual,
                "assigned_count": assigned,
                "optimal_count": optimal,
                "minimum_count": minimum,
                "status": status,
                "gap": assigned - visual,  # Positive = people missing from station
            }
        
        logger.info(
            f"✅ Occupancy: {len(occupancy['understaffed_lines'])} understaffed, "
            f"{len(occupancy['optimal_lines'])} optimal"
        )
        
        return occupancy
        
    except Exception as e:
        logger.error(f"❌ Error getting occupancy: {e}")
        raise


@tool(args_schema=AcknowledgeAlertInput)
async def acknowledge_vision_alert(
    alert_id: str,
    action_taken: str
) -> Dict[str, Any]:
    """
    Acknowledge and document action taken for a vision alert.
    
    Args:
        alert_id: The alert to acknowledge
        action_taken: Description of response action
        
    Returns:
        Confirmation of acknowledgment
    """
    logger.info(f"✅ Acknowledging alert {alert_id}")
    
    try:
        violations = await shared_context.safety_violations
        
        if alert_id in violations:
            violation = violations[alert_id]
            violation.resolved = True
            violation.resolution_notes = action_taken
            
            return {
                "status": "SUCCESS",
                "alert_id": alert_id,
                "acknowledged_at": datetime.now().isoformat(),
                "action_taken": action_taken,
            }
        
        return {
            "status": "NOT_FOUND",
            "alert_id": alert_id,
            "message": "Alert not found",
        }
        
    except Exception as e:
        logger.error(f"❌ Error acknowledging alert: {e}")
        raise

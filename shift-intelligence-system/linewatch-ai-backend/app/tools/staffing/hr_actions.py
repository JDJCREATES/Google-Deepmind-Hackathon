"""
HR action tools for LineWatch AI - Write-ups, rewards, and performance management.

This module provides tools for the Staffing Agent to manage employee
performance through rewards, reprimands, and escalation to human supervisors.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.state.context import shared_context
from app.models.domain import Alert, AlertSeverity
from app.utils.logging import get_agent_logger


logger = get_agent_logger("HRActionTools")


# ============================================================================
# ENUMS AND SCHEMAS
# ============================================================================

class ActionType(str, Enum):
    """Types of HR actions."""
    VERBAL_WARNING = "verbal_warning"
    WRITTEN_WARNING = "written_warning"
    FINAL_WARNING = "final_warning"
    BONUS_POINTS = "bonus_points"
    RECOGNITION = "recognition"
    COACHING = "coaching"


class ActionSeverity(str, Enum):
    """Severity of HR action."""
    LOW = "low"        # Coaching/verbal
    MEDIUM = "medium"  # Written warning
    HIGH = "high"      # Final warning - requires human
    CRITICAL = "critical"  # Termination consideration - requires human


class WriteUpInput(BaseModel):
    """Input schema for issuing write-up/reprimand."""
    employee_id: str = Field(description="Employee identifier")
    action_type: str = Field(
        description="Type: verbal_warning, written_warning, final_warning, coaching"
    )
    reason: str = Field(description="Detailed reason for action", min_length=20)
    violation_category: str = Field(
        description="Category: attendance, performance, safety, conduct"
    )


class RewardInput(BaseModel):
    """Input schema for issuing reward/bonus points."""
    employee_id: str = Field(description="Employee identifier")
    points: int = Field(description="Bonus points to award", ge=1, le=100)
    reason: str = Field(description="Reason for reward", min_length=10)
    category: str = Field(
        description="Category: productivity, safety, teamwork, initiative"
    )


class HumanEscalationInput(BaseModel):
    """Input schema for human escalation."""
    title: str = Field(description="Brief title", min_length=10)
    description: str = Field(description="Detailed description", min_length=30)
    priority: str = Field(description="Priority: low, medium, high, critical")
    requires_decision: bool = Field(
        description="True if human decision required before proceeding"
    )


# ============================================================================
# HR ACTION HISTORY (In-memory store)
# ============================================================================

_hr_action_history: List[Dict] = []
_reward_history: List[Dict] = []
_escalation_queue: List[Dict] = []


# ============================================================================
# HR TOOLS
# ============================================================================

@tool(args_schema=WriteUpInput)
async def issue_write_up(
    employee_id: str,
    action_type: str,
    reason: str,
    violation_category: str
) -> Dict[str, Any]:
    """
    Issue a write-up or reprimand to an employee.
    
    Low-severity actions (verbal warning, coaching) are autonomous.
    High-severity actions (written warning, final warning) require
    human supervisor approval.
    
    Args:
        employee_id: Employee to write up
        action_type: Type of disciplinary action
        reason: Detailed reason/documentation
        violation_category: attendance, performance, safety, conduct
        
    Returns:
        Action confirmation with approval status
    """
    logger.warning(f"📝 Issuing {action_type} to {employee_id}")
    
    try:
        employees = await shared_context.employees
        employee = employees.get(employee_id)
        
        if not employee:
            raise ValueError(f"Employee {employee_id} not found")
        
        # Determine if human approval needed
        requires_human = action_type in ["written_warning", "final_warning"]
        
        action = {
            "action_id": f"WU-{int(datetime.now().timestamp())}",
            "employee_id": employee_id,
            "employee_name": employee.name,
            "action_type": action_type,
            "violation_category": violation_category,
            "reason": reason,
            "issued_at": datetime.now().isoformat(),
            "requires_human_approval": requires_human,
            "status": "PENDING_APPROVAL" if requires_human else "APPLIED",
            "approved_by": None if requires_human else "StaffingAgent",
        }
        
        _hr_action_history.append(action)
        
        # If requires human, add to escalation queue
        if requires_human:
            await escalate_to_human_supervisor(
                title=f"{action_type.replace('_', ' ').title()} - {employee.name}",
                description=f"Reason: {reason}\n\nEmployee: {employee.name} ({employee_id})",
                priority="high" if action_type == "final_warning" else "medium",
                requires_decision=True,
            )
            logger.info(f"⚠️ Escalated to human supervisor for approval")
        else:
            logger.info(f"✅ {action_type} applied autonomously")
        
        return {
            "status": "SUCCESS",
            "action": action,
            "requires_human_approval": requires_human,
            "message": (
                "Action queued for human approval" if requires_human
                else "Action applied successfully"
            ),
        }
        
    except Exception as e:
        logger.error(f"❌ Error issuing write-up: {e}")
        raise


@tool(args_schema=RewardInput)
async def award_bonus_points(
    employee_id: str,
    points: int,
    reason: str,
    category: str
) -> Dict[str, Any]:
    """
    Award bonus points or recognition to an employee.
    
    Recognizes positive performance behaviors. All rewards are
    applied autonomously (no human approval needed).
    
    Args:
        employee_id: Employee to reward
        points: Bonus points (1-100)
        reason: Reason for recognition
        category: productivity, safety, teamwork, initiative
        
    Returns:
        Reward confirmation
    """
    logger.info(f"🏆 Awarding {points} points to {employee_id}")
    
    try:
        employees = await shared_context.employees
        employee = employees.get(employee_id)
        
        if not employee:
            raise ValueError(f"Employee {employee_id} not found")
        
        reward = {
            "reward_id": f"RW-{int(datetime.now().timestamp())}",
            "employee_id": employee_id,
            "employee_name": employee.name,
            "points": points,
            "category": category,
            "reason": reason,
            "awarded_at": datetime.now().isoformat(),
            "awarded_by": "StaffingAgent",
        }
        
        _reward_history.append(reward)
        
        logger.info(f"✅ {points} bonus points awarded to {employee.name}")
        
        return {
            "status": "SUCCESS",
            "reward": reward,
            "message": f"Awarded {points} points for {category}",
            "total_session_points": sum(
                r["points"] for r in _reward_history
                if r["employee_id"] == employee_id
            ),
        }
        
    except Exception as e:
        logger.error(f"❌ Error awarding points: {e}")
        raise


@tool(args_schema=HumanEscalationInput)
async def escalate_to_human_supervisor(
    title: str,
    description: str,
    priority: str,
    requires_decision: bool
) -> Dict[str, Any]:
    """
    Escalate an issue to the human shift supervisor.
    
    Use when:
    - High-severity HR actions need approval
    - Complex staffing decisions beyond AI authority
    - Safety concerns requiring human judgment
    - Labor regulation edge cases
    
    This is THE primary human-in-the-loop mechanism.
    
    Args:
        title: Brief title for escalation
        description: Detailed context for decision
        priority: low, medium, high, critical
        requires_decision: If True, system pauses for approval
        
    Returns:
        Escalation ticket with tracking ID
    """
    logger.warning(f"⬆️ ESCALATING TO HUMAN: {title}")
    
    try:
        severity_map = {
            "low": AlertSeverity.LOW,
            "medium": AlertSeverity.MEDIUM,
            "high": AlertSeverity.HIGH,
            "critical": AlertSeverity.CRITICAL,
        }
        
        escalation = {
            "escalation_id": f"ESC-{int(datetime.now().timestamp())}",
            "title": title,
            "description": description,
            "priority": priority,
            "requires_decision": requires_decision,
            "created_at": datetime.now().isoformat(),
            "status": "PENDING",
            "assigned_to": "Shift Supervisor",
            "estimated_response_time": (
                "< 5 min" if priority == "critical"
                else "< 15 min" if priority == "high"
                else "< 30 min" if priority == "medium"
                else "< 60 min"
            ),
        }
        
        _escalation_queue.append(escalation)
        
        # Also create alert
        alert = Alert(
            alert_id=escalation["escalation_id"],
            timestamp=datetime.now(),
            severity=severity_map.get(priority, AlertSeverity.MEDIUM),
            source="StaffingAgent",
            title=title,
            description=description,
            line_number=None,
            resolved=False,
        )
        await shared_context.add_alert(alert)
        
        logger.warning(
            f"⬆️ Escalation {escalation['escalation_id']} created "
            f"(Priority: {priority})"
        )
        
        return {
            "status": "ESCALATED",
            "escalation": escalation,
            "message": (
                "Waiting for human decision" if requires_decision
                else "Human notified - proceeding with default"
            ),
        }
        
    except Exception as e:
        logger.error(f"❌ Error escalating: {e}")
        raise


@tool
async def get_hr_action_history(employee_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get history of HR actions (write-ups and rewards).
    
    Args:
        employee_id: Optional - filter by employee
        
    Returns:
        Action history with counts
    """
    logger.info(f"📋 Retrieving HR action history")
    
    if employee_id:
        write_ups = [a for a in _hr_action_history if a["employee_id"] == employee_id]
        rewards = [r for r in _reward_history if r["employee_id"] == employee_id]
    else:
        write_ups = _hr_action_history
        rewards = _reward_history
    
    return {
        "timestamp": datetime.now().isoformat(),
        "write_ups": write_ups,
        "write_up_count": len(write_ups),
        "rewards": rewards,
        "reward_count": len(rewards),
        "total_points_awarded": sum(r["points"] for r in rewards),
        "pending_escalations": [e for e in _escalation_queue if e["status"] == "PENDING"],
    }


@tool
async def get_pending_escalations() -> Dict[str, Any]:
    """
    Get all pending human escalations requiring attention.
    
    Returns:
        List of pending escalations with details
    """
    logger.info("📋 Getting pending escalations")
    
    pending = [e for e in _escalation_queue if e["status"] == "PENDING"]
    
    return {
        "timestamp": datetime.now().isoformat(),
        "pending_count": len(pending),
        "escalations": pending,
        "critical_count": sum(1 for e in pending if e["priority"] == "critical"),
        "high_count": sum(1 for e in pending if e["priority"] == "high"),
    }

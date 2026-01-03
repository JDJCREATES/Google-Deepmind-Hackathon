"""
Master Orchestrator coordination tools for LineWatch AI.

This module provides tools for the Master Orchestrator to coordinate all specialized
agents, handle esscalations, and make final decisions.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.state.context import shared_context
from app.models.domain import Alert, AlertSeverity, Decision
from app.utils.logging import get_agent_logger


logger = get_agent_logger("OrchestratorTools")


# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class EscalationInput(BaseModel):
    """Input schema for escalations to human."""
    alert_title: str = Field(description="Alert title", min_length=10)
    description: str = Field(description="Detailed description", min_length=20)
    severity: str = Field(description="CRITICAL/HIGH/MEDIUM", pattern="^(CRITICAL|HIGH|MEDIUM)$")


class ShiftPlanInput(BaseModel):
    """Input schema for shift plan updates."""
    target_adjustment: float = Field(description="Throughput target adjustment percentage")
    reason: str = Field(description="Reason for adjustment", min_length=10)


# ============================================================================
# ORCHESTRATOR TOOLS
# ============================================================================

@tool(args_schema=EscalationInput)
async def escalate_to_human(
    alert_title: str,
    description: str,
    severity: str
) -> Dict[str, Any]:
    """
    Escalate issue to human supervisor with context.
    
    Creates high-priority alert that notifies human operators when
    AI agents cannot resolve situation autonomously.
    
    Args:
        alert_title: Brief title describing issue
        description: Detailed context and reasoning
        severity: CRITICAL, HIGH, or MEDIUM
        
    Returns:
        Dictionary with escalation confirmation
    """
    logger.warning(f"⬆️ ESCALATING TO HUMAN: {alert_title}")
    
    try:
        severity_map = {
            "CRITICAL": AlertSeverity.CRITICAL,
            "HIGH": AlertSeverity.HIGH,
            "MEDIUM": AlertSeverity.MEDIUM,
        }
        
        alert = Alert(
            alert_id=f"ESCALATION-{int(datetime.now().timestamp())}",
            timestamp=datetime.now(),
            severity=severity_map[severity],
            source="MasterOrchestrator",
            title=alert_title,
            description=description,
            line_number=None,
            resolved=False,
        )
        
        await shared_context.add_alert(alert)
        
        # In production: send SMS, email, page supervisor
        
        result = {
            "escalation_id": alert.alert_id,
            "severity": severity,
            "title": alert_title,
            "escalated_at": alert.timestamp.isoformat(),
            "notification_sent": True,
            "expected_response_time": "< 5 minutes" if severity == "CRITICAL" else "< 15 minutes",
        }
        
        logger.warning(f"⬆️ Escalation {alert.alert_id} created")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error escalating to human: {e}")
        raise


@tool(args_schema=ShiftPlanInput)
async def update_shift_plan(
    target_adjustment: float,
    reason: str
) -> Dict[str, Any]:
    """
    Update shift production targets based on situation.
    
    Adjusts overall production targets when agents determine current
    targets are unattainable or conditions have changed.
    
    Args:
        target_adjustment: Percentage adjustment (-50 to +20)
        reason: Reason for adjustment
        
    Returns:
        Dictionary with updated plan
    """
    logger.info(f"📊 Updating shift plan: {target_adjustment:+.1f}%")
    
    try:
        department = await shared_context.get_department()
        
        # Calculate new targets
        new_targets = {}
        for line_num in range(1, 21):
            line = department.get_line(line_num)
            if line:
                current_target = line.target_throughput
                new_target = current_target * (1 + target_adjustment / 100)
                new_targets[line_num] = round(new_target, 2)
                line.target_throughput = new_target
        
        result = {
            "adjustment_percent": target_adjustment,
            "reason": reason,
            "applied_at": datetime.now().isoformat(),
            "new_targets": new_targets,
            "total_target": sum(new_targets.values()),
        }
        
        logger.info(f"✅ Shift plan updated: {target_adjustment:+.1f}%")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error updating shift plan: {e}")
        raise


@tool
async def get_all_agent_status() -> Dict[str, Any]:
    """Get status summary from all specialized agents."""
    logger.info("📊 Getting status from all agents")
    
    try:
        # Get recent decisions from all agents
        decisions = shared_context.decisions
        
        agent_status = {
            "timestamp": datetime.now().isoformat(),
            "agents": {},
        }
        
        # Group by agent
        for decision in decisions[-50:]:  # Last 50 decisions
            agent_name = decision.agent_name
            if agent_name not in agent_status["agents"]:
                agent_status["agents"][agent_name] = {
                    "decision_count": 0,
                    "escalations": 0,
                    "avg_confidence": 0.0,
                    "recent_decisions": [],
                }
            
            agent_status["agents"][agent_name]["decision_count"] += 1
            if decision.escalated:
                agent_status["agents"][agent_name]["escalations"] += 1
            
            agent_status["agents"][agent_name]["recent_decisions"].append({
                "decision": decision.decision,
                "confidence": decision.confidence,
                "timestamp": decision.timestamp.isoformat(),
            })
        
        logger.info(f"✅ Agent status retrieved: {len(agent_status['agents'])} agents active")
        
        return agent_status
        
    except Exception as e:
        logger.error(f"❌ Error getting agent status: {e}")
        raise


@tool
async def read_kpis() -> Dict[str, Any]:
    """
    Read current Key Performance Indicators (OEE, Safety, Finance).
    
    Use this to assess long-term success and determine if strategic changes
    are needed (e.g. slowing down for safety or speeding up for OEE).
    
    Returns:
        Dictionary containing OEE, Safety Score, Balance, etc.
    """
    try:
        # Import inside function to avoid circular imports
        from app.services.simulation import simulation
        
        kpi = simulation.kpi
        fin = simulation.financials
        
        return {
            "oee": kpi.oee,
            "oee_percent": f"{kpi.oee*100:.1f}%",
            "safety_score": kpi.safety_score,
            "availability": kpi.availability,
            "performance": kpi.performance,
            "financials": {
                "balance": fin.balance,
                "revenue": fin.total_revenue,
                "expenses": fin.total_expenses,
                "burn_rate": fin.hourly_wage_cost
            }
        }
    except Exception as e:
        logger.error(f"❌ Error reading KPIs: {e}")
        return {"error": str(e)}

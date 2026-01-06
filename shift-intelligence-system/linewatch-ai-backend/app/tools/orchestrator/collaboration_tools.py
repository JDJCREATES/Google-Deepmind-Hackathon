"""
Agent collaboration tools for inter-agent communication and conflict resolution.

These tools enable agents to discuss trade-offs, request opinions from other agents,
and have the Orchestrator resolve conflicts with visible reasoning.
"""
from typing import Dict, Any, List, Optional
from langchain.tools import tool
from datetime import datetime
import asyncio


# Store for active debates/discussions
_active_debates: List[Dict] = []


@tool
async def request_agent_perspective(
    target_agent: str,
    proposed_action: str,
    context: str,
    requesting_agent: str
) -> Dict[str, Any]:
    """
    Request another agent's perspective on a proposed action.
    
    Use this when you want to understand potential impacts on other domains
    before making a decision.
    
    Args:
        target_agent: Which agent to ask (production, compliance, staffing, maintenance)
        proposed_action: What action you're considering
        context: Relevant context for the decision
        requesting_agent: Your agent name (for attribution)
    
    Example:
        request_agent_perspective(
            "compliance",
            "Increase line speed by 15%",
            "Current production behind target by 200 units",
            "production"
        )
    """
    from app.services.websocket import manager
    
    # Create perspective request
    request_id = f"REQ-{datetime.now().strftime('%H%M%S')}"
    
    perspective_request = {
        "id": request_id,
        "from_agent": requesting_agent,
        "to_agent": target_agent,
        "proposed_action": proposed_action,
        "context": context,
        "timestamp": datetime.now().isoformat(),
        "status": "pending"
    }
    
    # Broadcast for UI visualization
    await manager.broadcast({
        "type": "agent_collaboration",
        "data": {
            "event": "perspective_requested",
            "request": perspective_request
        }
    })
    
    # Generate simulated response based on target agent domain
    response = _generate_agent_perspective(target_agent, proposed_action, context)
    
    perspective_request["status"] = "responded"
    perspective_request["response"] = response
    
    # Broadcast response
    await manager.broadcast({
        "type": "agent_collaboration",
        "data": {
            "event": "perspective_received",
            "request": perspective_request
        }
    })
    
    return {
        "request_id": request_id,
        "target_agent": target_agent,
        "perspective": response["analysis"],
        "recommendation": response["recommendation"],
        "risk_level": response["risk_level"],
        "estimated_impact": response["estimated_impact"]
    }


def _generate_agent_perspective(target_agent: str, action: str, context: str) -> Dict:
    """Generate domain-specific perspective on proposed action."""
    
    action_lower = action.lower()
    
    if target_agent == "compliance":
        # Compliance focuses on safety and quality risks
        if "speed" in action_lower or "increase" in action_lower:
            return {
                "analysis": f"Increasing speed typically correlates with 20-40% higher defect rates. Current quality metrics show 2.3% defect rate - speed increase could push this to 3.5%+.",
                "recommendation": "CAUTION - Monitor quality closely if proceeding",
                "risk_level": "medium",
                "estimated_impact": {"defect_increase": "40%", "cost": "$2,500/hour in waste"}
            }
        elif "reduce" in action_lower or "slow" in action_lower:
            return {
                "analysis": "Reducing speed generally improves quality metrics and reduces safety incidents.",
                "recommendation": "APPROVE - Quality improvement expected",
                "risk_level": "low",
                "estimated_impact": {"defect_reduction": "15%", "savings": "$500/hour"}
            }
        else:
            return {
                "analysis": f"Reviewing action: {action}. No significant compliance concerns identified.",
                "recommendation": "NEUTRAL - Monitor as needed",
                "risk_level": "low",
                "estimated_impact": {}
            }
    
    elif target_agent == "production":
        # Production focuses on throughput and efficiency
        if "maintenance" in action_lower or "stop" in action_lower:
            return {
                "analysis": f"Stopping line for maintenance will reduce daily output by ~200 units. Current backlog is 500 units.",
                "recommendation": "DELAY - Wait for scheduled window if possible",
                "risk_level": "medium",
                "estimated_impact": {"production_loss": "200 units", "revenue_impact": "-$4,000"}
            }
        else:
            return {
                "analysis": f"Evaluating impact on production efficiency for: {action}",
                "recommendation": "APPROVE - Minimal production impact",
                "risk_level": "low",
                "estimated_impact": {}
            }
    
    elif target_agent == "staffing":
        return {
            "analysis": f"Staffing impact assessment for: {action}. Current shift has 18 operators active.",
            "recommendation": "Staffing can accommodate requested action",
            "risk_level": "low",
            "estimated_impact": {"overtime_needed": "none"}
        }
    
    elif target_agent == "maintenance":
        return {
            "analysis": f"Equipment impact assessment for: {action}. Current equipment health avg: 78%.",
            "recommendation": "Equipment can support requested action",
            "risk_level": "low",
            "estimated_impact": {"wear_increase": "5%"}
        }
    
    return {
        "analysis": "Unable to assess",
        "recommendation": "ESCALATE",
        "risk_level": "unknown",
        "estimated_impact": {}
    }


@tool
async def escalate_tradeoff_decision(
    situation: str,
    agent_perspectives: List[Dict],
    urgency: str = "normal"
) -> Dict[str, Any]:
    """
    Escalate a trade-off decision to the Master Orchestrator for resolution.
    
    Use when multiple agents have conflicting recommendations.
    
    Args:
        situation: Description of the trade-off situation
        agent_perspectives: List of {agent, recommendation, reasoning} from consulted agents
        urgency: 'low', 'normal', 'high', or 'critical'
    """
    from app.services.websocket import manager
    
    decision_id = f"DECISION-{datetime.now().strftime('%H%M%S')}"
    
    # Broadcast debate for visualization
    await manager.broadcast({
        "type": "agent_collaboration",
        "data": {
            "event": "tradeoff_escalated",
            "decision_id": decision_id,
            "situation": situation,
            "perspectives": agent_perspectives,
            "urgency": urgency
        }
    })
    
    # Orchestrator resolution (simulated reasoning)
    resolution = _resolve_tradeoff(situation, agent_perspectives)
    
    # Broadcast resolution
    await manager.broadcast({
        "type": "agent_collaboration",
        "data": {
            "event": "tradeoff_resolved",
            "decision_id": decision_id,
            "resolution": resolution
        }
    })
    
    return {
        "decision_id": decision_id,
        "resolved_by": "MasterOrchestrator",
        "decision": resolution["decision"],
        "reasoning": resolution["reasoning"],
        "action_taken": resolution["action"]
    }


def _resolve_tradeoff(situation: str, perspectives: List[Dict]) -> Dict:
    """Orchestrator resolution logic for trade-offs."""
    
    # Count recommendations
    approvals = sum(1 for p in perspectives if "APPROVE" in p.get("recommendation", ""))
    cautions = sum(1 for p in perspectives if "CAUTION" in p.get("recommendation", ""))
    rejections = sum(1 for p in perspectives if "REJECT" in p.get("recommendation", "") or "DELAY" in p.get("recommendation", ""))
    
    # Safety-first logic
    has_safety_concern = any("compliance" in p.get("agent", "").lower() and p.get("risk_level") in ["medium", "high"] for p in perspectives)
    
    if has_safety_concern:
        return {
            "decision": "PROCEED_WITH_CAUTION",
            "reasoning": f"Safety concerns identified. {len(perspectives)} agents consulted. Compliance raised medium/high risk. Proceeding with enhanced monitoring.",
            "action": "Implement action with safety monitoring protocols"
        }
    elif rejections > approvals:
        return {
            "decision": "REJECTED",
            "reasoning": f"Majority recommendation against action. {rejections}/{len(perspectives)} agents recommend delay or rejection.",
            "action": "Action postponed. Re-evaluate during next planning cycle."
        }
    else:
        return {
            "decision": "APPROVED",
            "reasoning": f"Consensus reached. {approvals}/{len(perspectives)} agents approve. Risk levels acceptable.",
            "action": "Proceeding with implementation"
        }

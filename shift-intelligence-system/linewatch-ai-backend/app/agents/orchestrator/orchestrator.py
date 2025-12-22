"""
Master Orchestrator - Central coordinator for all specialized agents.

This agent uses Gemini 3's deepest reasoning (Level 3) to make complex decisions,
resolve conflicts between agents, and escalate to humans when needed.
"""
from typing import Dict, Any

from app.agents.base import BaseAgent
from app.prompts.orchestrator.system import ORCHESTRATOR_SYSTEM_PROMPT
from app.tools.orchestrator import (
    escalate_to_human,
    update_shift_plan,
    get_all_agent_status,
)
from app.utils.logging import get_agent_logger


logger = get_agent_logger("MasterOrchestrator")


class MasterOrchestrator(BaseAgent):
    """
    Master Orchestrator - Central coordination agent.
    
    Key Features:
    - Coordinates all 4 specialized agents
    - Resolves conflicts between competing priorities
    - Makes final decisions on complex issues
    - Escalates to humans when confidence < 70%
    - Maintains shift-level planning
    
    Thinking Level: 3 (Deepest reasoning for complex coordination)
    Model: gemini-3.0-pro-exp (Uses Pro model for best reasoning)
    """
    
    def __init__(self):
        tools = [
            escalate_to_human,
            update_shift_plan,
            get_all_agent_status,
        ]
        
        super().__init__(
            agent_name="MasterOrchestrator",
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            tools=tools,
            use_flash_model=False,  # Use Pro model for deep reasoning
            thinking_level=3,  # Deepest level for complex decisions
        )
        
        logger.info("✅ Master Orchestrator initialized (Gemini 3 Pro)")
    
    async def _execute_action(self, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute orchestrator actions."""
        action_lower = action.lower()
        
        if "escalate" in action_lower:
            result = await escalate_to_human(
                alert_title=context.get("issue", "Complex situation detected"),
                description=action,
                severity=context.get("severity", "HIGH")
            )
            return {"status": "ESCALATED", "escalation": result, "side_effects": ["Human supervisor notified"]}
        
        elif "adjust" in action_lower or "plan" in action_lower:
            adjustment = context.get("adjustment_percent", 0)
            result = await update_shift_plan(adjustment, action)
            return {"status": "SUCCESS", "plan_update": result, "side_effects": ["Shift targets updated"]}
        
        return {"status": "UNKNOWN_ACTION", "side_effects": []}
    
    def _detect_critical_situation(self, context: Dict[str, Any]) -> bool:
        """Orchestrator rarely escalates - it IS the escalation point."""
        # Only escalate on catastrophic scenarios
        return context.get("catastrophic_failure", False)
    
    async def _create_subagent(self, subagent_type: str) -> BaseAgent:
        """Orchestrator doesn't spawn subagents - it coordinates main agents."""
        raise NotImplementedError("Orchestrator coordinates main agents, not subagents")

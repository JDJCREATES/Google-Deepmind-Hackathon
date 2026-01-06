"""
Maintenance Agent - Predictive maintenance and equipment health management.

This agent uses Gemini 3's reasoning for predictive failure analysis and
optimal maintenance window scheduling.
"""
from typing import Dict, Any, List

from app.agents.base import BaseAgent
from app.prompts.maintenance.system import MAINTENANCE_AGENT_SYSTEM_PROMPT
from app.tools.maintenance.dispatch_tools import dispatch_maintenance_crew
from app.tools.maintenance import (
    check_all_equipment_health,
    schedule_maintenance,
    create_work_order,
)
from app.utils.logging import get_agent_logger


logger = get_agent_logger("MaintenanceAgent")


class MaintenanceAgent(BaseAgent):
    """
    Predictive Maintenance & Equipment Health Agent.
    
    Thinking Level: 1 (Fast monitoring loop)
    Model: gemini-3.0-flash-exp
    """
    
    def __init__(self):
        tools = [
            check_all_equipment_health,
            dispatch_maintenance_crew,  # NEW: Real dispatch capability
            schedule_maintenance,
            create_work_order,
        ]
        
        super().__init__(
            agent_name="MaintenanceAgent",
            system_prompt=MAINTENANCE_AGENT_SYSTEM_PROMPT,
            tools=tools,
            use_flash_model=True,
            thinking_level="minimal",  # Fast for monitoring
        )
        
        logger.info("✅ Maintenance Agent initialized")
    
    def filter_context(self, full_context: Dict[str, Any]) -> Dict[str, Any]:
        """Filter context to maintenance-only data."""
        return {
            "machines": full_context.get("machines", {}),
            "line_health": full_context.get("line_health", {}),
            "maintenance_crew": full_context.get("maintenance_crew", {}),
            "current_shift": full_context.get("current_shift"),
        }
    
    
    # ========== HYPOTHESIS GENERATION ==========
    
    async def generate_hypotheses(self, signal: Dict[str, Any]) -> List[Any]:
        """
        Generate FMEA and RCA hypotheses for equipment issues.
        """
        from app.hypothesis import create_hypothesis, HypothesisFramework
        from uuid import uuid4
        
        self.logger.info("💡 Generating Maintenance hypotheses (FMEA/RCA)")
        
        hypotheses = []
        signal_desc = signal.get('description', '')
        
        # FMEA: Predictive failure
        if any(w in signal_desc.lower() for w in ['vibration', 'noise', 'smoke', 'fire', 'overheat', 'breakdown']):
            hs_desc = "Critical component failure detection"
            
            hypotheses.append(create_hypothesis(
                framework=HypothesisFramework.FMEA,
                hypothesis_id=f"H-MAINT-{uuid4().hex[:6]}",
                description=hs_desc,
                initial_confidence=0.95,
                impact=10.0,
                urgency=10.0,
                proposed_by=self.agent_name,
                recommended_action=f"dispatch_maintenance_crew(machine_id={signal.get('line_id', 0)})",
                target_agent="MaintenanceAgent"
            ))
            
        return hypotheses
    
    async def _execute_action(self, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute maintenance actions."""
        action_lower = action.lower()
        
        if "schedule" in action_lower:
            import re
            match = re.search(r'line[s]?\s+(\d+)', action_lower)
            if match:
                line_num = int(match.group(1))
                result = await schedule_maintenance(line_num, "2hr_window")
                return {"status": "SUCCESS", "scheduled": result, "side_effects": [f"Maintenance scheduled for Line {line_num}"]}
        elif "work order" in action_lower:
            import re
            match = re.search(r'line[s]?\s+(\d+)', action_lower)
            if match:
                line_num = int(match.group(1))
                result = await create_work_order(line_num, action, "HIGH")
                return {"status": "SUCCESS", "work_order": result, "side_effects": ["Work order created"]}
        
        return {"status": "UNKNOWN_ACTION", "side_effects": []}
    
    def _detect_critical_situation(self, context: Dict[str, Any]) -> bool:
        """Detect equipment emergencies."""
        critical_health = context.get('critical_health_lines', [])
        return len(critical_health) >= 2
    
    async def _create_subagent(self, subagent_type: str) -> BaseAgent:
        """Create maintenance subagents."""
        raise NotImplementedError(f"Subagent {subagent_type} not implemented")

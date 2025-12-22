"""
Maintenance Agent - Predictive maintenance and equipment health management.

This agent uses Gemini 3's reasoning for predictive failure analysis and
optimal maintenance window scheduling.
"""
from typing import Dict, Any

from app.agents.base import BaseAgent
from app.prompts.maintenance.system import MAINTENANCE_AGENT_SYSTEM_PROMPT
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
            schedule_maintenance,
            create_work_order,
        ]
        
        super().__init__(
            agent_name="MaintenanceAgent",
            system_prompt=MAINTENANCE_AGENT_SYSTEM_PROMPT,
            tools=tools,
            use_flash_model=True,
            thinking_level=1,  # Fast for monitoring
        )
        
        logger.info("✅ Maintenance Agent initialized")
    
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
        if 'vibration' in signal_desc.lower() or 'noise' in signal_desc:
            hypotheses.append(create_hypothesis(
                framework=HypothesisFramework.FMEA,
                hypothesis_id=f"H-MAINT-{uuid4().hex[:6]}",
                description="Bearing wear leading to potential seizure",
                initial_confidence=0.75,
                impact=6.0,
                urgency=5.0,
                proposed_by=self.agent_name,
                recommended_action="Schedule maintenance in next window",
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

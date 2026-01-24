"""
Maintenance Agent - Predictive maintenance and equipment health management.

This agent uses Gemini 3's reasoning for predictive failure analysis and
optimal maintenance window scheduling.
"""
from typing import Dict, Any, List

from app.agents.base import BaseAgent
from app.prompts.maintenance.system import MAINTENANCE_AGENT_SYSTEM_PROMPT
from app.tools.maintenance.dispatch_tools import dispatch_maintenance_crew
from app.tools.maintenance.equipment_tools import (
    check_all_equipment_health,
    schedule_maintenance,
    create_work_order,
)
from app.tools.analysis import (
    query_facility_subsystem,
    get_facility_layout,
    query_system_logs,
    analyze_historical_patterns,
)
from app.tools.actions import (
    query_available_resources,
    submit_resource_request,
    dispatch_personnel,
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
            # Maintenance-specific tools
            check_all_equipment_health,
            dispatch_maintenance_crew,
            schedule_maintenance,
            create_work_order,
            # General discovery tools  
            query_facility_subsystem,
            get_facility_layout,
            query_system_logs,
            analyze_historical_patterns,
            # General action tools
            query_available_resources,
            submit_resource_request,
            dispatch_personnel,
        ]
        
        super().__init__(
            agent_name="MaintenanceAgent",
            system_prompt=MAINTENANCE_AGENT_SYSTEM_PROMPT,
            tools=tools,
            use_flash_model=True,
            thinking_level="medium",  # Show reasoning for transparency
        )
        
        logger.info("✅ Maintenance Agent initialized")
    
    def filter_context(self, full_context: Dict[str, Any]) -> Dict[str, Any]:
        """Filter context to maintenance-only data."""
        # Start with specific state keys
        filtered = {
            "machines": full_context.get("machines", {}),
            "line_health": full_context.get("line_health", {}),
            "maintenance_crew": full_context.get("maintenance_crew", {}),
            "current_shift": full_context.get("current_shift"),
        }
        
        # Preserve specific event keys if present (for signal context)
        for key in ["line_id", "severity", "source", "description", "details"]:
            if key in full_context:
                filtered[key] = full_context[key]
                
        return filtered
    
    
    # ========== HYPOTHESIS GENERATION ==========
    
    async def generate_hypotheses(self, signal: Dict[str, Any]) -> List[Any]:
        """
        Generate FMEA and RCA hypotheses for equipment issues.
        Use REAL investigation tools instead of keyword matching.
        """
        from app.hypothesis import create_hypothesis, HypothesisFramework
        from uuid import uuid4
        
        self.logger.info("💡 MaintenanceAgent investigating maintenance hypothesis")
        
        signal_desc = signal.get('description', '')
        signal_data = signal.get('data', {})
        
        # Extract line_id
        line_id = signal_data.get('line_id') or signal.get('line_id') or 0
        
        # Use LLM to analyze the event and generate specific hypothesis
        investigation_prompt = f"""
EVENT ALERT: {signal_desc}
LINE ID: {line_id}
RAW DATA: {str(signal_data)[:300]}

You are the MaintenanceAgent. Investigate this equipment issue.

STEPS:
1. Use query_logs("{signal_desc[:50]}") to check recent failure history
2. Use check_all_equipment_health() to see current health scores
3. Generate a SPECIFIC hypothesis about the root cause

Respond in this JSON format:
{{
    "description": "Specific technical hypothesis (e.g. 'Bearing wear causing motor overheat on Line 11 due to 400hrs runtime')",
    "confidence": 0.75,
    "recommended_action": "dispatch_maintenance_crew(machine_id=11, issue='bearing_replacement')",
    "urgency": 9.0,
    "reasoning": "Brief technical explanation"
}}

BE SPECIFIC. Quote sensor readings, error codes, or failure patterns. NO generic "equipment failure" responses.
"""
        
        # Call LLM to investigate
        try:
            # BROADCAST to frontend: Agent is investigating
            from app.services.websocket import manager
            from datetime import datetime
            await manager.broadcast({
                "type": "agent_thinking",
                "data": {
                    "agent": "MAINTENANCE",
                    "thought": f"Investigating equipment issue: {signal_desc[:80]}...",
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            await self._ensure_agent_initialized()
            
            # Use structured output for reliable parsing
            from app.graphs.nodes import AgentHypothesisResponse
            # MUST use .llm, not .agent (which is a graph)
            structured_agent = self.llm.with_structured_output(AgentHypothesisResponse)
            
            from langchain_core.messages import HumanMessage
            result = await structured_agent.ainvoke(
                [HumanMessage(content=investigation_prompt)],
                config={"configurable": {"thread_id": f"maint-hypo-{uuid4().hex[:6]}"}}
            )
            
            # result is now a Pydantic model, not dict
            return [create_hypothesis(
                framework=HypothesisFramework.FMEA,
                hypothesis_id=f"H-MAINT-{uuid4().hex[:6]}",
                description=result.description,
                initial_confidence=result.confidence,
                impact=10.0,
                urgency=result.urgency,
                proposed_by=self.agent_name,
                recommended_action=result.recommended_action,
                target_agent="MaintenanceAgent"
            )]
                
        except Exception as e:
            self.logger.error(f"MaintenanceAgent investigation failed: {e}")
        
        # Fallback to generic if LLM fails
        return [create_hypothesis(
            framework=HypothesisFramework.FMEA,
            hypothesis_id=f"H-MAINT-{uuid4().hex[:6]}",
            description=f"Equipment issue detected: {signal_desc}",
            initial_confidence=0.6,
            impact=8.0,
            urgency=7.0,
            proposed_by=self.agent_name,
            recommended_action=f"dispatch_maintenance_crew(machine_id={line_id})",
            target_agent="MaintenanceAgent"
        )]
    
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

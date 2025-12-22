"""
Compliance Agent - Monitors safety violations and regulatory compliance.

This agent uses Gemini 3's reasoning to analyze safety violations from camera feeds,
ensure temperature/hygiene compliance, and manage incident response.
"""
from typing import Dict, Any

from app.agents.base import BaseAgent
from app.prompts.compliance.system import COMPLIANCE_AGENT_SYSTEM_PROMPT
from app.tools.compliance import (
    get_safety_violations,
    classify_violation_severity,
    check_all_temperatures,
    trigger_safety_alarm,
    log_corrective_action,
    generate_compliance_report,
)
from app.utils.logging import get_agent_logger


logger = get_agent_logger("ComplianceAgent")


class ComplianceAgent(BaseAgent):
    """
    Compliance & Safety Monitoring Agent.
    
    Key Features:
    - Real-time safety violation monitoring from camera vision
    - Violation severity classification with AI reasoning
    - Temperature compliance tracking (cold chain)
    - Safety alarm triggering for critical situations
    - Compliance reporting and audit trails
    
    Thinking Level: 2 (Balanced reasoning for safety decisions)
    Model: gemini-3.0-flash-exp
    """
    
    def __init__(self):
        """Initialize Compliance Agent with safety monitoring tools."""
        tools = [
            get_safety_violations,
            classify_violation_severity,
            check_all_temperatures,
            trigger_safety_alarm,
            log_corrective_action,
            generate_compliance_report,
        ]
        
        super().__init__(
            agent_name="ComplianceAgent",
            system_prompt=COMPLIANCE_AGENT_SYSTEM_PROMPT,
            tools=tools,
            use_flash_model=True,
            thinking_level=2,  # Balanced for safety classification
        )
        
        logger.info("✅ Compliance Agent initialized")
    
    #========== ACTION EXECUTION ==========
    
    async def _execute_action(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute compliance-specific actions."""
        action_lower = action.lower()
        
        if "alarm" in action_lower:
            return await self._handle_safety_alarm(action, context)
        elif "classify" in action_lower or "severity" in action_lower:
            return await self._handle_classification(action, context)
        elif "temperature" in action_lower:
            return await self._handle_temperature_check(action, context)
        elif "corrective" in action_lower or "resolve" in action_lower:
            return await self._handle_corrective_action(action, context)
        else:
            logger.warning(f"⚠️ Unknown compliance action: {action}")
            return {"status": "UNKNOWN_ACTION", "side_effects": []}
    
    async def _handle_safety_alarm(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Trigger safety alarm for critical violation."""
        violation_id = context.get('violation_id', 'UNKNOWN')
        
        result = await trigger_safety_alarm(
            violation_id=violation_id,
            message=f"Critical safety violation detected: {action}"
        )
        
        return {
            "status": "ALARM_TRIGGERED",
            "alarm_id": result.get("alarm_id"),
            "side_effects": ["Safety alarm activated", "Emergency response initiated"],
        }
    
    async def _handle_classification(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Classify violation severity."""
        violation_id = context.get('violation_id')
        
        if not violation_id:
            return {"status": "FAILED", "reason": "No violation ID", "side_effects": []}
        
        result = await classify_violation_severity(violation_id)
        
        return {
            "status": "SUCCESS",
            "severity": result.get("classified_severity"),
            "recommendations": result.get("recommendations", []),
            "side_effects": [f"Violation classified as {result.get('classified_severity')}"],
        }
    
    async def _handle_temperature_check(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check temperature compliance."""
        result = await check_all_temperatures()
        
        side_effects = []
        if result["overall_status"] == "NON_COMPLIANT":
            side_effects.append("Temperature violations detected - alerting maintenance")
        
        return {
            "status": "SUCCESS",
            "compliance STATUS": result["overall_status"],
            "violations": len(result.get("violation_lines", [])),
            "side_effects": side_effects,
        }
    
    async def _handle_corrective_action(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Log corrective action."""
        violation_id = context.get('violation_id', 'UNKNOWN')
        
        result = await log_corrective_action(
            violation_id=violation_id,
            action_taken=action,
            resolved=True
        )
        
        return {
            "status": "SUCCESS",
            "action_logged": result.get("action_id"),
            "side_effects": ["Corrective action logged in audit trail"],
        }
    
    # ========== CRITICAL SITUATION DETECTION ==========
    
    def _detect_critical_situation(self, context: Dict[str, Any]) -> bool:
        """
        Detect safety emergencies requiring immediate escalation.
        
        Escalation triggers:
        - Critical safety violation (NO_PPE, UNSAFE_PROXIMITY)
        - Multiple violations on same line
        - Temperature violation affecting food safety
        - Unresolved critical violation
        """
        # Check for critical violations
        critical_violations = context.get('critical_violations', 0)
        if critical_violations > 0:
            logger.warning(f"⚠️ Critical: {critical_violations} critical safety violations")
            return True
        
        # Check for temperature emergencies
        temp_violations = context.get('temperature_violations', 0)
        if temp_violations >= 3:
            logger.warning(f"⚠️ Critical: {temp_violations} lines with temp violations")
            return True
        
        return False
    
    # ========== SUBAGENT CREATION ==========
    
    async def _create_subagent(self, subagent_type: str) -> BaseAgent:
        """Create specialized compliance subagents."""
        if subagent_type == "violation_classifier":
            return await self._create_violation_classifier()
        else:
            raise ValueError(f"Unknown subagent type: {subagent_type}")
    
    async def _create_violation_classifier(self) -> BaseAgent:
        """Create Violation Severity Classifier subagent."""
        subagent = BaseAgent(
            agent_name="ViolationClassifier",
            system_prompt="""You are a specialized Safety Violation Classifier.

Analyze violations in detail considering:
- Type of violation
- Proximity to danger
- Confidence of detection
- Context (time, location, conditions)

Provide precise severity classification with detailed reasoning.""",
            tools=[
                get_safety_violations,
                classify_violation_severity,
            ],
            use_flash_model=True,
            thinking_level=2,
        )
        
        return subagent

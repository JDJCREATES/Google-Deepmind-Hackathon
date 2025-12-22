"""
Production Agent - Monitors all 20 production lines with nested subagent capabilities.

This agent uses Gemini 3's reasoning to detect bottlenecks, predict failures,
and coordinate with other agents for optimal production efficiency.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.agents.base import BaseAgent, ReasoningResult, ActionResult
from app.prompts.production.system import PRODUCTION_AGENT_SYSTEM_PROMPT
from app.tools.production import (
    get_line_metrics,
    get_all_line_metrics,
    analyze_throughput_trend,
    predict_bottleneck,
    request_maintenance,
    check_line_staffing,
)
from app.models.domain import LineStatus, AlertSeverity
from app.utils.logging import get_agent_logger


logger = get_agent_logger("ProductionAgent")


class ProductionAgent(BaseAgent):
    """
    Production Monitoring Agent for 20 production lines.
    
    Key Features:
    - Real-time monitoring of all lines (30-second intervals)
    - Bottleneck prediction using health + efficiency heuristics
    - Automatic maintenance requests for degraded equipment
    - Staffing verification via camera vision
    - Nested subagents: Bottleneck Analyzer, Efficiency Optimizer
    
    Thinking Level: 1 (Fast decisions for real-time monitoring)
    Model: gemini-3.0-flash-exp
    """
    
    def __init__(self):
        """Initialize Production Agent with tools and configuration."""
        tools = [
            get_line_metrics,
            get_all_line_metrics,
            analyze_throughput_trend,
            predict_bottleneck,
            request_maintenance,
            check_line_staffing,
        ]
        
        super().__init__(
            agent_name="ProductionAgent",
            system_prompt=PRODUCTION_AGENT_SYSTEM_PROMPT,
            tools=tools,
            use_flash_model=True,  # Use Flash for fast 30s loops
            thinking_level=1,  # Quick decisions for monitoring
        )
        
        logger.info("✅ Production Agent initialized")
    
    # ========== SPECIALIZED ACTION EXECUTION ==========
    
    async def _execute_action(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute production-specific actions.
        
        Actions include:
        - Request maintenance for degraded lines
        - Escalate bottleneck predictions
        - Verify staffing levels
        - Spawn bottleneck analyzer subagent
        
        Args:
            action: Action description from reasoning phase
            context: Current state context
            
        Returns:
            Result dictionary with status and side effects
        """
        action_lower = action.lower()
        
        # Maintenance request
        if "maintenance" in action_lower or "repair" in action_lower:
            return await self._handle_maintenance_request(action, context)
        
        # Bottleneck analysis
        elif "bottleneck" in action_lower:
            return await self._handle_bottleneck_analysis(action, context)
        
        # Staffing verification
        elif "staff" in action_lower or "worker" in action_lower:
            return await self._handle_staffing_check(action, context)
        
        # Spawn subagent
        elif "analyze" in action_lower or "deep" in action_lower:
            return await self._handle_deep_analysis(action, context)
        
        # Generic action
        else:
            logger.warning(f"⚠️ Unknown action type: {action}")
            return {
                "status": "UNKNOWN_ACTION",
                "action": action,
                "side_effects": [],
            }
    
    async def _handle_maintenance_request(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle maintenance request actions."""
        # Extract line number from action (simple parsing)
        # In production, would use better NLU
        import re
        match = re.search(r'line[s]?\s+(\d+)', action.lower())
        
        if not match:
            return {
                "status": "FAILED",
                "reason": "Could not identify line number",
                "side_effects": [],
            }
        
        line_num = int(match.group(1))
        
        # Determine priority based on context
        health = context.get('health_score', 50)
        if health < 30:
            priority = "CRITICAL"
        elif health < 50:
            priority = "HIGH"
        else:
            priority = "MEDIUM"
        
        # Call maintenance request tool
        result = await request_maintenance(
            line_number=line_num,
            priority=priority,
            reason=f"Production Agent detected degraded performance: {action}"
        )
        
        return {
            "status": "SUCCESS",
            "request_id": result.get("request_id"),
            "side_effects": [f"Maintenance requested for Line {line_num}"],
        }
    
    async def _handle_bottleneck_analysis(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle bottleneck prediction and analysis."""
        # Run bottleneck prediction
        prediction = await predict_bottleneck(line_number=None)
        
        at_risk_count = prediction.get("at_risk_count", 0)
        
        side_effects = []
        if at_risk_count > 0:
            side_effects.append(
                f"Identified {at_risk_count} lines at risk of bottleneck"
            )
            
            # Auto-escalate if multiple lines affected
            if at_risk_count >= 3:
                side_effects.append("Multiple lines affected - escalation triggered")
        
        return {
            "status": "SUCCESS",
            "at_risk_lines": at_risk_count,
            "predictions": prediction.get("predictions", []),
            "side_effects": side_effects,
        }
    
    async def _handle_staffing_check(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle staffing verification actions."""
        import re
        match = re.search(r'line[s]?\s+(\d+)', action.lower())
        
        if not match:
            return {
                "status": "FAILED",
                "reason": "Could not identify line number",
                "side_effects": [],
            }
        
        line_num = int(match.group(1))
        
        # Check staffing via camera
        staffing = await check_line_staffing(line_number=line_num)
        
        side_effects = []
        if staffing.get("is_understaffed"):
            side_effects.append(
                f"Line {line_num} is understaffed - notifying Staffing Agent"
            )
        
        return {
            "status": "SUCCESS",
            "staffing_info": staffing,
            "side_effects": side_effects,
        }
    
    async def _handle_deep_analysis(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Spawn nested subagent for deep analysis.
        
        Example: Spawn Bottleneck Analyzer for specific line investigation.
        """
        logger.info("🔀 Spawning Bottleneck Analyzer subagent")
        
        # Spawn subagent
        subagent_result = await self.spawn_subagent(
            "bottleneck_analyzer",
            context
        )
        
        return {
            "status": "SUCCESS",
            "subagent": "bottleneck_analyzer",
            "subagent_confidence": subagent_result.confidence,
            "subagent_actions": subagent_result.actions_taken,
            "side_effects": ["Bottleneck Analyzer subagent completed analysis"],
        }
    
    # ========== CRITICAL SITUATION DETECTION ==========
    
    def _detect_critical_situation(self, context: Dict[str, Any]) -> bool:
        """
        Detect if current situation requires escalation to Orchestrator.
        
        Escalation triggers:
        - Multiple lines (3+) in failure state
        - Critical equipment health (<30) on any line
        - Production throughput dropped >30% unexpectedly
        - Safety concern detected
        
        Args:
            context: Current state
            
        Returns:
            True if escalation needed
        """
        # Check for multiple line failures
        failed_lines = context.get('failed_lines', [])
        if len(failed_lines) >= 3:
            logger.warning(
                f"⚠️ Critical: {len(failed_lines)} lines in failure state"
            )
            return True
        
        # Check for critical health
        min_health = context.get('min_health_score', 100)
        if min_health < 30:
            logger.warning(f"⚠️ Critical: Equipment health at {min_health}")
            return True
        
        # Check for throughput collapse
        throughput_drop = context.get('throughput_drop_percent', 0)
        if throughput_drop > 30:
            logger.warning(
                f"⚠️ Critical: Throughput dropped {throughput_drop}%"
            )
            return True
        
        # Check for safety concerns
        if context.get('safety_concern', False):
            logger.warning("⚠️ Critical: Safety concern detected")
            return True
        
        return False
    
    # ========== NESTED SUBAGENT CREATION ==========
    
    async def _create_subagent(self, subagent_type: str) -> BaseAgent:
        """
        Create specialized production subagents.
        
        Available subagents:
        - bottleneck_analyzer: Deep analysis of bottleneck causes
        - efficiency_optimizer: Recommendations for efficiency improvement
        - equipment_diagnostics: Detailed equipment health analysis
        
        Args:
            subagent_type: Type of subagent to create
            
        Returns:
            Initialized subagent instance
            
        Raises:
            ValueError: If subagent type is unknown
        """
        if subagent_type == "bottleneck_analyzer":
            return await self._create_bottleneck_analyzer()
        elif subagent_type == "efficiency_optimizer":
            return await self._create_efficiency_optimizer()
        elif subagent_type == "equipment_diagnostics":
            return await self._create_equipment_diagnostics()
        else:
            raise ValueError(f"Unknown subagent type: {subagent_type}")
    
    async def _create_bottleneck_analyzer(self) -> BaseAgent:
        """
        Create Bottleneck Analyzer subagent.
        
        Specialized for deep analysis of bottleneck root causes,
        examining equipment health, staffing, and upstream dependencies.
        """
        from langchain_core.tools import tool
        
        # Bottleneck analyzer has subset of tools + specialized prompt
        @tool
        async def analyze_bottleneck_root_cause(line_number: int) -> str:
            """Analyze root cause of bottleneck on specific line."""
            metrics = await get_line_metrics(line_number)
            trend = await analyze_throughput_trend(line_number)
            staffing = await check_line_staffing(line_number)
            
            # Simple heuristic analysis
            causes = []
            if metrics['health_score'] < 60:
                causes.append("Equipment degradation")
            if staffing['is_understaffed']:
                causes.append("Insufficient staffing")
            if trend['trend'] == 'decreasing':
                causes.append("Performance degradation trend")
            
            return f"Root causes: {', '.join(causes) if causes else 'None identified'}"
        
        subagent = BaseAgent(
            agent_name="BottleneckAnalyzer",
            system_prompt="""You are a specialized Bottleneck Analyzer subagent.
            
Your sole purpose is to deeply analyze the root causes of bottlenecks on
production lines. Use your tools to gather comprehensive data and provide
detailed causal analysis.

Provide specific, actionable recommendations.""",
            tools=[
                analyze_bottleneck_root_cause,
                get_line_metrics,
                analyze_throughput_trend,
                check_line_staffing,
            ],
            use_flash_model=True,
            thinking_level=2,  # Deeper thinking for root cause analysis
        )
        
        return subagent
    
    async def _create_efficiency_optimizer(self) -> BaseAgent:
        """Create Efficiency Optimizer subagent (placeholder)."""
        # Simplified for hackathon - would be fully implemented in production
        return await self._create_bottleneck_analyzer()
    
    async def _create_equipment_diagnostics(self) -> BaseAgent:
        """Create Equipment Diagnostics subagent (placeholder)."""
        # Simplified for hackathon - would be fully implemented in production
        return await self._create_bottleneck_analyzer()

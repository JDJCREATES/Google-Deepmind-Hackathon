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
    set_production_speed,
)
from app.tools.analysis import (
    query_facility_subsystem,
    get_facility_layout,
    query_system_logs,
)
from app.tools.actions import (
    query_available_resources,
    submit_resource_request,
    dispatch_personnel,
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
            # Production-specific tools
            get_line_metrics,
            get_all_line_metrics,
            analyze_throughput_trend,
            predict_bottleneck,
            request_maintenance,
            check_line_staffing,
            set_production_speed,
            # General discovery tools
            query_facility_subsystem,
            get_facility_layout,
            query_system_logs,
            # General action tools
            query_available_resources,
            submit_resource_request,
            dispatch_personnel,
        ]
        
        super().__init__(
            agent_name="ProductionAgent",
            system_prompt=PRODUCTION_AGENT_SYSTEM_PROMPT,
            tools=tools,
            use_flash_model=True,  # Use Flash for fast 30s loops
            thinking_level="medium",  # Show reasoning for transparency
        )
        

        logger.info("✅ Production Agent initialized")
    
    def filter_context(self, full_context: Dict[str, Any]) -> Dict[str, Any]:
        """Filter context to production-only data (reduces size ~70%)."""
        return {
            "machines": full_context.get("machines", {}),
            "lines": full_context.get("lines", {}),
            "line_health": full_context.get("line_health", {}),
            "warehouse_inventory": full_context.get("warehouse_inventory", {}),
            "current_shift": full_context.get("current_shift"),
            "shift_elapsed_hours": full_context.get("shift_elapsed_hours"),
        }
    
    # ========== HYPOTHESIS GENERATION ==========
    
    async def generate_hypotheses(self, signal: Dict[str, Any]) -> List[Any]:
        """
        Generate RCA and TOC hypotheses for production issues.
        """
        from app.hypothesis import create_hypothesis, HypothesisFramework
        from uuid import uuid4
        
        self.logger.info("💡 Generating Production hypotheses (RCA/TOC)")
        
        hypotheses = []
        signal_desc = signal.get('description', '')
        
        # RCA Hypothesis: Equipment failure
        if any(w in signal_desc.lower() for w in ['throughput', 'stopped', 'smoke', 'fire', 'failure']):
            hypotheses.append(create_hypothesis(
                framework=HypothesisFramework.RCA,
                hypothesis_id=f"H-PROD-{uuid4().hex[:6]}",
                description=f"Equipment failure on line causing {signal_desc}",
                initial_confidence=0.9 if 'smoke' in signal_desc.lower() else 0.6,
                impact=10.0 if 'smoke' in signal_desc.lower() else 8.0,
                urgency=10.0 if 'smoke' in signal_desc.lower() else 9.0,
                proposed_by=self.agent_name,
                recommended_action="Emergency shutdown and diagnostic",
                target_agent="ProductionAgent"
            ))
            
        # TOC Hypothesis: Upstream bottleneck
        if 'slow' in signal_desc.lower() or 'waiting' in signal_desc:
            hypotheses.append(create_hypothesis(
                framework=HypothesisFramework.TOC,
                hypothesis_id=f"H-TOC-{uuid4().hex[:6]}",
                description="Upstream bottleneck constraining throughput",
                initial_confidence=0.5,
                impact=7.0,
                urgency=7.0,
                proposed_by=self.agent_name,
                recommended_action="Analyze bottleneck root cause",
                target_agent="ProductionAgent"
            ))
            
        return hypotheses

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
            thinking_level="medium",  # Deeper thinking for root cause analysis
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

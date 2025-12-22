"""
Staffing Agent - Manages workforce allocation with break scheduling and coverage optimization.

This agent uses Gemini 3's reasoning for intelligent staffing decisions including
dynamic reassignments, break scheduling, and fatigue management.
"""
from typing import Dict, Any
from datetime import datetime

from app.agents.base import BaseAgent
from app.prompts.staffing.system import STAFFING_AGENT_SYSTEM_PROMPT
from app.tools.staffing import (
    get_shift_roster,
    check_line_coverage,
    call_in_replacement,
    schedule_break,
    calculate_coverage_needs,
    reassign_worker,
    check_fatigue_levels,
)
from app.utils.logging import get_agent_logger


logger = get_agent_logger("StaffingAgent")


class StaffingAgent(BaseAgent):
    """
    Staffing & Workforce Management Agent.
    
    Key Features:
    - Shift roster management
    - Break scheduling without production disruption
    - Dynamic worker reassignment
    - Fatigue monitoring and compliance
    - Coverage gap prediction
    - Integration with camera vision for verification
    
    Thinking Level: 2 (Balanced reasoning for scheduling complexity)
    Model: gemini-3.0-flash-exp
    """
    
    def __init__(self):
        """Initialize Staffing Agent with workforce management tools."""
        tools = [
            get_shift_roster,
            check_line_coverage,
            call_in_replacement,
            schedule_break,
            calculate_coverage_needs,
            reassign_worker,
            check_fatigue_levels,
        ]
        
        super().__init__(
            agent_name="StaffingAgent",
            system_prompt=STAFFING_AGENT_SYSTEM_PROMPT,
            tools=tools,
            use_flash_model=True,
            thinking_level=2,  # Balanced for scheduling decisions
        )
        
        logger.info("✅ Staffing Agent initialized")
    
    # ========== ACTION EXECUTION ==========
    
    async def _execute_action(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute staffing-specific actions.
        
        Actions include:
        - Schedule breaks for fatigued workers
        - Reassign workers between lines
        - Call in replacements for absences
        - Check and resolve coverage gaps
        """
        action_lower = action.lower()
        
        if "break" in action_lower:
            return await self._handle_break_scheduling(action, context)
        elif "reassign" in action_lower or "move" in action_lower:
            return await self._handle_reassignment(action, context)
        elif "replacement" in action_lower or "call" in action_lower:
            return await self._handle_replacement_call(action, context)
        elif "coverage" in action_lower or "gap" in action_lower:
            return await self._handle_coverage_check(action, context)
        else:
            logger.warning(f"⚠️ Unknown staffing action: {action}")
            return {
                "status": "UNKNOWN_ACTION",
                "action": action,
                "side_effects": [],
            }
    
    async def _handle_break_scheduling(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Schedule breaks for workers based on fatigue."""
        # Check fatigue levels
        fatigue_report = await check_fatigue_levels()
        
        breaks_scheduled = []
        high_fatigue = fatigue_report.get("high_fatigue", [])
        
        for worker in high_fatigue[:3]:  # Limit to 3 for demo
            try:
                break_result = await schedule_break(
                    employee_id=worker["employee_id"],
                    duration_minutes=30 if worker["fatigue_level"] > 0.8 else 15,
                )
                breaks_scheduled.append(break_result)
            except Exception as e:
                logger.error(f"Failed to schedule break: {e}")
        
        return {
            "status": "SUCCESS",
            "breaks_scheduled": len(breaks_scheduled),
            "details": breaks_scheduled,
            "side_effects": [
                f"Scheduled {len(breaks_scheduled)} breaks for fatigued workers"
            ],
        }
    
    async def _handle_reassignment(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle worker reassignment between lines."""
        # Extract line numbers (simplified - in production use better NLU)
        import re
        matches = re.findall(r'\d+', action)
        
        if len(matches) < 2:
            return {
                "status": "FAILED",
                "reason": "Could not parse line numbers",
                "side_effects": [],
            }
        
        from_line = int(matches[0])
        to_line = int(matches[1])
        
        # Get roster to find worker
        roster = await get_shift_roster()
        from_line_staff = roster.get("line_assignments", {}).get(str(from_line), [])
        
        if not from_line_staff:
            return {
                "status": "FAILED",
                "reason": f"No staff on Line {from_line}",
                "side_effects": [],
            }
        
        # Reassign first available worker
        result = await reassign_worker(
            employee_id=from_line_staff[0],
            from_line=from_line,
            to_line=to_line,
            reason=action,
        )
        
        return {
            "status": result.get("status", "SUCCESS"),
            "reassignment": result,
            "side_effects": [
                f"Reassigned worker from Line {from_line} to Line {to_line}"
            ],
        }
    
    async def _handle_replacement_call(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call in replacement worker."""
        result = await call_in_replacement()
        
        return {
            "status": "SUCCESS",
            "replacement": result.get("replacement"),
            "side_effects": [
                f"Replacement worker called, ETA {result['replacement']['eta_minutes']}min"
            ],
        }
    
    async def _handle_coverage_check(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check coverage across all lines."""
        # Check all lines for coverage issues
        coverage_issues = []
        
        for line_num in range(1, 21):
            coverage = await check_line_coverage(line_num)
            if coverage.get("is_critical"):
                coverage_issues.append({
                    "line": line_num,
                    "visual_count": coverage["visual_count"],
                    "status": coverage["status"],
                })
        
        return {
            "status": "SUCCESS",
            "critical_lines": len(coverage_issues),
            "issues": coverage_issues,
            "side_effects": [
                f"Identified {len(coverage_issues)} lines with critical coverage"
            ],
        }
    
    # ========== CRITICAL SITUATION DETECTION ==========
    
    def _detect_critical_situation(self, context: Dict[str, Any]) -> bool:
        """
        Detect staffing emergencies requiring escalation.
        
        Escalation triggers:
        - Multiple lines (3+) critically understaffed
        - Labor regulation violation (worker >8 hours)
        - Sudden mass absence
        - Unable to maintain minimum coverage
        """
        # Check for critical understaffing
        critical_lines = context.get('critical_coverage_lines', [])
        if len(critical_lines) >= 3:
            logger.warning(
                f"⚠️ Critical: {len(critical_lines)} lines understaffed"
            )
            return True
        
        # Check for labor violations
        if context.get('labor_violation_detected', False):
            logger.warning("⚠️ Critical: Labor regulation violation")
            return True
        
        # Check for mass absence
        absent_count = context.get('sudden_absences', 0)
        if absent_count >= 5:
            logger.warning(f"⚠️ Critical: {absent_count} sudden absences")
            return True
        
        return False
    
    # ========== SUBAGENT CREATION ==========
    
    async def _create_subagent(self, subagent_type: str) -> BaseAgent:
        """
        Create specialized staffing subagents.
        
        Available:
        - break_scheduler: Optimizes break schedules
        - coverage_predictor: Predicts future coverage gaps
        """
        if subagent_type == "break_scheduler":
            return await self._create_break_scheduler()
        elif subagent_type == "coverage_predictor":
            return await self._create_coverage_predictor()
        else:
            raise ValueError(f"Unknown subagent type: {subagent_type}")
    
    async def _create_break_scheduler(self) -> BaseAgent:
        """Create Break Scheduler subagent."""
        subagent = BaseAgent(
            agent_name="BreakScheduler",
            system_prompt="""You are a specialized Break Scheduler subagent.

Your purpose is to optimize break schedules across all workers to minimize
production disruption while ensuring compliance with labor regulations.

Consider:
- Worker fatigue levels
- Line coverage requirements
- Production demand peaks
- Mandatory break regulations""",
            tools=[
                get_shift_roster,
                check_line_coverage,
                schedule_break,
                check_fatigue_levels,
            ],
            use_flash_model=True,
            thinking_level=2,
        )
        
        return subagent
    
    async def _create_coverage_predictor(self) -> BaseAgent:
        """Create Coverage Predictor subagent."""
        subagent = BaseAgent(
            agent_name="CoveragePredictor",
            system_prompt="""You are a specialized Coverage Predictor subagent.

Predict future staffing gaps based on:
- Current fatigue trends
- Scheduled breaks
- Historical absence patterns
- Production demand forecast

Provide proactive recommendations.""",
            tools=[
                get_shift_roster,
                check_fatigue_levels,
                calculate_coverage_needs,
            ],
            use_flash_model=True,
            thinking_level=2,
        )
        
        return subagent

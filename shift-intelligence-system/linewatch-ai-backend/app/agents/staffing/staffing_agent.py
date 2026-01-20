"""
Staffing Agent - Comprehensive workforce management with HR actions and vision integration.

This agent uses Gemini 3's reasoning for intelligent staffing decisions including:
- Operator and packager position management
- Break scheduling without production disruption
- Dynamic reassignments based on vision alerts
- HR actions (write-ups, rewards, bonus points)
- Human-in-the-loop escalation for critical decisions
- Fatigue monitoring and compliance

Thinking Level: 2 (Balanced reasoning for complex scheduling decisions)
Model: gemini-3.0-flash-exp
"""
from typing import Dict, Any, List
from datetime import datetime

from app.agents.base import BaseAgent
from app.prompts.staffing.system import STAFFING_AGENT_SYSTEM_PROMPT
from app.tools.staffing import (
    # Roster management (7 tools)
    get_shift_roster,
    check_line_coverage,
    call_in_replacement,
    schedule_break,
    calculate_coverage_needs,
    reassign_worker,
    check_fatigue_levels,
    # HR actions (5 tools)
    issue_write_up,
    award_bonus_points,
    escalate_to_human_supervisor,
    get_hr_action_history,
    get_pending_escalations,
    # Vision integration (3 tools)
    get_recent_vision_alerts,
    get_all_lines_occupancy,
    acknowledge_vision_alert,
)
from app.utils.logging import get_agent_logger


logger = get_agent_logger("StaffingAgent")


# ============================================================================
# POSITION TYPES (for a department of 20)
# ============================================================================
# 
# OPERATORS (5 per shift) - Run the main production lines
#   - Each operator manages 1 of 5 main lines
#   - Vision cameras monitor these positions
#   - Critical for production output
#
# PACKAGERS (15 per shift) - Handle boxes/packaging from downstairs
#   - Support role, less visibility on cameras
#   - Flexible reassignment between lines
#   - Handle downstream packaging tasks
#
# Ratio: 5 Operators : 15 Packagers = 25% : 75%
# ============================================================================


class StaffingAgent(BaseAgent):
    """
    Staffing & Workforce Management Agent.
    
    Key Features:
    - Shift roster management (20 staff: 5 operators + 15 packagers)
    - Break scheduling without production disruption  
    - Dynamic worker reassignment
    - Fatigue monitoring and compliance
    - HR actions: write-ups, warnings, rewards, bonus points
    - Vision alert integration for empty station detection
    - Human escalation for high-severity decisions
    - Coverage gap prediction
    
    Human-in-the-Loop:
    - Written/final warnings require human approval
    - 3+ critical coverage gaps escalate
    - Labor regulation violations escalate
    - Low severity actions are autonomous
    
    Thinking Level: 2 (Balanced reasoning for scheduling complexity)
    Model: gemini-3.0-flash-exp
    """
    
    # Position configuration
    OPERATORS_PER_SHIFT = 5
    PACKAGERS_PER_SHIFT = 15
    TOTAL_STAFF = 20
    
    # Escalation thresholds
    CRITICAL_COVERAGE_THRESHOLD = 3  # Lines understaffed before escalate
    FATIGUE_ESCALATION_THRESHOLD = 0.9  # Labor violation level
    
    def __init__(self):
        """Initialize Staffing Agent with all workforce management tools."""
        tools = [
            # Roster management
            get_shift_roster,
            check_line_coverage,
            call_in_replacement,
            schedule_break,
            calculate_coverage_needs,
            reassign_worker,
            check_fatigue_levels,
            # HR actions
            issue_write_up,
            award_bonus_points,
            escalate_to_human_supervisor,
            get_hr_action_history,
            get_pending_escalations,
            # Vision integration
            get_recent_vision_alerts,
            get_all_lines_occupancy,
            acknowledge_vision_alert,
        ]
        
        super().__init__(
            agent_name="StaffingAgent",
            system_prompt=STAFFING_AGENT_SYSTEM_PROMPT,
            tools=tools,
            use_flash_model=True,
            thinking_level="medium",  # Balanced for scheduling decisions
        )
        
        
        logger.info(
            f"✅ Staffing Agent initialized with {len(tools)} tools "
            f"(Operators: {self.OPERATORS_PER_SHIFT}, Packagers: {self.PACKAGERS_PER_SHIFT})"
        )

    def filter_context(self, full_context: Dict[str, Any]) -> Dict[str, Any]:
        """Filter context to staffing-only data."""
        return {
            "operators": full_context.get("operators", {}),
            "supervisor": full_context.get("supervisor", {}),
            "current_shift": full_context.get("current_shift"),
            "shift_elapsed_hours": full_context.get("shift_elapsed_hours"),
            # FILTERED: Only show fatigue if CRITICAL (> 80%) to prevent excessive chatter
            "fatigue_levels": {
                k: v for k, v in full_context.get("fatigue_levels", {}).items() 
                if v >= 0.80
            },
        }
    
    # ========== HYPOTHESIS GENERATION ==========
    
    async def generate_hypotheses(self, signal: Dict[str, Any]) -> List[Any]:
        """
        Generate Staffing-related hypotheses.
        """
        from app.hypothesis import create_hypothesis, HypothesisFramework
        from uuid import uuid4
        
        hypotheses = []
        signal_desc = signal.get('description', '')
        
        # TOC: Labor shortage
        # TOC: Labor shortage & Staffing Issues
        keywords = ['understaffed', 'coverage', 'fatigue', 'tired', 'break', 'staff', 'operator', 'absent', 'missing', 'empty', 'shift']
        if any(k in signal_desc.lower() for k in keywords):
            hypotheses.append(create_hypothesis(
                framework=HypothesisFramework.TOC,
                hypothesis_id=f"H-STAFF-{uuid4().hex[:6]}",
                description="Staffing/Labor optimization opportunity detected",
                initial_confidence=0.85,
                impact=8.0,
                urgency=8.0,
                proposed_by=self.agent_name,
                recommended_action="Check fatigue and optimize roster",
                target_agent="StaffingAgent"
            ))
            
        # Unattended Line Hypothesis (High Priority)
        if "unattended" in signal_desc.lower():
            import re
            line_match = re.search(r'line (\d+)', signal_desc.lower())
            target_line = line_match.group(1) if line_match else "unknown"
            
            hypotheses.append(create_hypothesis(
                framework=HypothesisFramework.TOC,
                hypothesis_id=f"H-COVERAGE-{uuid4().hex[:6]}",
                description=f"Critical coverage gap on Line {target_line}",
                initial_confidence=0.95,
                impact=9.0,
                urgency=9.0,
                proposed_by=self.agent_name,
                recommended_action=f"Reassign worker to Line {target_line}",
                target_agent="StaffingAgent"
            ))
            
        # Fallback to LLM reasoning if heuristics miss
        if not hypotheses:
            return await super().generate_hypotheses(signal)
            
        return hypotheses
    
    # ========== ACTION EXECUTION ==========
    
    async def _execute_action(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute staffing-specific actions.
        
        Actions include:
        - Schedule breaks for workers
        - Reassign workers between lines
        - Call in replacements
        - Issue write-ups
        """
        action_lower = action.lower()
        
        # Break scheduling
        if "break" in action_lower:
            return await self._handle_break_scheduling(action, context)
        
        # Worker reassignment
        elif "reassign" in action_lower or "move" in action_lower:
            return await self._handle_reassignment(action, context)
        
        # Replacement calling
        elif "replacement" in action_lower or "call in" in action_lower:
            return await self._handle_replacement_call(action, context)
        
        # HR actions
        elif "write up" in action_lower or "warning" in action_lower:
            return await self._handle_hr_disciplinary(action, context)
        
        elif "reward" in action_lower or "bonus" in action_lower or "points" in action_lower:
            return await self._handle_hr_reward(action, context)
        
        # Vision alerts
        elif "alert" in action_lower or "vision" in action_lower:
            return await self._handle_vision_alerts(action, context)
        
        # Coverage check
        elif "coverage" in action_lower or "gap" in action_lower:
            return await self._handle_coverage_check(action, context)
        
        # Escalation
        elif "escalate" in action_lower or "human" in action_lower:
            return await self._handle_escalation(action, context)
        
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
        fatigue_report = await check_fatigue_levels()
        
        breaks_scheduled = []
        high_fatigue = fatigue_report.get("high_fatigue", [])
        
        # Strict limit: Only schedule 1 break at a time to prevent mass exodus
        for worker in high_fatigue[:1]: 
            # Only intervene if fatigue is critical (voluntary system handles < 85%)
            if worker["fatigue_level"] < 0.85:
                continue
                
            try:
                break_result = await schedule_break(
                    employee_id=worker["employee_id"],
                    duration_minutes=30 if worker["fatigue_level"] > 0.9 else 15,
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
        import re
        matches = re.findall(r'\d+', action)
        
        from_line = None
        to_line = None
        
        if len(matches) >= 2:
            # Explicit: Reassign from Line X to Line Y
            from_line = int(matches[0])
            to_line = int(matches[1])
        elif len(matches) == 1:
            # Implicit: Reassign to Line X (find source)
            to_line = int(matches[0])
            
            # Find a donor line (most staffed)
            coverage_data = await check_line_coverage(to_line) # Just to init imports if needed, actually need ALL lines
            # We need to scan lines to find one with spare capacity
            roster = await get_shift_roster()
            line_counts = {int(k): len(v) for k, v in roster.get("line_assignments", {}).items()}
            
            # Find line with max staff that isn't the target
            # Default to Line 1 if nothing better found (safe fallback for simulation)
            best_source = 1
            max_staff = 0
            
            for line_num, count in line_counts.items():
                if line_num != to_line and count > max_staff:
                    max_staff = count
                    best_source = line_num
            
            from_line = best_source
            logger.info(f"🤖 Auto-selected source Line {from_line} (Staff: {max_staff}) for target Line {to_line}")
            
        else:
            return {
                "status": "FAILED",
                "reason": "Could not parse line numbers",
                "side_effects": [],
            }
        
        roster = await get_shift_roster()
        from_line_staff = roster.get("line_assignments", {}).get(str(from_line), [])
        
        if not from_line_staff:
            return {
                "status": "FAILED",
                "reason": f"No staff on Line {from_line}",
                "side_effects": [],
            }
        
        # Pick the first available worker
        worker_id = from_line_staff[0]
        
        result = await reassign_worker(
            employee_id=worker_id,
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
    
    async def _handle_hr_disciplinary(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle HR disciplinary action (write-up/warning)."""
        employee_id = context.get("employee_id", "")
        reason = context.get("reason", action)
        
        # Determine action type from text
        if "final" in action.lower():
            action_type = "final_warning"
        elif "written" in action.lower():
            action_type = "written_warning"
        elif "verbal" in action.lower():
            action_type = "verbal_warning"
        else:
            action_type = "coaching"
        
        result = await issue_write_up(
            employee_id=employee_id,
            action_type=action_type,
            reason=reason,
            violation_category=context.get("category", "performance"),
        )
        
        return {
            "status": result.get("status", "SUCCESS"),
            "hr_action": result.get("action"),
            "requires_human": result.get("requires_human_approval", False),
            "side_effects": [f"Issued {action_type} to {employee_id}"],
        }
    
    async def _handle_hr_reward(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle HR reward/bonus points."""
        employee_id = context.get("employee_id", "")
        points = context.get("points", 10)
        
        result = await award_bonus_points(
            employee_id=employee_id,
            points=points,
            reason=context.get("reason", action),
            category=context.get("category", "productivity"),
        )
        
        return {
            "status": result.get("status", "SUCCESS"),
            "reward": result.get("reward"),
            "side_effects": [f"Awarded {points} bonus points to {employee_id}"],
        }
    
    async def _handle_vision_alerts(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle vision system alerts."""
        alerts = await get_recent_vision_alerts(minutes=30)
        
        empty_stations = alerts.get("alerts", {}).get("empty_stations", [])
        
        actions_taken = []
        for station in empty_stations[:3]:  # Handle up to 3
            line = station.get("line")
            if line:
                # Check if we can reassign
                occupancy = await get_all_lines_occupancy()
                overstaffed = occupancy.get("overstaffed_lines", [])
                
                if overstaffed:
                    result = await reassign_worker(
                        employee_id="auto-select",
                        from_line=overstaffed[0],
                        to_line=line,
                        reason="Vision alert: empty station detected",
                    )
                    actions_taken.append(result)
        
        return {
            "status": "SUCCESS",
            "alerts_processed": len(empty_stations),
            "actions_taken": len(actions_taken),
            "side_effects": [f"Processed {len(empty_stations)} vision alerts"],
        }
    
    async def _handle_coverage_check(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check coverage across all lines."""
        coverage_issues = []
        
        for line_num in range(1, 21):
            coverage = await check_line_coverage(line_num)
            if coverage.get("is_critical"):
                coverage_issues.append({
                    "line": line_num,
                    "visual_count": coverage["visual_count"],
                    "status": coverage["status"],
                })
        
        # Escalate if too many critical
        if len(coverage_issues) >= self.CRITICAL_COVERAGE_THRESHOLD:
            await escalate_to_human_supervisor(
                title="Multiple Critical Coverage Gaps",
                description=f"{len(coverage_issues)} lines critically understaffed",
                priority="high",
                requires_decision=True,
            )
        
        return {
            "status": "SUCCESS",
            "critical_lines": len(coverage_issues),
            "issues": coverage_issues,
            "escalated": len(coverage_issues) >= self.CRITICAL_COVERAGE_THRESHOLD,
            "side_effects": [
                f"Identified {len(coverage_issues)} lines with critical coverage"
            ],
        }
    
    async def _handle_escalation(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Escalate to human supervisor."""
        result = await escalate_to_human_supervisor(
            title=context.get("title", "Staffing Issue Requires Attention"),
            description=context.get("description", action),
            priority=context.get("priority", "medium"),
            requires_decision=context.get("requires_decision", False),
        )
        
        return {
            "status": "ESCALATED",
            "escalation": result,
            "side_effects": ["Issue escalated to human supervisor"],
        }
    
    # ========== CRITICAL SITUATION DETECTION ==========
    
    def _detect_critical_situation(self, context: Dict[str, Any]) -> bool:
        """
        Detect staffing emergencies requiring escalation.
        
        Escalation triggers:
        - Multiple lines (3+) critically understaffed
        - Labor regulation violation (worker > 8 hours)
        - Sudden mass absence
        - Unable to maintain minimum operator coverage
        """
        # Check for critical understaffing
        critical_lines = context.get('critical_coverage_lines', [])
        if len(critical_lines) >= self.CRITICAL_COVERAGE_THRESHOLD:
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
        if absent_count >= self.OPERATORS_PER_SHIFT:
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
        - hr_assistant: Handles HR actions
        """
        if subagent_type == "break_scheduler":
            return await self._create_break_scheduler()
        elif subagent_type == "coverage_predictor":
            return await self._create_coverage_predictor()
        elif subagent_type == "hr_assistant":
            return await self._create_hr_assistant()
        else:
            raise ValueError(f"Unknown subagent type: {subagent_type}")
    
    async def _create_break_scheduler(self) -> BaseAgent:
        """Create Break Scheduler subagent."""
        return BaseAgent(
            agent_name="BreakScheduler",
            system_prompt="""You are a specialized Break Scheduler subagent.

Your purpose is to optimize break schedules across all workers to minimize
production disruption while ensuring compliance with labor regulations.

Consider:
- Worker fatigue levels
- Line coverage requirements (min 2 per line, optimal 3)
- Production demand peaks
- Mandatory break regulations
- Operator vs packager positions (operators are more critical)""",
            tools=[
                get_shift_roster,
                check_line_coverage,
                schedule_break,
                check_fatigue_levels,
            ],
            use_flash_model=True,
            thinking_level="medium",
        )
    
    async def _create_coverage_predictor(self) -> BaseAgent:
        """Create Coverage Predictor subagent."""
        return BaseAgent(
            agent_name="CoveragePredictor",
            system_prompt="""You are a specialized Coverage Predictor subagent.

Predict future staffing gaps based on:
- Current fatigue trends
- Scheduled breaks
- Historical absence patterns
- Production demand forecast

Provide proactive recommendations to prevent understaffing.""",
            tools=[
                get_shift_roster,
                check_fatigue_levels,
                calculate_coverage_needs,
                get_all_lines_occupancy,
            ],
            use_flash_model=True,
            thinking_level="medium",
        )
    
    async def _create_hr_assistant(self) -> BaseAgent:
        """Create HR Assistant subagent."""
        return BaseAgent(
            agent_name="HRAssistant",
            system_prompt="""You are a specialized HR Assistant subagent.

Handle performance management including:
- Issue appropriate disciplinary actions
- Award recognition and bonus points
- Escalate high-severity actions to human supervisor

Remember:
- Verbal warnings and coaching are autonomous
- Written/final warnings require human approval
- Always document reasons thoroughly""",
            tools=[
                issue_write_up,
                award_bonus_points,
                get_hr_action_history,
                escalate_to_human_supervisor,
            ],
            use_flash_model=True,
            thinking_level="medium",
        )


"""Staffing tools package."""
from app.tools.staffing.roster_tools import (
    get_shift_roster,
    check_line_coverage,
    call_in_replacement,
    schedule_break,
    calculate_coverage_needs,
    reassign_worker,
    check_fatigue_levels,
)
from app.tools.staffing.hr_actions import (
    issue_write_up,
    award_bonus_points,
    escalate_to_human_supervisor,
    get_hr_action_history,
    get_pending_escalations,
)
from app.tools.staffing.vision_integration import (
    get_recent_vision_alerts,
    get_all_lines_occupancy,
    acknowledge_vision_alert,
)

__all__ = [
    # Roster management
    "get_shift_roster",
    "check_line_coverage",
    "call_in_replacement",
    "schedule_break",
    "calculate_coverage_needs",
    "reassign_worker",
    "check_fatigue_levels",
    # HR actions
    "issue_write_up",
    "award_bonus_points",
    "escalate_to_human_supervisor",
    "get_hr_action_history",
    "get_pending_escalations",
    # Vision integration
    "get_recent_vision_alerts",
    "get_all_lines_occupancy",
    "acknowledge_vision_alert",
]

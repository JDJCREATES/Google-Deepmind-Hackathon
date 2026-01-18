"""
Staffing and workforce management tools for LineWatch AI.

This module provides tools for the Staffing Agent to manage workforce allocation,
break scheduling, coverage prediction, and fatigue monitoring across all lines.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.state.context import shared_context
from app.models.domain import Employee
from app.utils.logging import get_agent_logger


logger = get_agent_logger("StaffingTools")


# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class LineCoverageInput(BaseModel):
    """Input schema for checking line coverage."""
    line_number: int = Field(
        description="Production line number (1-20)",
        ge=1,
        le=20
    )


class BreakScheduleInput(BaseModel):
    """Input schema for scheduling breaks."""
    employee_id: str = Field(description="Employee identifier")
    duration_minutes: int = Field(
        description="Break duration in minutes",
        ge=15,
        le=60
    )
    preferred_time: Optional[str] = Field(
        default=None,
        description="Preferred break time (HH:MM format)"
    )


class ReassignmentInput(BaseModel):
    """Input schema for worker reassignment."""
    employee_id: str = Field(description="Employee to reassign")
    from_line: int = Field(description="Current line", ge=1, le=20)
    to_line: int = Field(description="Target line", ge=1, le=20)
    reason: str = Field(description="Reason for reassignment", min_length=10)


class CoverageNeedsInput(BaseModel):
    """Input schema for calculating coverage needs."""
    target_throughput_total: float = Field(
        description="Target total throughput for all lines",
        gt=0
    )
    shift_duration_hours: int = Field(
        default=8,
        description="Shift duration in hours",
        ge=4,
        le=12
    )


# ============================================================================
# STAFFING TOOLS
# ============================================================================

@tool
async def get_shift_roster() -> Dict[str, Any]:
    """
    Get current shift roster with all employee assignments.
    
    Returns comprehensive staffing information including:
    - Total staff count
    - Employees per line
    - Hours worked  
    - Fatigue levels
    - Break status
    
    Returns:
        Dictionary containing full roster details
    """
    logger.info("📋 Getting current shift roster")
    
    try:
        # Get employees from shared context
        employees = await shared_context.employees
        department = await shared_context.get_department()
        
        # Build roster
        roster = {
            "timestamp": datetime.now().isoformat(),
            "total_staff": len(employees),
            "employees": [],
            "line_assignments": {},
            "on_break": [],
            "high_fatigue": [],
        }
        
        for emp_id, employee in employees.items():
            emp_data = {
                "employee_id": emp_id,
                "name": employee.name,
                "assigned_line": employee.assigned_line,
                "skills": employee.skills,
                "hours_worked": employee.hours_worked,
                "fatigue_level": employee.fatigue_level,
                "on_break": employee.on_break,
            }
            roster["employees"].append(emp_data)
            
            # Group by line
            if employee.assigned_line:
                line_key = str(employee.assigned_line)
                if line_key not in roster["line_assignments"]:
                    roster["line_assignments"][line_key] = []
                roster["line_assignments"][line_key].append(emp_id)
            
            # Track break status
            if employee.on_break:
                roster["on_break"].append(emp_id)
            
            # Track high fatigue (>0.7)
            if employee.fatigue_level > 0.7:
                roster["high_fatigue"].append(emp_id)
        
        logger.info(
            f"✅ Roster: {len(employees)} staff, "
            f"{len(roster['on_break'])} on break, "
            f"{len(roster['high_fatigue'])} high fatigue"
        )
        
        return roster
        
    except Exception as e:
        logger.error(f"❌ Error getting shift roster: {e}")
        raise


@tool(args_schema=LineCoverageInput)
async def check_line_coverage(line_number: int) -> Dict[str, Any]:
    """
    Check if a specific line has adequate staffing coverage.
    
    Analyzes both assigned staff and visual confirmation from cameras.
    Determines if coverage meets minimum requirements (2 workers minimum,
    3 optimal).
    
    Args:
        line_number: Line to check (1-20)
        
    Returns:
        Dictionary with coverage status and recommendations
    """
    logger.info(f"👥 Checking coverage for Line {line_number}")
    
    try:
        from app.services.vision_service import vision_service
        
        # Get assigned staff
        employees = await shared_context.employees
        assigned = [
            emp for emp in employees.values()
            if emp.assigned_line == line_number
        ]
        assigned_count = len(assigned)
        assigned_ids = [emp.employee_id for emp in assigned]
        
        # Get visual confirmation
        visual_count = await vision_service.get_line_occupancy(line_number)
        
        # Assess coverage
        is_adequate = visual_count >= 2
        is_optimal = visual_count >= 3
        is_critical = visual_count < 2
        
        # Generate recommendation
        if is_critical:
            recommendation = "URGENT: Assign additional staff immediately"
            status = "CRITICAL"
        elif not is_optimal:
            recommendation = "Consider assigning one more worker for optimal efficiency"
            status = "SUBOPTIMAL"
        else:
            recommendation = "Coverage is adequate"
            status = "OPTIMAL"
        
        result = {
            "line_number": line_number,
            "assigned_count": assigned_count,
            "assigned_staff": assigned_ids,
            "visual_count": visual_count,
            "minimum_required": 2,
            "optimal_count": 3,
            "is_adequate": is_adequate,
            "is_optimal": is_optimal,
            "is_critical": is_critical,
            "status": status,
            "recommendation": recommendation,
            "timestamp": datetime.now().isoformat(),
        }
        
        logger.info(
            f"✅ Line {line_number} coverage: {status} "
            f"(assigned={assigned_count}, visual={visual_count})"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error checking coverage for Line {line_number}: {e}")
        raise


@tool
async def call_in_replacement() -> Dict[str, Any]:
    """
    Call in a replacement worker for unexpected absence.
    
    Simulates calling a backup worker from the on-call list.
    In production, would integrate with scheduling system and
    send actual notifications.
    
    Returns:
        Dictionary with replacement worker details and ETA
    """
    logger.info("📞 Calling in replacement worker")
    
    try:
        # Simulate finding available replacement
        import random
        
        replacement = {
            "employee_id": f"EMP-BACKUP-{random.randint(100, 999)}",
            "name": f"Backup Worker {random.randint(1, 50)}",
            "skills": ["general_production"],
            "eta_minutes": random.randint(20, 45),
            "call_time": datetime.now().isoformat(),
            "estimated_arrival": (
                datetime.now() + timedelta(minutes=random.randint(20, 45))
            ).isoformat(),
        }
        
        logger.info(
            f"✅ Replacement called: {replacement['name']}, "
            f"ETA {replacement['eta_minutes']}min"
        )
        
        return {
            "status": "SUCCESS",
            "replacement": replacement,
            "message": f"Replacement worker will arrive in {replacement['eta_minutes']} minutes",
        }
        
    except Exception as e:
        logger.error(f"❌ Error calling replacement: {e}")
        raise


@tool(args_schema=BreakScheduleInput)
async def schedule_break(
    employee_id: str,
    duration_minutes: int,
    preferred_time: Optional[str] = None
) -> Dict[str, Any]:
    """
    Schedule a break for an employee without disrupting production.
    
    Intelligently schedules breaks considering:
    - Line coverage requirements
    - Production demands
    - Employee fatigue levels
    - Other scheduled breaks
    
    Args:
        employee_id: Employee to schedule break for
        duration_minutes: Break duration (15-60 minutes)
        preferred_time: Optional preferred time (HH:MM)
        
    Returns:
        Dictionary with scheduled break time and coverage plan
    """
    logger.info(
        f"⏰ Scheduling {duration_minutes}min break for {employee_id}"
    )
    
    try:
        employees = await shared_context.employees
        employee = employees.get(employee_id)
        
        if not employee:
            raise ValueError(f"Employee {employee_id} not found")
        
        # Determine break type
        if duration_minutes <= 15:
            break_type = "SHORT"
        elif duration_minutes <= 30:
            break_type = "STANDARD"
        else:
            break_type = "MEAL"
        
        # Calculate optimal break time (simplified)
        now = datetime.now()
        if preferred_time:
            # Parse preferred time
            hour, minute = map(int, preferred_time.split(":"))
            scheduled_time = now.replace(hour=hour, minute=minute)
        else:
            # Schedule 15 minutes from now
            scheduled_time = now + timedelta(minutes=15)
        
        # Check if line coverage maintained
        line_num = employee.assigned_line
        if line_num:
            coverage = await check_line_coverage(line_num)
            # If critical coverage, delay break
            if coverage["is_critical"]:
                scheduled_time = now + timedelta(minutes=30)
                note = "Delayed due to critical coverage on line"
            else:
                note = "No coverage conflicts"
        else:
            note = "Employee not assigned to line"
        
        # TRIGGER SIMULATION ACTION
        # This bridges the gap between Agent Decision and Simulation Execution
        from app.services.simulation import simulation
        sim_triggered = simulation.trigger_operator_break(employee_id)
        
        sim_note = "Simulation executed" if sim_triggered else "Simulation trigger failed (operator not found)"
        
        result = {
            "employee_id": employee_id,
            "employee_name": employee.name,
            "break_type": break_type,
            "duration_minutes": duration_minutes,
            "scheduled_start": scheduled_time.isoformat(),
            "scheduled_end": (
                scheduled_time + timedelta(minutes=duration_minutes)
            ).isoformat(),
            "assigned_line": line_num,
            "coverage_note": note,
            "simulation_status": sim_note,
            "status": "SCHEDULED",
        }
        
        logger.info(
            f"✅ Break scheduled for {employee_id}: "
            f"{scheduled_time.strftime('%H:%M')} ({duration_minutes}min) - {sim_note}"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error scheduling break for {employee_id}: {e}")
        raise


@tool(args_schema=CoverageNeedsInput)
async def calculate_coverage_needs(
    target_throughput_total: float,
    shift_duration_hours: int = 8
) -> Dict[str, Any]:
    """
    Calculate staffing requirements based on production targets.
    
    Determines optimal staff count considering:
    - Total throughput targets
    - Worker productivity rates
    - Shift duration and break requirements
    - Skill requirements
    
    Args:
        target_throughput_total: Total target throughput for all lines
        shift_duration_hours: Shift length in hours
        
    Returns:
        Dictionary with required staff count and allocation
    """
    logger.info(
        f"📊 Calculating coverage needs for "
        f"{target_throughput_total} units over {shift_duration_hours}h"
    )
    
    try:
        # Simplified calculation
        # Assume 100 units/hour per worker optimal productivity
        units_per_worker_hour = 100
        
        total_worker_hours_needed = (
            target_throughput_total / units_per_worker_hour
        )
        
        # Account for breaks (15min every 4 hours)
        breaks_per_shift = shift_duration_hours // 4
        break_hours = breaks_per_shift * 0.25  # 15 min = 0.25 hour
        
        effective_hours_per_worker = shift_duration_hours - break_hours
        
        staff_needed = int(
            total_worker_hours_needed / effective_hours_per_worker
        ) + 1
        
        # Allocate across 20 lines
        staff_per_line = max(2, staff_needed // 20)
        
        result = {
            "target_throughput_total": target_throughput_total,
            "shift_duration_hours": shift_duration_hours,
            "total_staff_needed": staff_needed,
            "staff_per_line": staff_per_line,
            "effective_hours_per_worker": effective_hours_per_worker,
            "total_worker_hours_needed": round(total_worker_hours_needed, 2),
            "break_allowance_hours": break_hours,
            "calculation_timestamp": datetime.now().isoformat(),
        }
        
        logger.info(
            f"✅ Coverage needs: {staff_needed} total staff, "
            f"{staff_per_line} per line"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error calculating coverage needs: {e}")
        raise


@tool(args_schema=ReassignmentInput)
async def reassign_worker(
    employee_id: str,
    from_line: int,
    to_line: int,
    reason: str
) -> Dict[str, Any]:
    """
    Reassign a worker from one line to another dynamically.
    
    Moves worker between lines while ensuring both source and
    target lines maintain minimum coverage requirements.
    
    Args:
        employee_id: Employee to reassign
        from_line: Current line assignment
        to_line: New line assignment
        reason: Reason for reassignment
        
    Returns:
        Dictionary with reassignment confirmation and coverage impact
    """
    logger.info(
        f"🔄 Reassigning {employee_id}: Line {from_line} → Line {to_line}"
    )
    
    try:
        employees = await shared_context.employees
        employee = employees.get(employee_id)
        
        if not employee:
            raise ValueError(f"Employee {employee_id} not found")
        
        if employee.assigned_line != from_line:
            raise ValueError(
                f"Employee not assigned to Line {from_line}"
            )
        
        # Check coverage impact
        from_coverage = await check_line_coverage(from_line)
        to_coverage = await check_line_coverage(to_line)
        
        # Validate reassignment won't critically understaff from_line
        if from_coverage["visual_count"] <= 2:
            return {
                "status": "BLOCKED",
                "reason": "Source line would be critically understaffed",
                "from_line_coverage": from_coverage,
                "to_line_coverage": to_coverage,
            }
        
        # Perform reassignment
        employee.assigned_line = to_line
        
        # Update department line assignments
        department = await shared_context.get_department()
        from_line_obj = department.get_line(from_line)
        to_line_obj = department.get_line(to_line)
        
        if from_line_obj and employee_id in from_line_obj.assigned_staff:
            from_line_obj.assigned_staff.remove(employee_id)
        
        if to_line_obj:
            to_line_obj.assigned_staff.append(employee_id)
        
        # TRIGGER SIMULATION MOVEMENT
        from app.services.simulation import simulation
        sim_moved = simulation.move_operator_to_line(employee_id, to_line)
        sim_note = "Moving to new line" if sim_moved else "Simulation move failed (path not found)"
        
        result = {
            "status": "SUCCESS",
            "employee_id": employee_id,
            "employee_name": employee.name,
            "from_line": from_line,
            "to_line": to_line,
            "reason": reason,
            "from_line_remaining_count": from_coverage["visual_count"] - 1,
            "to_line_new_count": to_coverage["visual_count"] + 1,
            "simulation_status": sim_note, # Added for debugging
            "timestamp": datetime.now().isoformat(),
        }
        
        logger.info(
            f"✅ Worker reassigned: {employee_id} now on Line {to_line} ({sim_note})"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error reassigning worker: {e}")
        raise


@tool
async def check_fatigue_levels() -> Dict[str, Any]:
    """
    Check fatigue levels for all employees on current shift.
    
    Identifies workers with high fatigue (>6 hours worked) and
    recommends break scheduling or shift adjustments.
    
    Returns:
        Dictionary with fatigue analysis and recommendations
    """
    logger.info("😴 Checking employee fatigue levels")
    
    try:
        employees = await shared_context.employees
        
        fatigue_report = {
            "timestamp": datetime.now().isoformat(),
            "total_employees": len(employees),
            "low_fatigue": [],  # < 0.5 (< 4 hours)
            "moderate_fatigue": [],  # 0.5-0.7 (4-6 hours)
            "high_fatigue": [],  # > 0.7 (> 6 hours)
            "critical_fatigue": [],  # > 0.9 (> 8 hours)
            "recommendations": [],
        }
        
        # Fog of War: Only report fatigue for visible employees
        from app.services.simulation import simulation
        
        # In a real microservice architecture, this would be an API call
        # For this monolith, we access the service directly
        visible_ids = simulation.get_visible_operator_ids()
        
        for emp_id, employee in employees.items():
            # Fog of War check
            is_visible = emp_id in visible_ids
            
            fatigue_data = {
                "employee_id": emp_id,
                "name": employee.name,
                "fatigue_level": employee.fatigue_level if is_visible else 0.0, # Mask actual fatigue
                "hours_worked": employee.hours_worked, # This is known (HR data)
                "assigned_line": employee.assigned_line,
                "is_visible": is_visible
            }
            
            if not is_visible:
                # If not visible, we assume low fatigue physics-wise
                # But we still report them as "low_fatigue" or separate category?
                # For now, just assume they are fine unless seen otherwise
                fatigue_report["low_fatigue"].append(fatigue_data)
                continue
            
            if employee.fatigue_level > 0.9:
                fatigue_report["critical_fatigue"].append(fatigue_data)
                fatigue_report["recommendations"].append(
                    f"{emp_id}: URGENT - End shift immediately (labor violation)"
                )
            elif employee.fatigue_level > 0.7:
                fatigue_report["high_fatigue"].append(fatigue_data)
                fatigue_report["recommendations"].append(
                    f"{emp_id}: Schedule break or consider replacement"
                )
            elif employee.fatigue_level > 0.5:
                fatigue_report["moderate_fatigue"].append(fatigue_data)
            else:
                fatigue_report["low_fatigue"].append(fatigue_data)
        
        logger.info(
            f"✅ Fatigue check: "
            f"{len(fatigue_report['high_fatigue'])} high fatigue, "
            f"{len(fatigue_report['critical_fatigue'])} critical"
        )
        
        return fatigue_report
        
    except Exception as e:
        logger.error(f"❌ Error checking fatigue levels: {e}")
        raise

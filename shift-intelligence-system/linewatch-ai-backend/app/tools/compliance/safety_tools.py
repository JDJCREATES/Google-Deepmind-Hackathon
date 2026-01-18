"""
Compliance and safety monitoring tools for LineWatch AI.

This module provides tools for the Compliance Agent to monitor safety violations,
temperature compliance, hygiene protocols, and generate compliance reports.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.state.context import shared_context
from app.models.domain import SafetyViolation, SafetyViolationType, Alert, AlertSeverity
from app.utils.logging import get_agent_logger


logger = get_agent_logger("ComplianceTools")


# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class ViolationTimeWindowInput(BaseModel):
    """Input schema for getting violations in time window."""
    time_window_minutes: int = Field(
        default=60,
        description="Time window in minutes to look back",
        ge=5,
        le=1440
    )
    camera_id: Optional[str] = Field(
        default=None,
        description="Specific camera ID (CAM-01 to CAM-05)"
    )


class ViolationSeverityInput(BaseModel):
    """Input schema for classifying violation severity."""
    violation_id: str = Field(description="Violation identifier")


class SafetyAlarmInput(BaseModel):
    """Input schema for triggering safety alarms."""
    violation_id: str = Field(description="Violation causing alarm")
    message: str = Field(description="Alarm message", min_length=10)


class CorrectiveActionInput(BaseModel):
    """Input schema for logging corrective actions."""
    violation_id: str = Field(description="Violation being addressed")
    action_taken: str = Field(description="Action taken", min_length=10)
    resolved: bool = Field(description="Whether violation is now resolved")


class ComplianceReportInput(BaseModel):
    """Input schema for generating compliance reports."""
    period_hours: int = Field(
        default=8,
        description="Reporting period in hours",
        ge=1,
        le=168
    )


# ============================================================================
# COMPLIANCE TOOLS
# ============================================================================

@tool(args_schema=ViolationTimeWindowInput)
async def get_safety_violations(
    time_window_minutes: int = 60,
    camera_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieve safety violations from camera vision service.
    
    Gets violations detected by the vision service within specified
    time window. Can filter by specific camera if needed.
    
    Args:
        time_window_minutes: Look back window in minutes (default 60)
        camera_id: Optional specific camera (CAM-01 to CAM-05)
        
    Returns:
        Dictionary containing violations list and summary statistics
    """
    logger.info(
        f"🔍 Getting safety violations "
        f"(window: {time_window_minutes}min, camera: {camera_id or 'all'})"
    )
    
    try:
        from app.services.vision_service import vision_service
        
        # Get violations from vision service
        if camera_id:
            violations = await vision_service.detect_safety_violations(camera_id=camera_id)
        else:
            # Get from all cameras
            violations = await vision_service.detect_safety_violations()
        
        # Filter by time window
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        recent_violations = [
            v for v in violations
            if v.timestamp >= cutoff_time
        ]
        
        # Group by type
        by_type = {}
        for violation in recent_violations:
            vtype = violation.violation_type.value
            if vtype not in by_type:
                by_type[vtype] = []
            by_type[vtype].append({
                "violation_id": violation.violation_id,
                "line_number": violation.line_number,
                "camera_id": violation.camera_id,
                "confidence": violation.confidence,
                "description": violation.description,
                "acknowledged": violation.acknowledged,
                "timestamp": violation.timestamp.isoformat(),
            })
        
        # Count by severity (simplified - would use classifier)
        critical_count = sum(
            1 for v in recent_violations
            if v.violation_type in [
                SafetyViolationType.NO_PPE,
                SafetyViolationType.UNSAFE_PROXIMITY
            ]
        )
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "time_window_minutes": time_window_minutes,
            "camera_filter": camera_id,
            "total_violations": len(recent_violations),
            "critical_violations": critical_count,
            "violations_by_type": by_type,
            "violations": [
                {
                    "violation_id": v.violation_id,
                    "type": v.violation_type.value,
                    "line": v.line_number,
                    "camera": v.camera_id,
                    "confidence": v.confidence,
                    "description": v.description,
                }
                for v in recent_violations[:20]  # Limit to 20 most recent
            ],
        }
        
        logger.info(
            f"✅ Found {len(recent_violations)} violations "
            f"({critical_count} critical)"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error getting safety violations: {e}")
        raise


@tool(args_schema=ViolationSeverityInput)
async def classify_violation_severity(violation_id: str) -> Dict[str, Any]:
    """
    Classify severity of a safety violation using AI reasoning.
    
    Analyzes violation context to determine appropriate severity level:
    - CRITICAL: Immediate danger, requires instant action
    - HIGH: Significant risk, needs urgent attention  
    - MEDIUM: Moderate risk, should be addressed soon
    - LOW: Minor issue, track for patterns
    
    Args:
        violation_id: Violation to classify
        
    Returns:
        Dictionary with severity classification and reasoning
    """
    logger.info(f"⚖️ Classifying severity for violation {violation_id}")
    
    try:
        # Get violation from shared context
        violations = await shared_context.safety_violations
        violation = next(
            (v for v in violations if v.violation_id == violation_id),
            None
        )
        
        if not violation:
            raise ValueError(f"Violation {violation_id} not found")
        
        # Severity classification logic
        severity = "MEDIUM"  # Default
        risk_factors = []
        
        # Type-based severity
        if violation.violation_type == SafetyViolationType.NO_PPE:
            severity = "CRITICAL"
            risk_factors.append("Worker safety at immediate risk")
        elif violation.violation_type == SafetyViolationType.UNSAFE_PROXIMITY:
            severity = "CRITICAL"
            risk_factors.append("Proximity to machinery danger")
        elif violation.violation_type == SafetyViolationType.SPILL_DETECTED:
            severity = "HIGH"
            risk_factors.append("Slip/fall hazard")
        elif violation.violation_type == SafetyViolationType.BLOCKED_EXIT:
            severity = "HIGH"
            risk_factors.append("Emergency egress blocked")
        elif violation.violation_type == SafetyViolationType.TEMPERATURE_VIOLATION:
            severity = "MEDIUM"
            risk_factors.append("Cold chain integrity at risk")
        else:
            severity = "LOW"
        
        # Confidence modifier
        if violation.confidence > 0.95 and severity in ["CRITICAL", "HIGH"]:
            risk_factors.append(f"High confidence detection: {violation.confidence:.2f}")
        elif violation.confidence < 0.7:
            # Downgrade severity for low confidence
            severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
            current_idx = severity_order.index(severity)
            if current_idx < len(severity_order) - 1:
                severity = severity_order[current_idx + 1]
            risk_factors.append(f"Low confidence: {violation.confidence:.2f}")
        
        # Recommendations
        recommendations = []
        if severity == "CRITICAL":
            recommendations.append("Trigger immediate safety alarm")
            recommendations.append("Halt affected line until resolved")
            recommendations.append("Escalate to Master Orchestrator")
        elif severity == "HIGH":
            recommendations.append("Alert line supervisor immediately")
            recommendations.append("Dispatch safety personnel")
            recommendations.append("Log in incident report")
        elif severity == "MEDIUM":
            recommendations.append("Notify supervisor")
            recommendations.append("Schedule corrective action")
        else:
            recommendations.append("Log for pattern tracking")
        
        result = {
            "violation_id": violation_id,
            "violation_type": violation.violation_type.value,
            "classified_severity": severity,
            "confidence": violation.confidence,
            "risk_factors": risk_factors,
            "recommendations": recommendations,
            "line_number": violation.line_number,
            "timestamp": datetime.now().isoformat(),
        }
        
        logger.info(
            f"✅ Violation {violation_id} classified as {severity}"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error classifying violation: {e}")
        raise


@tool
async def check_all_temperatures() -> Dict[str, Any]:
    """
    Check temperature compliance across all 20 production lines.
    
    Verifies cold chain integrity by checking each line's temperature
    against required range (0-4°C for food production).
    
    Returns:
        Dictionary with compliance status and violations
    """
    logger.info("🌡️ Checking temperature compliance for all lines")
    
    try:
        department = await shared_context.get_department()
        
        compliance_report = {
            "timestamp": datetime.now().isoformat(),
            "required_range_celsius": {"min": 0, "max": 4},
            "total_lines": 20,
            "compliant_lines": 0,
            "warning_lines": [],  # Close to threshold
            "violation_lines": [],  # Out of range
            "line_temperatures": {},
        }
        
        for line_num in range(1, 21):
            line = department.get_line(line_num)
            if not line:
                continue
            
            temp = line.temperature
            compliance_report["line_temperatures"][str(line_num)] = temp
            
            # Check compliance
            if 0 <= temp <= 4:
                compliance_report["compliant_lines"] += 1
            elif 4 < temp <= 6:
                compliance_report["warning_lines"].append({
                    "line": line_num,
                    "temperature": temp,
                    "status": "WARNING - Approaching limit",
                })
            else:
                compliance_report["violation_lines"].append({
                    "line": line_num,
                    "temperature": temp,
                    "status": "VIOLATION - Out of range",
                    "severity": "CRITICAL" if temp > 8 or temp < -2 else "HIGH",
                })
        
        # Overall status
        if len(compliance_report["violation_lines"]) > 0:
            compliance_report["overall_status"] = "NON_COMPLIANT"
        elif len(compliance_report["warning_lines"]) > 0:
            compliance_report["overall_status"] = "WARNING"
        else:
            compliance_report["overall_status"] = "COMPLIANT"
        
        logger.info(
            f"✅ Temperature check: {compliance_report['overall_status']} "
            f"({compliance_report['compliant_lines']}/{20} compliant)"
        )
        
        return compliance_report
        
    except Exception as e:
        logger.error(f"❌ Error checking temperatures: {e}")
        raise


@tool(args_schema=SafetyAlarmInput)
async def trigger_safety_alarm(
    violation_id: str,
    message: str
) -> Dict[str, Any]:
    """
    Trigger safety alarm for critical situations.
    
    Activates alarm system for dangerous violations requiring
    immediate attention. Creates high-priority alert in system
    AND stops the affected production line.
    
    Args:
        violation_id: Violation triggering alarm
        message: Alarm message to display/announce
        
    Returns:
        Dictionary with alarm confirmation and response protocol
    """
    logger.warning(f"🚨 SAFETY ALARM TRIGGERED: {violation_id}")
    
    try:
        # Get violation to find line number
        violations = await shared_context.safety_violations
        violation = next(
            (v for v in violations if v.violation_id == violation_id),
            None
        )
        
        line_number = violation.line_number if violation else None
        
        # Create critical alert
        alert = Alert(
            alert_id=f"ALARM-{violation_id}",
            timestamp=datetime.now(),
            severity=AlertSeverity.CRITICAL,
            source="ComplianceAgent",
            title=f"SAFETY ALARM: {violation_id}",
            description=message,
            line_number=line_number,
            resolved=False,
        )
        
        await shared_context.add_alert(alert)
        
        sim_status = "Simulation not connected"
        if line_number:
            from app.services.simulation import simulation
            stopped = simulation.emergency_stop_line(line_number)
            sim_status = "Line STOPPED via Simulation" if stopped else "Failed to stop line"
        
        result = {
            "alarm_id": alert.alert_id,
            "violation_id": violation_id,
            "message": message,
            "triggered_at": alert.timestamp.isoformat(),
            "severity": "CRITICAL",
            "simulation_action": sim_status,
            "response_protocol": [
                "Safety personnel dispatched",
                "Line supervisor notified",
                f"Production halt on Line {line_number}" if line_number else "Production halt requested",
                "Incident logged for investigation",
            ],
            "estimated_response_time": "< 2 minutes",
        }
        
        logger.warning(f"🚨 Alarm {alert.alert_id} activated - {sim_status}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error triggering safety alarm: {e}")
        raise


@tool(args_schema=CorrectiveActionInput)
async def log_corrective_action(
    violation_id: str,
    action_taken: str,
    resolved: bool
) -> Dict[str, Any]:
    """
    Log corrective action taken for a safety violation.
    
    Documents response to violation for compliance audit trail.
    Marks violation as resolved if corrective action successful.
    
    Args:
        violation_id: Violation being addressed
        action_taken: Description of corrective action
        resolved: Whether violation is now resolved
        
    Returns:
        Dictionary confirming action logged
    """
    logger.info(f"📝 Logging corrective action for {violation_id}")
    
    try:
        # Update violation status
        violations = await shared_context.safety_violations
        violation = next(
            (v for v in violations if v.violation_id == violation_id),
            None
        )
        
        if violation:
            violation.acknowledged = True
            if resolved:
                violation.resolved_at = datetime.now()
        
        # Log action
        action_log = {
            "action_id": f"ACTION-{int(datetime.now().timestamp())}",
            "violation_id": violation_id,
            "action_taken": action_taken,
            "resolved": resolved,
            "timestamp": datetime.now().isoformat(),
            "logged_by": "ComplianceAgent",
        }
        
        # In production, would write to audit database
        
        logger.info(
            f"✅ Corrective action logged for {violation_id} "
            f"(resolved: {resolved})"
        )
        
        return action_log
        
    except Exception as e:
        logger.error(f"❌ Error logging corrective action: {e}")
        raise


@tool(args_schema=ComplianceReportInput)
async def generate_compliance_report(period_hours: int = 8) -> Dict[str, Any]:
    """
    Generate comprehensive compliance report for specified period.
    
    Aggregates all compliance data including safety violations,
    temperature compliance, corrective actions, and incident statistics.
    
    Args:
        period_hours: Reporting period in hours (default 8 for shift)
        
    Returns:
        Dictionary with full compliance report
    """
    logger.info(f"📊 Generating compliance report ({period_hours}h period)")
    
    try:
        # Get violations in period
        violations_data = await get_safety_violations(
            time_window_minutes=period_hours * 60
        )
        
        # Get temperature compliance
        temp_data = await check_all_temperatures()
        
        # Build report
        report = {
            "report_id": f"COMPLIANCE-{int(datetime.now().timestamp())}",
            "period_hours": period_hours,
            "period_start": (
                datetime.now() - timedelta(hours=period_hours)
            ).isoformat(),
            "period_end": datetime.now().isoformat(),
            "generated_at": datetime.now().isoformat(),
            
            "safety_violations": {
                "total": violations_data["total_violations"],
                "critical": violations_data["critical_violations"],
                "by_type": violations_data["violations_by_type"],
            },
            
            "temperature_compliance": {
                "status": temp_data["overall_status"],
                "compliant_lines": temp_data["compliant_lines"],
                "violations": len(temp_data["violation_lines"]),
                "warnings": len(temp_data["warning_lines"]),
            },
            
            "overall_compliance_score": None,  # Calculate below
            "recommendations": [],
        }
        
        # Calculate compliance score (simplified)
        score = 100.0
        score -= violations_data["critical_violations"] * 10
        score -= violations_data["total_violations"] * 2
        score -= len(temp_data["violation_lines"]) * 5
        score = max(0, score)
        report["overall_compliance_score"] = round(score, 2)
        
        # Recommendations
        if violations_data["critical_violations"] > 0:
            report["recommendations"].append(
                "URGENT: Address critical safety violations immediately"
            )
        if temp_data["overall_status"] == "NON_COMPLIANT":
            report["recommendations"].append(
                "Temperature violations detected - inspect refrigeration systems"
            )
        if score < 80:
            report["recommendations"].append(
                "Compliance score below acceptable threshold - review safety protocols"
            )
        
        logger.info(
            f"✅ Compliance report generated: Score {score:.1f}/100"
        )
        
        return report
        
    except Exception as e:
        logger.error(f"❌ Error generating compliance report: {e}")
        raise

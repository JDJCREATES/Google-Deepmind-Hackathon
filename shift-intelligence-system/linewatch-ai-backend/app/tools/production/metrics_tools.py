"""
Production monitoring tools for LineWatch AI.

This module provides tools for the Production Agent to monitor and analyze
production line performance across all 20 lines.
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.state.context import shared_context
from app.models.domain import LineStatus, ProductionLine
from app.utils.logging import get_agent_logger


logger = get_agent_logger("ProductionTools")


# ============================================================================
# INPUT SCHEMAS (Pydantic models for tool validation)
# ============================================================================

class LineMetricsInput(BaseModel):
    """Input schema for getting metrics of a specific line."""
    line_number: int = Field(
        description="Production line number (1-20)",
        ge=1,
        le=20
    )


class ThroughputTrendInput(BaseModel):
    """Input schema for analyzing throughput trends."""
    line_number: int = Field(
        description="Production line number to analyze",
        ge=1,
        le=20
    )
    time_window_minutes: int = Field(
        default=30,
        description="Time window for trend analysis in minutes",
        ge=5,
        le=480
    )


class BottleneckPredictionInput(BaseModel):
    """Input schema for bottleneck prediction."""
    line_number: Optional[int] = Field(
        default=None,
        description="Specific line to analyze, or None for all lines",
        ge=1,
        le=20
    )


class MaintenanceRequestInput(BaseModel):
    """Input schema for requesting maintenance."""
    line_number: int = Field(
        description="Line requiring maintenance",
        ge=1,
        le=20
    )
    priority: str = Field(
        description="Priority level: CRITICAL, HIGH, MEDIUM, or LOW",
        pattern="^(CRITICAL|HIGH|MEDIUM|LOW)$"
    )
    reason: str = Field(
        description="Reason for maintenance request",
        min_length=10,
        max_length=500
    )


# ============================================================================
# PRODUCTION TOOLS
# ============================================================================

@tool(args_schema=LineMetricsInput)
async def get_line_metrics(line_number: int) -> Dict[str, Any]:
    """
    Get current performance metrics for a specific production line.
    
    Retrieves real-time data including:
    - Throughput (units/minute)
    - Efficiency (0.0 to 1.0)
    - Health score (0-100)
    - Temperature (Celsius)
    - Current status
    - Assigned staff count
    - Active alerts
    
    Args:
        line_number: Production line number (1-20)
        
    Returns:
        Dictionary containing all current metrics for the line
        
    Raises:
        ValueError: If line_number is invalid
    """
    logger.info(f"📊 Getting metrics for Line {line_number}")
    
    try:
        department = await shared_context.get_department()
        line = department.get_line(line_number)
        
        if not line:
            raise ValueError(f"Line {line_number} not found")
        
        metrics = {
            "line_number": line.line_number,
            "status": line.status.value,
            "current_throughput": line.current_throughput,
            "target_throughput": line.target_throughput,
            "efficiency": line.efficiency,
            "performance_ratio": line.performance_ratio,
            "health_score": line.health_score,
            "temperature": line.temperature,
            "assigned_staff": len(line.assigned_staff),
            "staff_names": line.assigned_staff,
            "alert_count": len(line.alerts),
            "alerts": line.alerts,
            "last_maintenance": line.last_maintenance.isoformat() if line.last_maintenance else None,
            "timestamp": datetime.now().isoformat(),
        }
        
        logger.info(
            f"✅ Line {line_number}: "
            f"Status={line.status.value}, "
            f"Health={line.health_score:.1f}, "
            f"Efficiency={line.efficiency:.2f}"
        )
        
        return metrics
        
    except Exception as e:
        logger.error(f"❌ Error getting metrics for Line {line_number}: {e}")
        raise


@tool
async def get_all_line_metrics() -> Dict[str, Any]:
    """
    Get current performance metrics for all 20 production lines.
    
    Provides a comprehensive overview of the entire production floor,
    including aggregated statistics and per-line details.
    
    Returns:
        Dictionary containing:
        - Summary statistics (total throughput, average efficiency, etc.)
        - List of all line metrics
        - Lines grouped by status
        - Lines requiring attention
        
    This tool is ideal for the Production Agent's regular monitoring loop.
    """
    logger.info("📊 Getting metrics for all lines")
    
    try:
        department = await shared_context.get_department()
        
        # Collect all line data
        all_lines = []
        status_groups = {
            "operational": [],
            "warning": [],
            "degraded": [],
            "failure": [],
            "maintenance": []
        }
        
        total_throughput = 0.0
        total_efficiency = 0.0
        health_scores = []
        
        for line_num in range(1, 21):
            line = department.get_line(line_num)
            if not line:
                continue
                
            line_data = {
                "line_number": line.line_number,
                "status": line.status.value,
                "throughput": line.current_throughput,
                "efficiency": line.efficiency,
                "health": line.health_score,
                "temperature": line.temperature,
                "staff_count": len(line.assigned_staff),
            }
            
            all_lines.append(line_data)
            status_groups[line.status.value].append(line_num)
            
            total_throughput += line.current_throughput
            total_efficiency += line.efficiency
            health_scores.append(line.health_score)
        
        # Calculate aggregates
        avg_efficiency = total_efficiency / 20 if all_lines else 0.0
        avg_health = sum(health_scores) / len(health_scores) if health_scores else 0.0
        
        # Identify lines needing attention
        attention_needed = [
            line["line_number"] for line in all_lines
            if line["health"] < 60 or line["efficiency"] < 0.7
        ]
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_throughput": round(total_throughput, 2),
                "average_efficiency": round(avg_efficiency, 2),
                "average_health": round(avg_health, 2),
                "total_lines": 20,
                "operational_lines": len(status_groups["operational"]),
            },
            "status_distribution": status_groups,
            "lines": all_lines,
            "attention_needed": attention_needed,
        }
        
        logger.info(
            f"✅ All lines: "
            f"Throughput={total_throughput:.1f}, "
            f"AvgEfficiency={avg_efficiency:.2f}, "
            f"AvgHealth={avg_health:.1f}"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error getting all line metrics: {e}")
        raise


@tool(args_schema=ThroughputTrendInput)
async def analyze_throughput_trend(
    line_number: int,
    time_window_minutes: int = 30
) -> Dict[str, Any]:
    """
    Analyze throughput trends for a specific line over time.
    
    Detects performance degradation by analyzing historical throughput data.
    Useful for identifying gradual efficiency drops that may indicate
    developing issues.
    
    Args:
        line_number: Line to analyze (1-20)
        time_window_minutes: Historical window to analyze (default 30 min)
        
    Returns:
        Dictionary containing:
        - Current vs historical throughput
        - Trend direction (increasing/stable/decreasing)
        - Degradation rate if declining
        - Recommendation for action
    """
    logger.info(
        f"📈 Analyzing throughput trend for Line {line_number} "
        f"(window: {time_window_minutes}min)"
    )
    
    try:
        department = await shared_context.get_department()
        line = department.get_line(line_number)
        
        if not line:
            raise ValueError(f"Line {line_number} not found")
        
        # In production, this would query time-series database
        # For now, simulate with current + efficiency as proxy for trend
        current_throughput = line.current_throughput
        target_throughput = line.target_throughput
        efficiency = line.efficiency
        
        # Simulate historical average (would be from DB)
        # Use efficiency as indicator of trend
        historical_avg = target_throughput * min(1.0, efficiency + 0.1)
        
        degradation_rate = (
            (historical_avg - current_throughput) / historical_avg * 100
            if historical_avg > 0 else 0.0
        )
        
        # Determine trend
        if degradation_rate > 10:
            trend = "decreasing"
            severity = "HIGH" if degradation_rate > 20 else "MEDIUM"
        elif degradation_rate < -5:
            trend = "increasing"
            severity = "NONE"
        else:
            trend = "stable"
            severity = "LOW" if degradation_rate > 5 else "NONE"
        
        # Generate recommendation
        recommendations = []
        if trend == "decreasing":
            recommendations.append("Investigate cause of throughput decline")
            if line.health_score < 60:
                recommendations.append("Consider maintenance intervention")
            if len(line.assigned_staff) < 2:
                recommendations.append("Check staffing levels")
        elif trend == "stable" and efficiency < 0.8:
            recommendations.append("Monitor for further degradation")
        
        result = {
            "line_number": line_number,
            "current_throughput": current_throughput,
            "target_throughput": target_throughput,
            "historical_average": round(historical_avg, 2),
            "trend": trend,
            "degradation_rate_percent": round(degradation_rate, 2),
            "severity": severity,
            "time_window_minutes": time_window_minutes,
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat(),
        }
        
        logger.info(
            f"✅ Line {line_number} trend: {trend}, "
            f"degradation: {degradation_rate:.1f}%"
        )
        
        return result
        
    except Exception as e:
        logger.error(
            f"❌ Error analyzing trend for Line {line_number}: {e}"
        )
        raise


@tool(args_schema=BottleneckPredictionInput)
async def predict_bottleneck(line_number: Optional[int] = None) -> Dict[str, Any]:
    """
    Predict potential bottlenecks using heuristic analysis.
    
    Analyzes equipment health, efficiency, and staffing to identify
    lines at risk of becoming bottlenecks. Uses simple heuristics:
    - Health < 50 AND Efficiency < 0.7 = High risk
    - Health < 40 = Critical risk regardless of efficiency
    
    Args:
        line_number: Specific line to analyze, or None for all lines
        
    Returns:
        Dictionary containing:
        - At-risk lines with risk scores
        - Predicted time to bottleneck
        - Contributing factors
        - Recommended preventive actions
    """
    logger.info(
        f"🔍 Predicting bottlenecks for "
        f"{'Line ' + str(line_number) if line_number else 'all lines'}"
    )
    
    try:
        department = await shared_context.get_department()
        
        # Determine which lines to analyze
        if line_number:
            lines_to_check = [line_number]
        else:
            lines_to_check = list(range(1, 21))
        
        predictions = []
        
        for num in lines_to_check:
            line = department.get_line(num)
            if not line:
                continue
            
            # Calculate risk score (0-100)
            risk_score = 0
            factors = []
            
            # Health factor (40 points max)
            if line.health_score < 40:
                risk_score += 40
                factors.append(f"Critical health: {line.health_score:.1f}")
            elif line.health_score < 60:
                risk_score += int((60 - line.health_score) / 20 * 40)
                factors.append(f"Degraded health: {line.health_score:.1f}")
            
            # Efficiency factor (30 points max)
            if line.efficiency < 0.5:
                risk_score += 30
                factors.append(f"Very low efficiency: {line.efficiency:.2f}")
            elif line.efficiency < 0.7:
                risk_score += int((0.7 - line.efficiency) / 0.2 * 30)
                factors.append(f"Low efficiency: {line.efficiency:.2f}")
            
            # Staffing factor (20 points max)
            staff_count = len(line.assigned_staff)
            if staff_count < 2:
                risk_score += 20
                factors.append(f"Understaffed: {staff_count} workers")
            elif staff_count == 2:
                risk_score += 10
                factors.append("Minimal staffing")
            
            # Temperature factor (10 points max)
            if line.temperature > 6 or line.temperature < 0:
                risk_score += 10
                factors.append(f"Temperature issue: {line.temperature}°C")
            
            # Only include if risk > 20
            if risk_score >= 20:
                # Estimate time to bottleneck (simplified)
                if risk_score >= 70:
                    time_estimate = "< 1 hour"
                    severity = "CRITICAL"
                elif risk_score >= 50:
                    time_estimate = "1-2 hours"
                    severity = "HIGH"
                elif risk_score >= 30:
                    time_estimate = "2-4 hours"
                    severity = "MEDIUM"
                else:
                    time_estimate = "> 4 hours"
                    severity = "LOW"
                
                # Recommendations
                recommendations = []
                if line.health_score < 50:
                    recommendations.append("Schedule immediate maintenance")
                if staff_count < 2:
                    recommendations.append("Assign additional staff")
                if line.efficiency < 0.7:
                    recommendations.append("Investigate efficiency drop")
                
                predictions.append({
                    "line_number": num,
                    "risk_score": risk_score,
                    "severity": severity,
                    "estimated_time_to_bottleneck": time_estimate,
                    "contributing_factors": factors,
                    "recommendations": recommendations,
                    "current_status": line.status.value,
                })
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "analyzed_lines": lines_to_check,
            "at_risk_count": len(predictions),
            "predictions": sorted(
                predictions,
                key=lambda x: x["risk_score"],
                reverse=True
            ),
        }
        
        logger.info(
            f"✅ Bottleneck prediction: {len(predictions)} lines at risk"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error predicting bottlenecks: {e}")
        raise


@tool(args_schema=MaintenanceRequestInput)
async def request_maintenance(
    line_number: int,
    priority: str,
    reason: str
) -> Dict[str, Any]:
    """
    Request maintenance for a production line from the Maintenance Agent.
    
    Creates a maintenance request that will be processed by the Maintenance
    Agent. The request includes priority level and detailed reasoning.
    
    Args:
        line_number: Line requiring maintenance (1-20)
        priority: CRITICAL, HIGH, MEDIUM, or LOW
        reason: Detailed reason for maintenance request
        
    Returns:
        Dictionary containing:
        - Request ID
        - Estimated response time
        - Acknowledgment status
    """
    logger.info(
        f"🔧 Requesting {priority} maintenance for Line {line_number}"
    )
    
    try:
        from app.state.context import shared_context
        from app.models.domain import Alert, AlertSeverity
        
        # Map priority to severity
        severity_map = {
            "CRITICAL": AlertSeverity.CRITICAL,
            "HIGH": AlertSeverity.HIGH,
            "MEDIUM": AlertSeverity.MEDIUM,
            "LOW": AlertSeverity.LOW,
        }
        
        # Create alert for Maintenance Agent
        alert = Alert(
            alert_id=f"MAINT-{line_number}-{int(datetime.now().timestamp())}",
            timestamp=datetime.now(),
            severity=severity_map[priority],
            source="ProductionAgent",
            title=f"Maintenance Request: Line {line_number}",
            description=reason,
            line_number=line_number,
            resolved=False,
        )
        
        # Add to shared context
        await shared_context.add_alert(alert)
        
        # Estimate response time based on priority
        response_times = {
            "CRITICAL": "Immediate (< 15 minutes)",
            "HIGH": "< 1 hour",
            "MEDIUM": "< 4 hours",
            "LOW": "< 24 hours",
        }
        
        result = {
            "request_id": alert.alert_id,
            "line_number": line_number,
            "priority": priority,
            "estimated_response_time": response_times[priority],
            "status": "PENDING",
            "timestamp": alert.timestamp.isoformat(),
        }
        
        logger.info(
            f"✅ Maintenance request created: {alert.alert_id}"
        )
        
        return result
        
    except Exception as e:
        logger.error(
            f"❌ Error requesting maintenance for Line {line_number}: {e}"
        )
        raise


@tool(args_schema=LineMetricsInput)
async def check_line_staffing(line_number: int) -> Dict[str, Any]:
    """
    Check staffing levels for a line using camera vision service.
    
    Uses the Vision Service to verify actual worker presence on the line,
    complementing the assigned staff data with real-time visual confirmation.
    
    Args:
        line_number: Line to check (1-20)
        
    Returns:
        Dictionary containing:
        - Assigned staff count (from roster)
        - Visual headcount (from camera)
        - Discrepancy flag
        - Recommendation if understaffed
    """
    logger.info(f"👥 Checking staffing for Line {line_number}")
    
    try:
        from app.services.vision_service import vision_service
        
        # Get assigned staff from department
        department = await shared_context.get_department()
        line = department.get_line(line_number)
        
        if not line:
            raise ValueError(f"Line {line_number} not found")
        
        assigned_count = len(line.assigned_staff)
        assigned_names = line.assigned_staff
        
        # Get visual confirmation from camera
        visual_count = await vision_service.get_line_occupancy(line_number)
        
        # Check for discrepancy
        discrepancy = abs(visual_count - assigned_count)
        has_discrepancy = discrepancy > 0
        
        # Determine if understaffed
        optimal_count = 3  # Optimal staffing per line
        is_understaffed = visual_count < 2
        
        recommendation = None
        if is_understaffed:
            recommendation = "Line is critically understaffed - assign additional workers immediately"
        elif visual_count < optimal_count:
            recommendation = "Consider assigning one more worker for optimal efficiency"
        elif has_discrepancy:
            recommendation = "Investigate roster vs actual presence discrepancy"
        
        result = {
            "line_number": line_number,
            "assigned_staff_count": assigned_count,
            "assigned_staff_names": assigned_names,
            "visual_headcount": visual_count,
            "has_discrepancy": has_discrepancy,
            "discrepancy_count": discrepancy,
            "is_understaffed": is_understaffed,
            "optimal_count": optimal_count,
            "recommendation": recommendation,
            "timestamp": datetime.now().isoformat(),
        }
        
        logger.info(
            f"✅ Line {line_number} staffing: "
            f"assigned={assigned_count}, visual={visual_count}"
        )
        
        return result
        
    except Exception as e:
        logger.error(
            f"❌ Error checking staffing for Line {line_number}: {e}"
        )
        raise

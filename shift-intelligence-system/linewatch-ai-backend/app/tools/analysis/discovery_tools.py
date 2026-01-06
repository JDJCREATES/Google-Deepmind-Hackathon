"""
Discovery tools for querying factory state.

General-purpose tools that return raw data. Agents must analyze and interpret
the data themselves to identify problems.
"""
from typing import Dict, List, Any, Optional
from langchain.tools import tool
from app.services.simulation import simulation


@tool
async def query_facility_subsystem(subsystem: str) -> Dict[str, Any]:
    """
    Query the current state of any facility subsystem.
    
    Args:
        subsystem: Which subsystem to query - 'monitoring', 'equipment', 'inventory', 'personnel', 'production'
    
    Returns raw data about the subsystem's current state.
    You must analyze this data yourself to identify any issues or gaps.
    
    Examples:
        query_facility_subsystem('monitoring') - Get all sensors/cameras and their locations
        query_facility_subsystem('equipment') - Get all production line health data
        query_facility_subsystem('inventory') - Get current inventory levels
    """
    if subsystem == "monitoring":
        # Return raw camera/sensor data - agent must analyze for gaps
        from app.services.camera_coverage import calculate_camera_coverage_stats
        cameras = simulation.layout.get("cameras", [])
        coverage_stats = calculate_camera_coverage_stats(cameras)
        
        return {
            "subsystem": "monitoring",
            "cameras": [
                {
                    "id": cam.get("id"),
                    "position": cam.get("position"),
                    "type": cam.get("type", "visual"),
                    "status": "active"
                }
                for cam in cameras
            ],
            "facility_dimensions": {
                "width": simulation.canvas_width,
                "height": simulation.canvas_height
            },
            "production_zone": {
                "x_range": [150, simulation.canvas_width - 180],
                "y_range": [100, simulation.canvas_height - 100],
                "total_lines": 20
            },
            "coverage_analysis": {
                "coverage_pct": coverage_stats["coverage_percentage"],
                "camera_range_px": coverage_stats["camera_range_px"],
                "lines_with_coverage": coverage_stats["covered_lines"],
                "lines_without_coverage": coverage_stats["uncovered_lines"],
                "note": "You can only detect violations/fatigue in covered areas"
            }
        }
    
    elif subsystem == "equipment":
        # Return raw equipment health data
        return {
            "subsystem": "equipment",
            "production_lines": {
                line_id: {
                    "line_id": line_id,
                    "health_pct": health,
                    "is_running": simulation.machine_production.get(line_id, {}).get("is_running", False),
                    "product_type": simulation.machine_production.get(line_id, {}).get("product_type"),
                }
                for line_id, health in simulation.line_health.items()
            },
            "total_lines": len(simulation.line_health)
        }
    
    elif subsystem == "inventory":
        # Return raw inventory data
        return {
            "subsystem": "inventory",
            "warehouse_inventory": simulation.warehouse_inventory,
            "spare_parts": {
                "pneumatic_cylinder": 2,
                "belt_assembly": 5,
                "motor_assembly": 1,
                "sensor_module": 8,
                "hydraulic_pump": 0,
            }
        }
    
    elif subsystem == "personnel":
        # Return raw personnel data
        return {
            "subsystem": "personnel",
            "operators": [
                {
                    "name": op.get("name"),
                    "status": op.get("status"),
                    "fatigue": op.get("fatigue", 0),
                    "assigned_line": op.get("assigned_line")
                }
                for op in simulation.operators
            ],
            "total_operators": len(simulation.operators),
            "shift": simulation.current_shift
        }
    
    elif subsystem == "production":
        # Return raw production metrics
        return {
            "subsystem": "production",
            "lines_running": sum(1 for s in simulation.machine_production.values() if s.get("is_running")),
            "total_lines": len(simulation.machine_production),
            "warehouse_boxes": len([b for b in simulation.conveyor_boxes if b.get("at_warehouse")]),
            "kpis": {
                "oee": simulation.kpi.oee,
                "safety_score": simulation.kpi.safety_score
            }
        }
    
    else:
        return {
            "error": f"Unknown subsystem '{subsystem}'",
            "available_subsystems": ["monitoring", "equipment", "inventory", "personnel", "production"]
        }


@tool
async def get_facility_layout() -> Dict[str, Any]:
    """
    Get the physical layout of the facility including zones, dimensions, and structure.
    
    Returns raw layout data. You must interpret this to understand the facility.
    """
    return {
        "dimensions": {
            "width": simulation.canvas_width,
            "height": simulation.canvas_height
        },
        "zones": {
            "warehouse": {"x": 0, "y": 0, "width": 80, "height": simulation.canvas_height},
            "production": {
                "x": 150,
                "y": 100,
                "width": simulation.canvas_width - 330,
                "height": simulation.canvas_height - 200
            },
            "maintenance": {"x": 150, "y": 0, "width": simulation.canvas_width - 330, "height": 50},
            "breakroom": {
                "x": simulation.canvas_width - 100,
                "y": 0,
                "width": 100,
                "height": simulation.canvas_height
            }
        },
        "critical_areas": [
            "production_zone",
            "warehouse_loading",
            "maintenance_access"
        ]
    }


@tool
async def query_system_logs(
    system: str,
    time_range_minutes: int = 60,
    severity: Optional[str] = None
) -> Dict[str, Any]:
    """
    Query system logs for any subsystem.
    
    Args:
        system: Which system logs to query - 'safety', 'equipment', 'quality', 'production', 'all'
        time_range_minutes: How far back to look (default 60 minutes)
        severity: Filter by severity - 'critical', 'warning', 'info', or None for all
    
    Returns raw log entries. You must analyze them to identify patterns or issues.
    """
    # Simulated log data - in production would query actual log system
    from datetime import datetime, timedelta
    from app.services.shared_context import shared_context
    
    logs = []
    
    if system in ["safety", "all"]:
        # Get recent safety violations
        for violation in shared_context.safety_violations[-10:]:
            logs.append({
                "timestamp": violation.timestamp.isoformat(),
                "system": "safety",
                "severity": "warning"  if "restricted" in violation.description.lower() else "critical",
                "message": violation.description
            })
    
    if system in ["equipment", "all"]:
        # Get equipment health issues
        for line_id, health in simulation.line_health.items():
            if health < 70:
                logs.append({
                    "timestamp": datetime.now().isoformat(),
                    "system": "equipment",
                    "severity": "critical" if health < 40 else "warning",
                    "message": f"Line {line_id} health degraded to {health:.1f}%"
                })
    
    # Filter by severity if specified
    if severity:
        logs = [log for log in logs if log["severity"] == severity]
    
    return {
        "system": system,
        "time_range_minutes": time_range_minutes,
        "log_count": len(logs),
        "logs": logs[-20:]  # Last 20 entries
    }

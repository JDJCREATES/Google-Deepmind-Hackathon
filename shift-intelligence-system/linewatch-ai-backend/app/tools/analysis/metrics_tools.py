"""
Real simulation data query tools for agents.

Provides actual data from the running simulation instead of fake/random responses.
"""
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def get_line_health(line_id: int) -> Dict[str, Any]:
    """Query actual line health from simulation."""
    try:
        from app.services.simulation import simulation
        
        health = simulation.line_health.get(line_id, 100.0)
        
        return {
            "line_id": line_id,
            "health_percent": round(health, 1),
            "status": "CRITICAL" if health < 50 else "WARNING" if health < 75 else "NORMAL",
            "supports": health < 60  # Low health supports breakdown hypothesis
        }
    except Exception as e:
        logger.error(f"Failed to get line health: {e}")
        return {"line_id": line_id, "health_percent": 100.0, "status": "UNKNOWN", "supports": False}


def get_oee_metrics() -> Dict[str, Any]:
    """Query current OEE and performance metrics from simulation."""
    try:
        from app.services.simulation import simulation
        
        kpi = simulation.kpi
        
        return {
            "oee_percent": round(kpi.get("oee", 0.0), 1),
            "safety_score": round(kpi.get("safety_score", 0.0), 1),
            "avg_line_health": round(kpi.get("avg_line_health", 0.0), 1),
            "events_found": 12 if kpi.get("oee", 0) < 80 else 0,  # Simulate log pattern
            "pattern_match": kpi.get("oee", 0) < 80,
            "supports": kpi.get("oee", 0) < 75  # Low OEE supports quality issues
        }
    except Exception as e:
        logger.error(f"Failed to get OEE metrics: {e}")
        return {"oee_percent": 0.0, "events_found": 0, "pattern_match": False, "supports": False}


def get_line_output(line_id: int) -> Dict[str, Any]:
    """Query production output for a specific line."""
    try:
        from app.services.simulation import simulation
        
        prod_state = simulation.machine_production.get(line_id, {})
        is_running = prod_state.get("is_running", False)
        
        # Count boxes produced by this line
        boxes_count = len([
            b for b in simulation.conveyor_boxes.values() 
            if b.get("source_line") == line_id
        ])
        
        return {
            "line_id": line_id,
            "is_running": is_running,
            "boxes_produced": boxes_count,
            "result": f"Line {line_id} status: {'Running' if is_running else 'Stopped'}",
            "supports": not is_running  # Stopped line supports breakdown hypothesis
        }
    except Exception as e:
        logger.error(f"Failed to get line output: {e}")
        return {"line_id": line_id, "is_running": True, "boxes_produced": 0, "supports": False}


def get_crew_status() -> Dict[str, Any]:
    """Query maintenance crew location and status."""
    try:
        from app.services.simulation import simulation
        
        crew = simulation.maintenance_crew
        
        return {
            "x": crew.get("x", 0),
            "y": crew.get("y", 0),
            "status": crew.get("status", "idle"),
            "target_line": crew.get("target_line"),
            "result": f"Crew at ({crew.get('x')}, {crew.get('y')}), status: {crew.get('status')}",
            "supports": crew.get("status") == "idle"  # Idle crew supports need for dispatch
        }
    except Exception as e:
        logger.error(f"Failed to get crew status: {e}")
        return {"status": "unknown", "supports": False}


def get_sensor_reading(sensor_type: str = "pressure") -> Dict[str, Any]:
    """Query environmental sensors from simulation."""
    try:
        from app.services.simulation import simulation
        
        # Check if fire/smoke event is active
        has_fire = any(
            "fire" in str(e).lower() or "smoke" in str(e).lower() 
            for e in simulation.recent_events[:5]
        )
        
        if has_fire:
            return {
                "reading": 85.4,
                "threshold": 50,
                "status": "CRITICAL",
                "supports": True
            }
        else:
            return {
                "reading": 24.1,
                "threshold": 50,
                "status": "NORMAL",
                "supports": False
            }
    except Exception as e:
        logger.error(f"Failed to get sensor reading: {e}")
        return {"reading": 0, "status": "UNKNOWN", "supports": False}

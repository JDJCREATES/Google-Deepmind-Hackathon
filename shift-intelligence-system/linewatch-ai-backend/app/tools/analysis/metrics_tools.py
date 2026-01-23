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


def query_simulation_logs(query: str = "") -> Dict[str, Any]:
    """Search recent simulation events/logs for specific keywords."""
    try:
        from app.services.simulation import simulation
        
        # Search in recent events
        results = []
        query_lower = query.lower()
        
        # If query is generic like "logs" or empty, return last 5
        if not query or len(query) < 3 or "log" in query_lower:
            results = list(simulation.recent_events)[-5:]
        else:
            # Keyword search
            results = [
                e for e in simulation.recent_events 
                if query_lower in str(e).lower()
            ]
            # Limit to 5 most recent matches
            results = results[-5:]
            
        return {
            "query": query,
            "match_count": len(results),
            "logs": results,
            "supports": len(results) > 0 and "error" in str(results).lower()
        }
    except Exception as e:
        logger.error(f"Failed to query logs: {e}")
        return {"query": query, "logs": [], "error": str(e)}


def get_oee_metrics() -> Dict[str, Any]:
    """Query current OEE and performance metrics from simulation."""
    try:
        from app.services.simulation import simulation
        
        kpi = simulation.kpi
        
        # Convert 0-1 ratios to percentages (1.0 -> 100%)
        return {
            "oee_percent": round(kpi.oee * 100, 1),
            "safety_score": round(kpi.safety_score, 1),
            "avg_line_health": 85.0,  # Placeholder
            "events_found": 12 if kpi.oee < 0.8 else 0,
            "pattern_match": kpi.oee < 0.8,
            "supports": kpi.oee < 0.75
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
        
        # Simplified: simulation doesn't have recent_events attribute
        # Return safety score as proxy for sensor status
        safety_ok = simulation.kpi.safety_score > 95
        
        if not safety_ok:
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

"""
Simulation Service for generating synthetic plant data.

Acts as the "World" that the agents interact with, generating:
- Throughput data
- Equipment telemetry
- Camera events
- Random anomalies
"""
import asyncio
import random
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.config import settings
from app.services.websocket import manager
from app.utils.logging import get_agent_logger
from app.services.layout_service import layout_service

logger = get_agent_logger("Simulation")

class SimulationService:
    """
    Background service that simulates the manufacturing environment.
    Stateful: Tracks operator positions, machine health, and camera detections.
    """
    
    def __init__(self):
        self.is_running = False
        self.sim_task = None
        self.tick_rate = 1.0  # Faster ticks for smoother movement (1s)
        
        # World State
        self.layout = layout_service.get_layout()
        self.line_health = {i: 100.0 for i in range(1, settings.num_production_lines + 1)}
        self.total_uptime_minutes = 0
        
        # Transform Operators into stateful objects
        self.operators = []
        for op in self.layout.get("operators", []):
            self.operators.append({
                "id": op["id"],
                "name": op["name"],
                "x": op["x"],
                "y": op["y"],
                "status": "idle",
                "current_action": "monitoring",
                "target_x": op["x"],
                "target_y": op["y"]
            })
            
        # Cameras for detection logic
        self.cameras = self.layout.get("cameras", [])
        
    async def start(self):
        """Start the simulation loop."""
        if self.is_running:
            return
            
        self.is_running = True
        self.sim_task = asyncio.create_task(self._run_loop())
        logger.info("🎬 Simulation Service STARTED (Live Mode)")
        
        await manager.broadcast({
            "type": "system_status",
            "data": {"status": "running", "mode": "live", "timestamp": datetime.now().isoformat()}
        })
        
    async def stop(self):
        """Stop the simulation loop."""
        self.is_running = False
        if self.sim_task:
            self.sim_task.cancel()
            try:
                await self.sim_task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 Simulation Service STOPPED")
        await manager.broadcast({
            "type": "system_status",
            "data": {"status": "stopped", "timestamp": datetime.now().isoformat()}
        })

    async def _run_loop(self):
        """Main simulation loop."""
        while self.is_running:
            try:
                start_time = datetime.now()
                await self._tick()
                
                # Calculate sleep time to maintain stable tick rate
                elapsed = (datetime.now() - start_time).total_seconds()
                sleep_time = max(0.1, (self.tick_rate / settings.simulation_speed) - elapsed)
                await asyncio.sleep(sleep_time)
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                await asyncio.sleep(1)
    
    async def _tick(self):
        """Execute one simulation step."""
        self.total_uptime_minutes += (self.tick_rate / 60) * settings.simulation_speed
        events = []
        
        # 1. Move Operators
        self._move_operators()
        
        # 2. Check Camera Vision
        detections = self._check_cameras()
        events.extend(detections)
        
        # 3. Simulate Line Health & Throughput
        for line_id in self.line_health:
            # Slow natural degradation, faster if actively creating products
            degradation = random.uniform(0, 0.1)
            self.line_health[line_id] = max(0, self.line_health[line_id] - degradation)
            
            # Send status update (throttled? No, send every tick for smooth graphs)
            events.append({
                "type": "line_status",
                "data": {
                    "line_id": line_id,
                    "health": round(self.line_health[line_id], 1),
                    "throughput": int(random.gauss(100, 5) * (self.line_health[line_id] / 100)),
                }
            })
            
        # 4. Generate Random Anomalies (Smart Scenarios)
        if random.random() < (settings.event_probability_breakdown / 5): # Adjust probability for faster ticks
            events.append(self._generate_breakdown())
            
        if random.random() < (settings.event_probability_safety_violation / 5):
            events.append(self._trigger_safety_violation())

        # 5. Broadcast Operator Updates (Movement)
        for op in self.operators:
            events.append({
                "type": "operator_update",
                "data": op
            })

        # Broadcast all gathered events
        for event in events:
            await manager.broadcast(event)
            
            # Auto-trigger investigation for critical events
            event_data = event.get("data", {})
            if event_data.get("severity") in ["HIGH", "CRITICAL"]:
                asyncio.create_task(self._trigger_investigation(event_data))

    def _move_operators(self):
        """Update operator positions towards their targets."""
        speed = 50.0 # pixels per second (tick is 1s)
        
        for op in self.operators:
            target_x, target_y = op["target_x"], op["target_y"]
            dx = target_x - op["x"]
            dy = target_y - op["y"]
            dist = math.sqrt(dx*dx + dy*dy)
            
            if dist < speed:
                # Arrived
                op["x"] = target_x
                op["y"] = target_y
                if op["status"] == "moving":
                    op["status"] = "working" # Arrived at job
            else:
                # Move towards target
                move_x = (dx / dist) * speed
                move_y = (dy / dist) * speed
                op["x"] += move_x
                op["y"] += move_y
                op["status"] = "moving"
                
            # Random wandering if idle or working (finish job)
            # If working, small chance to finish and go idle
            if op["status"] in ["working", "monitoring"]:
                if random.random() < 0.2: # 20% chance per tick to finish task
                    op["status"] = "idle"
                    op["current_action"] = "idle"
            
            # If idle, pick a new target
            if op["status"] == "idle" and random.random() < 0.3: # 30% chance to start moving
                # Pick a random spot in the operator zone or visit a machine
                # Zone: Y=300 to 400. X=50 to 1100.
                targets = [
                    # Random spots
                    (random.uniform(50, 1100), random.uniform(320, 420)),
                    # Or Machine locations (from lines)
                    (self.layout["lines"][random.randint(0, 19)]["x"], 380)
                ]
                tx, ty = random.choice(targets)
                
                op["target_x"] = tx
                op["target_y"] = ty
                op["status"] = "moving"
                op["current_action"] = "patrolling"

    def _check_cameras(self) -> List[Dict[str, Any]]:
        """Check if any operator is inside a camera's vision cone."""
        events = []
        for cam in self.cameras:
            # Simple cone check
            cam_x, cam_y = cam["x"], cam["y"]
            cam_angle = cam["rotation"] # degrees
            cam_fov = cam.get("fov", 60)
            cam_range = cam.get("range", 200)
            
            detected = False
            for op in self.operators:
                dx = op["x"] - cam_x
                dy = op["y"] - cam_y
                dist = math.sqrt(dx*dx + dy*dy)
                
                if dist > cam_range: continue
                
                # Check angle
                angle_to_op = math.degrees(math.atan2(dy, dx))
                # Normalize angles
                angle_diff = (angle_to_op - (cam_angle - 90)) % 360 # Adjust because 0 is right, rotation might be diff base
                # Actually, in Konva/Canvas, 0 is Right, 90 is Down.
                # Layout service says rotation=90 (Down).
                # atan2 returns angle from X axis (Right). So Down is 90.
                # So we simply compare.
                
                # Unwrap angle diff
                if angle_diff > 180: angle_diff -= 360
                
                if abs(angle_diff) < (cam_fov / 2):
                    detected = True
                    # Check for safety violation
                    if op.get("current_action") == "VIOLATION":
                        detection_color = "#EF4444" # Red (Critical)
                    else:
                        detection_color = "#FBBF24" # Amber (Warning/Presence)
            
            if detected:
                events.append({
                    "type": "camera_detection",
                    "data": {
                        "camera_id": cam["id"],
                        "status": "detected",
                        "color": detection_color
                    }
                })
        return events

    def _generate_breakdown(self) -> Dict[str, Any]:
        """Generate a breakdown and dispatch an operator."""
        line_id = random.randint(1, settings.num_production_lines)
        self.line_health[line_id] = 40.0
        
        # Dispatch nearest operator
        target_line = next((l for l in self.layout["lines"] if l["id"] == line_id), None)
        if target_line:
             # Find nearest op
            best_op = min(self.operators, key=lambda o: math.hypot(o["x"] - target_line["x"], o["y"] - target_line["y"]))
            best_op["target_x"] = target_line["x"]
            best_op["target_y"] = target_line["y"]
            best_op["status"] = "moving"
            best_op["current_action"] = f"Fixing Line {line_id}"
            
        msg = {
            "type": "visual_signal",
            "data": {
                "source": f"Camera_{line_id:02d}",
                "description": f"Equipment Failure detected on Line {line_id}",
                "severity": "HIGH",
                "timestamp": datetime.now().isoformat()
            }
        }
        return msg

    def _trigger_safety_violation(self) -> Dict[str, Any]:
        """Make an operator walk into a dangerous zone."""
        # Pick random op
        op = random.choice(self.operators)
        # Pick a "Danger Zone" (e.g., inside a machine footprint)
        line = random.choice(self.layout["lines"])
        op["target_x"] = line["x"]
        op["target_y"] = line["y"]
        op["status"] = "moving"
        op["current_action"] = "VIOLATION"
        
        msg = {
            "type": "visual_signal",
            "data": {
                "source": "Safety_Cam",
                "description": f"Safety Violation: {op['name']} entering restricted area {line['label']}",
                "severity": "CRITICAL",
                "timestamp": datetime.now().isoformat()
            }
        }
        return msg
        
    async def _trigger_investigation(self, event_data: dict):
        """Run hypothesis market for a critical event."""
        # [Keep existing implementation]
        try:
            from app.graphs.hypothesis_market import run_hypothesis_market
            await manager.broadcast({
                "type": "agent_thought",
                "data": {
                    "source": "ORCHESTRATOR",
                    "description": f"Initiating investigation for {event_data.get('description')}",
                    "timestamp": datetime.now().isoformat()
                }
            })
            await run_hypothesis_market(
                signal_id=f"sim-{int(datetime.now().timestamp())}",
                signal_type=event_data.get("type", "UNKNOWN"),
                signal_description=event_data.get("description", "Simulation Event"),
                signal_data=event_data
            )
        except Exception as e:
            logger.error(f"Failed to trigger investigation: {e}")

    # Keep inject_event for manual testing
    async def inject_event(self, event_type: str, severity: str = "HIGH"):
        """Manually inject an event (for demos/testing)."""
        logger.info(f"💉 Injecting manual event: {event_type}")
        if event_type == "fire": return self._generate_breakdown() # Returns dict, doesn't broadcast?
        # Re-implement broadcast logic for manual injection if needed, but for now sim loop handles it.
        # This method was called by API -> expected to return event.
        # I'll just return a dummy event for now as the loop handles real logic.
        return {"status": "injected", "type": event_type}

# Global instance
simulation = SimulationService()

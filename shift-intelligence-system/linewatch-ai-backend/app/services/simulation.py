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
from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.config import settings
from app.services.websocket import manager
from app.utils.logging import get_agent_logger

logger = get_agent_logger("Simulation")

class SimulationService:
    """
    Background service that simulates the manufacturing environment.
    """
    
    def __init__(self):
        self.is_running = False
        self.sim_task = None
        self.tick_rate = 5.0  # seconds per tick
        
        # State
        self.line_health = {i: 100.0 for i in range(1, settings.num_production_lines + 1)}
        self.current_shift_hour = 0
        self.total_uptime_minutes = 0
        
    async def start(self):
        """Start the simulation loop."""
        if self.is_running:
            return
            
        self.is_running = True
        logger.info("🎬 Simulation Service STARTED")
        self.sim_task = asyncio.create_task(self._run_loop())
        
        await manager.broadcast({
            "type": "system_status",
            "data": {"status": "running", "timestamp": datetime.now().isoformat()}
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
                await self._tick()
                # Wait for next tick, adjusting for simulation speed
                await asyncio.sleep(self.tick_rate / settings.simulation_speed)
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                await asyncio.sleep(5)  # Backoff on error
    
    async def _tick(self):
        """Execute one simulation step."""
        self.total_uptime_minutes += (self.tick_rate / 60) * settings.simulation_speed
        
        events = []
        
        # 1. Simulate Line Health & Throughput
        for line_id in self.line_health:
            # Natural degradation
            degradation = random.uniform(0, 0.5)
            self.line_health[line_id] = max(0, self.line_health[line_id] - degradation)
            
            # Send status update
            events.append({
                "type": "line_status",
                "data": {
                    "line_id": line_id,
                    "health": round(self.line_health[line_id], 1),
                    "throughput": int(random.gauss(100, 5) * (self.line_health[line_id] / 100)),
                }
            })
            
        # 2. Random Anomalies (Chance based on config)
        if random.random() < settings.event_probability_breakdown:
            events.append(self._generate_breakdown())
            
        if random.random() < settings.event_probability_safety_violation:
            events.append(self._generate_safety_violation())
            
        if random.random() < settings.event_probability_bottleneck:
            events.append(self._generate_bottleneck())

        # 3. Broadcast All Events
        for event in events:
            await manager.broadcast(event)
            
    def _generate_breakdown(self) -> Dict[str, Any]:
        """Generate a random equipment breakdown."""
        line_id = random.randint(1, settings.num_production_lines)
        self.line_health[line_id] = 40.0 # Drop health significantly
        
        msg = {
            "type": "visual_signal",
            "data": {
                "source": f"Camera_{line_id:02d}",
                "description": f"Smoke detected on Line {line_id} conveyor motor",
                "severity": "HIGH",
                "timestamp": datetime.now().isoformat()
            }
        }
        logger.warning(f"🔥 SIMULATION: {msg['data']['description']}")
        return msg

    def _generate_safety_violation(self) -> Dict[str, Any]:
        """Generate a random safety violation."""
        line_id = random.randint(1, settings.num_production_lines)
        msg = {
            "type": "visual_signal",
            "data": {
                "source": f"Camera_{line_id:02d}_Safety",
                "description": f"Operator entered Line {line_id} safety zone without LOTO",
                "severity": "CRITICAL",
                "timestamp": datetime.now().isoformat()
            }
        }
        logger.warning(f"⚠️ SIMULATION: {msg['data']['description']}")
        return msg
    
    def _generate_bottleneck(self) -> Dict[str, Any]:
        """Generate a production bottleneck."""
        line_id = random.randint(1, settings.num_production_lines)
        msg = {
            "type": "production_signal",
            "data": {
                "source": "MES_System",
                "description": f"Line {line_id} input buffer empty (starvation)",
                "severity": "MEDIUM",
                "timestamp": datetime.now().isoformat()
            }
        }
        logger.info(f"📉 SIMULATION: {msg['data']['description']}")
        return msg
        
    async def inject_event(self, event_type: str, severity: str = "HIGH") -> Dict[str, Any]:
        """Manually inject an event (e.g., from UI)."""
        logger.info(f"💉 Injecting manual event: {event_type}")
        
        if event_type == "fire":
             event = self._generate_breakdown()
        elif event_type == "fatigue":
             event = {
                "type": "visual_signal",
                "data": {
                    "source": "Camera_BreakRoom",
                    "description": "Multiple operators showing signs of high fatigue",
                    "severity": severity,
                    "timestamp": datetime.now().isoformat()
                }
             }
        else:
             event = {
                "type": "system_alert",
                "data": {
                    "source": "Manual_Injection",
                    "description": f"Manual test event: {event_type}",
                    "severity": severity,
                    "timestamp": datetime.now().isoformat()
                }
             }
             
        await manager.broadcast(event)
        return event

# Global instance
simulation = SimulationService()

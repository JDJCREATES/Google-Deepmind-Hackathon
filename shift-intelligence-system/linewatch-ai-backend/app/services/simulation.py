"""
Simulation Service for generating synthetic plant data.

Acts as the "World" that the agents interact with, generating:
- Production flow (small boxes → large boxes → conveyor → warehouse)
- Equipment telemetry and health
- Camera events
- Random anomalies

Production is now REAL and backend-driven:
- Each line produces a specific product type (AI-assignable)
- Machine health affects production rate
- Boxes travel on conveyor and stack in warehouse
"""
import asyncio
import random
import math
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.config import settings
from app.services.websocket import manager
from app.utils.logging import get_agent_logger
from app.services.layout_service import layout_service

logger = get_agent_logger("Simulation")


# =============================================================================
# PRODUCT CATALOG
# =============================================================================
PRODUCT_CATALOG: Dict[str, Dict[str, Any]] = {
    "widget_a": {
        "name": "Widget A",
        "color": "#3B82F6",  # Blue
        "base_time": 90,      # Seconds to fill large box
        "small_per_large": (8, 12),  # Range of small boxes per large
    },
    "widget_b": {
        "name": "Widget B",
        "color": "#10B981",  # Green
        "base_time": 75,
        "small_per_large": (10, 15),
    },
    "gizmo_x": {
        "name": "Gizmo X",
        "color": "#F59E0B",  # Amber
        "base_time": 120,
        "small_per_large": (6, 10),
    },
    "gizmo_y": {
        "name": "Gizmo Y",
        "color": "#EF4444",  # Red
        "base_time": 100,
        "small_per_large": (8, 14),
    },
    "part_z": {
        "name": "Part Z",
        "color": "#8B5CF6",  # Purple
        "base_time": 60,
        "small_per_large": (12, 18),
    },
}


class SimulationService:
    """
    Background service that simulates the manufacturing environment.
    
    Stateful: Tracks operator positions, machine health, production state,
    conveyor boxes, and warehouse inventory.
    """
    
    def __init__(self):
        self.is_running = False
        self.sim_task: Optional[asyncio.Task] = None
        self.tick_rate = 1.0  # 1 second per tick
        
        # Layout Data
        self.layout = layout_service.get_layout()
        self.canvas_height = self.layout["dimensions"]["height"]
        self.canvas_width = self.layout["dimensions"]["width"]
        
        # Timing
        self.total_uptime_minutes = 0.0
        
        # =================================================================
        # MACHINE HEALTH (existing)
        # =================================================================
        self.line_health: Dict[int, float] = {
            i: 100.0 for i in range(1, settings.num_production_lines + 1)
        }
        
        # =================================================================
        # PRODUCTION STATE (NEW)
        # =================================================================
        self.machine_production: Dict[int, Dict[str, Any]] = {}
        self._initialize_production_state()
        
        # =================================================================
        # CONVEYOR BOXES (NEW)
        # =================================================================
        self.conveyor_boxes: List[Dict[str, Any]] = []
        self.next_box_id = 1
        
        # =================================================================
        # WAREHOUSE INVENTORY (NEW)
        # =================================================================
        self.warehouse_inventory: Dict[str, int] = {
            pt: 0 for pt in PRODUCT_CATALOG
        }
        
        # =================================================================
        # OPERATORS (existing)
        # =================================================================
        self.operators: List[Dict[str, Any]] = []
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
        
        logger.info(f"🏭 SimulationService initialized with {len(self.machine_production)} production lines")
    
    def _initialize_production_state(self):
        """Initialize production state for each machine line."""
        product_types = list(PRODUCT_CATALOG.keys())
        
        for line in self.layout.get("lines", []):
            line_id = line["id"]
            
            # Round-robin product assignment by default
            assigned_product = product_types[(line_id - 1) % len(product_types)]
            product_info = PRODUCT_CATALOG[assigned_product]
            
            # Randomize cycle parameters within product constraints
            small_min, small_max = product_info["small_per_large"]
            base_time = product_info["base_time"]
            
            self.machine_production[line_id] = {
                # Product Config
                "product_type": assigned_product,
                "product_color": product_info["color"],
                
                # Cycle Parameters
                "small_boxes_per_large": random.randint(small_min, small_max),
                "cycle_time": base_time * random.uniform(0.8, 1.2),
                
                # Current State
                "small_boxes_produced": 0,
                "large_box_fill_level": 0.0,
                "elapsed_time": 0.0,
                "is_running": True,
                
                # Position (for box spawning)
                "x": line["x"],
                "y": line["y"],
                "machine_w": line.get("machine_w", 22),
                "machine_h": line.get("machine_h", 42),
            }
    
    def _reset_state(self):
        """Reset all production state (called on start)."""
        self._initialize_production_state()
        self.conveyor_boxes.clear()
        self.next_box_id = 1
        self.warehouse_inventory = {pt: 0 for pt in PRODUCT_CATALOG}
        self.total_uptime_minutes = 0.0
        
        # Reset line health
        for line_id in self.line_health:
            self.line_health[line_id] = 100.0
    
    # =========================================================================
    # LIFECYCLE
    # =========================================================================
    
    async def start(self):
        """Start the simulation loop."""
        if self.is_running:
            return
        
        self._reset_state()
        self.is_running = True
        self.sim_task = asyncio.create_task(self._run_loop())
        logger.info("🎬 Simulation Service STARTED (Live Production Mode)")
        
        await manager.broadcast({
            "type": "system_status",
            "data": {
                "status": "running",
                "mode": "live_production",
                "timestamp": datetime.now().isoformat()
            }
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
                
                elapsed = (datetime.now() - start_time).total_seconds()
                sleep_time = max(0.1, (self.tick_rate / settings.simulation_speed) - elapsed)
                await asyncio.sleep(sleep_time)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in simulation loop: {e}")
                await asyncio.sleep(1)
    
    # =========================================================================
    # MAIN TICK
    # =========================================================================
    
    async def _tick(self):
        """Execute one simulation step."""
        self.total_uptime_minutes += (self.tick_rate / 60) * settings.simulation_speed
        events: List[Dict[str, Any]] = []
        
        # 1. UPDATE LINE HEALTH (natural degradation)
        self._update_line_health(events)
        
        # 2. PRODUCTION TICK (boxes from machines)
        await self._tick_production(events)
        
        # 3. MOVE CONVEYOR BOXES
        await self._tick_conveyor(events)
        
        # 4. MOVE OPERATORS
        self._move_operators()
        
        # 5. CHECK CAMERAS
        detections = self._check_cameras()
        events.extend(detections)
        
        # 6. RANDOM ANOMALIES
        if random.random() < (settings.event_probability_breakdown / 5):
            events.append(self._generate_breakdown())
        
        if random.random() < (settings.event_probability_safety_violation / 5):
            events.append(self._trigger_safety_violation())
        
        # 7. BROADCAST OPERATOR UPDATES
        for op in self.operators:
            events.append({"type": "operator_update", "data": op})
        
        # 8. BROADCAST WAREHOUSE INVENTORY (periodic)
        events.append({
            "type": "warehouse_inventory",
            "data": self.warehouse_inventory.copy()
        })
        
        # Broadcast all events
        for event in events:
            await manager.broadcast(event)
            
            # Auto-trigger investigation for critical events
            event_data = event.get("data", {})
            if event_data.get("severity") in ["HIGH", "CRITICAL"]:
                asyncio.create_task(self._trigger_investigation(event_data))
    
    # =========================================================================
    # PRODUCTION LOGIC
    # =========================================================================
    
    def _update_line_health(self, events: List[Dict[str, Any]]):
        """Update machine health with natural degradation."""
        for line_id in self.line_health:
            # Slow natural degradation
            degradation = random.uniform(0, 0.05)
            self.line_health[line_id] = max(0, self.line_health[line_id] - degradation)
            
            events.append({
                "type": "line_status",
                "data": {
                    "line_id": line_id,
                    "health": round(self.line_health[line_id], 1),
                }
            })
    
    async def _tick_production(self, events: List[Dict[str, Any]]):
        """Process production for each machine line."""
        for line_id, prod_state in self.machine_production.items():
            machine_health = self.line_health.get(line_id, 100)
            
            # === DETERMINE PRODUCTION SPEED ===
            if machine_health < 20:
                # Critical - machine stopped
                prod_state["is_running"] = False
                speed_modifier = 0.0
            elif machine_health < 50:
                # Warning - machine slowed to 50%
                prod_state["is_running"] = True
                speed_modifier = 0.5
            else:
                # Normal - speed proportional to health
                prod_state["is_running"] = True
                speed_modifier = machine_health / 100.0
            
            # === PRODUCTION PROGRESS ===
            if prod_state["is_running"] and speed_modifier > 0:
                prod_state["elapsed_time"] += self.tick_rate * speed_modifier
                
                # Calculate how many small boxes should have been produced
                progress_ratio = prod_state["elapsed_time"] / prod_state["cycle_time"]
                target_small = int(progress_ratio * prod_state["small_boxes_per_large"])
                
                # Create small boxes as needed
                while prod_state["small_boxes_produced"] < target_small:
                    prod_state["small_boxes_produced"] += 1
                    events.append({
                        "type": "small_box_created",
                        "data": {
                            "line_id": line_id,
                            "count": prod_state["small_boxes_produced"],
                            "product_type": prod_state["product_type"],
                        }
                    })
                
                # Update fill level
                prod_state["large_box_fill_level"] = min(100.0,
                    (prod_state["small_boxes_produced"] / prod_state["small_boxes_per_large"]) * 100
                )
                
                # === LARGE BOX COMPLETE ===
                if prod_state["elapsed_time"] >= prod_state["cycle_time"]:
                    await self._drop_large_box(line_id, prod_state)
                    self._reset_production_cycle(line_id, prod_state)
            
            # Broadcast production state
            events.append({
                "type": "machine_production_state",
                "data": {
                    "line_id": line_id,
                    "fill_level": round(prod_state["large_box_fill_level"], 1),
                    "small_boxes": prod_state["small_boxes_produced"],
                    "product_type": prod_state["product_type"],
                    "product_color": prod_state["product_color"],
                    "is_running": prod_state["is_running"],
                }
            })
    
    def _reset_production_cycle(self, line_id: int, prod_state: Dict[str, Any]):
        """Reset production cycle after dropping a large box."""
        product_info = PRODUCT_CATALOG[prod_state["product_type"]]
        small_min, small_max = product_info["small_per_large"]
        base_time = product_info["base_time"]
        
        prod_state["small_boxes_produced"] = 0
        prod_state["large_box_fill_level"] = 0.0
        prod_state["elapsed_time"] = 0.0
        prod_state["small_boxes_per_large"] = random.randint(small_min, small_max)
        prod_state["cycle_time"] = base_time * random.uniform(0.8, 1.2)
    
    async def _drop_large_box(self, line_id: int, prod_state: Dict[str, Any]):
        """Create a large box on the conveyor from the machine."""
        box_id = f"box_{self.next_box_id}"
        self.next_box_id += 1
        
        # Spawn position: on conveyor Y
        conveyor_y = self.canvas_height - 90  # Main conveyor approximate Y
        
        box = {
            "id": box_id,
            "x": prod_state["x"] + prod_state["machine_w"] / 2,  # Center of machine
            "y": conveyor_y + 8,  # On the belt
            "speed": 25.0,  # Pixels per second
            "product_type": prod_state["product_type"],
            "color": prod_state["product_color"],
            "line_id": line_id,
        }
        self.conveyor_boxes.append(box)
        
        await manager.broadcast({
            "type": "large_box_dropped",
            "data": box
        })
        
        logger.debug(f"📦 Large box dropped from Line {line_id}: {prod_state['product_type']}")
    
    async def _tick_conveyor(self, events: List[Dict[str, Any]]):
        """Move boxes on conveyor towards warehouse."""
        warehouse_x = 75  # Left edge of warehouse zone
        
        boxes_to_remove = []
        for box in self.conveyor_boxes:
            # Move left
            box["x"] -= box["speed"] * self.tick_rate
            
            if box["x"] <= warehouse_x:
                # Arrived at warehouse
                await self._receive_box_at_warehouse(box)
                boxes_to_remove.append(box)
            else:
                # Still moving
                events.append({
                    "type": "conveyor_box_update",
                    "data": {
                        "id": box["id"],
                        "x": box["x"],
                        "y": box["y"],
                        "color": box["color"],
                        "product_type": box["product_type"],
                    }
                })
        
        for box in boxes_to_remove:
            self.conveyor_boxes.remove(box)
    
    async def _receive_box_at_warehouse(self, box: Dict[str, Any]):
        """Add box to warehouse inventory."""
        product_type = box["product_type"]
        self.warehouse_inventory[product_type] += 1
        
        await manager.broadcast({
            "type": "box_arrived_warehouse",
            "data": {
                "id": box["id"],
                "product_type": product_type,
                "color": box["color"],
                "total": self.warehouse_inventory[product_type],
            }
        })
        
        logger.debug(f"📥 Box arrived at warehouse: {product_type} (total: {self.warehouse_inventory[product_type]})")
    
    # =========================================================================
    # AI AGENT INTERFACE
    # =========================================================================
    
    def set_line_product(self, line_id: int, product_type: str) -> Dict[str, Any]:
        """
        AI Agent API: Assign a product type to a production line.
        
        Args:
            line_id: The production line ID (1-20)
            product_type: Product type key from PRODUCT_CATALOG
        
        Returns:
            Status dict with result or error
        """
        if line_id not in self.machine_production:
            return {"error": f"Line {line_id} not found", "status": "error"}
        
        if product_type not in PRODUCT_CATALOG:
            valid = list(PRODUCT_CATALOG.keys())
            return {"error": f"Invalid product '{product_type}'. Valid: {valid}", "status": "error"}
        
        prod_state = self.machine_production[line_id]
        old_product = prod_state["product_type"]
        
        # Update product assignment
        product_info = PRODUCT_CATALOG[product_type]
        prod_state["product_type"] = product_type
        prod_state["product_color"] = product_info["color"]
        
        # Reset production cycle for new product
        self._reset_production_cycle(line_id, prod_state)
        
        logger.info(f"🔄 Line {line_id} product changed: {old_product} → {product_type}")
        
        return {
            "status": "ok",
            "line_id": line_id,
            "product_type": product_type,
            "old_product": old_product,
        }
    
    def get_production_schedule(self) -> Dict[int, Dict[str, Any]]:
        """
        AI Agent API: Get current production assignments for all lines.
        
        Returns:
            Dict mapping line_id to production state
        """
        return {
            line_id: {
                "product_type": state["product_type"],
                "product_name": PRODUCT_CATALOG[state["product_type"]]["name"],
                "is_running": state["is_running"],
                "fill_level": round(state["large_box_fill_level"], 1),
                "health": round(self.line_health.get(line_id, 0), 1),
            }
            for line_id, state in self.machine_production.items()
        }
    
    def get_warehouse_inventory(self) -> Dict[str, int]:
        """
        AI Agent API: Get current warehouse inventory by product type.
        
        Returns:
            Dict mapping product_type to count
        """
        return self.warehouse_inventory.copy()
    
    def get_product_catalog(self) -> Dict[str, Dict[str, Any]]:
        """
        AI Agent API: Get available product types.
        
        Returns:
            The product catalog
        """
        return PRODUCT_CATALOG.copy()
    
    # =========================================================================
    # OPERATORS (existing logic, cleaned up)
    # =========================================================================
    
    def _move_operators(self):
        """Update operator positions towards their targets."""
        speed = 50.0  # pixels per second
        
        for op in self.operators:
            target_x, target_y = op["target_x"], op["target_y"]
            dx = target_x - op["x"]
            dy = target_y - op["y"]
            dist = math.sqrt(dx * dx + dy * dy)
            
            if dist < speed:
                # Arrived
                op["x"] = target_x
                op["y"] = target_y
                if op["status"] == "moving":
                    op["status"] = "working"
            else:
                # Move towards target
                op["x"] += (dx / dist) * speed
                op["y"] += (dy / dist) * speed
                op["status"] = "moving"
            
            # Transition from working to idle
            if op["status"] in ["working", "monitoring"]:
                if random.random() < 0.2:
                    op["status"] = "idle"
                    op["current_action"] = "idle"
            
            # Pick new target if idle
            if op["status"] == "idle" and random.random() < 0.3:
                if self.layout["lines"]:
                    targets = [
                        (random.uniform(50, 1100), random.uniform(320, 420)),
                        (self.layout["lines"][random.randint(0, len(self.layout["lines"]) - 1)]["x"], 380)
                    ]
                    tx, ty = random.choice(targets)
                    op["target_x"] = tx
                    op["target_y"] = ty
                    op["status"] = "moving"
                    op["current_action"] = "patrolling"
    
    # =========================================================================
    # CAMERAS (existing logic)
    # =========================================================================
    
    def _check_cameras(self) -> List[Dict[str, Any]]:
        """Check if any operator is inside a camera's vision cone."""
        events = []
        for cam in self.cameras:
            cam_x, cam_y = cam["x"], cam["y"]
            cam_angle = cam["rotation"]
            cam_fov = cam.get("fov", 60)
            cam_range = cam.get("range", 200)
            
            detected = False
            detection_color = "#FBBF24"  # Default amber
            
            for op in self.operators:
                dx = op["x"] - cam_x
                dy = op["y"] - cam_y
                dist = math.sqrt(dx * dx + dy * dy)
                
                if dist > cam_range:
                    continue
                
                angle_to_op = math.degrees(math.atan2(dy, dx))
                angle_diff = (angle_to_op - (cam_angle - 90)) % 360
                if angle_diff > 180:
                    angle_diff -= 360
                
                if abs(angle_diff) < (cam_fov / 2):
                    detected = True
                    if op.get("current_action") == "VIOLATION":
                        detection_color = "#EF4444"  # Red
            
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
    
    # =========================================================================
    # ANOMALIES (existing logic)
    # =========================================================================
    
    def _generate_breakdown(self) -> Dict[str, Any]:
        """Generate a breakdown and dispatch an operator."""
        line_id = random.randint(1, settings.num_production_lines)
        self.line_health[line_id] = 40.0
        
        # Also stop production on that line
        if line_id in self.machine_production:
            self.machine_production[line_id]["is_running"] = False
        
        # Dispatch nearest operator
        target_line = next((l for l in self.layout["lines"] if l["id"] == line_id), None)
        if target_line and self.operators:
            best_op = min(self.operators, 
                         key=lambda o: math.hypot(o["x"] - target_line["x"], o["y"] - target_line["y"]))
            best_op["target_x"] = target_line["x"]
            best_op["target_y"] = target_line["y"]
            best_op["status"] = "moving"
            best_op["current_action"] = f"Fixing Line {line_id}"
        
        return {
            "type": "visual_signal",
            "data": {
                "source": f"Camera_{line_id:02d}",
                "description": f"Equipment Failure detected on Line {line_id}",
                "severity": "HIGH",
                "line_id": line_id,
                "timestamp": datetime.now().isoformat()
            }
        }
    
    def _trigger_safety_violation(self) -> Dict[str, Any]:
        """Make an operator walk into a dangerous zone."""
        if not self.operators or not self.layout["lines"]:
            return {"type": "noop", "data": {}}
        
        op = random.choice(self.operators)
        line = random.choice(self.layout["lines"])
        op["target_x"] = line["x"]
        op["target_y"] = line["y"]
        op["status"] = "moving"
        op["current_action"] = "VIOLATION"
        
        return {
            "type": "visual_signal",
            "data": {
                "source": "Safety_Cam",
                "description": f"Safety Violation: {op['name']} entering restricted area {line['label']}",
                "severity": "CRITICAL",
                "timestamp": datetime.now().isoformat()
            }
        }
    
    async def _trigger_investigation(self, event_data: dict):
        """Run hypothesis market for a critical event."""
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
    
    async def inject_event(self, event_type: str, severity: str = "HIGH"):
        """Manually inject an event (for demos/testing)."""
        logger.info(f"💉 Injecting manual event: {event_type}")
        if event_type == "fire":
            event = self._generate_breakdown()
            await manager.broadcast(event)
            return event
        return {"status": "injected", "type": event_type}


# Global instance
simulation = SimulationService()

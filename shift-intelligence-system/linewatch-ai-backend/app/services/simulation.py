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


# =============================================================================
# PATHFINDING SYSTEM
# =============================================================================

class PathfindingGrid:
    """
    Grid-based A* pathfinding for realistic operator movement.
    
    Discretizes the factory floor into a grid and uses A* to find paths
    around obstacles (machines, equipment).
    """
    
    def __init__(self, width: int, height: int, cell_size: int = 10):
        """
        Initialize pathfinding grid.
        
        Args:
            width: Floor width in pixels
            height: Floor height in pixels
            cell_size: Size of each grid cell (smaller = more precise, slower)
        """
        self.width = width
        self.height = height
        self.cell_size = cell_size
        self.grid_w = width // cell_size
        self.grid_h = height // cell_size
        self.obstacles: set = set()  # Set of (grid_x, grid_y) tuples
        
        logger.info(f"🗺️  PathfindingGrid initialized: {self.grid_w}x{self.grid_h} cells ({self.grid_w * self.grid_h} total)")
    
    def mark_obstacle(self, x: int, y: int, w: int, h: int):
        """Mark a rectangular area as obstacle."""
        # Convert to int in case floats are passed
        x, y, w, h = int(x), int(y), int(w), int(h)
        
        for gx in range(x // self.cell_size, (x + w) // self.cell_size + 1):
            for gy in range(y // self.cell_size, (y + h) // self.cell_size + 1):
                if 0 <= gx < self.grid_w and 0 <= gy < self.grid_h:
                    self.obstacles.add((gx, gy))
    
    def find_path(self, start_x: float, start_y: float, 
                  end_x: float, end_y: float) -> List[tuple]:
        """
        A* pathfinding algorithm.
        
        Returns:
            List of (x, y) waypoints in world coordinates, or empty list if no path
        """
        from heapq import heappush, heappop
        
        # Convert to grid coords
        start = (int(start_x // self.cell_size), int(start_y // self.cell_size))
        goal = (int(end_x // self.cell_size), int(end_y // self.cell_size))
        
        # Bounds check
        if not (0 <= start[0] < self.grid_w and 0 <= start[1] < self.grid_h):
            return []
        if not (0 <= goal[0] < self.grid_w and 0 <= goal[1] < self.grid_h):
            return []
        
        # Heuristic: Manhattan distance
        def heuristic(a: tuple, b: tuple) -> float:
            return abs(a[0] - b[0]) + abs(a[1] - b[1])
        
        # A* algorithm
        frontier = []
        heappush(frontier, (0, start))
        came_from = {start: None}
        cost_so_far = {start: 0}
        
        while frontier:
            _, current = heappop(frontier)
            
            if current == goal:
                break
            
            # 8-directional movement
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1), 
                          (-1,-1), (-1,1), (1,-1), (1,1)]:
                next_pos = (current[0] + dx, current[1] + dy)
                
                # Bounds check
                if not (0 <= next_pos[0] < self.grid_w and 
                       0 <= next_pos[1] < self.grid_h):
                    continue
                
                # Obstacle check
                if next_pos in self.obstacles:
                    continue
                
                # Cost (diagonal = 1.414, straight = 1)
                move_cost = 1.414 if (dx != 0 and dy != 0) else 1.0
                new_cost = cost_so_far[current] + move_cost
                
                if next_pos not in cost_so_far or new_cost < cost_so_far[next_pos]:
                    cost_so_far[next_pos] = new_cost
                    priority = new_cost + heuristic(next_pos, goal)
                    heappush(frontier, (priority, next_pos))
                    came_from[next_pos] = current
        
        # Reconstruct path
        if goal not in came_from:
            return []  # No path found
        
        path = []
        current = goal
        while current is not None:
            # Convert back to world coords (center of cell)
            wx = current[0] * self.cell_size + self.cell_size / 2
            wy = current[1] * self.cell_size + self.cell_size / 2
            path.append((wx, wy))
            current = came_from[current]
        
        path.reverse()
        return path


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
        
        # =================================================================
        # PATHFINDING GRID
        # =================================================================
        self.pathfinding = PathfindingGrid(
            width=self.canvas_width,
            height=self.canvas_height,
            cell_size=10  # 10px cells for good balance
        )
        self._initialize_obstacles()
        
        # Production zone boundaries (where operators can walk)
        warehouse_w = 80
        breakroom_w = 100
        maintenance_h = 50
        self.production_zone = {
            "x_min": warehouse_w + 50,
            "x_max": self.canvas_width - breakroom_w - 20,
            "y_min": maintenance_h + 20,
            "y_max": self.canvas_height - 100
        }
        
        # Timing
        self.total_uptime_minutes = 0.0
        self.simulation_hours = 0.0  # Track simulation time in hours
        
        # =================================================================
        # 3-SHIFT SYSTEM
        # =================================================================
        self.current_shift = "A"  # A, B, or C
        self.shift_elapsed_hours = 0.0
        self.shift_duration_hours = 8.0  # 8-hour shifts
        
        # Define operator crews for each shift
        self.shift_crews = {
            "A": ["Alex", "Jordan", "Sam", "Casey", "Riley"],
            "B": ["Morgan", "Taylor", "Jamie", "Avery", "Quinn"],
            "C": ["Blake", "Drew", "Sage", "River", "Skylar"]
        }
        
        # =================================================================
        # MACHINE HEALTH
        # =================================================================
        self.line_health: Dict[int, float] = {
            i: 100.0 for i in range(1, settings.num_production_lines + 1)
        }
        
        # =================================================================
        # PRODUCTION STATE
        # =================================================================
        self.machine_production: Dict[int, Dict[str, Any]] = {}
        self._initialize_production_state()
        
        # =================================================================
        # CONVEYOR BOXES
        # =================================================================
        self.conveyor_boxes: List[Dict[str, Any]] = []
        self.next_box_id = 1
        
        # =================================================================
        # WAREHOUSE INVENTORY
        # =================================================================
        self.warehouse_inventory: Dict[str, int] = {
            pt: 0 for pt in PRODUCT_CATALOG
        }
        
        # =================================================================
        # OPERATORS (3-shift system)
        # =================================================================
        self.all_operators: List[Dict[str, Any]] = []  # All 15 operators
        self.operators: List[Dict[str, Any]] = []  # Currently active shift
        self._initialize_all_operators()
        
        # =================================================================
        # SUPERVISOR
        # =================================================================
        office_x = 100
        office_y = 100
        self.supervisor = {
            "id": "SUP-01",
            "name": "Supervisor",
            "x": office_x,
            "y": office_y,
            "status": "idle",
            "current_action": "monitoring",
            "target_x": office_x,
            "target_y": office_y,
            "assigned_operator_id": None,
            "path": [],
            "path_index": 0
        }
        
        # Cameras for detection logic
        self.cameras = self.layout.get("cameras", [])
        
        logger.info(f"🏭 SimulationService initialized with {len(self.machine_production)} production lines")
        logger.info(f"👥 3-shift system: {len(self.all_operators)} total operators (5 per shift)")
    
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
    
    def _initialize_obstacles(self):
        """Mark machines and equipment as obstacles in the pathfinding grid."""
        obstacle_count = 0
        
        # Mark all production line machines as obstacles
        # REDUCED padding to ensure paths exist between machines
        for line in self.layout.get("lines", []):
            x = line["x"]
            y = line["y"]
            w = line.get("machine_w", 22)
            h = line.get("machine_h", 42)
            
            # Reduced padding from 5 to 2 for tighter navigation
            padding = 2
            self.pathfinding.mark_obstacle(
                x - padding, 
                y - padding, 
                w + 2 * padding, 
                h + 2 * padding
            )
            obstacle_count += 1
        
        # Mark warehouse zone as obstacle
        warehouse_w = 80
        self.pathfinding.mark_obstacle(0, 0, warehouse_w, self.canvas_height)
        obstacle_count += 1
        
        # Mark break room and offices as obstacles
        breakroom_w = 100
        self.pathfinding.mark_obstacle(
            self.canvas_width - breakroom_w, 0, 
            breakroom_w, self.canvas_height
        )
        obstacle_count += 1
        
        logger.info(f"🚧 Marked {obstacle_count} obstacles in pathfinding grid")
    
    def _initialize_all_operators(self):
        """Initialize all 15 operators (5 per shift) and activate Shift A."""
        # Get operator positions from layout
        layout_ops = self.layout.get("operators", [])
        
        # Create all 15 operators
        for shift_name, crew_names in self.shift_crews.items():
            for i, name in enumerate(crew_names):
                # Use layout positions, cycling through them
                layout_op = layout_ops[i % len(layout_ops)]
                
                operator = {
                    "id": f"op_{shift_name}_{i+1}",
                    "name": name,
                    "shift": shift_name,
                    "x": layout_op["x"],
                    "y": layout_op["y"],
                    "status": "idle",
                    "current_action": "monitoring",
                    "target_x": layout_op["x"],
                    "target_y": layout_op["y"],
                    "fatigue": 0.0,
                    "on_break": False,
                    "break_requested": False,
                    "path": [],
                    "path_index": 0,
                    "is_active": (shift_name == "A")  # Only Shift A starts active
                }
                self.all_operators.append(operator)
        
        # Set active operators to Shift A
        self.operators = [op for op in self.all_operators if op["shift"] == "A"]
        logger.info(f"👥 Initialized {len(self.all_operators)} operators, Shift A active ({len(self.operators)} operators)")
    
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
        # Update timing
        tick_hours = (self.tick_rate / 3600) * settings.simulation_speed
        self.total_uptime_minutes += tick_hours * 60
        self.simulation_hours += tick_hours
        self.shift_elapsed_hours += tick_hours
        
        events: List[Dict[str, Any]] = []
        
        # 0. CHECK FOR SHIFT CHANGE
        if self.shift_elapsed_hours >= self.shift_duration_hours:
            await self._perform_shift_change(events)
        
        # 1. UPDATE LINE HEALTH (natural degradation)
        self._update_line_health(events)
        
        # 2. PRODUCTION TICK (boxes from machines)
        await self._tick_production(events)
        
        # 3. MOVE CONVEYOR BOXES
        await self._tick_conveyor(events)
        
        # 4. MOVE OPERATORS (with pathfinding)
        self._move_operators()
        
        # 5. ACCUMULATE OPERATOR FATIGUE
        self._update_operator_fatigue()
        
        # 6. MOVE SUPERVISOR (relief logic)
        self._move_supervisor()
        
        # 7. CHECK CAMERAS
        detections = self._check_cameras()
        events.extend(detections)
        
        # 8. RANDOM ANOMALIES
        if random.random() < (settings.event_probability_breakdown / 5):
            events.append(self._generate_breakdown())
        
        if random.random() < (settings.event_probability_safety_violation / 5):
            events.append(self._trigger_safety_violation())
        
        # 9. BROADCAST OPERATOR UPDATES (only active operators)
        for op in self.operators:
            if op.get("is_active", True):
                events.append({"type": "operator_update", "data": op})
        
        # 10. BROADCAST SUPERVISOR UPDATE
        events.append({"type": "supervisor_update", "data": self.supervisor})
        
        # 11. BROADCAST SHIFT INFO
        events.append({
            "type": "shift_status",
            "data": {
                "current_shift": self.current_shift,
                "shift_hours_elapsed": round(self.shift_elapsed_hours, 2),
                "shift_hours_remaining": round(self.shift_duration_hours - self.shift_elapsed_hours, 2),
                "total_simulation_hours": round(self.simulation_hours, 2)
            }
        })
        
        # 12. BROADCAST WAREHOUSE INVENTORY (periodic)
        events.append({
            "type": "warehouse_inventory",
            "data": self.warehouse_inventory.copy()
        })
        
        # Broadcast all events
        for event in events:
            await manager.broadcast(event)
            
            # Auto-trigger investigation for critical events (ONLY if simulation is running)
            if self.is_running:
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
        """Update operator positions using A* pathfinding."""
        speed = 50.0  # pixels per second
        
        for op in self.operators:
            # Skip inactive operators
            if not op.get("is_active", True) or op.get("on_break", False):
                continue
            
            # If operator has a path, follow it
            if op["path"] and op["path_index"] < len(op["path"]):
                waypoint_x, waypoint_y = op["path"][op["path_index"]]
                dx = waypoint_x - op["x"]
                dy = waypoint_y - op["y"]
                dist = math.sqrt(dx * dx + dy * dy)
                
                if dist < speed * self.tick_rate:
                    # Reached waypoint
                    op["x"] = waypoint_x
                    op["y"] = waypoint_y
                    op["path_index"] += 1
                    
                    # Check if reached final destination
                    if op["path_index"] >= len(op["path"]):
                        op["status"] = "working"
                        op["path"] = []
                        op["path_index"] = 0
                else:
                    # Move towards waypoint
                    op["x"] += (dx / dist) * speed * self.tick_rate
                    op["y"] += (dy / dist) * speed * self.tick_rate
                    op["status"] = "moving"
            else:
                # No active path - operator is stationary
                # Transition from working to idle
                if op["status"] in ["working", "monitoring"]:
                    if random.random() < 0.1:  # Reduced frequency
                        op["status"] = "idle"
                        op["current_action"] = "idle"
                
                # Pick new target if idle (with pathfinding)
                if op["status"] == "idle" and random.random() < 0.2:  # Reduced frequency
                    # Generate random target within production zone
                    target_x = random.uniform(
                        self.production_zone["x_min"],
                        self.production_zone["x_max"]
                    )
                    target_y = random.uniform(
                        self.production_zone["y_min"],
                        self.production_zone["y_max"]
                    )
                    
                    # Calculate path using A*
                    path = self.pathfinding.find_path(
                        op["x"], op["y"],
                        target_x, target_y
                    )
                    
                    if path:
                        op["path"] = path
                        op["path_index"] = 0
                        op["target_x"] = target_x
                        op["target_y"] = target_y
                        op["status"] = "moving"
                        op["current_action"] = "patrolling"
                    # If no path found, stay in place
    
    def _update_operator_fatigue(self):
        """Accumulate operator fatigue and handle break requests."""
        FATIGUE_RATE = 0.5  # Fatigue points per tick (1 second)
        FATIGUE_THRESHOLD = 80.0  # Request break at 80%
        BREAK_RECOVERY_RATE = 2.0  # Fatigue recovery per tick on break
        
        for op in self.operators:
            if op["on_break"]:
                # Recover fatigue while on break
                op["fatigue"] = max(0.0, op["fatigue"] - BREAK_RECOVERY_RATE)
                
                # End break when fully recovered
                if op["fatigue"] <= 0:
                    op["on_break"] = False
                    op["break_requested"] = False
                    op["status"] = "idle"
                    op["current_action"] = "returning_from_break"
                    logger.info(f"👷 {op['name']} has returned from break")
            else:
                # Accumulate fatigue while working
                op["fatigue"] = min(100.0, op["fatigue"] + FATIGUE_RATE)
                
                # Request break if fatigued
                if op["fatigue"] >= FATIGUE_THRESHOLD and not op["break_requested"]:
                    op["break_requested"] = True
                    logger.info(f"😓 {op['name']} is requesting a break (fatigue: {op['fatigue']:.1f}%)")
    
    def _move_supervisor(self):
        """Handle supervisor movement and operator relief logic."""
        speed = 60.0  # Supervisor moves slightly faster
        
        # Check if any operator needs relief
        if self.supervisor["status"] == "idle":
            for op in self.operators:
                if op["break_requested"] and not op["on_break"]:
                    # Assign supervisor to relieve this operator
                    self.supervisor["assigned_operator_id"] = op["id"]
                    self.supervisor["status"] = "moving_to_operator"
                    self.supervisor["current_action"] = f"relieving_{op['name']}"
                    
                    # Calculate path to operator
                    path = self.pathfinding.find_path(
                        self.supervisor["x"],
                        self.supervisor["y"],
                        op["x"],
                        op["y"]
                    )
                    
                    if path:
                        self.supervisor["path"] = path
                        self.supervisor["path_index"] = 0
                        logger.info(f"👔 Supervisor dispatched to relieve {op['name']}")
                    else:
                        logger.warning(f"⚠️  No path found for supervisor to {op['name']}")
                    break
        
        # Move supervisor along path
        if self.supervisor["status"] == "moving_to_operator" and self.supervisor["path"]:
            path = self.supervisor["path"]
            idx = self.supervisor["path_index"]
            
            if idx < len(path):
                target_x, target_y = path[idx]
                dx = target_x - self.supervisor["x"]
                dy = target_y - self.supervisor["y"]
                dist = math.sqrt(dx * dx + dy * dy)
                
                if dist < speed:
                    # Reached waypoint
                    self.supervisor["x"] = target_x
                    self.supervisor["y"] = target_y
                    self.supervisor["path_index"] += 1
                    
                    # Check if reached final destination
                    if self.supervisor["path_index"] >= len(path):
                        # Arrived at operator
                        self._relieve_operator()
                else:
                    # Move towards waypoint
                    self.supervisor["x"] += (dx / dist) * speed
                    self.supervisor["y"] += (dy / dist) * speed
    
    def _relieve_operator(self):
        """Relieve an operator and send them on break."""
        op_id = self.supervisor["assigned_operator_id"]
        operator = next((op for op in self.operators if op["id"] == op_id), None)
        
        if operator:
            # Send operator on break
            operator["on_break"] = True
            operator["status"] = "on_break"
            operator["current_action"] = "resting"
            logger.info(f"✅ Supervisor relieved {operator['name']}, now on break")
            
            # Supervisor returns to office
            office_x = 100
            office_y = 100
            path = self.pathfinding.find_path(
                self.supervisor["x"],
                self.supervisor["y"],
                office_x,
                office_y
            )
            
            if path:
                self.supervisor["path"] = path
                self.supervisor["path_index"] = 0
                self.supervisor["status"] = "returning"
                self.supervisor["current_action"] = "returning_to_office"
            else:
                # Fallback: teleport back
                self.supervisor["x"] = office_x
                self.supervisor["y"] = office_y
                self.supervisor["status"] = "idle"
                self.supervisor["current_action"] = "monitoring"
            
            self.supervisor["assigned_operator_id"] = None
        
        # Handle supervisor returning to office
        if self.supervisor["status"] == "returning" and self.supervisor["path"]:
            path = self.supervisor["path"]
            idx = self.supervisor["path_index"]
            
            if idx >= len(path):
                # Arrived back at office
                self.supervisor["status"] = "idle"
                self.supervisor["current_action"] = "monitoring"
                self.supervisor["path"] = []
                self.supervisor["path_index"] = 0
    
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
        
        # Dispatch nearest operator using pathfinding
        target_line = next((l for l in self.layout["lines"] if l["id"] == line_id), None)
        if target_line and self.operators:
            best_op = min(self.operators, 
                         key=lambda o: math.hypot(o["x"] - target_line["x"], o["y"] - target_line["y"]))
            
            # Use pathfinding to navigate to the machine
            path = self.pathfinding.find_path(
                best_op["x"], best_op["y"],
                target_line["x"], target_line["y"]
            )
            
            if path:
                best_op["path"] = path
                best_op["path_index"] = 0
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
        
        # Use pathfinding even for violations (they'll still trigger alerts)
        path = self.pathfinding.find_path(
            op["x"], op["y"],
            line["x"], line["y"]
        )
        
        if path:
            op["path"] = path
            op["path_index"] = 0
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
        """Run hypothesis market for a critical event (only if simulation is running)."""
        # CRITICAL FIX: Check if simulation is still running before starting investigation
        if not self.is_running:
            logger.debug("Skipping investigation - simulation is stopped")
            return
        
        try:
            from app.graphs.hypothesis_market import run_hypothesis_market
            
            # Double-check before broadcasting
            if not self.is_running:
                return
            
            await manager.broadcast({
                "type": "agent_thought",
                "data": {
                    "source": "ORCHESTRATOR",
                    "description": f"Initiating investigation for {event_data.get('description')}",
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            # Pass simulation reference to allow checking if still running
            await run_hypothesis_market(
                signal_id=f"sim-{int(datetime.now().timestamp())}",
                signal_type=event_data.get("type", "UNKNOWN"),
                signal_description=event_data.get("description", "Simulation Event"),
                signal_data=event_data
            )
        except Exception as e:
            # Suppress errors if simulation stopped during investigation
            if self.is_running:
                logger.error(f"Failed to trigger investigation: {e}")
    
    async def _perform_shift_change(self, events: List[Dict[str, Any]]):
        """Perform shift change: deactivate current shift, activate next shift."""
        # Determine next shift
        shift_order = ["A", "B", "C"]
        current_index = shift_order.index(self.current_shift)
        next_shift = shift_order[(current_index + 1) % 3]
        
        logger.info(f"🔄 SHIFT CHANGE: {self.current_shift} → {next_shift}")
        
        # Deactivate current shift operators
        for op in self.operators:
            op["is_active"] = False
            op["status"] = "off_duty"
        
        # Activate next shift operators
        self.current_shift = next_shift
        self.operators = [op for op in self.all_operators if op["shift"] == next_shift]
        
        # Reset new shift operators
        for op in self.operators:
            op["is_active"] = True
            op["fatigue"] = 0.0  # Fresh operators
            op["on_break"] = False
            op["break_requested"] = False
            op["status"] = "idle"
            op["current_action"] = "starting_shift"
            op["path"] = []
            op["path_index"] = 0
        
        # Reset shift timer
        self.shift_elapsed_hours = 0.0
        
        # Broadcast shift change event
        events.append({
            "type": "shift_change",
            "data": {
                "new_shift": next_shift,
                "operator_names": [op["name"] for op in self.operators],
                "timestamp": datetime.now().isoformat()
            }
        })
        
        logger.info(f"✅ Shift {next_shift} now active: {[op['name'] for op in self.operators]}")
    
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

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
import json
import os

from app.config import settings
from app.services.websocket import manager
from app.utils.logging import get_agent_logger
from app.services.layout_service import layout_service
# Import the new models
from app.models.domain import SimulationState, FinancialState, PerformanceMetrics
from app.services.experiment_service import experiment_service

logger = get_agent_logger("Simulation")


# =============================================================================
# PRODUCT CATALOG
# =============================================================================
PRODUCT_CATALOG: Dict[str, Dict[str, Any]] = {
    "widget_a": {
        "name": "Widget A",
        "color": "#3B82F6",  # Blue
        "base_time": 70,      # Seconds to fill large box (reduced from 90)
        "small_per_large": (8, 12),  # Range of small boxes per large
        "price": 12.0,       # Sale price
    },
    "widget_b": {
        "name": "Widget B",
        "color": "#10B981",  # Green
        "base_time": 60,  # Reduced from 75
        "small_per_large": (10, 15),
        "price": 10.0,
    },
    "gizmo_x": {
        "name": "Gizmo X",
        "color": "#F59E0B",  # Amber
        "base_time": 95,  # Reduced from 120
        "small_per_large": (6, 10),
        "price": 18.0,
    },
    "drone_chassis": {
        "name": "Drone Chassis",
        "color": "#8B5CF6",  # Violet
        "base_time": 150,
        "small_per_large": (4, 6),
        "price": 45.0,
    }
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
        self.tick_rate = 0.5  # 0.5 seconds per tick (2Hz updates)
        
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
        self.production_rate_per_min = 0.0  # Track overall production rate
        
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
        

        # =====================================================================
        # STATE & PERSISTENCE
        # =====================================================================
        self.state_file_path = "data/simulation_state.json"
        
        # Initialize Financials (Will be overwritten by load_state if exists)
        self.financials = FinancialState(
            balance=10000.0,
            hourly_wage_cost=0.0
        )
        
        # Initialize KPIs (New)
        self.kpi = PerformanceMetrics(
            oee=1.0,
            availability=1.0,
            performance=1.0,
            safety_score=100.0
        )
        
        # Rate limiting - track which IP started the simulation
        self._current_ip: Optional[str] = None
        
        # Log storage for agents (Last 50 events)
        from collections import deque
        self.recent_events = deque(maxlen=50)
        
        # Initialize Warehouse Inventory
        self.warehouse_inventory = {k: 0 for k in PRODUCT_CATALOG.keys()}
        
        # REMOVED DUPLICATE: The block below was RE-initializing entities that were already set up earlier
        # This was WIPING OUT self.operators after _initialize_all_operators() populated it!
        # Keeping only cameras and conveyors which are legitimately initialized here
        
        # Supervisor & Maintenance Crew (Restored)
        self.supervisor = {
            "x": self.canvas_width - 50, 
            "y": int(self.canvas_height * 0.7),
            "status": "idle",
            "current_action": "monitoring",
            "path": [],
            "path_index": 0,
            "assigned_operator_id": None
        }
        self.maintenance_crew = {
            "x": 60,
            "y": 40,
            "status": "idle",
            "current_action": "standby",
            "path": [],
            "path_index": 0,
            "assigned_machine_id": None
        }
        
        self.cameras = self._initialize_cameras()
        self.conveyors = self.layout["conveyors"]
        self.conveyor_boxes = [] # Boxes on conveyor
        self.evacuation_active = False # Track emergency state
        
        # =================================================================
        # ASYNC TASK TRACKING (for proper cancellation)
        # =================================================================
        self.pending_tasks: set = set()  # Track spawned async tasks
        
        self.last_log_sim_hour = 0.0  # For experiment logging
        
        logger.info(f"🏭 SimulationService initialized with {len(self.machine_production)} production lines")
        logger.info(f"👥 3-shift system: {len(self.all_operators)} total operators (5 per shift)")
    
    def _initialize_cameras(self) -> List[Dict[str, Any]]:
        """Initialize fixed cameras using layout service configuration."""
        cameras = []
        # Inherit cameras directly from layout to ensure ID and position sync with frontend
        layout_cameras = self.layout.get("cameras", [])
        
        if not layout_cameras:
            logger.warning("⚠️ No cameras found in layout configuration!")
            return []

        for cam in layout_cameras:
            # Create a localized copy for simulation state
            sim_cam = cam.copy()
            sim_cam["active"] = True
            cameras.append(sim_cam)
            
        logger.info(f"📹 Initialized {len(cameras)} cameras from layout")
        return cameras

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
                "target_speed_pct": 100.0,  # NEW: Agent controllable setting (100% = normal)
                
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
        
        # Mark break room as obstacle (top portion only, leave office area walkable)
        obstacle_count += 1
        
        # REMOVED: Break room is now walkable so operators can enter
        # breakroom_w = 100
        # breakroom_h = int(self.canvas_height * 0.4)
        # self.pathfinding.mark_obstacle(...)
        obstacle_count += 1
        # Office area (bottom 60%) is left walkable for supervisor
        
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
                    "fatigue_rate": random.uniform(0.1, 0.3),  # MUCH slower fatigue accumulation
                    "on_break": False,
                    "break_requested": False,
                    "path": [],
                    "path_index": 0,
                    "is_active": (shift_name == "A"),  # Only Shift A starts active
                    "visible_to_cameras": False  # Camera visibility tracking
                }
                self.all_operators.append(operator)
        
        # Set active operators to Shift A
        self.operators = [op for op in self.all_operators if op["shift"] == "A"]
        logger.info(f"👥 Initialized {len(self.all_operators)} operators, Shift A active ({len(self.operators)} operators)")
    
    def _load_state(self):
        """Load simulation state from JSON persistence."""
        if not os.path.exists(self.state_file_path):
            logger.info("🆕 No saved state found. Starting fresh simulation.")
            return

        try:
            with open(self.state_file_path, "r") as f:
                data = json.load(f)
            
            # Restore Financials
            fin_data = data.get("financials", {})
            self.financials.balance = fin_data.get("balance", 10000.0)
            self.financials.total_revenue = fin_data.get("total_revenue", 0.0)
            self.financials.total_expenses = fin_data.get("total_expenses", 0.0)
            
            # Restore KPIs
            kpi_data = data.get("kpi", {})
            self.kpi.oee = kpi_data.get("oee", 1.0)
            self.kpi.safety_score = kpi_data.get("safety_score", 100.0)
            self.kpi.availability = kpi_data.get("availability", 1.0)
            self.kpi.performance = kpi_data.get("performance", 1.0)
            self.kpi.uptime_hours = kpi_data.get("uptime_hours", 0.0)
            
            logger.info(f"💾 Loaded simulation state. Balance: ${self.financials.balance:,.2f}, OEE: {self.kpi.oee:.1%}")
            
            # Restore Inventory
            self.warehouse_inventory = data.get("inventory", self.warehouse_inventory)
            
            # Restore Machine Health (Key is string in JSON, convert to int)
            saved_health = data.get("line_health", {})
            for k, v in saved_health.items():
                self.line_health[int(k)] = v
                
            self.shift_elapsed_hours = data.get("shift_elapsed_hours", 0.0)
            

            
        except Exception as e:
            logger.error(f"❌ Failed to load simulation state: {e}")

    def _save_state(self):
        """Save simulation state to JSON persistence."""
        try:
            os.makedirs(os.path.dirname(self.state_file_path), exist_ok=True)
            
            state = {
                "timestamp": datetime.now().isoformat(),
                "financials": {
                    "balance": self.financials.balance,
                    "total_revenue": self.financials.total_revenue,
                    "total_expenses": self.financials.total_expenses
                },
                "kpi": {
                    "oee": self.kpi.oee,
                    "safety_score": self.kpi.safety_score,
                    "availability": self.kpi.availability,
                    "performance": self.kpi.performance,
                    "uptime_hours": self.kpi.uptime_hours
                },
                "inventory": self.warehouse_inventory,
                "line_health": self.line_health,
                "shift_elapsed_hours": self.shift_elapsed_hours
            }
            
            with open(self.state_file_path, "w") as f:
                json.dump(state, f, indent=2)
                
        except Exception as e:
            logger.error(f"❌ Failed to save simulation state: {e}")

    def _calculate_metrics(self, tick_seconds: float):
        """Calculate OEE and Safety Score."""
        # 1. Availability (Are machines operational?)
        lines = self.layout.get("lines", [])
        total_lines = len(lines)
        if total_lines == 0:
            return
            
        # Count operational lines based on health
        operational_lines = sum(1 for line in lines if self.line_health.get(line["id"], 0) > 20)
        current_availability = operational_lines / total_lines
        
        # Simple rolling average for smoothness
        alpha = 0.05
        self.kpi.availability = (self.kpi.availability * (1 - alpha)) + (current_availability * alpha)
        
        # 2. Performance (Are they running at speed?)
        # For simulation, we assume operational lines run at 100% speed unless health degraded
        # Simplified: Performance = Average Health of Operational Lines / 100
        if operational_lines > 0:
            operational_line_ids = [line["id"] for line in lines if self.line_health.get(line["id"], 0) > 20]
            avg_health = sum(self.line_health.get(lid, 0) for lid in operational_line_ids) / operational_lines
            current_performance = avg_health / 100.0
        else:
            current_performance = 0.0
            
        self.kpi.performance = (self.kpi.performance * (1 - alpha)) + (current_performance * alpha)
        
        # 3. OEE
        self.kpi.oee = self.kpi.availability * self.kpi.performance
        
        # 4. Safety Recovery
        # Slowly recover safety score if above 0 (0.1% per tick)
        if self.kpi.safety_score < 100.0:
            self.kpi.safety_score = min(100.0, self.kpi.safety_score + 0.005)
            
        # 5. Uptime
        self.kpi.uptime_hours += (tick_seconds / 3600.0)

    def _calculate_wage_costs(self):
        """Calculate hourly wage cost based on active staff."""
        # Configurable wages
        OPERATOR_WAGE = 30.0  # $/hr
        SUPERVISOR_WAGE = 60.0 # $/hr
        
        op_count = len([o for o in self.operators if o.get("is_active", True)])
        self.financials.hourly_wage_cost = (op_count * OPERATOR_WAGE) + SUPERVISOR_WAGE
        
    def _process_finances(self, tick_seconds: float):
        """Deduct wages and simulate constant operating costs."""
        # Calculate cost per second
        cost_per_second = self.financials.hourly_wage_cost / 3600.0
        tick_cost = cost_per_second * tick_seconds
        
        self.financials.balance -= tick_cost
        self.financials.total_expenses += tick_cost
        
    def _process_market_sales(self):
        """Simulate market demand consuming inventory."""
        # 5% chance per tick to make a sale
        if random.random() < 0.05:
            # Pick a product with inventory
            available_products = [p for p, count in self.warehouse_inventory.items() if count > 0]
            
            if available_products:
                product_key = random.choice(available_products)
                qty = random.randint(1, 5) # Sell 1-5 units
                
                # Check supply
                qty = min(qty, self.warehouse_inventory[product_key])
                
                if qty > 0:
                    price = PRODUCT_CATALOG[product_key]["price"]
                    revenue = qty * price
                    
                    # Transaction
                    self.warehouse_inventory[product_key] -= qty
                    self.financials.balance += revenue
                    self.financials.total_revenue += revenue
                    
                    logger.debug(f"💰 SOLD {qty}x {PRODUCT_CATALOG[product_key]['name']} for ${revenue:.2f}")

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
            
        # Reset Operators (Staggered Fatigue)
        for op in self.operators:
            op["fatigue"] = random.uniform(0, 25.0) # Random start to prevent sync
            op["on_break"] = False
            op["break_requested"] = False
            op["status"] = "monitoring"
            op["current_action"] = "monitoring"
            
        # Reset Evacuation State
        self.evacuation_active = False
    
    # =========================================================================
    # LIFECYCLE
    # =========================================================================
    

    def _create_task(self, coro):
        """
        Helper to create a unified tracked task.
        Ensures all spawned background tasks are tracked in self.pending_tasks
        so they can be cleanly cancelled on stop().
        """
        task = asyncio.create_task(coro)
        self.pending_tasks.add(task)
        task.add_done_callback(self.pending_tasks.discard)
        return task
    
    async def start(self):
        """Start the simulation loop."""
        if self.is_running:
            return
        
        # PERSISTENCE ENABLED: Removed _reset_state() so inventory/health persists across stops.
        # State is only cleared on full server restart or manual clean.
        
        self.is_running = True
        self.is_running = True
        self.sim_task = self._create_task(self._run_loop())
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
        """Stop the simulation loop and all pending async tasks."""
        self.is_running = False
        
        # Cancel main simulation task
        if self.sim_task:
            self.sim_task.cancel()
            try:
                await self.sim_task
            except asyncio.CancelledError:
                pass
        
        # Cancel all pending investigation/agent tasks
        if self.pending_tasks:
            logger.info(f"🛑 Cancelling {len(self.pending_tasks)} pending async tasks...")
            for task in self.pending_tasks:
                if not task.done():
                    task.cancel()
            # Wait for all to complete (with cancellation)
            await asyncio.gather(*self.pending_tasks, return_exceptions=True)
            self.pending_tasks.clear()
        
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
                
                # LOG EXPERIMENT DATA (Every 0.1 sim hours)
                if self.simulation_hours - self.last_log_sim_hour >= 0.1:
                    self.last_log_sim_hour = self.simulation_hours
                    # Prepare log state
                    # We access shared_context here for full data
                    from app.state.context import shared_context
                    log_state = {
                        "simulation_hours": self.simulation_hours,
                        "kpi": {
                            "oee": self.kpi.oee,
                            "safety_score": self.kpi.safety_score,
                        },
                        "financials": {
                            "total_revenue": self.financials.total_revenue,
                            "total_expenses": self.financials.total_expenses,
                            "balance": self.financials.balance,
                        },
                        "active_alerts": shared_context.active_alerts,
                        "safety_violations": shared_context.safety_violations,
                        "production_rate": self.production_rate_per_min,
                        "inventory": self.warehouse_inventory,
                        # For hackathon, assume token stats are tracked globally or mock
                        "agent_stats": {"total_tokens_in": 0, "total_tokens_out": 0} 
                    }
                    await experiment_service.log_tick(log_state)

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
        
        if random.random() < (settings.event_probability_breakdown / 4):
            events.append(self._generate_breakdown())
        
        if random.random() < (settings.event_probability_safety_violation / 4):
            violation_event = await self._trigger_safety_violation()
            events.append(violation_event)
        
        # 9. CHECK FOR UNATTENDED LINES (Staffing Trigger)
        # Random check (1% chance per tick) to avoid spamming
        if random.random() < 0.01:
            unattended_events = self._check_unattended_lines()
            events.extend(unattended_events)
            
            # Trigger investigation for unattended lines if found
            for evt in unattended_events:
                await self._trigger_investigation(evt["data"])
        
        # 10. PROCESS ECONOMY (wages, sales)
        self._process_finances(self.tick_rate)
        self._process_market_sales()
        self._calculate_metrics(self.tick_rate)  # Calculate OEE and safety scores
        
        # 10. BROADCAST ALL OPERATOR DATA (for UI - fatigue bars, stats, etc)
        # This is SEPARATE from fog-of-war visibility
        all_operators_data = {}
        for op in self.operators:
            if op.get("is_active", True):
                all_operators_data[op["id"]] = {
                    "id": op["id"],
                    "name": op["name"],
                    "x": op["x"],  # CRITICAL: Must include position for backend state sync
                    "y": op["y"],
                    "fatigue": op["fatigue"],
                    "on_break": op["on_break"],
                    "break_requested": op["break_requested"],
                    "status": op["status"],
                    "current_action": op["current_action"]
                }
        
        events.append({
            "type": "operator_data_update",
            "data": all_operators_data
        })
        
        # 10. FOG OF WAR - Map Visibility (for rendering positions on map)
        visible_operator_ids = []
        visible_operators_data = {}
        for op in self.operators:
            if op.get("is_active", True) and op.get("visible_to_cameras", False):
                visible_operator_ids.append(op["id"])
                visible_operators_data[op["id"]] = op  # Full data including x, y
        
        # Send visibility sync - frontend will use this for MAP RENDERING only
        events.append({
            "type": "visibility_sync",
            "data": {
                "visible_operator_ids": visible_operator_ids,
                "operators": visible_operators_data
            }
        })
        
        # 10. BROADCAST SUPERVISOR UPDATE
        events.append({"type": "supervisor_update", "data": self.supervisor})
        
        # 11. BROADCAST MAINTENANCE CREW UPDATE
        events.append({"type": "maintenance_crew_update", "data": self.maintenance_crew})
        
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
            "type": "inventory_update",
            "data": self.warehouse_inventory.copy()
        })
        
        # Broadcast Finance Update
        revenue_per_hour = self.financials.total_revenue / self.simulation_hours if self.simulation_hours > 0 else 0.0
        
        await manager.broadcast({
            "type": "financial_update",
            "data": {
                "balance": self.financials.balance,
                "total_revenue": self.financials.total_revenue,
                "total_expenses": self.financials.total_expenses,
                "revenue_per_hour": revenue_per_hour,
                "expenses_per_hour": self.financials.hourly_wage_cost,
                "net_profit": self.financials.total_revenue - self.financials.total_expenses
            }
        })
        
        # Broadcast KPI Update
        await manager.broadcast({
             "type": "kpi_update",
             "data": {
                 "oee": self.kpi.oee,
                 "safety_score": self.kpi.safety_score,
                 "availability": self.kpi.availability,
                 "performance": self.kpi.performance,
                 "quality": self.kpi.quality,
                 "uptime_hours": self.simulation_hours
             }
        })

        # Log to Experiment Service (periodically, e.g. every 10 ticks = 5 seconds)
        # We don't want to log every 0.5s as it fills DB too fast
        if self.is_running and int(self.simulation_hours * 3600) % 5 == 0:
            await experiment_service.log_metric(
                sim_time_hours=self.simulation_hours,
                kpi={
                    "oee": self.kpi.oee,
                    "safety_score": self.kpi.safety_score,
                    "availability": self.kpi.availability,
                    "performance": self.kpi.performance, 
                    "quality": self.kpi.quality
                },
                fin={
                    "total_revenue": self.financials.total_revenue,
                    "total_expenses": self.financials.total_expenses,
                    "balance": self.financials.balance,
                    "hourly_wage_cost": self.financials.hourly_wage_cost
                },
                state={
                    "active_alerts": [], # Placeholder - could link to alert service
                    "safety_violations": [], # Placeholder
                    "production_rate": self.production_rate_per_min
                }
            )

        
        # ====== RATE LIMITING TRACKING ======
        if hasattr(self, '_current_ip') and self._current_ip:
            from app.services.rate_limiter import rate_limiter
            rate_limiter.record_simulation_time(self._current_ip, self.tick_rate)
            
            # Check if IP exceeded daily limit
            can_continue, remaining = rate_limiter.check_daily_limit(self._current_ip)
            if not can_continue:
                logger.warning(f"IP {self._current_ip} exceeded 5-minute daily limit, auto-stopping")
                await self.stop()
                
        # Broadcast all events in a SINGLE batched message
        # This prevents overwhelming the WebSocket with 15-20+ messages per tick
        if events:
            # Store events for agent queries
            self.recent_events.extend(events)
            
            await manager.broadcast({
                "type": "batch_update",
                "data": {
                    "events": events,
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            # Auto-trigger investigation for critical events (ONLY if simulation is running)
            if self.is_running:
                for event in events:
                    event_data = event.get("data", {})
                    if event_data.get("severity") in ["HIGH", "CRITICAL"]:
                        task = asyncio.create_task(self._trigger_investigation(event_data))
                        self.pending_tasks.add(task)
                        task.add_done_callback(lambda t: self.pending_tasks.discard(t))
    
    # =========================================================================
    # PRODUCTION LOGIC
    # =========================================================================
    
    def _update_line_health(self, events: List[Dict[str, Any]]):
        """Update machine health with natural degradation."""
        for line_id in self.line_health:
            # Natural degradation
            base_degradation = random.uniform(0, 0.05)
            
            # Risk factor from high speed
            target_speed = self.machine_production.get(line_id, {}).get("target_speed_pct", 100.0)
            risk_multiplier = 1.0
            if target_speed > 100.0:
                # Exponential risk increase above 100%
                # 110% speed = 1.2x wear
                # 150% speed = 3.2x wear
                excess = (target_speed - 100.0) / 100.0
                risk_multiplier = 1.0 + (excess * 5.0) 
            
            total_degradation = base_degradation * risk_multiplier
            self.line_health[line_id] = max(0, self.line_health[line_id] - total_degradation)
            
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
                # Normal - Speed depends on HEALTH and TARGET SETTING
                health_factor = machine_health / 100.0
                target_factor = prod_state.get("target_speed_pct", 100.0) / 100.0
                prod_state["is_running"] = True
                speed_modifier = health_factor * target_factor
            
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
                    box_event = self._drop_large_box(line_id, prod_state)
                    events.append(box_event)
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
    
    def _drop_large_box(self, line_id: int, prod_state: Dict[str, Any]) -> Dict[str, Any]:
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
        
        logger.debug(f"📦 Large box dropped from Line {line_id}: {prod_state['product_type']}")
        
        # Return event for batching instead of broadcasting directly
        return {
            "type": "large_box_dropped",
            "data": box
        }
    
    async def _tick_conveyor(self, events: List[Dict[str, Any]]):
        """Move boxes on conveyor towards warehouse."""
        warehouse_x = 75  # Left edge of warehouse zone
        
        boxes_to_remove = []
        for box in self.conveyor_boxes:
            # Move left
            box["x"] -= box["speed"] * self.tick_rate
            
            if box["x"] <= warehouse_x:
                # Arrived at warehouse
                warehouse_event = self._receive_box_at_warehouse(box)
                events.append(warehouse_event)
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
    
    def _receive_box_at_warehouse(self, box: Dict[str, Any]) -> Dict[str, Any]:
        """Add box to warehouse inventory."""
        product_type = box["product_type"]
        self.warehouse_inventory[product_type] += 1
        
        logger.debug(f"📥 Box arrived at warehouse: {product_type} (total: {self.warehouse_inventory[product_type]})")
        
        # Return event for batching
        return {
            "type": "box_arrived_warehouse",
            "data": {
                "id": box["id"],
                "product_type": product_type,
                "color": box["color"],
                "total": self.warehouse_inventory[product_type],
            }
        }
    
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

    def dispatch_maintenance_crew(self, machine_id: str, issue: str = "check") -> Dict[str, Any]:
        """
        AI Agent API: Dispatch maintenance crew to a specific machine.
        """
        # Find machine
        target_machine = None
        # Parse machine ID (e.g. CYL-09-A2 -> Line 9)
        # Or look up in machine map?
        # Fallback: Search lines
        line_match = None
        try:
            if "CYL" in machine_id or "Line" in machine_id:
                # Extract number
                import re
                nums = re.findall(r'\d+', machine_id)
                if nums:
                    line_id = int(nums[0])
                    target_machine = next((l for l in self.layout["lines"] if l["id"] == line_id), None)
        except:
            pass
            
        if not target_machine:
            return {"success": False, "error": f"Machine {machine_id} not found on floor map"}
            
        # Dispatch logic
        machine_x = target_machine["x"] + 20
        machine_y = target_machine["y"] + 40
        
        # Calculate path
        start_x, start_y = self.maintenance_crew["x"], self.maintenance_crew["y"]
        path = self.pathfinding.find_path(start_x, start_y, machine_x, machine_y)
        
        if path:
            self.maintenance_crew["path"] = path
            self.maintenance_crew["path_index"] = 0
            self.maintenance_crew["status"] = "moving_to_machine"
            self.maintenance_crew["assigned_machine_id"] = machine_id
            self.maintenance_crew["current_action"] = f"responding_to_{issue}"[:30] # Limit length
            
            logger.info(f"🛠️ Dispatching Maintenance Crew to {machine_id} (Issue: {issue})")
            return {"success": True, "eta_seconds": len(path) * 0.5} # Approx
        else:
            return {"success": False, "error": "Pathfinding failed"}

    async def initiate_safety_clearance(self, line_id_str: str, personnel: str) -> Dict[str, Any]:
        """
        AI Agent API: Execute safety clearance protocol (E-Stop + Log).
        """
        # Parse line ID (L19 -> 19)
        try:
            import re
            nums = re.findall(r'\d+', line_id_str)
            if not nums:
                return {"success": False, "error": "Invalid Line ID"}
            line_id = int(nums[0])
        except:
            return {"success": False, "error": "ID Parse Error"}
            
        # 1. Suspend Line
        await self._suspend_production_line(str(line_id), f"Safety Violation: {personnel}")
        
        # 2. Dispatch Supervisor if available
        # Find machine pos
        target_machine = next((l for l in self.layout["lines"] if l["id"] == line_id), None)
        if target_machine:
            self.dispatch_supervisor_to_location(target_machine["x"], target_machine["y"], f"Safety Audit {line_id}")
            
        return {
            "success": True, 
            "status": "Production Suspended", 
            "protocol": "OSHA-1910-CONTROL-HAZARDOUS-ENERGY"
        }
    
    # =========================================================================
    # OPERATORS (existing logic, cleaned up)
    # =========================================================================
    
    def _move_operators(self):
        """Update operator positions using A* pathfinding."""
        speed = 50.0  # pixels per second
        
        for op in self.operators:
            # === EVACUATION LOGIC (Top Priority) ===
            if self.evacuation_active:
                assembly_x, assembly_y = 1150, 250
                dist = math.hypot(op["x"] - assembly_x, op["y"] - assembly_y)
                
                if dist > 30:
                    if not op["path"] or op["status"] != "evacuating":
                        path = self.pathfinding.find_path(op["x"], op["y"], assembly_x, assembly_y)
                        if path:
                            op["path"] = path
                            op["path_index"] = 0
                            op["status"] = "evacuating"
                            logger.info(f"🚨 {op['name']} evacuating to Assembly Point")
                        else:
                            # Teleport in emergency if stuck
                             op["x"] = assembly_x
                             op["y"] = assembly_y
                             op["status"] = "evacuated"
                else:
                     op["status"] = "evacuated"
                     op["current_action"] = "waiting_at_assembly"
            
            # Skip inactive operators (unless evacuating, handled above)
            elif not op.get("is_active", True):
                continue
                
            # === BREAK LOGIC ===
            if op.get("on_break", False):
                # If on break, go to breakroom (Top Right)
                breakroom_x = self.canvas_width - 50
                breakroom_y = 50
                
                # If not at breakroom, path to it
                dist_to_break = math.hypot(op["x"] - breakroom_x, op["y"] - breakroom_y)
                
                if dist_to_break > 30 and not op["path"]:
                     # Plan path to breakroom
                    path = self.pathfinding.find_path(op["x"], op["y"], breakroom_x, breakroom_y)
                    if path:
                        op["path"] = path
                        op["path_index"] = 0
                        op["status"] = "moving_to_break"
                        logger.info(f"☕ {op['name']} walking to breakroom")
                    else:
                        # Fallback: Teleport if pathfinding fails to avoid getting stuck
                        logger.warning(f"⚠️ Could not pathfind to breakroom for {op['name']} - Teleporting")
                        op["x"] = breakroom_x
                        op["y"] = breakroom_y
                        op["status"] = "on_break"
                
                # If already at breakroom, just chill
                elif dist_to_break <= 30:
                    op["status"] = "on_break"
                    op["current_action"] = "resting"
                    # Small random movement in breakroom? Maybe later.
                    
            # === RETURNING FROM BREAK LOGIC ===
            elif op.get("just_returned_from_break", False):
                 # Go back to station
                dist_to_station = math.hypot(op["x"] - op["target_x"], op["y"] - op["target_y"])
                
                if dist_to_station > 20 and not op["path"]:
                     path = self.pathfinding.find_path(op["x"], op["y"], op["target_x"], op["target_y"])
                     if path:
                        op["path"] = path
                        op["path_index"] = 0
                        op["status"] = "returning_to_work"
                        logger.info(f"🔙 {op['name']} returning to station")
                     else:
                        # Fallback teleport
                        op["x"] = op["target_x"]
                        op["y"] = op["target_y"]
                        op["status"] = "working"
                        op["just_returned_from_break"] = False
                
                elif dist_to_station <= 20:
                    # Arrived at station
                    op["just_returned_from_break"] = False
                    op["status"] = "working"
                    op["current_action"] = "monitoring"

            
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
                        op["path"] = []
                        op["path_index"] = 0
                        
                        # Update status on arrival
                        if op.get("on_break"):
                            op["status"] = "on_break"
                        elif op.get("just_returned_from_break"):
                            op["just_returned_from_break"] = False
                            op["status"] = "working"
                        else:
                            op["status"] = "working"
                else:
                    # Move towards waypoint
                    op["x"] += (dx / dist) * speed * self.tick_rate
                    op["y"] += (dy / dist) * speed * self.tick_rate
                    
                    # Keep status accurate
                    # CRITICAL FIX: Don't overwrite moving_to_break status if path exists
                    if op.get("on_break"):
                        op["status"] = "moving_to_break"
                    elif op.get("just_returned_from_break"):
                         op["status"] = "returning_to_work"
                    elif op["status"] not in ["moving_to_break", "returning_to_work"]:
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
        # Fatigue constants - TUNED
        FATIGUE_THRESHOLD = 60.0  # Request break at 60%
        CRITICAL_FATIGUE = 90.0   # Force break at 90%
        BREAK_RECOVERY_RATE = 2.0  # Fatigue recovery per tick on break
        MAX_CONCURRENT_BREAKS = 2
        
        # Calculate current break load
        current_breaks = 0
        for o in self.operators:
            if o.get("on_break") or o.get("status") == "moving_to_break" or o.get("break_requested"):
                current_breaks += 1
        
        # Supervisor counts if relieving
        if self.supervisor["current_action"].startswith("relieving"):
             current_breaks += 1
        
        for op in self.operators:
            if op["on_break"]:
                # Only recover fatigue if actually AT the breakroom (status is 'on_break')
                # 'moving_to_break' means they are still walking
                if op["status"] == "on_break":
                    op["fatigue"] = max(0.0, op["fatigue"] - BREAK_RECOVERY_RATE)
                    op["current_action"] = "recovering"
                else:
                    # Still walking to break, no recovery yet
                    pass
                
                # End break when fully recovered
                if op["fatigue"] <= 0:
                    op["on_break"] = False
                    op["break_requested"] = False
                    op["status"] = "idle"
                    op["current_action"] = "returning_from_break"
                    op["just_returned_from_break"] = True # Flag to trigger return walk
                    logger.info(f"👷 {op['name']} has returned from break")
            else:
                # Accumulate fatigue while working (using operator's individual rate)
                fatigue_rate = op.get("fatigue_rate", 0.2)  # Fallback to 0.2
                op["fatigue"] = min(100.0, op["fatigue"] + fatigue_rate)
                
                # Request break if fatigued
                if op["fatigue"] >= FATIGUE_THRESHOLD and not op["break_requested"] and not op["on_break"]:
                    
                    # VOLUNTARY BREAK CHECK
                    # If slots available and not critical, go on your own
                    if current_breaks < MAX_CONCURRENT_BREAKS and op["fatigue"] < CRITICAL_FATIGUE:
                        current_breaks += 1
                        op["on_break"] = True
                        op["status"] = "moving_to_break"
                        op["current_action"] = "walking_to_break"
                        
                        # Find breakroom target
                        br_zone = next((z for z in self.layout.get("zones", []) if z["id"] == "break_room"), None)
                        target_x = int(br_zone["x"] + br_zone["width"]/2) if br_zone else self.canvas_width - 50
                        target_y = int(br_zone["y"] + br_zone["height"]/2) if br_zone else 50
                        
                        path = self.pathfinding.find_path(op["x"], op["y"], target_x, target_y)
                        if path:
                            op["path"] = path
                            op["path_index"] = 0
                            op["target_x"] = target_x
                            op["target_y"] = target_y
                        else:
                            op["x"], op["y"] = target_x, target_y
                            op["status"] = "on_break"
                            
                        logger.info(f"☕ {op['name']} taking voluntary break (Fatigue: {op['fatigue']:.1f}%)")
                    
                    elif op["fatigue"] >= CRITICAL_FATIGUE:
                        # CRITICAL: Fatigue is too high, MUST request relief even if queue is full
                        op["break_requested"] = True
                        logger.warning(f"🚨 {op['name']} CRITICAL FATIGUE - Requesting immediate relief (Fatigue: {op['fatigue']:.1f}%)")
                        
                        # EMIT CRITICAL FATIGUE EVENT
                        # Only trigger if NOT already requested to avoid spam
                        task = asyncio.create_task(self._trigger_investigation({
                            "type": "FATIGUE_ALERT",
                            "description": f"CRITICAL: Operator {op['name']} needs immediate relief (fatigue: {op['fatigue']:.1f}%)",
                            "operator_id": op["id"],
                            "operator_name": op["name"],
                            "fatigue_level": op["fatigue"],
                            "severity": "CRITICAL"
                        }))
                        self.pending_tasks.add(task)
                        task.add_done_callback(lambda t: self.pending_tasks.discard(t))

                    else:
                        # Queue is full but not critical yet (< 90%). 
                        # Operator waits and keeps working.
                        pass
    
    def _move_supervisor(self):
        """Handle supervisor movement and operator relief logic."""
        speed = 100.0  # Supervisor moves FAST
        MAX_CONCURRENT_BREAKS = 2
        
        # Check if any operator needs relief
        if self.supervisor["status"] == "idle":
            # Check concurrency
            current_breaks = 0
            for o in self.operators:
                if o.get("on_break") or o.get("current_action", "").startswith("relieving"):
                     current_breaks += 1
            if self.supervisor["current_action"].startswith("relieving"): # Count self if busy
                 current_breaks += 1
            
            # REMOVED: Auto-dispatch logic. 
            # Supervisor now waits for explicit assignment via trigger_operator_break
            pass
        
        # Move supervisor along path
        # Handle both operator relief and location checks
        if self.supervisor["status"] in ["moving_to_operator", "moving_to_location"] and self.supervisor["path"]:
            path = self.supervisor["path"]
            idx = self.supervisor["path_index"]
            
            if idx < len(path):
                target_x, target_y = path[idx]
                dx = target_x - self.supervisor["x"]
                dy = target_y - self.supervisor["y"]
                dist = math.sqrt(dx * dx + dy * dy)
                
                # CONSISTENT SPEED CHECK: Use tick_rate scaling
                step_dist = speed * self.tick_rate
                
                if dist < step_dist:
                    # Reached fast enough to snap to waypoint
                    self.supervisor["x"] = target_x
                    self.supervisor["y"] = target_y
                    self.supervisor["path_index"] += 1
                    
                    # Check if reached final destination
                    if self.supervisor["path_index"] >= len(path):
                        # Arrived at destination
                        if self.supervisor["status"] == "moving_to_operator":
                            self._relieve_operator()
                        else:
                            # Just visiting a location
                            logger.info(f"✅ Supervisor arrived at location for check")
                            
                            # Stay briefly then return
                            self.supervisor["current_action"] = "inspecting"
                            
                            # Trigger return after short delay (simulated via immediate return planning)
                            self._return_supervisor_to_office()
                else:
                    # Move towards waypoint
                    self.supervisor["x"] += (dx / dist) * step_dist
                    self.supervisor["y"] += (dy / dist) * step_dist
        
        # Handle supervisor returning to office
        elif self.supervisor["status"] == "returning" and self.supervisor["path"]:
            path = self.supervisor["path"]
            idx = self.supervisor["path_index"]
            
            if idx < len(path):
                target_x, target_y = path[idx]
                dx = target_x - self.supervisor["x"]
                dy = target_y - self.supervisor["y"]
                dist = math.sqrt(dx * dx + dy * dy)
                
                step_dist = speed * self.tick_rate
                
                if dist < step_dist:
                    # Reached waypoint
                    self.supervisor["x"] = target_x
                    self.supervisor["y"] = target_y
                    self.supervisor["path_index"] += 1
                    
                    # Check if reached final destination
                    if self.supervisor["path_index"] >= len(path):
                        # Arrived back at office
                        logger.info("✅ Supervisor returned to office")
                        self.supervisor["status"] = "idle"
                        self.supervisor["current_action"] = "monitoring"
                        self.supervisor["assigned_operator_id"] = None
                        self.supervisor["path"] = []
                else:
                    # Move towards waypoint
                    self.supervisor["x"] += (dx / dist) * step_dist
                    self.supervisor["y"] += (dy / dist) * step_dist

        # =====================================================================
        # UPDATE MAINTENANCE CREW
        # =====================================================================
        if self.maintenance_crew["status"] == "moving_to_machine" and self.maintenance_crew["path"]:
            path = self.maintenance_crew["path"]
            idx = self.maintenance_crew["path_index"]
            
            if idx < len(path):
                target_x, target_y = path[idx]
                dx = target_x - self.maintenance_crew["x"]
                dy = target_y - self.maintenance_crew["y"]
                dist = math.sqrt(dx * dx + dy * dy)
                
                if dist < speed * self.tick_rate:
                    # Reached waypoint
                    self.maintenance_crew["x"] = target_x
                    self.maintenance_crew["y"] = target_y
                    self.maintenance_crew["path_index"] += 1
                    
                    if self.maintenance_crew["path_index"] >= len(path):
                        # Arrived at machine
                        self.maintenance_crew["status"] = "working"
                        self.maintenance_crew["current_action"] = "repairing"
                        logger.info("🛠️ Maintenance Crew arrived at machine - starting repair")
                        
                        # Simulate repair time then return (or triggered by agent?)
                        # For now, let's fix it after 5 seconds
                        # For now, let's fix it after 5 seconds
                        self._create_task(self._finish_repair(self.maintenance_crew["assigned_machine_id"]))
                else:
                    self.maintenance_crew["x"] += (dx / dist) * speed * self.tick_rate
                    self.maintenance_crew["y"] += (dy / dist) * speed * self.tick_rate
                    
        elif self.maintenance_crew["status"] == "returning" and self.maintenance_crew["path"]:
             path = self.maintenance_crew["path"]
             idx = self.maintenance_crew["path_index"]
            
             if idx < len(path):
                target_x, target_y = path[idx]
                dx = target_x - self.maintenance_crew["x"]
                dy = target_y - self.maintenance_crew["y"]
                dist = math.sqrt(dx * dx + dy * dy)
                
                if dist < speed * self.tick_rate:
                     self.maintenance_crew["x"] = target_x
                     self.maintenance_crew["y"] = target_y
                     self.maintenance_crew["path_index"] += 1
                     
                     if self.maintenance_crew["path_index"] >= len(path):
                         self.maintenance_crew["status"] = "idle"
                         self.maintenance_crew["current_action"] = "standby"
                         self.maintenance_crew["assigned_machine_id"] = None
                         self.maintenance_crew["path"] = []
                else:
                    self.maintenance_crew["x"] += (dx / dist) * speed * self.tick_rate
                    self.maintenance_crew["y"] += (dy / dist) * speed * self.tick_rate

    def dispatch_supervisor_to_location(self, target_x: int, target_y: int, reason: str) -> bool:
        """
        External command to dispatch supervisor to a specific location.
        Used by Master Orchestrator for proactive checking.
        """
        if self.supervisor["status"] != "idle":
            return False  # Supervisor busy
            
        path = self.pathfinding.find_path(
            self.supervisor["x"], self.supervisor["y"],
            target_x, target_y
        )
        
        if path:
            self.supervisor["path"] = path
            self.supervisor["path_index"] = 0
            # Use distinct status so we don't try to relieve an operator upon arrival
            self.supervisor["status"] = "moving_to_location" 
            self.supervisor["current_action"] = f"checking_{reason}"
            logger.info(f"👔 Supervisor dispatched to ({target_x}, {target_y}) for: {reason}")
            return True
        return False

    def dispatch_maintenance_crew(self, machine_id: int) -> bool:
        """
        External command to dispatch maintenance crew to a broken machine.
        Used by Maintenance Agent.
        """
        if self.maintenance_crew["status"] != "idle":
            return False
            
        # Find machine coords
        target_machine = next((l for l in self.layout["lines"] if l["id"] == machine_id), None)
        if not target_machine:
            return False
            
        path = self.pathfinding.find_path(
            self.maintenance_crew["x"], self.maintenance_crew["y"],
            target_machine["x"], target_machine["y"]
        )
        
        if path:
            self.maintenance_crew["path"] = path
            self.maintenance_crew["path_index"] = 0
            self.maintenance_crew["status"] = "moving_to_machine"
            self.maintenance_crew["assigned_machine_id"] = machine_id
            self.maintenance_crew["current_action"] = f"responding_to_line_{machine_id}"
            logger.info(f"🛠️ Maintenance Crew dispatched to Line {machine_id}")
            return True
            
        logger.warning(f"⚠️ No path found for maintenance crew to Line {machine_id}")
        return False

    async def trigger_evacuation(self):
        """Trigger emergency evacuation."""
        if self.evacuation_active:
            return
            
        logger.critical("🚨 TRIGGERING EMERGENCY EVACUATION 🚨")
        self.evacuation_active = True
        
        # 1. Suspend all lines
        for line_id in self.machine_production:
             await self._suspend_production_line(str(line_id), "Emergency Evacuation")
            
        # 2. Update status for all staff and move to Assembly Point
        # Assembly Point is approx (1150, 250) - Front Entrance
        for op in self.operators:
            op["status"] = "evacuating"
            op["current_action"] = "evacuating"
            op["path"] = [] 
            
            # Add randomization to prevent stacking (jitter +/- 40px)
            import random
            offset_x = random.randint(-40, 40)
            offset_y = random.randint(-40, 40)
            
            target_x = 1150 + offset_x
            target_y = 250 + offset_y
            
            path = self.pathfinding.find_path(op["x"], op["y"], target_x, target_y)
            if path:
                op["path"] = path
                op["path_index"] = 0
            
        self.supervisor["status"] = "evacuating"
        self.supervisor["current_action"] = "coordinating_evacuation"
        
        # Supervisor moves to assembly point (central)
        assembly_path = self.pathfinding.find_path(self.supervisor["x"], self.supervisor["y"], 1150, 250)
        if assembly_path:
             self.supervisor["path"] = assembly_path
             self.supervisor["path_index"] = 0
             
        await manager.broadcast({
            "type": "evacuation_alert",
            "data": {
                "status": "ACTIVE",
                "message": "EMERGENCY EVACUATION IN PROGRESS - PROCEED TO ASSEMBLY POINT",
                "timestamp": datetime.now().isoformat()
            }
        })

    async def lift_evacuation(self):
        """Lift emergency evacuation and return to work."""
        if not self.evacuation_active:
            return

        logger.info("✅ LIFTING EVACUATION - ALL CLEAR")
        self.evacuation_active = False

        # 1. Reset Supervisor
        self.supervisor["status"] = "returning"
        self._return_supervisor_to_office()

        # 2. Reset Operators
        # Reset them to 'idle' so they automatically look for work/assigned lines in the next tick
        for op in self.operators:
            op["status"] = "idle"
            op["current_action"] = "returning_to_work"
            op["path"] = []
            
            # Optionally: Find path back to their assigned line immediately
            # (Assuming assigned_line logic exists, but 'idle' usually prompts standard behavior)
            
        # 3. Resume Lines? 
        # Typically lines stay suspended until manually restarted, but for 'return to work' 
        # let's assume operators will restart them.
        
        await manager.broadcast({
            "type": "evacuation_alert",
            "data": {
                "status": "CLEARED",
                "message": "ALL CLEAR - Return to stations",
                "timestamp": datetime.now().isoformat()
            }
        })

    def trigger_operator_break(self, operator_id: str) -> bool:
        """
        External command to force an operator break.
        Used by Staffing Agent.
        """
        # Check concurrency first
        MAX_CONCURRENT_BREAKS = 2
        current_breaks = 0
        for o in self.operators:
            if o.get("on_break") or o.get("current_action", "").startswith("relieving"):
                    current_breaks += 1
        if self.supervisor["current_action"].startswith("relieving"):
                current_breaks += 1
        
        if current_breaks >= MAX_CONCURRENT_BREAKS:
            logger.warning(f"⛔ Break requested for {operator_id} but max concurrent breaks reached")
            return False

        if self.supervisor["status"] != "idle":
            logger.warning(f"⛔ Break requested but Supervisor is busy ({self.supervisor['status']})")
            return False

        for op in self.operators:
            if op["id"] == operator_id:
                op["break_requested"] = True
                
                # IMMEDIATE DISPATCH (Agent-driven)
                self.supervisor["assigned_operator_id"] = op["id"]
                self.supervisor["status"] = "moving_to_operator"
                self.supervisor["current_action"] = f"relieving_{op['name']}"
                
                path = self.pathfinding.find_path(
                    self.supervisor["x"], self.supervisor["y"],
                    op["x"], op["y"]
                )
                
                if path:
                    self.supervisor["path"] = path
                    self.supervisor["path_index"] = 0
                    logger.info(f"👔 Agent dispatched Supervisor to relieve {op['name']}")
                else:
                    logger.warning(f"⚠️  No path found for supervisor")
                    
                return True
        return False

    def set_line_speed(self, line_id: int, speed_pct: float) -> bool:
        """
        External command to set production line target speed.
        Used by Production Agent.
        """
        if line_id not in self.machine_production:
            logger.warning(f"⚠️ Cannot set speed for invalid line {line_id}")
            return False
            
        # Clamp speed between 0% and 200%
        safe_speed = max(0.0, min(200.0, speed_pct))
        self.machine_production[line_id]["target_speed_pct"] = safe_speed
        
        logger.info(f"⚙️ Line {line_id} target speed set to {safe_speed}%")
        return True

    def emergency_stop_line(self, line_id: int) -> bool:
        """
        External command to IMMEDIATELY stop a line (Safety critical).
        Used by Compliance Agent.
        """
        if line_id not in self.machine_production:
            logger.error(f"❌ Cannot emergency stop invalid line {line_id}")
            return False
            
        self.machine_production[line_id]["target_speed_pct"] = 0.0
        self.machine_production[line_id]["is_running"] = False
        
        logger.critical(f"🛑 EMERGENCY STOP TRIGGERED ON LINE {line_id}")
        return True

    def get_visible_operator_ids(self) -> List[str]:
        """
        Get IDs of operators currently visible to cameras.
        Used by Agents to enforce Fog of War.
        """
        return [
            op["id"] for op in self.operators 
            if op.get("visible_to_cameras", False)
        ]

    
    def _return_supervisor_to_office(self):
        """Send supervisor back to office."""
        office_x = self.supervisor.get("office_x", self.canvas_width - 50)
        office_y = self.supervisor.get("office_y", int(self.canvas_height * 0.7))
        
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
            logger.info("🔙 Supervisor returning to office")
        else:
            # Fallback: teleport back
            self.supervisor["x"] = office_x
            self.supervisor["y"] = office_y
            self.supervisor["status"] = "idle"
            self.supervisor["current_action"] = "monitoring"
            self.supervisor["path"] = []

    def _relieve_operator(self):
        """Relieve an operator and send them on break."""
        op_id = self.supervisor["assigned_operator_id"]
        operator = next((op for op in self.operators if op["id"] == op_id), None)
        
        if operator:
            # Send operator on break
            operator["on_break"] = True
            operator["status"] = "moving_to_break" # Set moving status immediately
            operator["current_action"] = "walking_to_breakroom"
            operator["path"] = [] # Clear existing path to force new pathfinding
            logger.info(f"✅ Supervisor relieved {operator['name']}, now moving to break")
            
            # Supervisor returns to office
            self._return_supervisor_to_office()
            
            self.supervisor["assigned_operator_id"] = None
        else:
            # ERROR STATE: Operator not found
            logger.error(f"❌ Supervisor arrived but could not find operator {op_id}")
            # Reset supervisor to avoid getting stuck
            self._return_supervisor_to_office()
            self.supervisor["assigned_operator_id"] = None
        

    
    # =========================================================================
    # CAMERAS (existing logic)
    # =========================================================================
    
    def _check_cameras(self) -> List[Dict[str, Any]]:
        """Check camera FOV and update operator visibility + camera status colors."""
        events = []
        
        # Reset all operator visibility
        for op in self.operators:
            op["visible_to_cameras"] = False
        
        # Check each camera
        for cam in self.cameras:
            cam_x, cam_y = cam["x"], cam["y"]
            cam_angle = cam["rotation"]
            cam_fov = cam.get("fov", 60)
            cam_range = cam.get("range", 200)
            
            detected_operators = []
            camera_status = "idle"
            camera_color = "#64748B"  # Default gray (idle)
            detection_type = "none"
            
            # Check for operators in FOV
            for op in self.operators:
                if not op.get("is_active", True):
                    continue
                
                dx = op["x"] - cam_x
                dy = op["y"] - cam_y
                dist = math.sqrt(dx * dx + dy * dy)
                
                if dist > cam_range:
                    continue
                
                # Check if in FOV cone
                # atan2 returns angle in radians, convert to degrees
                # In canvas coords: 0° = right, 90° = down, 180° = left, 270° = up
                angle_to_op = math.degrees(math.atan2(dy, dx))
                
                # Calculate angle difference (cam_angle is already in same coord system)
                angle_diff = angle_to_op - cam_angle
                
                # Normalize to -180 to 180
                while angle_diff > 180:
                    angle_diff -= 360
                while angle_diff < -180:
                    angle_diff += 360
                
                if abs(angle_diff) < (cam_fov / 2):
                    # Operator is visible!
                    op["visible_to_cameras"] = True
                    detected_operators.append(op["id"])
                    
                    # Determine camera color based on priority
                    if op.get("current_action") == "VIOLATION":
                        camera_status = "critical"
                        camera_color = "#EF4444"  # Red - Safety violation
                        detection_type = "violation"
                    elif "Fixing" in op.get("current_action", ""):
                        if camera_status not in ["critical"]:
                            camera_status = "maintenance"
                            camera_color = "#F97316"  # Orange - Maintenance
                            detection_type = "maintenance"
                    elif camera_status not in ["critical", "maintenance"]:
                        camera_status = "detecting"
                        camera_color = "#FBBF24"  # Yellow - Person detected
                        detection_type = "person"
            
            # Broadcast camera status
            events.append({
                "type": "camera_update",
                "data": {
                    "id": cam["id"],  # Frontend expects "id" not "camera_id"
                    "status": camera_status,
                    "color": camera_color,
                    "detected_operators": detected_operators,
                    "detection_type": detection_type,
                    "operator_count": len(detected_operators)
                }
            })
        
        # Supervisor is always visible (has radio/tracking)
        # No need to mark supervisor as visible since it's broadcast separately
        
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
        # REMOVED: Auto-dispatch logic. Operators should NOT automatically fix lines.
        # This forces the Maintenance Agent to detect and dispatch the crew.
        
        # Only log the breakdown
        logger.warning(f"🚨 Breakdown generated on Line {line_id} (Health: 40%) - Waiting for Maintenance Agent")
            

        
        failure_modes = [
            "Motor Overheat (Temp > 85°C)",
            "Conveyor Belt Jam",
            "Sensor Misalignment",
            "Hydraulic Pressure Drop",
            "Pneumatic Cylinder Stuck"
        ]
        detail = random.choice(failure_modes)
        
        signal = {
            "type": "visual_signal",
            "data": {
                "source": f"Camera_{line_id:02d}",
                "description": f"Equipment Warning: {detail} on Line {line_id}",
                "severity": "HIGH",
                "line_id": line_id,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # Trigger investigation automatically (Fix for missing monitoring loop)
        self._create_task(self._trigger_investigation(signal["data"]))
        
        return signal
    
    async def _trigger_safety_violation(self) -> Dict[str, Any]:
        """Make an operator walk into a dangerous zone and trigger investigation."""
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
        
        # Create the signal
        signal = {
            "type": "visual_signal",
            "data": {
                "source": "Safety_Cam",
                "description": f"Safety Violation: {op['name']} entering restricted area {line['label']}",
                "severity": "CRITICAL",
            "timestamp": datetime.now().isoformat()
            }
        }
        
        
        # The external monitoring loop was missing, so we invoke the agent here.
        self._create_task(self._trigger_investigation(signal["data"]))
        
        return signal
    
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
            
            logger.warning(f"🔍 INVESTIGATION STARTED: {event_data.get('description', 'Unknown Event')}")
            
            await manager.broadcast({
                "type": "agent_thinking",
                "data": {
                    "agent": "ORCHESTRATOR",
                    "thought": f"Initiating investigation for {event_data.get('description')}",
                    "timestamp": datetime.now().isoformat()
                }
            })
            
            # FIX: Call directly instead of creating nested async task
            await run_hypothesis_market(
                signal_id=f"sim-{int(datetime.now().timestamp())}",
                signal_type=event_data.get("type", "UNKNOWN"),
                signal_description=event_data.get("description", "Simulation Event"),
                signal_data=event_data
            )
            
            logger.info(f"✅ INVESTIGATION COMPLETED: {event_data.get('description')}")
            
        except Exception as e:
            # ALWAYS log the error, even if simulation stopped
            logger.error(f"❌ INVESTIGATION FAILED: {event_data.get('description')} - Error: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def _finish_repair(self, machine_id: int):
        """Helper to simulate repair duration and return trip."""
        await asyncio.sleep(5) # Repair takes 5 seconds
        
        # Fix machine
        self.line_health[machine_id] = 100.0
        if machine_id in self.machine_production:
             self.machine_production[machine_id]["is_running"] = True
        
        # Determine repair cost
        repair_cost = 500.0
        self.financials.balance -= repair_cost
        self.financials.total_expenses += repair_cost
        
        logger.info(f"✅ Line {machine_id} repaired by Maintenance Crew (-${repair_cost:.2f})")
        
        # Return to base
        self.maintenance_crew["status"] = "returning"
        self.maintenance_crew["current_action"] = "returning_to_base"
        
        # Maintenance Bay is at (canvas_width - 60, 40)
        target_x = self.canvas_width - 60
        target_y = 40
        
        path = self.pathfinding.find_path(
            self.maintenance_crew["x"], self.maintenance_crew["y"],
            target_x, target_y
        )
        if path:
            self.maintenance_crew["path"] = path
            self.maintenance_crew["path_index"] = 0
            
    def _check_unattended_lines(self) -> List[Dict[str, Any]]:
        """Check for running lines with no operator nearby."""
        events = []
        
        # Initialize tracker if not exists (lazy init)
        if not hasattr(self, "last_alert_times"):
            self.last_alert_times = {}
            
        current_time = datetime.now().timestamp()
        COOLDOWN_SECONDS = 300  # 5 minutes
        
        for line_id, state in self.machine_production.items():
            if not state.get("is_running", False):
                continue
                
            # Check cooldown first
            last_alert = self.last_alert_times.get(line_id, 0)
            if (current_time - last_alert) < COOLDOWN_SECONDS:
                continue
                
            line_x = state["x"]
            line_y = state["y"]
            
            # Check if any operator is within range
            has_operator = False
            for op in self.operators:
                if not op.get("is_active", True):
                    continue
                
                # Check distance
                dx = op["x"] - line_x
                dy = op["y"] - line_y
                dist = math.sqrt(dx * dx + dy * dy)
                
                if dist < 200:  # INCREASED to 200px (approx 3-4 machines wide)
                    has_operator = True
                    break
            
            # DISABLED: Prevents event spam for demo
            # Unattended lines are not critical enough to trigger investigations
            # if not has_operator:
            #     # Line is running but abandoned!
            #     self.last_alert_times[line_id] = current_time
            #     
            #     events.append({
            #         "type": "visual_signal",
            #         "data": {
            #             "source": f"Camera_Line_{line_id}",
            #             "description": f"Staffing Alert: Line {line_id} is running UNATTENDED (Check coverage)",
            #             "severity": "MEDIUM",
            #             "line_id": line_id,
            #             "timestamp": datetime.now().isoformat()
            #         }
            #     })
        
        return events

    def move_operator_to_line(self, operator_id: str, line_id: int) -> bool:
        """
        Force move an operator to a specific line (Agent Action).
        """
        # Find operator
        operator = next((op for op in self.operators if op["id"] == operator_id), None)
        if not operator:
            logger.error(f"❌ Cannot move operator {operator_id}: Not found")
            return False
            
        # Find line location
        line_data = self.machine_production.get(line_id)
        if not line_data:
            logger.error(f"❌ Cannot move operator to Line {line_id}: Line not found")
            return False
            
        target_x = line_data["x"]
        target_y = line_data["y"]
        
        # Calculate path
        path = self.pathfinding.find_path(
            operator["x"], operator["y"],
            target_x, target_y
        )
        
        if path:
            operator["path"] = path
            operator["path_index"] = 0
            operator["status"] = "moving_to_offset" # Custom status
            operator["current_action"] = f"Relocating to Line {line_id}"
            
            # Update their "assigned" line in the sim state immediately so they don't wander back
            # Note: The Roster/Department object is separate, but we update the sim entity here
            # The agent tool handles the Roster update.
            return True
        else:
            logger.warning(f"⚠️ No path found for {operator['name']} to Line {line_id}")
            return False
            
    def _perform_shift_change(self, events: List[Dict[str, Any]]):
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
        
        event = None
        if event_type == "fire" or event_type == "breakdown":
            event = self._generate_breakdown()
            # Force severity if specified
            if severity:
                event["data"]["severity"] = severity
                
        elif event_type == "safety_violation":
            event = await self._trigger_safety_violation()
            
        if event:
            # Broadcast to UI
            await manager.broadcast(event)
            
            # TRIGGER THE AGENT GRAPH!
            # This was missing - agents were ignoring manual events
            if event["data"].get("severity") in ["HIGH", "CRITICAL"]:
                logger.info(f"🤖 Triggering Agent Investigation for manual {event_type}")
            if event["data"].get("severity") in ["HIGH", "CRITICAL"]:
                logger.info(f"🤖 Triggering Agent Investigation for manual {event_type}")
                self._create_task(self._trigger_investigation(event["data"]))
            
            return event
            
        return {"status": "ignored", "reason": "unknown event type"}


# Global instance
simulation = SimulationService()

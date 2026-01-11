"""
Mock layout service to provide 2D coordinates for the frontend map.
Production floor layout synced with vision_service camera configuration.

Layout based on user's sketch:
- Warehouse: LEFT column with feeders going IN from production
- Main conveyor: BOTTOM horizontal strip (Curved upward on left)
- Machines: Vertical stacks feeding DOWN to main conveyor
- Operators: Above machines
- Maintenance: TOP strip
- Break Room: TOP RIGHT
"""
from typing import Dict, List, Any

class LayoutService:
    """Generates the floor layout for the visualization."""
    
    # Camera configuration (synced with vision_service.py)
    CAMERA_CONFIG = {
        "CAM-01": [1, 2, 3, 4],
        "CAM-02": [5, 6, 7, 8],
        "CAM-03": [9, 10, 11, 12],
        "CAM-04": [13, 14, 15, 16],
        "CAM-05": [17, 18, 19, 20],
    }
    
    def get_layout(self) -> Dict[str, Any]:
        """Return the floor plan with new user requirements."""
        
        # Canvas dimensions
        canvas_w = 1200
        canvas_h = 500
        
        # Zone dimensions
        warehouse_w = 80
        maintenance_h = 50
        breakroom_w = 100
        main_conveyor_h = 30
        
        # Key layout positions (calculated from bottom up to avoid gaps)
        # Bringing everything UP significantly (User Req: "bring machines and people up")
        bottom_spacer = 60 
        main_conveyor_y = canvas_h - main_conveyor_h - bottom_spacer
        
        # Machine stack dimensions (User Req: "smaller width but taller vertically")
        machine_w = 22  # Narrower
        machine_h = 42  # Taller
        equip_w = 18     
        equip_h = 20    
        
        # Position machines just above the main conveyor
        # Stack: Machine -> Equipment -> Connector -> Main Conveyor
        connector_h = 10 # Short, tight connector
        machine_zone_y = main_conveyor_y - (connector_h + equip_h + machine_h + 5)
        
        # Operators sit just above the machines
        operator_zone_y = machine_zone_y - 35
        
        layout = {
            "dimensions": {"width": canvas_w, "height": canvas_h},
            "zones": [
                # Maintenance Bay - Top strip (center only)
                {
                    "id": "maintenance_bay",
                    "x": warehouse_w, 
                    "y": 0, 
                    "width": canvas_w - warehouse_w - breakroom_w, 
                    "height": maintenance_h, 
                    "label": "Maintenance",
                    "color": "#0D9488"
                },
                # Warehouse - Left column (full height)
                {
                    "id": "warehouse",
                    "x": 0,
                    "y": 0,
                    "width": warehouse_w,
                    "height": canvas_h,
                    "label": "Warehouse",
                    "color": "#F59E0B" # Amber/Yellow for hatch base
                },
                # Break Room - Top Right (Reduced height to fit Reception)
                {
                    "id": "break_room",
                    "x": canvas_w - breakroom_w,
                    "y": 0,
                    "width": breakroom_w,
                    "height": canvas_h * 0.4,
                    "label": "Break Room",
                    "color": "#475569"
                },
                # Reception / Front Door - Middle Right
                {
                    "id": "reception",
                    "x": canvas_w - breakroom_w,
                    "y": canvas_h * 0.4,
                    "width": breakroom_w,
                    "height": canvas_h * 0.2, # Middle section
                    "label": "Entrance",
                    "color": "#64748B"
                },
                # Offices - Bottom Right
                {
                    "id": "offices",
                    "x": canvas_w - breakroom_w,
                    "y": canvas_h * 0.6,
                    "width": breakroom_w,
                    "height": canvas_h * 0.4 - 20, # Fill to near bottom
                    "label": "Offices",
                    "color": "#334155"
                },
                # Production Floor - Center area
                {
                    "id": "production_floor",
                    "x": warehouse_w,
                    "y": maintenance_h,
                    "width": canvas_w - warehouse_w - breakroom_w,
                    "height": canvas_h - maintenance_h,
                    "label": "",
                    "color": "#1E293B"
                },
            ],
            "lines": [],
            "operators": [],
            "conveyors": [],
            "cameras": []
        }
        
        # Production area bounds
        # Shift start X slightly right to make room for vertical conveyor curve
        # "look at all that space" -> use a curve allowance that fills the gap but looks nice
        curve_allowance = 45 
        prod_start_x = warehouse_w + curve_allowance
        prod_end_x = canvas_w - breakroom_w - 20
        available_width = prod_end_x - prod_start_x
        line_spacing = available_width / 20
        
        # Store last machine X to end main conveyor there
        last_machine_right_x = 0
        
        # Generate 20 production lines (vertical stacks feeding down to conveyor)
        for i in range(1, 21):
            x = prod_start_x + (i - 0.5) * line_spacing - machine_w / 2
            # Update last machine X
            last_machine_right_x = x + machine_w + 10 # Little buffer
            
            layout["lines"].append({
                "id": i,
                "label": f"L{i}",
                "x": x,
                "y": machine_zone_y,
                "machine_w": machine_w,
                "machine_h": machine_h,
                "equip_w": equip_w,
                "equip_h": equip_h,
                "connector_h": connector_h,
                "status": "operational",
                "health": 100
            })
        
        # 5 Cameras (Strategic Surveillance Points - User Request: 4 Corners + 1 Center)
        # Production Floor Bounds
        cam_top_y = maintenance_h + 10
        cam_bot_y = canvas_h - 10 # Absolute bottom edge
        cam_left_x = prod_start_x + 10
        cam_right_x = prod_end_x - 10
        cam_center_x = (prod_start_x + prod_end_x) / 2
        
        # Cameras positioned to point toward center of operator zone
        # Operator zone center: ~(690, 310)
        # Angles calculated to make cameras face inward
        # FOV and range reduced to create coverage gaps (AI can recommend more cameras)
        
        # Cam 1: Top-Left → point toward center-right-down
        layout["cameras"].append({
            "id": "cam_01", "label": "CAM-01", "lines_covered": [1,2,3,4],
            "x": cam_left_x - 50, "y": cam_top_y, "rotation": 26, 
            "fov": 80, "range": 250, "status": "active"
        })
        
        # Cam 2: Top-Right → point toward center-left-down
        layout["cameras"].append({
            "id": "cam_02", "label": "CAM-02", "lines_covered": [17,18,19,20],
            "x": cam_right_x + 20, "y": cam_top_y, "rotation": 154, 
            "fov": 80, "range": 250, "status": "active"
        })
        
        # Cam 3: Bottom-Left → point toward center-right-up
        layout["cameras"].append({
            "id": "cam_03", "label": "CAM-03", "lines_covered": [5,6,7,8],
            "x": cam_left_x - 50, "y": cam_bot_y, "rotation": 342, 
            "fov": 80, "range": 250, "status": "active"
        })
        
        # Cam 4: Bottom-Right → point toward center-left-up
        layout["cameras"].append({
            "id": "cam_04", "label": "CAM-04", "lines_covered": [13,14,15,16],
            "x": cam_right_x + 20, "y": cam_bot_y, "rotation": 198, 
            "fov": 80, "range": 250, "status": "active"
        })
        
        # Cam 5: Top-Center → point straight down at operators
        layout["cameras"].append({
            "id": "cam_05", "label": "CAM-05", "lines_covered": [9,10,11,12],
            "x": cam_center_x, "y": cam_top_y, "rotation": 90, 
            "fov": 90, "range": 280, "status": "active"
        })
        
        # Cam 6: Break Room → small camera pointing down (checks who's on break)
        breakroom_x = canvas_w - breakroom_w
        breakroom_cam_x = breakroom_x + (breakroom_w / 2)
        breakroom_cam_y = 10
        layout["cameras"].append({
            "id": "cam_06", "label": "CAM-06", "lines_covered": [],
            "x": breakroom_cam_x, "y": breakroom_cam_y, "rotation": 90, 
            "fov": 50, "range": 150, "status": "active"
        })

        # Cam 7: Entrance/Assembly Point (User Req: Monitoring outside/entrance)
        entrance_x = canvas_w - 50
        entrance_y = canvas_h * 0.5  # middle of right side
        layout["cameras"].append({
            "id": "cam_07", "label": "CAM-07", "lines_covered": [],
            "x": entrance_x - 40, "y": entrance_y, "rotation": 0, # Point right towards door
            "fov": 90, "range": 200, "status": "active"
        })
        
        # RESTORED: Operator Generation
        operator_names = ["Alex", "Jordan", "Sam", "Casey", "Riley"]
        operator_statuses = ["monitoring", "inspecting", "idle", "idle", "monitoring"]
        # Spread them out
        op_spacing = available_width / 6
        
        for i, (name, status) in enumerate(zip(operator_names, operator_statuses)):
            layout["operators"].append({
                "id": f"op_{i+1}",
                "name": name,
                "x": prod_start_x + (i + 1) * op_spacing,
                "y": operator_zone_y,
                "status": status,
                "current_action": "monitoring",
                "assigned_lines": [] 
            })
        
        # Conveyor Logic: Flow TOWARDS Warehouse (Right -> Left)
        # Main Conveyor (Bottom)
        main_conv_total_width = last_machine_right_x - (warehouse_w + 10)
        segment_count = 4
        segment_width = main_conv_total_width / segment_count
        
        for i in range(segment_count):
            layout["conveyors"].append({
                "id": f"main_conv_{i+1}",
                "x": (warehouse_w + 10) + i * segment_width,
                "y": main_conveyor_y,
                "width": segment_width,
                "height": main_conveyor_h,
                "direction": "horizontal",
                "flow": "reverse", # Move Right to Left
                "status": "running"
            })
            
        # Entry/Intake Conveyor (From Warehouse to Machines? No, Machines make things.)
        # Maybe "Raw Material" feed?
        # User said: "machines making small product boxes that quickly going into larger boxes that then go onto the conveyors off into conveyor"
        # So Machines -> Main Conveyor -> Warehouse.
        
        # We don't need the weird vertical curve anymore.
        # Just a clean layout.
            
        return layout

layout_service = LayoutService()

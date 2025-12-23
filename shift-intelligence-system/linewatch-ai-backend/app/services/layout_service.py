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
        
        # 5 Cameras (positioned above their line groups)
        for cam_idx, (cam_id, lines_covered) in enumerate(self.CAMERA_CONFIG.items()):
            first_x = prod_start_x + (lines_covered[0] - 0.5) * line_spacing
            last_x = prod_start_x + (lines_covered[-1] - 0.5) * line_spacing
            cam_x = (first_x + last_x) / 2
            
            layout["cameras"].append({
                "id": cam_id.lower().replace("-", "_"),
                "label": cam_id,
                "lines_covered": lines_covered,
                "x": cam_x,
                "y": operator_zone_y - 15, # Above operators
                "rotation": 180,
                "fov": 50,
                "range": machine_h + equip_h + 60,
                "status": "active"
            })
        
        # 5 Operators (in operator zone above machines)
        operator_names = ["Alex", "Jordan", "Sam", "Casey", "Riley"]
        operator_statuses = ["monitoring", "inspecting", "idle", "moving", "monitoring"]
        for i, name in enumerate(operator_names):
            x = prod_start_x + (i + 0.5) * (available_width / 5)
            layout["operators"].append({
                "id": f"op_{i+1}",
                "name": name,
                "x": x,
                "y": operator_zone_y,
                "status": operator_statuses[i],
                "assigned_lines": list(self.CAMERA_CONFIG[f"CAM-0{i+1}"])
            })
        
        # Conveyor segments
        # 1. Main conveyor (bottom) - Horizontal
        # Calculate width to stop exactly at last machine (User Req)
        main_conv_total_width = last_machine_right_x - (warehouse_w + curve_allowance)
        
        segment_count = 5
        segment_width = main_conv_total_width / segment_count
        
        for i in range(segment_count):
            layout["conveyors"].append({
                "id": f"main_conv_{i+1}",
                "x": (warehouse_w + curve_allowance) + i * segment_width,
                "y": main_conveyor_y,
                "width": segment_width,
                "height": main_conveyor_h,
                "direction": "horizontal",
                "status": "running"
            })
            
        # 2. Vertical Connector Curve (Left side) 
        # Connects main conveyor up to the feeders
        feeder_spacing = 35 
        top_feeder_y = main_conveyor_y - (4 * feeder_spacing) 
        
        layout["conveyors"].append({
            "id": "vert_curve_conv",
            "x": warehouse_w, # Starts at warehouse edge
            "y": top_feeder_y,
            "width": curve_allowance + 2, # Connects to start of main conveyor
            "height": main_conveyor_y + main_conveyor_h - top_feeder_y,
            "direction": "vertical",
            "status": "running"
        })
        
        # 3. Warehouse feeder conveyors (Horizontal going INTO vertical curve)
        for i in range(4):
            y_pos = main_conveyor_y - ((i + 1) * feeder_spacing)
            feeder_h = 10 
            
            layout["conveyors"].append({
                "id": f"feeder_{i+1}",
                "x": 0,
                "y": y_pos + (main_conveyor_h - feeder_h)/2 + 8, 
                "width": warehouse_w + 10, # Connect slightly into curve
                "height": feeder_h,
                "direction": "horizontal",
                "status": "running"
            })
            
        return layout

layout_service = LayoutService()

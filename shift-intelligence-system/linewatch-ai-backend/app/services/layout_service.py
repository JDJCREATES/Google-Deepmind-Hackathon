"""
Mock layout service to provide 2D coordinates for the frontend map.
"""
from typing import Dict, List, Any

class LayoutService:
    """Generates the static floor layout for the visualization."""
    
    def get_layout(self) -> Dict[str, Any]:
        """Return the floor plan including zones, lines, and cameras."""
        
        # Canvas dimensions: 1200x800
        layout = {
            "dimensions": {"width": 1200, "height": 800},
            "zones": [
                {
                    "id": "production_floor",
                    "x": 20, 
                    "y": 20, 
                    "width": 800, 
                    "height": 760, 
                    "label": "Assembly Area",
                    "color": "#1e293b" # Slate-800
                },
                {
                    "id": "break_room",
                    "x": 840,
                    "y": 20,
                    "width": 340,
                    "height": 200,
                    "label": "Break Room",
                    "color": "#334155" # Slate-700
                },
                {
                    "id": "maintenance_bay",
                    "x": 840,
                    "y": 240,
                    "width": 340,
                    "height": 200,
                    "label": "Maintenance Bay",
                    "color": "#334155" 
                },
                {
                    "id": "warehouse",
                    "x": 840,
                    "y": 460,
                    "width": 340,
                    "height": 320,
                    "label": "Warehouse",
                    "color": "#334155" 
                }
            ],
            "lines": [],
            "cameras": []
        }
        
        # Generate 20 lines in a 2-column grid
        # Col 1: Lines 1-10
        # Col 2: Lines 11-20
        start_x = 60
        start_y = 60
        col_width = 360
        row_height = 70
        
        for i in range(1, 21):
            col = 0 if i <= 10 else 1
            row_idx = (i - 1) % 10
            
            x = start_x + (col * col_width)
            y = start_y + (row_idx * row_height)
            
            line_id = i
            line_w = 280
            line_h = 40
            
            layout["lines"].append({
                "id": line_id,
                "label": f"Line {line_id}",
                "x": x,
                "y": y,
                "width": line_w,
                "height": line_h,
                "orientation": "horizontal",
                "status": "operational" # default
            })
            
            # Place a camera above each line looking down
            # Camera is a point + FOV cone
            layout["cameras"].append({
                "id": f"cam_{line_id:02d}",
                "line_id": line_id,
                "x": x + (line_w / 2), # Center of line
                "y": y - 10,           # Slightly above
                "rotation": 90,        # Pointing down (0 is right, 90 is down)
                "fov": 60,
                "range": 100,
                "label": f"CAM-{line_id:02d}"
            })
            
        return layout

layout_service = LayoutService()

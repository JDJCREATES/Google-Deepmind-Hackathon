"""
Camera coverage system - enforces that violations are only detected in covered areas.
"""
from typing import Dict, List, Any, Tuple
from app.services.simulation import simulation


def is_position_visible_to_cameras(x: float, y: float, cameras: List[Dict]) -> bool:
    """
    Check if a position is visible to any camera.
    
    Args:
        x, y: Position to check
        cameras: List of camera dicts with position and range
    
    Returns:
        True if position is within range of at least one camera
    """
    CAMERA_RANGE = 80  # pixels - cameras can see 80px radius
    
    for camera in cameras:
        cam_pos = camera.get("position", {})
        cam_x = cam_pos.get("x", 0)
        cam_y = cam_pos.get("y", 0)
        
        # Calculate distance
        dist = ((x - cam_x) ** 2 + (y - cam_y) ** 2) ** 0.5
        
        if dist <= CAMERA_RANGE:
            return True
    
    return False


def filter_violations_by_camera_coverage(
    violations: List[Dict[str, Any]],
    cameras: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Filter violations to only those visible to cameras.
    
    This enforces the constraint that agents can only detect issues
    in camera-covered areas.
    
    Args:
        violations: All safety violations
        cameras: Current camera positions
    
    Returns:
        Only violations within camera range
    """
    visible_violations = []
    
    for violation in violations:
        # Get violation location
        location = violation.get("location", {})
        x = location.get("x", 0)
        y = location.get("y", 0)
        
        # Check if any camera can see this location
        if is_position_visible_to_cameras(x, y, cameras):
            visible_violations.append(violation)
        # else: violation exists but can't be detected - blind spot!
    
    return visible_violations


def calculate_camera_coverage_stats(cameras: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate coverage statistics for current camera layout.
    
    Returns data that agents can use to discover blind spots.
    """
    CAMERA_RANGE = 80
    
    # Production zone boundaries
    prod_x_min = 150
    prod_x_max = simulation.canvas_width - 180
    prod_y_min = 100
    prod_y_max = simulation.canvas_height - 100
    
    # Sample points across production zone to estimate coverage
    sample_points = []
    for x in range(int(prod_x_min), int(prod_x_max), 50):
        for y in range(int(prod_y_min), int(prod_y_max), 50):
            sample_points.append((x, y))
    
    # Count how many sample points are covered
    covered = 0
    for x, y in sample_points:
        if is_position_visible_to_cameras(x, y, cameras):
            covered += 1
    
    coverage_pct = (covered / len(sample_points)) * 100 if sample_points else 0
    
    # Identify which production lines have coverage
    covered_lines = set()
    uncovered_lines = set()
    
    for line_id in range(1, 21):  # 20 lines
        line_y = 100 + (line_id * 30)
        line_x = (prod_x_min + prod_x_max) / 2
        
        if is_position_visible_to_cameras(line_x, line_y, cameras):
            covered_lines.add(line_id)
        else:
            uncovered_lines.add(line_id)
    
    return {
        "coverage_percentage": round(coverage_pct, 1),
        "camera_count": len(cameras),
        "camera_range_px": CAMERA_RANGE,
        "covered_lines": sorted(list(covered_lines)),
        "uncovered_lines": sorted(list(uncovered_lines)),
        "total_lines": 20
    }


async def install_camera(location: Dict[str, float], camera_type: str = "visual") -> Dict[str, Any]:
    """
    Install a new camera at specified location.
    
    This actually adds the camera to the simulation layout so it appears on the map
    and starts providing coverage.
    
    Args:
        location: {x, y} position for camera
        camera_type: 'visual' or 'thermal'
    
    Returns:
        Camera installation confirmation
    """
    # Get current cameras
    cameras = simulation.layout.get("cameras", [])
    
    # Generate camera ID
    new_camera_id = f"CAM-{len(cameras) + 1:02d}"
    
    # Create camera object
    new_camera = {
        "id": new_camera_id,
        "position": location,
        "type": camera_type,
        "status": "active",
        "installed_at": simulation.simulation_hours
    }
    
    # Add to layout
    cameras.append(new_camera)
    simulation.layout["cameras"] = cameras
    
    # Broadcast camera update to frontend
    from app.services.websocket import manager
    await manager.broadcast({
        "type": "camera_installed",
        "data": {
            "camera": new_camera,
            "total_cameras": len(cameras)
        }
    })
    
    return {
        "camera_id": new_camera_id,
        "location": location,
        "status": "installed",
        "coverage_added": "80px radius"
    }

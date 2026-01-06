"""
Resource discovery and action tools.

General-purpose tools for querying available resources and submitting requests.
Agents must discover what's available before requesting it.
"""
from typing import Dict, List, Any, Optional
from langchain.tools import tool
from datetime import datetime, timedelta
import uuid


# Resource catalog - what can be procured
RESOURCE_CATALOG = {
    "sensors": [
        {
            "type": "industrial_camera",
            "model": "VisionPro-4K",
            "cost": 1200,
            "delivery_hours": 3,
            "description": "High-resolution camera for quality inspection and monitoring"
        },
        {
            "type": "thermal_sensor",
            "model": "ThermalGuard-300",
            "cost": 800,
            "delivery_hours": 6,
            "description": "Thermal imaging sensor for equipment temperature monitoring"
        },
        {
            "type": "vibration_sensor",
            "model": "VibeAlert-Pro",
            "cost": 450,
            "delivery_hours": 4,
            "description": "Detect abnormal vibrations in machinery"
        }
    ],
    "parts": [
        {
            "type": "pneumatic_cylinder",
            "model": "PC-2000-HD",
            "cost": 450,
            "delivery_hours": 4,
            "description": "Heavy-duty pneumatic cylinder for production lines"
        },
        {
            "type": "belt_assembly",
            "model": "ConveyBelt-X",
            "cost": 320,
            "delivery_hours": 2,
            "description": "Conveyor belt assembly kit"
        },
        {
            "type": "motor_assembly",
            "model": "PowerDrive-5000",
            "cost": 1500,
            "delivery_hours": 8,
            "description": "Industrial motor assembly for production machinery"
        },
        {
            "type": "hydraulic_pump",
            "model": "HydroForce-700",
            "cost": 2200,
            "delivery_hours": 12,
            "description": "High-pressure hydraulic pump"
        }
    ],
    "personnel": [
        {
            "type": "maintenance_tech",
            "hourly_cost": 75,
            "response_minutes": 10,
            "description": "General maintenance technician for routine repairs"
        },
        {
            "type": "specialist_tech",
            "hourly_cost": 125,
            "response_minutes": 45,
            "description": "Specialist technician for complex equipment issues"
        },
        {
            "type": "safety_inspector",
            "hourly_cost": 95,
            "response_minutes": 30,
            "description": "Safety compliance inspector"
        }
    ]
}


@tool
async def query_available_resources(category: str = "all") -> Dict[str, Any]:
    """
    Query the catalog of resources that can be procured or dispatched.
    
    Args:
        category: Filter by category - 'sensors', 'parts', 'personnel', or 'all'
    
    Returns catalog of available resources with costs, delivery times, and descriptions.
    Use this to discover what resources are available before submitting requests.
    """
    if category == "all":
        return {
            "categories": list(RESOURCE_CATALOG.keys()),
            "catalog": RESOURCE_CATALOG,
            "total_resource_types": sum(len(items) for items in RESOURCE_CATALOG.values())
        }
    elif category in RESOURCE_CATALOG:
        return {
            "category": category,
            "resources": RESOURCE_CATALOG[category],
            "count": len(RESOURCE_CATALOG[category])
        }
    else:
        return {
            "error": f"Unknown category '{category}'. Available: {list(RESOURCE_CATALOG.keys())}"
        }


@tool
async def submit_resource_request(
    resource_type: str,
    quantity: int,
    justification: str,
    urgency: str = "normal",
    location: Optional[str] = None
) -> Dict[str, Any]:
    """
    Submit a request for resources (cameras, parts, equipment, etc).
    
    Args:
        resource_type: Type of resource (e.g., 'industrial_camera', 'pneumatic_cylinder')
        quantity: Number of units requested
        justification: Clear business justification for the request
        urgency: 'low', 'normal', 'high', or 'critical'
        location: Optional installation/delivery location
    
    Returns request confirmation with ID, estimated delivery time, and cost.
    
    Example:
        submit_resource_request(
            "industrial_camera",
            2,
            "Cover blind spots in L12-L15 for safety compliance",
            "high",
            "production_zone_north"
        )
    """
    # Find resource in catalog
    resource_info = None
    for category, items in RESOURCE_CATALOG.items():
        for item in items:
            if item["type"] == resource_type:
                resource_info = item
                break
        if resource_info:
            break
    
    if not resource_info:
        return {
            "status": "rejected",
            "reason": f"Resource type '{resource_type}' not found in catalog. Use query_available_resources() to see options."
        }
    
    # Calculate delivery time and cost
    delivery_hours = resource_info.get("delivery_hours", resource_info.get("response_minutes", 60) / 60)
    unit_cost = resource_info.get("cost", resource_info.get("hourly_cost", 0))
    total_cost = unit_cost * quantity
    
    estimated_delivery = datetime.now() + timedelta(hours=delivery_hours)
    
    request_id = f"REQ-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"
    
    # Log request (would integrate with procurement queue later)
    print(f"📋 Resource Request: {quantity}x {resource_type} | Justification: {justification} | Cost: ${total_cost}")
    
    return {
        "request_id": request_id,
        "status": "approved",
        "resource_type": resource_type,
        "quantity": quantity,
        "total_cost": total_cost,
        "estimated_delivery": estimated_delivery.isoformat(),
        "delivery_hours": delivery_hours,
        "justification_recorded": justification,
        "urgency": urgency,
        "location": location or "warehouse"
    }


@tool
async def dispatch_personnel(
    role: str,
    location: str,
    task_description: str,
    priority: str = "normal"
) -> Dict[str, Any]:
    """
    Dispatch personnel to a specific location for a task.
    
    Args:
        role: Personnel role - 'maintenance_tech', 'specialist_tech', 'safety_inspector'
        location: Target location (e.g., 'line_12', 'warehouse', 'production_zone_north')
        task_description: Clear description of the task to be performed
        priority: 'low', 'normal', 'high', or 'critical'
    
    Returns dispatch confirmation with personnel ID, ETA, and estimated cost.
    
    Example:
        dispatch_personnel(
            "maintenance_tech",
            "line_12",
            "Replace pneumatic cylinder on assembly unit",
            "high"
        )
    """
    # Find personnel in catalog
    personnel_info = None
    for item in RESOURCE_CATALOG.get("personnel", []):
        if item["type"] == role:
            personnel_info = item
            break
    
    if not personnel_info:
        return {
            "status": "rejected",
            "reason": f"Personnel role '{role}' not available. Use query_available_resources('personnel') to see options."
        }
    
    # Calculate ETA and cost
    response_minutes = personnel_info["response_minutes"]
    hourly_cost = personnel_info["hourly_cost"]
    estimated_duration_hours = 1.5  # Default task duration
    
    dispatch_id = f"DISP-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"
    personnel_id = f"TECH-{role[:4].upper()}-{str(uuid.uuid4())[:4]}"
    
    eta = datetime.now() + timedelta(minutes=response_minutes)
    
    # Log dispatch (would integrate with simulation later)
    print(f"🔧 Personnel Dispatch: {role} to {location} | Task: {task_description} | ETA: {response_minutes}min")
    
    return {
        "dispatch_id": dispatch_id,
        "personnel_id": personnel_id,
        "role": role,
        "status": "en_route",
        "location": location,
        "task": task_description,
        "eta_minutes": response_minutes,
        "eta_timestamp": eta.isoformat(),
        "estimated_duration_hours": estimated_duration_hours,
        "estimated_cost": hourly_cost * estimated_duration_hours,
        "priority": priority
    }

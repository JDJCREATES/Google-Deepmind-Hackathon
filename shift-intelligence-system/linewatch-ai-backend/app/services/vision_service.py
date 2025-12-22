"""Production-grade camera vision analysis service.

This service provides a centralized, reusable interface for camera feed analysis.
Mock implementation for demo - structured to easily integrate real computer vision later.

All agents can request vision analysis through this service:
- Compliance Agent: Primary user for safety violations
- Staffing Agent: Line occupancy counts
- Production Agent: Visual indicators of performance issues
- Maintenance Agent: Area clearance before work
"""
import asyncio
import random
from datetime import datetime
from typing import List, Optional, Dict
from enum import Enum

from app.models.domain import SafetyViolationType, SafetyViolation


class VisionDetectionType(str, Enum):
    """Types of detections the vision system can make."""
    SAFETY_VIOLATION = "safety_violation"
    PERSON_COUNT = "person_count"
    SPILL = "spill"
    OBSTRUCTION = "obstruction"
    EQUIPMENT_ANOMALY = "equipment_anomaly"


class VisionService:
    """
    Centralized camera vision analysis service.
    
    Camera Coverage (5 cameras):
    - CAM-01: Lines 1-4
    - CAM-02: Lines 5-8
    - CAM-03: Lines 9-12
    - CAM-04: Lines 13-16
    - CAM-05: Lines 17-20
    """
    
    def __init__(self):
        """Initialize vision service with camera configuration."""
        self.cameras: Dict[str, List[int]] = {
            "CAM-01": [1, 2, 3, 4],
            "CAM-02": [5, 6, 7, 8],
            "CAM-03": [9, 10, 11, 12],
            "CAM-04": [13, 14, 15, 16],
            "CAM-05": [17, 18, 19, 20],
        }
        
        # Reverse mapping: line number -> camera ID
        self.line_to_camera: Dict[int, str] = {}
        for camera_id, lines in self.cameras.items():
            for line in lines:
                self.line_to_camera[line] = camera_id
        
        self._violation_counter = 0
    
    def get_camera_for_line(self, line_number: int) -> Optional[str]:
        """Get the camera ID covering a specific line."""
        return self.line_to_camera.get(line_number)
    
    async def analyze_feed(self, camera_id: str) -> Dict:
        """
        General camera feed analysis.
        
        Returns comprehensive feed data including all detection types.
        Mock implementation generates random detections.
        
        Args:
            camera_id: ID of camera to analyze (e.g., "CAM-01")
            
        Returns:
            Dict with detection results
        """
        if camera_id not in self.cameras:
            return {"error": f"Invalid camera ID: {camera_id}"}
        
        # Simulate processing delay
        await asyncio.sleep(0.1)
        
        lines_covered = self.cameras[camera_id]
        
        return {
            "camera_id": camera_id,
            "timestamp": datetime.now().isoformat(),
            "lines_covered": lines_covered,
            "detections": {
                "people_count": random.randint(2, 8),
                "safety_violations": await self._generate_mock_violations(camera_id),
                "obstructions": self._check_obstructions(camera_id),
                "spills": self._detect_spills(camera_id),
            }
        }
    
    async def detect_safety_violations(
        self, 
        camera_id: Optional[str] = None,
        line_number: Optional[int] = None
    ) -> List[SafetyViolation]:
        """
        Detect safety violations from camera feed.
        
        Primary method for Compliance Agent.
        
        Args:
            camera_id: Specific camera to check (optional)
            line_number: Specific line to check (will find its camera)
            
        Returns:
            List of detected safety violations
        """
        if line_number and not camera_id:
            camera_id = self.get_camera_for_line(line_number)
        
        if not camera_id:
            # Check all cameras
            all_violations = []
            for cam_id in self.cameras.keys():
                violations = await self._generate_mock_violations(cam_id)
                all_violations.extend(violations)
            return all_violations
        
        return await self._generate_mock_violations(camera_id)
    
    async def get_line_occupancy(self, line_number: int) -> int:
        """
        Count people currently on a specific production line.
        
        Used by Staffing Agent to verify coverage.
        
        Args:
            line_number: Line to check (1-20)
            
        Returns:
            Number of people detected on line
        """
        camera_id = self.get_camera_for_line(line_number)
        if not camera_id:
            return 0
        
        # Simulate processing
        await asyncio.sleep(0.05)
        
        # Mock: typically 1-3 people per line, sometimes 0 or 4
        return random.choices([0, 1, 2, 3, 4], weights=[5, 20, 35, 30, 10])[0]
    
    async def check_area_clear(self, line_number: int) -> bool:
        """
        Check if area around a line is clear of people.
        
        Used by Maintenance Agent before starting work.
        
        Args:
            line_number: Line to check
            
        Returns:
            True if area is clear, False otherwise
        """
        occupancy = await self.get_line_occupancy(line_number)
        return occupancy == 0
    
    async def detect_spills_or_obstructions(
        self, 
        camera_id: str
    ) -> List[Dict]:
        """
        Detect spills or obstructions in camera view.
        
        Used by Compliance Agent for hazard detection.
        
        Args:
            camera_id: Camera to analyze
            
        Returns:
            List of detected hazards
        """
        detections = []
        
        # Random chance of spill (5% per frame)
        if random.random() < 0.05:
            line = random.choice(self.cameras[camera_id])
            detections.append({
                "type": "spill",
                "line_number": line,
                "confidence": random.uniform(0.7, 0.98),
                "location": f"Near line {line}",
            })
        
        # Random chance of obstruction (3% per frame)
        if random.random() < 0.03:
            line = random.choice(self.cameras[camera_id])
            detections.append({
                "type": "obstruction",
                "line_number": line,
                "confidence": random.uniform(0.6, 0.95),
                "location": f"Exit path near line {line}",
            })
        
        return detections
    
    # Private helper methods
    
    async def _generate_mock_violations(
        self, 
        camera_id: str
    ) -> List[SafetyViolation]:
        """Generate mock safety violations for demo."""
        violations = []
        
        # Random chance of violation (10% per check)
        if random.random() < 0.1:
            line = random.choice(self.cameras[camera_id])
            violation_type = random.choice(list(SafetyViolationType))
            
            self._violation_counter += 1
            
            violation = SafetyViolation(
                violation_id=f"VIO-{self._violation_counter:04d}",
                timestamp=datetime.now(),
                violation_type=violation_type,
                line_number=line,
                camera_id=camera_id,
                confidence=random.uniform(0.7, 0.98),
                description=self._get_violation_description(violation_type, line),
                image_data=None,  # Could add base64 mock image later
                acknowledged=False,
            )
            violations.append(violation)
        
        return violations
    
    def _get_violation_description(
        self, 
        violation_type: SafetyViolationType, 
        line: int
    ) -> str:
        """Generate description for violation type."""
        descriptions = {
            SafetyViolationType.NO_PPE: f"Worker on Line {line} not wearing required PPE (hairnet/gloves)",
            SafetyViolationType.UNSAFE_PROXIMITY: f"Person too close to moving machinery on Line {line}",
            SafetyViolationType.SPILL_DETECTED: f"Liquid spill detected near Line {line}",
            SafetyViolationType.BLOCKED_EXIT: f"Emergency exit partially blocked near Line {line}",
            SafetyViolationType.TEMPERATURE_VIOLATION: f"Warm air vents detected near Line {line} (cold chain risk)",
            SafetyViolationType.HYGIENE_VIOLATION: f"Hygiene protocol breach observed on Line {line}",
        }
        return descriptions.get(violation_type, f"Safety issue on Line {line}")
    
    def _check_obstructions(self, camera_id: str) -> List[str]:
        """Check for obstructions in camera view."""
        # Mock: rarely detect obstructions
        if random.random() < 0.05:
            line = random.choice(self.cameras[camera_id])
            return [f"Boxes blocking walkway near Line {line}"]
        return []
    
    def _detect_spills(self, camera_id: str) -> List[str]:
        """Detect spills in camera view."""
        # Mock: rarely detect spills
        if random.random() < 0.03:
            line = random.choice(self.cameras[camera_id])
            return [f"Potential liquid spill near Line {line}"]
        return []


# Global vision service instance
vision_service = VisionService()

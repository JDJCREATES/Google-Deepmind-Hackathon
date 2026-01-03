"""Shared context manager for global state accessible to all agents."""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from app.models.domain import Department, Employee, Alert, SafetyViolation, Decision
from app.config import settings


class SharedContext:
    """
    Global state shared across all agents.
    Thread-safe using asyncio.Lock for concurrent access.
    """
    
    def __init__(self):
        self._lock = asyncio.Lock()
        
        # Core department state
        self.department: Department = Department(name=settings.department_name)
        
        # Staffing
        self.employees: Dict[str, Employee] = {}
        
        # Alerts and incidents
        self.active_alerts: List[Alert] = []
        self.safety_violations: List[SafetyViolation] = []
        
        # Agent decisions history
        self.decisions: List[Decision] = []
        
        # Simulation state
        self.simulation_running: bool = False
        self.simulation_start_time: Optional[datetime] = None
    
    async def get_department(self) -> Department:
        """Get current department state."""
        async with self._lock:
            return self.department
    
    async def update_line_status(self, line_number: int, **kwargs):
        """Update a production line's status."""
        async with self._lock:
            line = self.department.get_line(line_number)
            if line:
                for key, value in kwargs.items():
                    if hasattr(line, key):
                        setattr(line, key, value)
    
    async def add_alert(self, alert: Alert):
        """Add a new alert to the system."""
        async with self._lock:
            self.active_alerts.append(alert)
            if len(self.active_alerts) > 1000:
                self.active_alerts = self.active_alerts[-1000:]
            self.department.active_alerts.append(alert)
    
    async def add_safety_violation(self, violation: SafetyViolation):
        """Register a safety violation detected by camera."""
        async with self._lock:
            self.safety_violations.append(violation)
            if len(self.safety_violations) > 1000:
                self.safety_violations = self.safety_violations[-1000:]
    
    async def add_decision(self, decision: Decision):
        """Log an agent decision with reasoning."""
        async with self._lock:
            self.decisions.append(decision)
            if len(self.decisions) > 1000:
                self.decisions = self.decisions[-1000:]
    
    async def get_active_alerts(self, severity: Optional[str] = None) -> List[Alert]:
        """Get all active (unresolved) alerts, optionally filtered by severity."""
        async with self._lock:
            alerts = [a for a in self.active_alerts if not a.resolved]
            if severity:
                alerts = [a for a in alerts if a.severity.value == severity]
            return alerts
    
    async def get_recent_violations(self, minutes: int = 30) -> List[SafetyViolation]:
        """Get safety violations from the last N minutes."""
        async with self._lock:
            cutoff = datetime.now()
            # Simple filter - in real app would check timestamp properly
            return self.safety_violations[-10:]  # Last 10 for demo


# Global shared context instance
shared_context = SharedContext()

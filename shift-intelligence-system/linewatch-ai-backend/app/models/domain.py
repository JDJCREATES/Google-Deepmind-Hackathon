"""Domain models for the shift intelligence system."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class LineStatus(str, Enum):
    """Production line operational status."""
    OPERATIONAL = "operational"
    WARNING = "warning"
    DEGRADED = "degraded"
    FAILURE = "failure"
    MAINTENANCE = "maintenance"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SafetyViolationType(str, Enum):
    """Types of safety violations detected by camera."""
    NO_PPE = "no_ppe"  # Missing personal protective equipment
    UNSAFE_PROXIMITY = "unsafe_proximity"  # Too close to machinery
    SPILL_DETECTED = "spill_detected"  # Liquid spill on floor
    BLOCKED_EXIT = "blocked_exit"  # Emergency exit obstruction
    TEMPERATURE_VIOLATION = "temperature_violation"  # Cold chain break
    HYGIENE_VIOLATION = "hygiene_violation"  # Food safety issue


@dataclass
class ProductionLine:
    """Represents a single production line in the department."""
    line_number: int
    status: LineStatus = LineStatus.OPERATIONAL
    current_throughput: float = 0.0  # units per minute
    target_throughput: float = 100.0  # units per minute
    efficiency: float = 1.0  # 0.0 to 1.0
    health_score: float = 100.0  # 0-100, degraded by wear
    temperature: float = 4.0  # Celsius (cold storage)
    last_maintenance: Optional[datetime] = None
    assigned_staff: List[str] = field(default_factory=list)
    alerts: List[str] = field(default_factory=list)
    
    @property
    def performance_ratio(self) -> float:
        """Calculate current performance vs target."""
        if self.target_throughput == 0:
            return 0.0
        return (self.current_throughput / self.target_throughput) * self.efficiency


@dataclass
class Department:
    """Represents the entire production department with multiple lines."""
    name: str
    lines: Dict[int, ProductionLine] = field(default_factory=dict)
    shift_start: Optional[datetime] = None
    shift_end: Optional[datetime] = None
    total_staff_count: int = 0
    active_alerts: List['Alert'] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize production lines if not provided."""
        if not self.lines:
            # Create lines 1-20
            for i in range(1, 21):
                self.lines[i] = ProductionLine(
                    line_number=i,
                    target_throughput=100.0,
                )
    
    def get_line(self, line_number: int) -> Optional[ProductionLine]:
        """Get a specific production line by number."""
        return self.lines.get(line_number)
    
    def get_operational_lines(self) -> List[ProductionLine]:
        """Get all operational lines."""
        return [
            line for line in self.lines.values()
            if line.status == LineStatus.OPERATIONAL
        ]
    
    def get_total_throughput(self) -> float:
        """Calculate total department throughput."""
        return sum(line.current_throughput for line in self.lines.values())
    
    def get_average_efficiency(self) -> float:
        """Calculate average efficiency across all lines."""
        if not self.lines:
            return 0.0
        return sum(line.efficiency for line in self.lines.values()) / len(self.lines)


@dataclass
class Employee:
    """Represents a worker on shift."""
    employee_id: str
    name: str
    skills: List[str] = field(default_factory=list)
    assigned_line: Optional[int] = None
    fatigue_level: float = 0.0  # 0.0 to 1.0
    hours_worked: float = 0.0
    on_break: bool = False


@dataclass
class Alert:
    """Represents a system alert or incident."""
    alert_id: str
    timestamp: datetime
    severity: AlertSeverity
    source: str  # Which agent/line generated it
    title: str
    description: str
    line_number: Optional[int] = None
    resolved: bool = False
    resolution_time: Optional[datetime] = None
    escalated_to_human: bool = False


@dataclass
class SafetyViolation:
    """Safety violation detected by camera watching agent."""
    violation_id: str
    timestamp: datetime
    violation_type: SafetyViolationType
    line_number: int
    camera_id: str
    confidence: float  # 0.0 to 1.0
    description: str
    image_data: Optional[str] = None  # Base64 encoded image (mock)
    acknowledged: bool = False
    corrective_action_taken: Optional[str] = None


@dataclass
class Decision:
    """Agent decision with Gemini 3 reasoning trace."""
    decision_id: str
    timestamp: datetime
    agent_name: str
    decision: str
    reasoning: str  # Gemini 3's reasoning output
    confidence: float  # 0.0 to 1.0
    actions_taken: List[str] = field(default_factory=list)
    escalated: bool = False

@dataclass
class FinancialState:
    """Financial tracking state."""
    balance: float = 10000.0
    total_revenue: float = 0.0
    total_expenses: float = 0.0
    hourly_wage_cost: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class PerformanceMetrics:
    """Key Performance Indicators (KPIs)."""
    oee: float = 1.0  # Overall Equipment Effectiveness (0.0 - 1.0)
    availability: float = 1.0
    performance: float = 1.0
    quality: float = 1.0
    safety_score: float = 100.0  # 0 - 100
    uptime_hours: float = 0.0
    last_incident: Optional[datetime] = None

@dataclass
class SimulationState:
    """Complete state of the simulation for persistence."""
    timestamp: datetime = field(default_factory=datetime.now)
    financials: FinancialState = field(default_factory=FinancialState)
    kpi: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    inventory: Dict[str, int] = field(default_factory=dict)
    line_health: Dict[str, float] = field(default_factory=dict)
    shift_elapsed_hours: float = 0.0

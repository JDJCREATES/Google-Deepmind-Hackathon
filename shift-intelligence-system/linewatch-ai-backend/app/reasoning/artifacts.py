"""
Self-evolving Reasoning Artifacts for epistemic decision-making.

This module implements Gemini-generated decision structures that evolve
over time based on experience and counterfactual insights.

Key Innovation: Instead of fixed decision trees, Gemini invents and
refines its own decision criteria through meta-learning.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class DiscoveredCriterion:
    """
    A decision criterion discovered by Gemini through experience.
    
    Gemini identifies patterns in successful decisions and codifies
    them as criteria for future reasoning. These are NOT predefined.
    
    Example discovered criteria:
    - "detectability_lag": Time since signal started matters
    - "blast_radius": Number of downstream lines affected
    - "confidence_decay": Hypothesis staleness after 15 minutes
    
    Attributes:
        name: Machine-readable criterion name (snake_case)
        description: Human-readable explanation
        weight: Importance in decision scoring (0-1)
        threshold: When this criterion triggers action
        discovery_context: What incident revealed this insight
        times_validated: How often this criterion proved useful
        last_revised: When Gemini last updated this
    """
    name: str
    description: str
    weight: float = 0.5
    threshold: Any = None
    discovery_context: str = ""
    times_validated: int = 0
    last_revised: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "weight": self.weight,
            "threshold": self.threshold,
            "discovery_context": self.discovery_context,
            "times_validated": self.times_validated,
            "last_revised": self.last_revised.isoformat(),
        }


@dataclass
class ReasoningArtifact:
    """
    Self-invented decision structure evolved by Gemini.
    
    Instead of fixed ISO standards or predefined decision trees,
    Gemini generates and refines its own reasoning schemas.
    
    Version Evolution Example:
        v1.0: Basic criteria (confidence, impact, urgency)
        v1.1: + detectability_lag (discovered early detection matters)
        v2.0: + blast_radius, + confidence_decay (major insight)
    
    Attributes:
        artifact_id: Unique identifier
        version: Semantic version string (e.g., "v1.2")
        name: Human-readable name for this schema
        criteria: List of self-discovered decision criteria
        usage_count: Number of times this artifact was applied
        success_rate: Percentage of successful decisions
        evolved_from: Previous version artifact_id
        evolution_reason: Why Gemini updated this
        created_at: When this version was created
        updated_at: Last modification time
    """
    artifact_id: str = field(default_factory=lambda: f"RA-{uuid4().hex[:8]}")
    version: str = "v1.0"
    name: str = ""
    
    # Self-discovered criteria
    criteria: List[DiscoveredCriterion] = field(default_factory=list)
    
    # Performance tracking
    usage_count: int = 0
    success_rate: float = 0.0
    
    # Lineage
    evolved_from: Optional[str] = None
    evolution_reason: str = ""
    
    # Temporal
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def calculate_priority(self, values: Dict[str, float]) -> float:
        """
        Calculate decision priority using discovered criteria.
        
        Args:
            values: Dictionary mapping criterion names to values
            
        Returns:
            Weighted priority score
        """
        if not self.criteria:
            return 0.0
        
        total = 0.0
        weight_sum = 0.0
        
        for criterion in self.criteria:
            if criterion.name in values:
                total += criterion.weight * values[criterion.name]
                weight_sum += criterion.weight
        
        return total / weight_sum if weight_sum > 0 else 0.0
    
    def increment_version(self, major: bool = False) -> str:
        """Increment version string."""
        parts = self.version.lstrip("v").split(".")
        if major:
            parts[0] = str(int(parts[0]) + 1)
            parts[1] = "0"
        else:
            parts[1] = str(int(parts[1]) + 1)
        self.version = f"v{'.'.join(parts)}"
        self.updated_at = datetime.now()
        return self.version
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "version": self.version,
            "name": self.name,
            "criteria": [c.to_dict() for c in self.criteria],
            "usage_count": self.usage_count,
            "success_rate": self.success_rate,
            "evolved_from": self.evolved_from,
            "evolution_reason": self.evolution_reason,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    @classmethod
    def create_initial(cls, name: str) -> ReasoningArtifact:
        """
        Create initial reasoning artifact with base criteria.
        
        These are starting criteria that Gemini will evolve.
        """
        return cls(
            name=name,
            version="v1.0",
            criteria=[
                DiscoveredCriterion(
                    name="confidence",
                    description="Posterior probability of hypothesis",
                    weight=0.35,
                    discovery_context="Initial design",
                ),
                DiscoveredCriterion(
                    name="impact",
                    description="Production or safety effect magnitude",
                    weight=0.30,
                    discovery_context="Initial design",
                ),
                DiscoveredCriterion(
                    name="urgency",
                    description="Time sensitivity of the decision",
                    weight=0.20,
                    discovery_context="Initial design",
                ),
                DiscoveredCriterion(
                    name="reversibility",
                    description="Cost of being wrong (inverse)",
                    weight=0.15,
                    discovery_context="Initial design",
                ),
            ],
        )


@dataclass
class DecisionPolicy:
    """
    Versioned policy governing how decisions are made.
    
    Policies evolve as Gemini learns from outcomes. Each version
    captures insights and threshold adjustments.
    
    Evolution Example:
        v1.0: confidence_threshold_act = 0.80
        v1.1: confidence_threshold_act = 0.75 (early action helped)
        v2.0: + "maintenance before compliance" priority rule
    
    Attributes:
        policy_id: Unique identifier
        version: Semantic version string
        confidence_threshold_act: Minimum confidence to take action
        confidence_threshold_escalate: Below this, escalate to human
        framework_weights: Preferences for each epistemic framework
        reasoning_artifacts: Active decision schemas
        policy_insights: Lessons learned (Gemini-generated)
        incidents_evaluated: Total incidents using this policy
        accuracy_rate: Percentage of correct decisions
        created_at: When this policy version was created
    """
    policy_id: str = field(default_factory=lambda: f"DP-{uuid4().hex[:8]}")
    version: str = "v1.0"
    
    # Action thresholds
    confidence_threshold_act: float = 0.75
    confidence_threshold_escalate: float = 0.45
    
    # Framework preferences (adjusted by drift detection)
    framework_weights: Dict[str, float] = field(default_factory=lambda: {
        "RCA": 0.30,
        "COUNTERFACTUAL": 0.15,
        "FMEA": 0.20,
        "TOC": 0.20,
        "HACCP": 0.15,
    })
    
    # Active reasoning artifacts
    reasoning_artifacts: List[ReasoningArtifact] = field(default_factory=list)
    
    # Meta-learning
    policy_insights: List[str] = field(default_factory=list)
    
    # Performance tracking
    incidents_evaluated: int = 0
    accuracy_rate: float = 0.0
    
    # Temporal
    created_at: datetime = field(default_factory=datetime.now)
    
    def should_act(self, confidence: float) -> bool:
        """Check if confidence is high enough to act."""
        return confidence >= self.confidence_threshold_act
    
    def should_escalate(self, confidence: float) -> bool:
        """Check if confidence is too low (need human)."""
        return confidence < self.confidence_threshold_escalate
    
    def add_insight(self, insight: str) -> None:
        """Add a learned insight to the policy."""
        self.policy_insights.append(insight)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "confidence_threshold_act": self.confidence_threshold_act,
            "confidence_threshold_escalate": self.confidence_threshold_escalate,
            "framework_weights": self.framework_weights,
            "reasoning_artifacts": [ra.to_dict() for ra in self.reasoning_artifacts],
            "policy_insights": self.policy_insights,
            "incidents_evaluated": self.incidents_evaluated,
            "accuracy_rate": self.accuracy_rate,
            "created_at": self.created_at.isoformat(),
        }
    
    @classmethod
    def create_initial(cls) -> DecisionPolicy:
        """Create initial policy with default settings."""
        policy = cls()
        policy.reasoning_artifacts.append(
            ReasoningArtifact.create_initial("Production Decision Schema")
        )
        return policy

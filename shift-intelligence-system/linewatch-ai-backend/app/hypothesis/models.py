"""
Core hypothesis models for the epistemic reasoning framework.

This module defines the fundamental data structures for hypothesis-driven
manufacturing intelligence, including typed hypotheses, evidence, and belief states.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4


class HypothesisFramework(str, Enum):
    """
    The 5 epistemic frameworks for hypothesis classification.
    
    Each framework represents a different mode of reasoning:
    - RCA: Root Cause Analysis (Why is this happening?)
    - COUNTERFACTUAL: What-if analysis (What if we act/don't act?)
    - FMEA: Failure Mode Effects Analysis (What could go wrong?)
    - TOC: Theory of Constraints (What's the bottleneck?)
    - HACCP: Hazard Analysis Critical Control Points (Compliance risk?)
    """
    RCA = "RCA"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    FMEA = "FMEA"
    TOC = "TOC"
    HACCP = "HACCP"


class CauseCategory(str, Enum):
    """Root cause categories for RCA hypotheses."""
    MECHANICAL = "mechanical"
    PROCESS = "process"
    HUMAN = "human"
    ENVIRONMENTAL = "environmental"


@dataclass
class Evidence:
    """
    Evidence supporting or refuting a hypothesis.
    
    Evidence is gathered from tools (sensors, cameras, logs) and used
    to update belief in hypotheses via Bayesian reasoning.
    
    Attributes:
        evidence_id: Unique identifier
        hypothesis_id: The hypothesis this evidence relates to
        source: Where the evidence came from (e.g., "CameraFeed", "TempSensor")
        data: The actual evidence data
        supports: True if evidence supports the hypothesis
        strength: How strongly the evidence affects belief (0-1)
        confidence: Confidence in the evidence quality (0-1)
        gathered_by: Agent or tool that gathered this
        gathered_at: Timestamp of collection
    """
    evidence_id: str = field(default_factory=lambda: f"E-{uuid4().hex[:8]}")
    hypothesis_id: str = ""
    source: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    supports: bool = True
    strength: float = 0.5
    confidence: float = 0.9
    gathered_by: str = ""
    gathered_at: datetime = field(default_factory=datetime.now)


@dataclass
class Hypothesis:
    """
    Base hypothesis class representing a competing explanation.
    
    Every hypothesis is typed under one of 5 epistemic frameworks,
    enabling structured reasoning and framework-specific analysis.
    
    Attributes:
        hypothesis_id: Unique identifier
        framework: Which epistemic framework (RCA, FMEA, etc.)
        description: Human-readable explanation
        initial_confidence: Prior probability before evidence
        current_confidence: Posterior probability after evidence
        evidence: List of evidence gathered
        impact: Production/safety effect magnitude (1-10)
        urgency: Time sensitivity (1-10)
        reversibility: Cost of being wrong (1-10, higher = harder to reverse)
        proposed_by: Agent that generated this hypothesis
        target_agent: Agent that should act on this if selected
        recommended_action: What to do if this hypothesis is selected
        created_at: When hypothesis was generated
        last_updated: Last belief update time
    """
    hypothesis_id: str = field(default_factory=lambda: f"H-{uuid4().hex[:8]}")
    framework: HypothesisFramework = HypothesisFramework.RCA
    description: str = ""
    
    # Uncertainty modeling
    initial_confidence: float = 0.5
    current_confidence: float = 0.5
    
    # Evidence
    evidence: List[Evidence] = field(default_factory=list)
    
    # Decision scoring inputs (Gemini estimates these)
    impact: float = 5.0
    urgency: float = 5.0
    reversibility: float = 5.0
    
    # Provenance
    proposed_by: str = ""
    target_agent: Optional[str] = None
    recommended_action: Optional[str] = None
    
    # Temporal
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def decision_priority(self) -> float:
        """
        Calculate decision priority using learned formula.
        
        Priority = confidence × impact × urgency × (1 / reversibility)
        
        This balances:
        - How certain we are (confidence)
        - How important it is (impact)
        - How time-sensitive it is (urgency)
        - Risk of being wrong (inversw reversibility)
        """
        return (
            self.current_confidence *
            self.impact *
            self.urgency *
            (1 / max(self.reversibility, 0.1))
        )
    
    def add_evidence(self, evidence: Evidence) -> None:
        """Add evidence and mark as updated."""
        evidence.hypothesis_id = self.hypothesis_id
        self.evidence.append(evidence)
        self.last_updated = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "hypothesis_id": self.hypothesis_id,
            "framework": self.framework.value,
            "description": self.description,
            "initial_confidence": self.initial_confidence,
            "current_confidence": self.current_confidence,
            "impact": self.impact,
            "urgency": self.urgency,
            "reversibility": self.reversibility,
            "decision_priority": self.decision_priority,
            "proposed_by": self.proposed_by,
            "target_agent": self.target_agent,
            "recommended_action": self.recommended_action,
            "evidence_count": len(self.evidence),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class BeliefState:
    """
    Current belief distribution across competing hypotheses.
    
    Represents the epistemic state at a point in time, tracking
    all active hypotheses and their posterior probabilities.
    
    Attributes:
        belief_id: Unique identifier
        signal_id: The signal that triggered this reasoning
        signal_description: Human-readable signal description
        hypotheses: All competing hypotheses
        posterior_probabilities: Normalized posteriors by hypothesis_id
        leading_hypothesis_id: Hypothesis with highest posterior
        confidence_in_leader: Posterior of the leading hypothesis
        converged: Whether we have enough confidence to act
        recommended_action: Selected action (if converged)
        created_at: When belief state was created
        resolved_at: When incident was resolved (if applicable)
    """
    belief_id: str = field(default_factory=lambda: f"B-{uuid4().hex[:8]}")
    signal_id: str = ""
    signal_description: str = ""
    
    # Hypotheses
    hypotheses: List[Hypothesis] = field(default_factory=list)
    
    # Posteriors
    posterior_probabilities: Dict[str, float] = field(default_factory=dict)
    leading_hypothesis_id: Optional[str] = None
    confidence_in_leader: float = 0.0
    
    # Decision state
    converged: bool = False
    recommended_action: Optional[str] = None
    action_taken: Optional[str] = None
    
    # Temporal
    created_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    
    def get_leading_hypothesis(self) -> Optional[Hypothesis]:
        """Get the hypothesis with highest posterior."""
        if not self.leading_hypothesis_id:
            return None
        return next(
            (h for h in self.hypotheses if h.hypothesis_id == self.leading_hypothesis_id),
            None
        )
    
    def get_second_best(self) -> Optional[Hypothesis]:
        """Get the second most likely hypothesis (for counterfactual)."""
        if len(self.hypotheses) < 2:
            return None
        sorted_h = sorted(
            self.hypotheses,
            key=lambda h: self.posterior_probabilities.get(h.hypothesis_id, 0),
            reverse=True
        )
        return sorted_h[1] if len(sorted_h) > 1 else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "belief_id": self.belief_id,
            "signal_id": self.signal_id,
            "signal_description": self.signal_description,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "posterior_probabilities": self.posterior_probabilities,
            "leading_hypothesis_id": self.leading_hypothesis_id,
            "confidence_in_leader": self.confidence_in_leader,
            "converged": self.converged,
            "recommended_action": self.recommended_action,
            "created_at": self.created_at.isoformat(),
        }

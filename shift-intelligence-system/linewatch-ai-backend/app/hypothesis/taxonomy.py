"""
Framework-specific hypothesis types for epistemic reasoning.

This module extends the base Hypothesis class with specialized fields
for each of the 5 epistemic frameworks (RCA, Counterfactual, FMEA, TOC, HACCP).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.hypothesis.models import (
    CauseCategory,
    Evidence,
    Hypothesis,
    HypothesisFramework,
)


@dataclass
class RCAHypothesis(Hypothesis):
    """
    Root Cause Analysis hypothesis - "Why is this happening?"
    
    Uses standard RCA methodology to identify root causes of issues.
    Categories: mechanical, process, human, environmental.
    
    Attributes:
        cause_category: Classification of the root cause
        expected_effect: What we'd observe if this cause is true
        supporting_evidence_summary: Brief summary of supporting evidence
    """
    framework: HypothesisFramework = field(default=HypothesisFramework.RCA, init=False)
    cause_category: CauseCategory = CauseCategory.MECHANICAL
    expected_effect: str = ""
    supporting_evidence_summary: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "cause_category": self.cause_category.value,
            "expected_effect": self.expected_effect,
            "supporting_evidence_summary": self.supporting_evidence_summary,
        })
        return base


@dataclass
class CounterfactualHypothesis(Hypothesis):
    """
    Counterfactual hypothesis - "What if we act/don't act?"
    
    Enables what-if analysis for decision comparison.
    Used by Orchestrator for evaluating action alternatives.
    
    Attributes:
        action: The action being considered
        predicted_outcome: Expected outcome if action taken
        risk_delta: How risk changes if we act (positive = risk increases)
        production_delta: Expected production change (units)
    """
    framework: HypothesisFramework = field(default=HypothesisFramework.COUNTERFACTUAL, init=False)
    action: str = ""
    predicted_outcome: str = ""
    risk_delta: float = 0.0
    production_delta: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "action": self.action,
            "predicted_outcome": self.predicted_outcome,
            "risk_delta": self.risk_delta,
            "production_delta": self.production_delta,
        })
        return base


@dataclass
class FMEAHypothesis(Hypothesis):
    """
    FMEA hypothesis - "What could go wrong?"
    
    Failure Mode and Effects Analysis for risk assessment.
    Computes Risk Priority Number (RPN) = Severity × Occurrence × Detectability.
    
    Attributes:
        failure_mode: Description of the potential failure
        severity: Impact if failure occurs (1-10, 10 = catastrophic)
        occurrence: Likelihood of failure (1-10, 10 = very likely)
        detectability: Difficulty detecting failure (1-10, 10 = undetectable)
    """
    framework: HypothesisFramework = field(default=HypothesisFramework.FMEA, init=False)
    failure_mode: str = ""
    severity: int = 5
    occurrence: int = 5
    detectability: int = 5
    
    @property
    def rpn(self) -> int:
        """
        Risk Priority Number.
        
        RPN = Severity × Occurrence × Detectability
        Range: 1-1000 (higher = more critical)
        """
        return self.severity * self.occurrence * self.detectability
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "failure_mode": self.failure_mode,
            "severity": self.severity,
            "occurrence": self.occurrence,
            "detectability": self.detectability,
            "rpn": self.rpn,
        })
        return base


@dataclass
class TOCHypothesis(Hypothesis):
    """
    Theory of Constraints hypothesis - "What's the bottleneck?"
    
    Identifies system constraints limiting throughput.
    Used for bottleneck analysis and capacity planning.
    
    Attributes:
        constraint: Description of the bottleneck
        throughput_impact: Units/hour affected by this constraint
        time_horizon_minutes: How long until this becomes critical
        downstream_lines: Lines affected if constraint not addressed
    """
    framework: HypothesisFramework = field(default=HypothesisFramework.TOC, init=False)
    constraint: str = ""
    throughput_impact: float = 0.0
    time_horizon_minutes: int = 60
    downstream_lines: List[int] = field(default_factory=list)
    
    @property
    def blast_radius(self) -> int:
        """Number of downstream lines affected."""
        return len(self.downstream_lines)
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "constraint": self.constraint,
            "throughput_impact": self.throughput_impact,
            "time_horizon_minutes": self.time_horizon_minutes,
            "downstream_lines": self.downstream_lines,
            "blast_radius": self.blast_radius,
        })
        return base


@dataclass
class HACCPHypothesis(Hypothesis):
    """
    HACCP hypothesis - "Are we violating compliance rules?"
    
    Hazard Analysis Critical Control Points for food safety compliance.
    Tracks regulation violations and time-to-noncompliance.
    
    Attributes:
        regulation: Specific regulation code or name
        violation_likelihood: Probability of violation (0-1)
        time_to_noncompliance_minutes: Minutes until we're in violation
        critical_control_point: Which CCP is at risk
    """
    framework: HypothesisFramework = field(default=HypothesisFramework.HACCP, init=False)
    regulation: str = ""
    violation_likelihood: float = 0.5
    time_to_noncompliance_minutes: int = 30
    critical_control_point: str = ""
    
    @property
    def is_urgent(self) -> bool:
        """Returns True if violation is imminent (< 15 minutes)."""
        return self.time_to_noncompliance_minutes < 15
    
    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            "regulation": self.regulation,
            "violation_likelihood": self.violation_likelihood,
            "time_to_noncompliance_minutes": self.time_to_noncompliance_minutes,
            "critical_control_point": self.critical_control_point,
            "is_urgent": self.is_urgent,
        })
        return base


# Factory function for creating typed hypotheses
def create_hypothesis(
    framework: HypothesisFramework | str,
    **kwargs
) -> Hypothesis:
    """
    Factory function to create framework-specific hypothesis.
    
    Args:
        framework: The epistemic framework type
        **kwargs: Framework-specific fields
        
    Returns:
        Typed hypothesis instance
        
    Example:
        >>> h = create_hypothesis("RCA", cause_category="mechanical", ...)
    """
    if isinstance(framework, str):
        framework = HypothesisFramework(framework)
    
    type_map = {
        HypothesisFramework.RCA: RCAHypothesis,
        HypothesisFramework.COUNTERFACTUAL: CounterfactualHypothesis,
        HypothesisFramework.FMEA: FMEAHypothesis,
        HypothesisFramework.TOC: TOCHypothesis,
        HypothesisFramework.HACCP: HACCPHypothesis,
    }
    
    cls = type_map.get(framework, Hypothesis)
    return cls(**kwargs)

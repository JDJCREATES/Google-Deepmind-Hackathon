"""
Framework drift detection for epistemic bias prevention.

Detects when Gemini over-relies on specific frameworks and
triggers rebalancing to ensure diverse reasoning.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from app.hypothesis.models import HypothesisFramework


@dataclass
class DriftAlert:
    """
    Alert indicating framework usage imbalance.
    
    Attributes:
        drift_type: "OVERUSE" or "UNDERUSE"
        framework: Affected framework
        expected_ratio: Expected usage percentage
        actual_ratio: Actual usage percentage
        recommendation: Action to take
        detected_at: When drift was detected
    """
    drift_type: str
    framework: str
    expected_ratio: float
    actual_ratio: float
    recommendation: str
    detected_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "drift_type": self.drift_type,
            "framework": self.framework,
            "expected_ratio": self.expected_ratio,
            "actual_ratio": self.actual_ratio,
            "recommendation": self.recommendation,
            "detected_at": self.detected_at.isoformat(),
        }


class FrameworkDriftDetector:
    """
    Detects and prevents epistemic bias in framework selection.
    
    Tracks framework usage over a sliding window and alerts when
    actual usage deviates significantly from expected distribution.
    
    Example:
        If Gemini always blames "staffing" (RCA.human), drift
        detector flags bias and recommends exploring other causes.
    """
    
    def __init__(
        self,
        window_size: int = 50,
        overuse_threshold: float = 2.0,
        underuse_threshold: float = 0.5,
    ):
        """
        Initialize drift detector.
        
        Args:
            window_size: Number of recent decisions to track
            overuse_threshold: Multiplier for overuse detection (2.0 = 2x expected)
            underuse_threshold: Multiplier for underuse detection (0.5 = half expected)
        """
        self.window_size = window_size
        self.overuse_threshold = overuse_threshold
        self.underuse_threshold = underuse_threshold
        
        self.history: List[str] = []
        
        # Expected distribution (can be adjusted)
        self.expected_distribution: Dict[str, float] = {
            HypothesisFramework.RCA.value: 0.30,
            HypothesisFramework.COUNTERFACTUAL.value: 0.15,
            HypothesisFramework.FMEA.value: 0.20,
            HypothesisFramework.TOC.value: 0.20,
            HypothesisFramework.HACCP.value: 0.15,
        }
    
    def record_usage(self, framework: HypothesisFramework | str) -> None:
        """
        Record a framework being used in a decision.
        
        Args:
            framework: The framework that was selected
        """
        if isinstance(framework, HypothesisFramework):
            framework = framework.value
        
        self.history.append(framework)
        
        # Maintain sliding window
        if len(self.history) > self.window_size:
            self.history.pop(0)
    
    def detect_drift(self) -> Optional[DriftAlert]:
        """
        Check for framework usage drift.
        
        Returns:
            DriftAlert if drift detected, None otherwise
        """
        if len(self.history) < 20:
            return None  # Not enough data
        
        actual = Counter(self.history)
        total = len(self.history)
        
        for framework, expected_pct in self.expected_distribution.items():
            actual_pct = actual.get(framework, 0) / total
            
            # Check for overuse
            if actual_pct > expected_pct * self.overuse_threshold:
                return DriftAlert(
                    drift_type="OVERUSE",
                    framework=framework,
                    expected_ratio=expected_pct,
                    actual_ratio=actual_pct,
                    recommendation=(
                        f"Reduce reliance on {framework} framework. "
                        f"Explore alternative explanations."
                    ),
                )
            
            # Check for underuse (only for significant expected frameworks)
            if expected_pct > 0.1 and actual_pct < expected_pct * self.underuse_threshold:
                return DriftAlert(
                    drift_type="UNDERUSE",
                    framework=framework,
                    expected_ratio=expected_pct,
                    actual_ratio=actual_pct,
                    recommendation=(
                        f"Consider {framework} framework more often. "
                        f"Current usage is below expected."
                    ),
                )
        
        return None
    
    def get_prompt_injection(self) -> Optional[str]:
        """
        Get prompt text to inject when drift detected.
        
        Returns:
            Warning text for Gemini prompt, or None if no drift
        """
        drift = self.detect_drift()
        if not drift:
            return None
        
        return f"""
⚠️ FRAMEWORK DRIFT DETECTED:
You have been {drift.drift_type.lower().replace('_', '-')}ing the {drift.framework} framework.
Expected usage: {drift.expected_ratio:.0%}, Actual: {drift.actual_ratio:.0%}

For this incident, explicitly explore OTHER frameworks before defaulting.
Consider: {self._get_alternative_frameworks(drift.framework)}
"""
    
    def _get_alternative_frameworks(self, exclude: str) -> str:
        """Get comma-separated list of alternative frameworks."""
        alternatives = [
            f for f in self.expected_distribution.keys()
            if f != exclude
        ]
        return ", ".join(alternatives)
    
    def get_stats(self) -> Dict:
        """Get current usage statistics."""
        if not self.history:
            return {"history_size": 0, "distribution": {}}
        
        actual = Counter(self.history)
        total = len(self.history)
        
        return {
            "history_size": total,
            "distribution": {
                framework: {
                    "expected": expected,
                    "actual": actual.get(framework, 0) / total,
                    "count": actual.get(framework, 0),
                }
                for framework, expected in self.expected_distribution.items()
            },
        }

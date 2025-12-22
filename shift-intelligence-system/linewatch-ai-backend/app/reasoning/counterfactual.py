"""
Counterfactual replay engine for strategic learning.

Analyzes "what if we chose differently" after each decision,
enabling the system to learn strategically, not just tactically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.hypothesis.models import Hypothesis


@dataclass
class CounterfactualReplay:
    """
    Post-action analysis comparing chosen vs alternative paths.
    
    After every action, we ask: "What if we had chosen the
    second-most-likely hypothesis instead?"
    
    This enables strategic learning beyond simple success/failure.
    
    Attributes:
        replay_id: Unique identifier
        incident_id: The incident this replay analyzes
        
        chosen_hypothesis: The hypothesis we acted on
        action_taken: The action we executed
        actual_outcome: What actually happened
        
        alternative_hypothesis: The hypothesis we didn't choose
        alternative_action: What we would have done
        predicted_alternative_outcome: Gemini's prediction of what would have happened
        
        production_delta: Units saved/lost compared to alternative
        time_delta_minutes: Minutes faster/slower detection
        risk_delta: Risk avoided/incurred
        cost_delta: Dollars saved/lost
        
        insight: Strategic learning from this analysis
        should_update_policy: Whether this warrants policy evolution
        
        created_at: When replay was performed
    """
    replay_id: str = field(default_factory=lambda: f"CF-{uuid4().hex[:8]}")
    incident_id: str = ""
    
    # What we did
    chosen_hypothesis_id: str = ""
    chosen_hypothesis_description: str = ""
    action_taken: str = ""
    actual_outcome: Dict[str, Any] = field(default_factory=dict)
    
    # What we didn't do
    alternative_hypothesis_id: str = ""
    alternative_hypothesis_description: str = ""
    alternative_action: str = ""
    predicted_alternative_outcome: Dict[str, Any] = field(default_factory=dict)
    
    # Delta metrics
    production_delta: float = 0.0  # Units saved/lost
    time_delta_minutes: int = 0     # Faster/slower detection
    risk_delta: float = 0.0         # Risk avoided/incurred
    cost_delta: float = 0.0         # Dollars saved/lost
    
    # Strategic learning
    insight: str = ""
    should_update_policy: bool = False
    update_recommendation: str = ""
    
    # Temporal
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def was_optimal_choice(self) -> bool:
        """Returns True if chosen path was better than alternative."""
        # Positive deltas mean our choice was better
        score = (
            self.production_delta * 0.4 +
            -self.time_delta_minutes * 0.3 +  # Negative time is better
            -self.risk_delta * 0.2 +          # Negative risk is better
            self.cost_delta * 0.1
        )
        return score >= 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "replay_id": self.replay_id,
            "incident_id": self.incident_id,
            "chosen_hypothesis_id": self.chosen_hypothesis_id,
            "chosen_hypothesis_description": self.chosen_hypothesis_description,
            "action_taken": self.action_taken,
            "actual_outcome": self.actual_outcome,
            "alternative_hypothesis_id": self.alternative_hypothesis_id,
            "alternative_hypothesis_description": self.alternative_hypothesis_description,
            "alternative_action": self.alternative_action,
            "predicted_alternative_outcome": self.predicted_alternative_outcome,
            "production_delta": self.production_delta,
            "time_delta_minutes": self.time_delta_minutes,
            "risk_delta": self.risk_delta,
            "cost_delta": self.cost_delta,
            "insight": self.insight,
            "was_optimal_choice": self.was_optimal_choice,
            "should_update_policy": self.should_update_policy,
            "update_recommendation": self.update_recommendation,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class StrategicMemory:
    """
    Long-term memory for strategic learning.
    
    Stores counterfactual replays and policy evolution history
    to enable continuous improvement.
    """
    replays: List[CounterfactualReplay] = field(default_factory=list)
    policy_updates: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_replay(self, replay: CounterfactualReplay) -> None:
        """Add a counterfactual replay to memory."""
        self.replays.append(replay)
    
    def get_recent_replays(self, count: int = 20) -> List[CounterfactualReplay]:
        """Get most recent replays."""
        return self.replays[-count:]
    
    def get_suboptimal_decisions(self) -> List[CounterfactualReplay]:
        """Get replays where we made a suboptimal choice."""
        return [r for r in self.replays if not r.was_optimal_choice]
    
    def get_policy_update_candidates(self) -> List[CounterfactualReplay]:
        """Get replays that recommend policy updates."""
        return [r for r in self.replays if r.should_update_policy]
    
    def get_insights_for_prompt(self, max_insights: int = 5) -> str:
        """
        Get formatted insights for injecting into Gemini prompts.
        
        Returns recent strategic insights to inform future decisions.
        """
        recent_with_insights = [
            r for r in self.replays[-50:]
            if r.insight
        ][-max_insights:]
        
        if not recent_with_insights:
            return ""
        
        insights = "\n".join([
            f"- {r.insight}" for r in recent_with_insights
        ])
        
        return f"""
STRATEGIC INSIGHTS FROM RECENT DECISIONS:
{insights}
"""
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        total = len(self.replays)
        optimal = sum(1 for r in self.replays if r.was_optimal_choice)
        
        return {
            "total_replays": total,
            "optimal_decisions": optimal,
            "suboptimal_decisions": total - optimal,
            "accuracy_rate": optimal / total if total > 0 else 0.0,
            "policy_updates_recommended": len(self.get_policy_update_candidates()),
        }

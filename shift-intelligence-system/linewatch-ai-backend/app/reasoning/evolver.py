"""
Policy and Reasoning Artifact evolution logic.

Implements the meta-learning layer that allows Gemini to evolve
its own decision structures based on experience and counterfactual insights.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import json

from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings
from app.hypothesis import Hypothesis
from app.reasoning.artifacts import DecisionPolicy, DiscoveredCriterion, ReasoningArtifact
from app.reasoning.counterfactual import CounterfactualReplay, StrategicMemory
from app.utils.logging import get_agent_logger


logger = get_agent_logger("PolicyEvolver")


class PolicyEvolver:
    """
    Evolves decision policies based on accumulated experience.
    
    Uses Gemini to analyze patterns in outcomes and counterfactual
    analyses to suggest policy improvements.
    
    Example evolution:
        - After 50 incidents: "Early intervention reduces cascade failures"
        - After 100 incidents: "Maintenance hypotheses weighted higher in morning"
        - After 150 incidents: "Staffing issues peak at hour 6 of shift"
    """
    
    def __init__(
        self,
        evolution_threshold: int = 25,
        min_accuracy_delta: float = 0.05,
    ):
        """
        Initialize policy evolver.
        
        Args:
            evolution_threshold: Minimum incidents before evolution check
            min_accuracy_delta: Minimum accuracy improvement to update
        """
        self.evolution_threshold = evolution_threshold
        self.min_accuracy_delta = min_accuracy_delta
        
        if settings.google_api_key:
            self.llm = ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                google_api_key=settings.google_api_key,
                temperature=0.4,
            )
        else:
            self.llm = None
    
    async def should_evolve(
        self,
        policy: DecisionPolicy,
        memory: StrategicMemory
    ) -> bool:
        """Check if policy evolution should be triggered."""
        if len(memory.replays) < self.evolution_threshold:
            return False
        
        # Check for significant suboptimal decisions
        suboptimal = memory.get_suboptimal_decisions()
        suboptimal_rate = len(suboptimal) / len(memory.replays)
        
        if suboptimal_rate > 0.3:  # > 30% suboptimal
            logger.info(f"📊 Suboptimal rate {suboptimal_rate:.1%} triggers evolution")
            return True
        
        # Check for policy update recommendations
        candidates = memory.get_policy_update_candidates()
        if len(candidates) >= 5:
            logger.info(f"📊 {len(candidates)} replays recommend policy update")
            return True
        
        return False
    
    async def evolve_policy(
        self,
        current_policy: DecisionPolicy,
        memory: StrategicMemory
    ) -> DecisionPolicy:
        """
        Evolve policy based on accumulated learning.
        
        Uses Gemini to analyze patterns and suggest improvements.
        """
        logger.info("🔄 Evolving decision policy...")
        
        # Prepare context for Gemini
        recent_replays = memory.get_recent_replays(30)
        suboptimal = memory.get_suboptimal_decisions()[-10:]
        
        prompt = f"""
You are the Chief AI Safety Officer for a 24/7 manufacturing facility.
Your job is to EVOLVE the decision-making policy based on empirical evidence from RECENT OUTCOMES.

OBJECTIVE:
Analyze the decision history to optimize two competing goals:
1. Operational Efficiency (Throughput, OEE)
2. Safety & Compliance (Zero incidents, <1% violation rate)

CURRENT POLICY (v{current_policy.version}):
- Confidence Threshold (To Act): {current_policy.confidence_threshold_act} 
- Confidence Threshold (To Escalate): {current_policy.confidence_threshold_escalate}
- Active Insights: {current_policy.policy_insights}

DATA ANALYSIS:
{self._format_replays(recent_replays)}

SUBOPTIMAL DECISIONS (LEARNING OPPORTUNITIES):
{self._format_replays(suboptimal)}

SAFETY GUARDRAILS (IMMUTABLE):
- NEVER lower 'confidence_threshold_act' below 0.60.
- NEVER raise 'confidence_threshold_escalate' above 0.85 (must remain sensitive to risks).
- Changes must be INCREMENTAL (+/- 0.05 max per evolution) to ensure stability.

INSTRUCTIONS:
1. Analyze the 'Suboptimal Decisions'. Why did we fail?
   - If we acted but failed: We were overconfident -> RAISE confidence_act threshold.
   - If we escalated unnecessarily: We were underconfident -> LOWER confidence_act threshold.
2. Analyze 'Framework Weights'.
   - If safety incidents occurred: Increase 'FMEA' (Failure Mode Analysis) weight.
   - If throughput lagged: Increase 'TOC' (Constraints) weight.

OUTPUT FORMAT (JSON ONLY):
{{
    "confidence_threshold_act": <float or null>,
    "confidence_threshold_escalate": <float or null>,
    "framework_weight_changes": {{"RCA": <float>, "FMEA": <float>}},
    "new_insights": ["<Short, punchy insight about production physics>"],
    "reasoning": "<Explanation of why this change improves safety/efficiency>"
}}
"""

        result = await self.llm.ainvoke(prompt)
        
        # Parse result and create new policy
        try:
            import re
            json_match = re.search(r'\{.*\}', result.content, re.DOTALL)
            if json_match:
                changes = json.loads(json_match.group())
            else:
                changes = {}
        except Exception as e:
            logger.error(f"Error parsing evolution result: {e}")
            changes = {}
        
        # Create evolved policy
        new_policy = DecisionPolicy(
            version=self._increment_version(current_policy.version),
            confidence_threshold_act=(
                changes.get("confidence_threshold_act") or
                current_policy.confidence_threshold_act
            ),
            confidence_threshold_escalate=(
                changes.get("confidence_threshold_escalate") or
                current_policy.confidence_threshold_escalate
            ),
            framework_weights={
                **current_policy.framework_weights,
                **changes.get("framework_weight_changes", {})
            },
            reasoning_artifacts=current_policy.reasoning_artifacts.copy(),
            policy_insights=(
                current_policy.policy_insights +
                changes.get("new_insights", [])
            ),
            incidents_evaluated=len(memory.replays),
            accuracy_rate=memory.get_stats()["accuracy_rate"],
        )
        
        # Evolve reasoning artifacts if new criteria discovered
        if changes.get("discovered_criteria"):
            new_policy = await self._evolve_artifacts(
                new_policy,
                changes["discovered_criteria"]
            )
        
        # ACTIVATE POLICY
        from app.services.policy_service import policy_service
        await policy_service.update_policy(new_policy)
        
        logger.info(
            f"✅ Policy evolved: v{current_policy.version} → v{new_policy.version}"
        )
        logger.info(f"   New insights: {changes.get('new_insights', [])}")
        
        return new_policy
    
    async def _evolve_artifacts(
        self,
        policy: DecisionPolicy,
        new_criteria: List[Dict]
    ) -> DecisionPolicy:
        """Add discovered criteria to reasoning artifacts."""
        if not policy.reasoning_artifacts:
            return policy
        
        # Update first artifact
        artifact = policy.reasoning_artifacts[0]
        old_version = artifact.version
        
        for criterion_data in new_criteria:
            criterion = DiscoveredCriterion(
                name=criterion_data.get("name", "unknown"),
                description=criterion_data.get("description", ""),
                weight=criterion_data.get("weight", 0.1),
                discovery_context="Policy evolution",
            )
            artifact.criteria.append(criterion)
        
        artifact.increment_version()
        artifact.evolution_reason = f"Added {len(new_criteria)} new criteria"
        
        logger.info(
            f"   Artifact evolved: {old_version} → {artifact.version}"
        )
        
        return policy
    
    def _format_replays(self, replays: List[CounterfactualReplay]) -> str:
        """Format replays for prompt."""
        if not replays:
            return "No replays available"
        
        lines = []
        for r in replays[:10]:  # Limit for prompt size
            lines.append(
                f"- Chose: {r.chosen_hypothesis_description[:50]}... "
                f"| Alt: {r.alternative_hypothesis_description[:50]}... "
                f"| Optimal: {r.was_optimal_choice}"
            )
        return "\n".join(lines)
    
    def _increment_version(self, version: str) -> str:
        """Increment version string."""
        parts = version.lstrip("v").split(".")
        parts[1] = str(int(parts[1]) + 1)
        return f"v{'.'.join(parts)}"


async def generate_insight_message(
    policy: DecisionPolicy,
    memory: StrategicMemory
) -> Optional[str]:
    """
    Generate a user-facing insight message for UI display.
    
    Example:
        "Over the last 12 simulated hours, the system learned that
        early maintenance interventions reduce downstream compliance
        risk by 18%, and updated its action prioritization accordingly."
    """
    if not policy.policy_insights:
        return None
    
    latest_insight = policy.policy_insights[-1]
    stats = memory.get_stats()
    
    return (
        f"Over the last {stats['total_replays']} decisions, "
        f"the system learned: \"{latest_insight}\" "
        f"(current accuracy: {stats['accuracy_rate']:.0%})"
    )

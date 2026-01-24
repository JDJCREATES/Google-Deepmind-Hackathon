"""
Policy Service for managing the active DecisionPolicy.

Acts as the single source of truth for agents to retrieve
current parameters (thresholds, weights) that evolve over time.
Persistence is handled via JSON to survive restarts.
"""
import json
import os
from typing import Optional, Dict, Any, List

from app.reasoning.artifacts import DecisionPolicy
from app.utils.logging import logger

POLICY_FILE = "data/active_policy.json"

class PolicyService:
    def __init__(self):
        self._current_policy: Optional[DecisionPolicy] = None
        self._load_policy()

    def get_current_policy(self) -> DecisionPolicy:
        """Get the active policy (or default if none loaded)."""
        if self._current_policy:
            return self._current_policy
        return self._create_default_policy()

    async def update_policy(self, new_policy: DecisionPolicy) -> None:
        """Update the active policy and persist to disk."""
        self._current_policy = new_policy
        self._save_policy()
        logger.info(f"🔄 Policy upgraded to {new_policy.version}")
        
        # Broadcast toast to frontend
        try:
            from app.services.websocket import manager
            await manager.broadcast({
                "type": "policy_update",
                "data": {
                    "version": new_policy.version,
                    "insight": new_policy.policy_insights[-1] if new_policy.policy_insights else "Policy updated based on recent learning.",
                    "timestamp": datetime.now().isoformat()
                }
            })
        except Exception as e:
            logger.warning(f"Failed to broadcast policy update: {e}")

    def _create_default_policy(self) -> DecisionPolicy:
        """Create a baseline default policy."""
        return DecisionPolicy(
            version="v1.0",
            confidence_threshold_act=0.7,
            confidence_threshold_escalate=0.4,
            framework_weights={"RCA": 0.4, "FMEA": 0.3, "TOC": 0.3},
            reasoning_artifacts=[],
            policy_insights=["Initial baseline policy"],
            incidents_evaluated=0,
            accuracy_rate=0.0
        )

    def _save_policy(self):
        """Save current policy to JSON."""
        if not self._current_policy:
            return
            
        try:
            os.makedirs(os.path.dirname(POLICY_FILE), exist_ok=True)
            # Serialization - assuming DecisionPolicy is Pydantic/dataclass
            # Since it's a Pydantic model (based on artifacts.py usage), we can use .model_dump() or .dict()
            with open(POLICY_FILE, 'w') as f:
                f.write(self._current_policy.json())
        except Exception as e:
            logger.error(f"Failed to save policy: {e}")

    def _load_policy(self):
        """Load policy from JSON on startup."""
        if not os.path.exists(POLICY_FILE):
            logger.info("ℹ️ No saved policy found, using default.")
            return

        try:
            with open(POLICY_FILE, 'r') as f:
                data = json.load(f)
                # Reconstruct DecisionPolicy
                # We need to handle potential schema changes or import errors
                try:
                    self._current_policy = DecisionPolicy(**data)
                    logger.info(f"✅ Loaded active policy: {self._current_policy.version}")
                except Exception as e:
                     logger.error(f"Failed to parse saved policy: {e}")
        except Exception as e:
            logger.error(f"Failed to load policy file: {e}")

# Global Singleton
policy_service = PolicyService()

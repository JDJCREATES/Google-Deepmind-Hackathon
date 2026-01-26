"""
Counterfactual replay engine for strategic learning.

Analyzes "what if we chose differently" after each decision,
enabling the system to learn strategically, not just tactically.

Now with SQLite persistence for long-term learning across restarts.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

import aiosqlite

from app.hypothesis.models import Hypothesis
from app.utils.logging import get_agent_logger

logger = get_agent_logger("StrategicMemory")


@dataclass
class CounterfactualReplay:
    """
    Post-action analysis comparing chosen vs alternative paths.
    
    After every action, we ask: "What if we had chosen the
    second-most-likely hypothesis instead?"
    
    This enables strategic learning beyond simple success/failure.
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
    production_delta: float = 0.0
    time_delta_minutes: int = 0
    risk_delta: float = 0.0
    cost_delta: float = 0.0
    
    # Strategic learning
    insight: str = ""
    should_update_policy: bool = False
    update_recommendation: str = ""
    
    # Temporal
    created_at: datetime = field(default_factory=datetime.now)
    
    @property
    def was_optimal_choice(self) -> bool:
        """Returns True if chosen path was better than alternative."""
        score = (
            self.production_delta * 0.4 +
            -self.time_delta_minutes * 0.3 +
            -self.risk_delta * 0.2 +
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
            "created_at": self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CounterfactualReplay":
        """Reconstruct from dictionary (database row)."""
        # Parse JSON fields
        if isinstance(data.get("actual_outcome"), str):
            data["actual_outcome"] = json.loads(data["actual_outcome"]) if data["actual_outcome"] else {}
        if isinstance(data.get("predicted_alternative_outcome"), str):
            data["predicted_alternative_outcome"] = json.loads(data["predicted_alternative_outcome"]) if data["predicted_alternative_outcome"] else {}
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("should_update_policy"), int):
            data["should_update_policy"] = bool(data["should_update_policy"])
            
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class StrategicMemory:
    """
    Long-term memory for strategic learning with SQLite persistence.
    
    Stores counterfactual replays and policy evolution history
    to enable continuous improvement across application restarts.
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Import settings lazily to avoid circular imports
            from app.config import settings
            self.db_path = os.path.join(settings.data_dir, "learning.db")
        else:
            self.db_path = db_path
            
        self._table_initialized = False
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        logger.info(f"🧠 StrategicMemory persistence enabled at: {self.db_path}")
    
    async def _ensure_tables(self, db: aiosqlite.Connection):
        """Ensure all required tables exist."""
        if self._table_initialized:
            return
            
        await db.execute("""
            CREATE TABLE IF NOT EXISTS counterfactual_replays (
                replay_id TEXT PRIMARY KEY,
                incident_id TEXT,
                chosen_hypothesis_id TEXT,
                chosen_hypothesis_description TEXT,
                action_taken TEXT,
                actual_outcome TEXT,
                alternative_hypothesis_id TEXT,
                alternative_hypothesis_description TEXT,
                alternative_action TEXT,
                predicted_alternative_outcome TEXT,
                production_delta REAL,
                time_delta_minutes INTEGER,
                risk_delta REAL,
                cost_delta REAL,
                insight TEXT,
                should_update_policy INTEGER,
                update_recommendation TEXT,
                created_at TEXT
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS policy_evolution (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT,
                description TEXT,
                trigger_event TEXT,
                changes TEXT,
                confidence_threshold_act REAL,
                confidence_threshold_escalate REAL,
                framework_weights TEXT,
                policy_insights TEXT,
                incidents_evaluated INTEGER,
                accuracy_rate REAL,
                created_at TEXT
            )
        """)
        
        await db.commit()
        
        # Seed Baseline Policy if empty
        cursor = await db.execute("SELECT count(*) FROM policy_evolution")
        count = (await cursor.fetchone())[0]
        
        if count == 0:
            logger.info("🌱 Seeding Baseline Policy v1.0...")
            baseline_weights = {
                 "production_impact": 0.4,
                 "safety_risk": 0.3,
                 "cost_efficiency": 0.2,
                 "time_urgency": 0.1
            }
            await db.execute("""
                INSERT INTO policy_evolution (
                    version, description, trigger_event, changes,
                    confidence_threshold_act, confidence_threshold_escalate,
                    framework_weights, policy_insights, incidents_evaluated,
                    accuracy_rate, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "v1.0",
                "Initial Baseline Policy",
                "System Initialization",
                json.dumps(["Established baseline confidence thresholds", "Initialized weighing framework"]),
                0.75, # Act threshold
                0.90, # Escalate threshold
                json.dumps(baseline_weights),
                json.dumps([]),
                0,
                0.0,
                datetime.now().isoformat()
            ))
            await db.commit()

        self._table_initialized = True
    
    async def add_replay(self, replay: CounterfactualReplay) -> None:
        """Add a counterfactual replay to persistent memory."""
        async with aiosqlite.connect(self.db_path) as db:
            await self._ensure_tables(db)
            
            await db.execute("""
                INSERT OR REPLACE INTO counterfactual_replays (
                    replay_id, incident_id, chosen_hypothesis_id, chosen_hypothesis_description,
                    action_taken, actual_outcome, alternative_hypothesis_id,
                    alternative_hypothesis_description, alternative_action,
                    predicted_alternative_outcome, production_delta, time_delta_minutes,
                    risk_delta, cost_delta, insight, should_update_policy,
                    update_recommendation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                replay.replay_id,
                replay.incident_id,
                replay.chosen_hypothesis_id,
                replay.chosen_hypothesis_description,
                replay.action_taken,
                json.dumps(replay.actual_outcome),
                replay.alternative_hypothesis_id,
                replay.alternative_hypothesis_description,
                replay.alternative_action,
                json.dumps(replay.predicted_alternative_outcome),
                replay.production_delta,
                replay.time_delta_minutes,
                replay.risk_delta,
                replay.cost_delta,
                replay.insight,
                1 if replay.should_update_policy else 0,
                replay.update_recommendation,
                replay.created_at.isoformat() if isinstance(replay.created_at, datetime) else replay.created_at,
            ))
            await db.commit()
            
        logger.info(f"📝 Stored counterfactual replay: {replay.replay_id}")
    
    async def get_recent_replays(self, count: int = 20) -> List[CounterfactualReplay]:
        """Get most recent replays from database."""
        replays = []
        async with aiosqlite.connect(self.db_path) as db:
            await self._ensure_tables(db)
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute("""
                SELECT * FROM counterfactual_replays
                ORDER BY created_at DESC LIMIT ?
            """, (count,))
            rows = await cursor.fetchall()
            
            for row in rows:
                replays.append(CounterfactualReplay.from_dict(dict(row)))
                
        return list(reversed(replays))  # Chronological order
    
    async def get_all_replays(self) -> List[CounterfactualReplay]:
        """Get all replays for analytics."""
        replays = []
        async with aiosqlite.connect(self.db_path) as db:
            await self._ensure_tables(db)
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute("""
                SELECT * FROM counterfactual_replays
                ORDER BY created_at ASC
            """)
            rows = await cursor.fetchall()
            
            for row in rows:
                replays.append(CounterfactualReplay.from_dict(dict(row)))
                
        return replays
    
    async def get_suboptimal_decisions(self) -> List[CounterfactualReplay]:
        """Get replays where we made a suboptimal choice."""
        all_replays = await self.get_all_replays()
        return [r for r in all_replays if not r.was_optimal_choice]
    
    async def get_policy_update_candidates(self) -> List[CounterfactualReplay]:
        """Get replays that recommend policy updates."""
        replays = []
        async with aiosqlite.connect(self.db_path) as db:
            await self._ensure_tables(db)
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute("""
                SELECT * FROM counterfactual_replays
                WHERE should_update_policy = 1
                ORDER BY created_at DESC
            """)
            rows = await cursor.fetchall()
            
            for row in rows:
                replays.append(CounterfactualReplay.from_dict(dict(row)))
                
        return replays
    
    async def get_insights_for_prompt(self, max_insights: int = 5) -> str:
        """
        Get formatted insights for injecting into Gemini prompts.
        
        Returns recent strategic insights to inform future decisions.
        """
        replays = await self.get_recent_replays(50)
        recent_with_insights = [r for r in replays if r.insight][-max_insights:]
        
        if not recent_with_insights:
            return ""
        
        insights = "\n".join([f"- {r.insight}" for r in recent_with_insights])
        
        return f"""
STRATEGIC INSIGHTS FROM PAST DECISIONS:
{insights}

Use these learnings to inform your current analysis.
"""
    
    def get_insights_for_prompt_sync(self, max_insights: int = 5) -> str:
        """Synchronous version for use in sync contexts."""
        import sqlite3
        
        if not os.path.exists(self.db_path):
            return ""
            
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT insight FROM counterfactual_replays
                WHERE insight IS NOT NULL AND insight != ''
                ORDER BY created_at DESC LIMIT ?
            """, (max_insights,))
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return ""
                
            insights = "\n".join([f"- {row['insight']}" for row in reversed(rows)])
            
            return f"""
STRATEGIC INSIGHTS FROM PAST DECISIONS:
{insights}

Use these learnings to inform your current analysis.
"""
        except Exception as e:
            logger.debug(f"Could not load insights: {e}")
            return ""
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        replays = await self.get_all_replays()
        total = len(replays)
        optimal = sum(1 for r in replays if r.was_optimal_choice)
        policy_candidates = await self.get_policy_update_candidates()
        
        return {
            "total_replays": total,
            "optimal_decisions": optimal,
            "suboptimal_decisions": total - optimal,
            "accuracy_rate": optimal / total if total > 0 else 0.0,
            "policy_updates_recommended": len(policy_candidates),
        }
    
    async def save_policy_evolution(
        self,
        version: str,
        confidence_threshold_act: float,
        confidence_threshold_escalate: float,
        framework_weights: Dict[str, float],
        policy_insights: List[str],
        incidents_evaluated: int,
        accuracy_rate: float,
        description: str = "",
        trigger_event: str = "",
        changes: List[str] = None
    ) -> None:
        """Save a policy evolution record."""
        changes = changes or []
        async with aiosqlite.connect(self.db_path) as db:
            await self._ensure_tables(db)
            
            # Simple migration: check if columns exist
            try:
                await db.execute("SELECT description FROM policy_evolution LIMIT 1")
            except Exception:
                # Add missing columns
                logger.info("🔧 Migrating policy_evolution table...")
                await db.execute("ALTER TABLE policy_evolution ADD COLUMN description TEXT")
                await db.execute("ALTER TABLE policy_evolution ADD COLUMN trigger_event TEXT")
                await db.execute("ALTER TABLE policy_evolution ADD COLUMN changes TEXT")
                await db.commit()
            
            await db.execute("""
                INSERT INTO policy_evolution (
                    version, description, trigger_event, changes,
                    confidence_threshold_act, confidence_threshold_escalate,
                    framework_weights, policy_insights, incidents_evaluated,
                    accuracy_rate, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                version,
                description,
                trigger_event,
                json.dumps(changes),
                confidence_threshold_act,
                confidence_threshold_escalate,
                json.dumps(framework_weights),
                json.dumps(policy_insights),
                incidents_evaluated,
                accuracy_rate,
                datetime.now().isoformat(),
            ))
            await db.commit()
            
        logger.info(f"📊 Saved policy evolution: {version}")
    
    async def get_policy_history(self) -> List[Dict[str, Any]]:
        """Get all policy evolution records for analytics."""
        records = []
        async with aiosqlite.connect(self.db_path) as db:
            await self._ensure_tables(db)
            db.row_factory = aiosqlite.Row
            
            cursor = await db.execute("""
                SELECT * FROM policy_evolution ORDER BY created_at ASC
            """)
            rows = await cursor.fetchall()
            
            for row in rows:
                record = dict(row)
                record["framework_weights"] = json.loads(record["framework_weights"]) if record.get("framework_weights") else {}
                record["policy_insights"] = json.loads(record["policy_insights"]) if record.get("policy_insights") else []
                record["changes"] = json.loads(record["changes"]) if record.get("changes") else []
                # Fallbacks for existing records
                if "description" not in record: record["description"] = f"Policy update {record['version']}"
                if "trigger_event" not in record: record["trigger_event"] = "Accumulated suboptimal decisions"
                records.append(record)
                
        return records
    
    async def get_all_insights(self) -> List[Dict[str, Any]]:
        """Get all insights with metadata for frontend display."""
        replays = await self.get_all_replays()
        insights = []
        
        for r in replays:
            if r.insight:
                insights.append({
                    "insight": r.insight,
                    "incident_id": r.incident_id,
                    "was_optimal": r.was_optimal_choice,
                    "created_at": r.created_at.isoformat() if isinstance(r.created_at, datetime) else r.created_at,
                })
                
        return insights


# Global singleton instance
strategic_memory = StrategicMemory()

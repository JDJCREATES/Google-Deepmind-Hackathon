"""
WebSocket message types for streaming agent reasoning to the frontend.

Every reasoning step, hypothesis, evidence gathering, and belief update
must be broadcast so the frontend can visualize the complete agent thought process.
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class ReasoningPhase(str, Enum):
    """Phases of agent reasoning."""
    SIGNAL_RECEIVED = "signal_received"
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    EVIDENCE_GATHERING = "evidence_gathering"
    BELIEF_UPDATE = "belief_update"
    ACTION_SELECTION = "action_selection"
    ACTION_EXECUTION = "action_execution"
    VALIDATION = "validation"


@dataclass
class HypothesisMessage:
    """Message for a generated hypothesis."""
    agent_name: str
    hypothesis_id: str
    description: str
    confidence: float
    evidence_required: List[str]
    cost_if_wrong: float
    timestamp: str


@dataclass
class EvidenceMessage:
    """Message for evidence gathering."""
    agent_name: str
    hypothesis_id: str
    evidence_source: str
    evidence_data: Dict[str, Any]
    supports: bool
    strength: float
    timestamp: str


@dataclass
class BeliefUpdateMessage:
    """Message for belief state update."""
    agent_name: str
    hypotheses: List[Dict[str, Any]]
    posterior_probabilities: Dict[str, float]
    leading_hypothesis: str
    confidence_in_leader: float
    reasoning_trace: str  # Gemini's reasoning
    timestamp: str


@dataclass
class AgentThoughtMessage:
    """Message for any agent thought/reasoning."""
    agent_name: str
    phase: ReasoningPhase
    thought: str
    gemini_thinking: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


def broadcast_message(msg_type: str, data: Any):
    """Helper to broadcast structured messages via WebSocket."""
    from app.services.websocket import manager
    import asyncio
    
    message = {
        "type": msg_type,
        "data": data if isinstance(data, dict) else asdict(data),
        "timestamp": datetime.now().isoformat()
    }
    
    # Run in event loop
    try:
        asyncio.create_task(manager.broadcast(message))
    except RuntimeError:
        # If no event loop, schedule for later
        pass

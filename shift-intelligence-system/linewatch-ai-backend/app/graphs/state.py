"""
LangGraph state schema for hypothesis market.

Defines the typed state that flows through the hypothesis-driven
reasoning graph, enabling persistent beliefs and policy evolution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from app.hypothesis import BeliefState, Hypothesis
from app.reasoning import CounterfactualReplay, DecisionPolicy, DriftAlert
from langgraph.graph.message import add_messages


def merge_hypotheses(left: List, right: List) -> List:
    """Merge hypothesis lists (accumulate from multiple agents)."""
    return left + right


def merge_evidence(left: List, right: List) -> List:
    """Merge evidence lists."""
    return left + right


class HypothesisMarketState(TypedDict, total=False):
    """
    State schema for the hypothesis market LangGraph.
    
    This state flows through all nodes in the reasoning graph,
    accumulating hypotheses, evidence, and beliefs.
    
    Attributes:
        signal_id: Unique identifier for the triggering signal
        signal_type: Classification of the signal
        signal_description: Human-readable description
        signal_data: Raw signal data
        
        knowledge_context: Relevant company knowledge
        
        hypotheses: Accumulated hypotheses from all agents
        evidence: Accumulated evidence
        belief_state: Current belief distribution
        
        decision_policy: Active policy governing decisions
        reasoning_artifact: Active decision schema
        
        selected_action: Chosen action (if converged)
        action_result: Result of executing action
        
        counterfactual: Post-action analysis
        drift_alert: Framework drift warning (if detected)
        
        iteration: Current loop iteration
        converged: Whether we have enough confidence to act
        needs_human: Whether human escalation is needed
    """
    # Signal
    signal_id: str
    signal_type: str
    signal_description: str
    signal_data: Dict[str, Any]
    
    # Knowledge
    knowledge_context: str
    
    # Hypotheses (accumulated from agents)
    hypotheses: Annotated[List[Hypothesis], merge_hypotheses]
    
    # Evidence (accumulated from tools)
    evidence: Annotated[List[Any], merge_evidence]
    
    # Belief state
    belief_state: Optional[BeliefState]
    
    # Decision structures
    decision_policy: Optional[DecisionPolicy]
    reasoning_artifact_version: str
    
    # Action
    selected_action: Optional[str]
    action_result: Optional[Dict[str, Any]]
    
    # Learning
    counterfactual: Optional[CounterfactualReplay]
    drift_alert: Optional[DriftAlert]
    policy_update_recommended: bool
    
    # Control
    iteration: int
    max_iterations: int
    converged: bool
    needs_human: bool
    
    # Messages (for agent communication)
    messages: Annotated[List[Any], add_messages]
    
    # Gemini 3 Thought Signature (Chain of Thought continuity)
    thought_signature: Optional[str]


def create_initial_state(
    signal_id: str,
    signal_type: str,
    signal_description: str,
    signal_data: Dict[str, Any],
) -> HypothesisMarketState:
    """
    Create initial state for a new hypothesis market run.
    
    Args:
        signal_id: Unique identifier for this incident
        signal_type: Type of signal (e.g., "production_slowdown")
        signal_description: Human-readable description
        signal_data: Raw data from sensors/cameras
        
    Returns:
        Initialized state dictionary
    """
    return HypothesisMarketState(
        signal_id=signal_id,
        signal_type=signal_type,
        signal_description=signal_description,
        signal_data=signal_data,
        knowledge_context="",
        hypotheses=[],
        evidence=[],
        belief_state=None,
        decision_policy=None,
        reasoning_artifact_version="v1.0",
        selected_action=None,
        action_result=None,
        counterfactual=None,
        drift_alert=None,
        policy_update_recommended=False,
        iteration=0,
        max_iterations=5,
        converged=False,
        needs_human=False,
        messages=[],
        thought_signature=None,
    )

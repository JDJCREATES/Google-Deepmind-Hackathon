"""
Hypothesis Market LangGraph - Main graph assembly.

Assembles the complete hypothesis-driven reasoning graph with:
- Knowledge loading
- Framework classification
- Hypothesis generation
- Evidence gathering
- Bayesian belief updates
- Action selection
- Counterfactual replays
- Framework drift detection
- Policy evolution
"""
from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.graphs.state import HypothesisMarketState, create_initial_state
from app.graphs.nodes import (
    load_knowledge_node,
    classify_frameworks_node,
    generate_hypotheses_node,
    gather_evidence_node,
    update_beliefs_node,
    select_action_node,
    execute_action_node,
    counterfactual_replay_node,
    check_drift_node,
    evolve_policy_node,
)
from app.utils.logging import get_agent_logger


logger = get_agent_logger("HypothesisMarketGraph")


def should_gather_more_evidence(
    state: HypothesisMarketState
) -> Literal["gather_more", "decide"]:
    """
    Determine if we need more evidence or can make a decision.
    
    Returns "gather_more" if:
    - Not converged AND
    - Haven't hit max iterations
    
    Otherwise returns "decide".
    """
    converged = state.get("converged", False)
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 5)
    
    if not converged and iteration < max_iterations:
        return "gather_more"
    return "decide"


def should_execute_action(
    state: HypothesisMarketState
) -> Literal["execute", "escalate", "skip"]:
    """
    Determine if we should execute action or escalate.
    """
    needs_human = state.get("needs_human", False)
    selected_action = state.get("selected_action")
    
    if needs_human:
        return "escalate"
    elif selected_action:
        return "execute"
    else:
        return "skip"


def should_evolve_policy(
    state: HypothesisMarketState
) -> Literal["evolve", "done"]:
    """
    Determine if policy evolution is needed.
    """
    if state.get("policy_update_recommended", False):
        return "evolve"
    return "done"


def create_hypothesis_market_graph() -> StateGraph:
    """
    Create the complete hypothesis market LangGraph.
    
    Graph Flow:
    1. load_knowledge: Load relevant company policies/SOPs
    2. classify_frameworks: Determine which frameworks apply
    3. generate_hypotheses: Create competing hypotheses
    4. gather_evidence: Collect evidence from tools
    5. update_beliefs: Bayesian belief update
       ↓ (loop if not converged)
    6. select_action: Choose action based on beliefs
    7. execute_action: Run the selected action
    8. counterfactual_replay: Analyze alternative paths
    9. check_drift: Detect framework bias
    10. evolve_policy: Update policy if needed
    
    Returns:
        Compiled LangGraph ready for execution
    """
    logger.info("🔧 Building hypothesis market graph")
    
    # Create graph with state schema
    graph = StateGraph(HypothesisMarketState)
    
    # Add nodes
    graph.add_node("load_knowledge", load_knowledge_node)
    graph.add_node("classify_frameworks", classify_frameworks_node)
    graph.add_node("generate_hypotheses", generate_hypotheses_node)
    graph.add_node("gather_evidence", gather_evidence_node)
    graph.add_node("update_beliefs", update_beliefs_node)
    graph.add_node("select_action", select_action_node)
    graph.add_node("execute_action", execute_action_node)
    graph.add_node("counterfactual_replay", counterfactual_replay_node)
    graph.add_node("check_drift", check_drift_node)
    graph.add_node("evolve_policy", evolve_policy_node)
    
    # Entry point
    graph.set_entry_point("load_knowledge")
    
    # Sequential flow: knowledge → classify → generate → gather → update
    graph.add_edge("load_knowledge", "classify_frameworks")
    graph.add_edge("classify_frameworks", "generate_hypotheses")
    graph.add_edge("generate_hypotheses", "gather_evidence")
    graph.add_edge("gather_evidence", "update_beliefs")
    
    # Conditional: need more evidence or decide?
    graph.add_conditional_edges(
        "update_beliefs",
        should_gather_more_evidence,
        {
            "gather_more": "gather_evidence",
            "decide": "select_action",
        }
    )
    
    # Conditional: execute, escalate, or skip?
    graph.add_conditional_edges(
        "select_action",
        should_execute_action,
        {
            "execute": "execute_action",
            "escalate": END,  # Exit to human
            "skip": END,
        }
    )
    
    # Post-action flow
    graph.add_edge("execute_action", "counterfactual_replay")
    graph.add_edge("counterfactual_replay", "check_drift")
    
    # Conditional: evolve policy?
    graph.add_conditional_edges(
        "check_drift",
        should_evolve_policy,
        {
            "evolve": "evolve_policy",
            "done": END,
        }
    )
    
    graph.add_edge("evolve_policy", END)
    
    logger.info("✅ Hypothesis market graph built")
    
    return graph


def compile_hypothesis_market(
    use_checkpointing: bool = True
) -> "CompiledGraph":
    """
    Compile the hypothesis market graph for execution.
    
    Args:
        use_checkpointing: Whether to enable state persistence
        
    Returns:
        Compiled graph ready for .invoke() or .stream()
    """
    graph = create_hypothesis_market_graph()
    
    if use_checkpointing:
        # Use SQLite persistent checkpointer
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from app.config import settings
        
        checkpoint_path = settings.agent_checkpoint_db or "data/agent_checkpoints.db"
        checkpointer = AsyncSqliteSaver.from_conn_string(checkpoint_path)
        compiled = graph.compile(checkpointer=checkpointer)
    else:
        compiled = graph.compile()
    
    logger.info("✅ Hypothesis market graph compiled with SQLite persistence")
    
    return compiled


# Convenience function for running the graph
async def run_hypothesis_market(
    signal_id: str,
    signal_type: str,
    signal_description: str,
    signal_data: dict,
    thread_id: str = "default",
) -> dict:
    """
    Run a complete hypothesis market cycle.
    
    Args:
        signal_id: Unique identifier for this incident
        signal_type: Classification of the signal
        signal_description: Human-readable description
        signal_data: Raw data from sensors/cameras
        thread_id: Thread ID for checkpointing
        
    Returns:
        Final state after graph execution
    """
    logger.info(f"🚀 Running hypothesis market for signal: {signal_id}")
    
    # Create initial state
    initial_state = create_initial_state(
        signal_id=signal_id,
        signal_type=signal_type,
        signal_description=signal_description,
        signal_data=signal_data,
    )
    
    # Compile and run graph
    graph = compile_hypothesis_market()
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # Run graph
    final_state = await graph.ainvoke(initial_state, config)
    
    logger.info("✅ Hypothesis market cycle complete")
    
    return final_state

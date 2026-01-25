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

import logging
logger = logging.getLogger(__name__)

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
    
    QUICK WIN: Hard limit to 2 iterations to prevent infinite loops.
    """
    converged = state.get("converged", False)
    iteration = state.get("iteration", 0)
    max_iterations = 2  # HARD LIMIT: Force decision after 2 evidence gathering cycles
    
    # Edge case: If we have no new evidence from last iteration, force decision
    evidence_count = len(state.get("evidence", []))
    last_evidence_count = state.get("last_evidence_count", 0)
    
    if iteration > 0 and evidence_count == last_evidence_count:
        logger.info(f"🛑 No new evidence gathered in iteration {iteration}, forcing decision")
        return "decide"
    
    if not converged and iteration < max_iterations:
        return "gather_more"
    
    logger.info(f"🛑 Reached max iterations ({max_iterations}) or converged, forcing decision")
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
    use_checkpointing: bool = True,
    checkpointer: Any = None
) -> "CompiledGraph":
    """
    Compile the hypothesis market graph for execution.
    
    Args:
        use_checkpointing: Whether to enable state persistence
        checkpointer: Optional specific checkpointer instance (e.g. AsyncSqliteSaver)
        
    Returns:
        Compiled graph ready for .invoke() or .stream()
    """
    graph = create_hypothesis_market_graph()
    
    if use_checkpointing:
        # Use provided checkpointer or default to MemorySaver
        if checkpointer is None:
            checkpointer = MemorySaver()
            
        compiled = graph.compile(checkpointer=checkpointer)
    else:
        compiled = graph.compile()
    
    logger.info(f"✅ Hypothesis market graph compiled (Persistence: {type(checkpointer).__name__ if use_checkpointing else 'Disabled'})")
    
    return compiled


# Convenience function for running the graph
async def run_hypothesis_market(
    signal_id: str,
    signal_type: str,
    signal_description: str,
    signal_data: dict,
    thread_id: str = None,
) -> dict:
    """
    Run a complete hypothesis market cycle.
    """
    if thread_id is None:
        thread_id = f"signal_{signal_id}"

    logger.info(f"🚀 Running hypothesis market for signal: {signal_id} (Thread: {thread_id})")
    
    # Create initial state
    initial_state = create_initial_state(
        signal_id=signal_id,
        signal_type=signal_type,
        signal_description=signal_description,
        signal_data=signal_data,
    )
    
    # FORCE MEMORY SAVER FOR CLOUD RUN
    # SQLite persistence is causing issues and is not needed for ephemeral demo.
    logger.info("💾 using MemorySaver for agent persistence (Cloud Run optimized)")
    checkpointer = MemorySaver()
    persistence_mode = "memory"
    
    try:
        # VERIFY API KEY FIRST - Fail early if missing
        if not settings.google_api_key:
            raise ValueError("Missing GOOGLE_API_KEY. Cannot run agent graph.")
            
        # Compile graph using the checkpointer
        graph = compile_hypothesis_market(use_checkpointing=True, checkpointer=checkpointer)
        
        config = {"configurable": {"thread_id": thread_id}}
        
        logger.info(f"🚀 Executing Agent Graph (Persistence: {persistence_mode})...")
        
        # Run graph
        final_state = await graph.ainvoke(initial_state, config)
        
        logger.info("✅ Hypothesis market cycle complete")
        return final_state
        
    except Exception as e:
        logger.error(f"❌ Hypothesis market execution failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {"error": str(e)}
    finally:
        if conn:
            await conn.close()


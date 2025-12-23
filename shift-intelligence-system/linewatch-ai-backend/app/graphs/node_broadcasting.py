"""
WebSocket broadcasting helpers for LangGraph nodes.

Add these imports and calls to app/graphs/nodes.py to enable
real-time visualization of the hypothesis market reasoning process.
"""

# ADD THIS IMPORT AT TOP OF nodes.py:
# from app.services.websocket import manager

# =================================================================
# BROADCASTING HELPER - ADD THIS TO nodes.py
# =================================================================

async def broadcast_node_entry(node_name: str, state: dict):
    """Broadcast when entering a graph node."""
    from app.services.websocket import manager
    await manager.broadcast({
        "type": "node_entered",
        "data": {
            "node": node_name,
            "timestamp": datetime.now().isoformat()
        }
    })

async def broadcast_node_exit(node_name: str, state: dict):
    """Broadcast when exiting a graph node."""
    from app.services.websocket import manager
    await manager.broadcast({
        "type": "node_exited",
        "data": {
            "node": node_name,
            "timestamp": datetime.now().isoformat()
        }
    })

# =================================================================
# UPDATE gather_evidence_node - ADD THESE CALLS
# =================================================================

# AT START OF gather_evidence_node:
await broadcast_node_entry("gather_evidence", state)
await manager.broadcast({
    "type": "evidence_gathering_started",
    "data": {
        "hypothesis_count": len(hypotheses),
        "timestamp": datetime.now().isoformat()
    }
})

# AFTER GATHERING EVIDENCE (before return):
await manager.broadcast({
    "type": "evidence_gathered",
    "data": {
        "count": len(evidence_list),
        "evidence": [
            {
                "source": e.source,
                "supports": e.supports,
                "strength": e.strength
            }
            for e in evidence_list
        ],
        "timestamp": datetime.now().isoformat()
    }
})
await broadcast_node_exit("gather_evidence", state)

# =================================================================
# UPDATE update_beliefs_node - ADD THESE CALLS
# =================================================================

# AT START:
await broadcast_node_entry("update_beliefs", state)

# AFTER GEMINI REASONING (after llm.ainvoke):
await manager.broadcast({
    "type": "belief_update",
    "data": {
        "posteriors": posteriors,
        "leading_hypothesis": leading_id,
        "confidence": leading_confidence,
        "gemini_reasoning": result.content[:500],  # First 500 chars
        "timestamp": datetime.now().isoformat()
    }
})
await broadcast_node_exit("update_beliefs", state)

# =================================================================
# UPDATE select_action_node - ADD THESE CALLS
# =================================================================

# AT START:
await broadcast_node_entry("select_action", state)

# AFTER ACTION SELECTED:
await manager.broadcast({
    "type": "action_selected",
    "data": {
        "action": selected_action,
        "confidence": confidence,
        "hypothesis_id": hypothesis_id,
        "timestamp": datetime.now().isoformat()
    }
})
await broadcast_node_exit("select_action", state)

# =================================================================
# UPDATE execute_action_node - ADD THESE CALLS
# =================================================================

# AT START:
await broadcast_node_entry("execute_action", state)

# AFTER EXECUTION:
await manager.broadcast({
    "type": "action_executed",
    "data": {
        "action": action,
        "result": result_summary,
        "timestamp": datetime.now().isoformat()
    }
})
await broadcast_node_exit("execute_action", state)

# =================================================================
# UPDATE load_knowledge_node - ADD THESE CALLS
# =================================================================

# AT START:
await broadcast_node_entry("load_knowledge", state)

# BEFORE RETURN:
await broadcast_node_exit("load_knowledge", state)

# =================================================================
# UPDATE classify_frameworks_node - ADD THESE CALLS
# =================================================================

# AT START:
await broadcast_node_entry("classify_frameworks", state)

# AFTER CLASSIFICATION:
await manager.broadcast({
    "type": "frameworks_classified",
    "data": {
        "frameworks": frameworks,
        "timestamp": datetime.now().isoformat()
    }
})
await broadcast_node_exit("classify_frameworks", state)

# =================================================================
# UPDATE counterfactual_replay_node - ADD THESE CALLS
# =================================================================

# AT START:
await broadcast_node_entry("counterfactual_replay", state)

# BEFORE RETURN:
await broadcast_node_exit("counterfactual_replay", state)

# =================================================================
# UPDATE check_drift_node - ADD THESE CALLS
# =================================================================

# AT START:
await broadcast_node_entry("check_drift", state)

# BEFORE RETURN:
await broadcast_node_exit("check_drift", state)

# =================================================================
# UPDATE evolve_policy_node - ADD THESE CALLS
# =================================================================

# AT START:
await broadcast_node_entry("evolve_policy", state)

# BEFORE RETURN:
await broadcast_node_exit("evolve_policy", state)

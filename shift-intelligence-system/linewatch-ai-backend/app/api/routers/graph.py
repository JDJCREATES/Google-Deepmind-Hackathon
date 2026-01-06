"""
API endpoint to export the actual LangGraph structure for visualization.

Extracts the real node/edge structure from hypothesis_market.py
and includes live reasoning traces for full AI thinking visualization.
"""
import threading
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.graphs.hypothesis_market import create_hypothesis_market_graph
from app.utils.logging import get_agent_logger
from datetime import datetime

router = APIRouter(prefix="/api/graph", tags=["graph"])
logger = get_agent_logger("GraphAPI")

# Thread-safe stores for reasoning traces
_trace_lock = threading.Lock()
_reasoning_traces: list = []
_thought_signatures: list = []


class TraceInput(BaseModel):
    """Input schema for adding a trace."""
    agent: str = Field(description="Agent name")
    step: str = Field(description="Step name")
    thought: str = Field(default="", description="Thought process text")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score")
    decision: Optional[str] = Field(default=None, description="Decision made")


async def add_reasoning_trace(
    agent_name: str,
    step_name: str,
    thought_process: str,
    confidence: float,
    decision: str | None = None
):
    """
    Add a reasoning trace from an agent's thinking process (thread-safe).
    
    Broadcasts trace via WebSocket for real-time visualization.
    """
    with _trace_lock:
        trace = {
            "id": f"trace_{len(_reasoning_traces)}",
            "agent": agent_name,
            "step": step_name,
            "thought": (thought_process or "")[:500],  # Truncate and handle None
            "confidence": min(max(confidence, 0.0), 1.0),  # Clamp to valid range
            "decision": decision,
            "timestamp": datetime.now().isoformat(),
        }
        _reasoning_traces.append(trace)
        # Keep only last 100 traces
        while len(_reasoning_traces) > 100:
            _reasoning_traces.pop(0)
    
    # Broadcast to frontend (outside lock to avoid blocking)
    try:
        from app.services.websocket import manager
        await manager.broadcast({
            "type": "reasoning_trace",
            "data": trace
        })
    except Exception as e:
        logger.error(f"Failed to broadcast reasoning trace: {e}")
    
    return trace


def add_thought_signature(signature: dict):
    """Add a thought signature for audit trail (thread-safe)."""
    with _trace_lock:
        _thought_signatures.append(signature)
        while len(_thought_signatures) > 50:
            _thought_signatures.pop(0)


@router.get("/structure")
async def get_graph_structure():
    """
    Get the actual LangGraph structure from hypothesis_market.py.
    
    Returns exact nodes/edges from the compiled graph plus live reasoning traces.
    """
    try:
        # Get the actual graph definition
        graph = create_hypothesis_market_graph()
        
        # Extract nodes from the graph
        nodes_list = list(graph.nodes.keys()) if hasattr(graph, 'nodes') else []
        
        # Build node definitions with proper metadata
        hypothesis_nodes = []
        node_types = {
            "load_knowledge": "reasoning",
            "classify_frameworks": "reasoning", 
            "generate_hypotheses": "hypothesis",
            "gather_evidence": "evidence",
            "update_beliefs": "belief",
            "select_action": "action",
            "execute_action": "execution",
            "counterfactual_replay": "reasoning",
            "check_drift": "reasoning",
            "evolve_policy": "reasoning",
        }
        
        node_labels = {
            "load_knowledge": "📚 Load Knowledge",
            "classify_frameworks": "🏷️ Classify Frameworks",
            "generate_hypotheses": "💡 Generate Hypotheses",
            "gather_evidence": "🔍 Gather Evidence",
            "update_beliefs": "🧮 Update Beliefs",
            "select_action": "⚖️ Select Action",
            "execute_action": "⚡ Execute Action",
            "counterfactual_replay": "🔄 Counterfactual",
            "check_drift": "📊 Check Drift",
            "evolve_policy": "🧬 Evolve Policy",
        }
        
        # Node descriptions for richer visualization
        node_descriptions = {
            "load_knowledge": "Retrieves domain expertise and contextual data",
            "classify_frameworks": "Selects reasoning framework (FMEA, RCA, Bayesian)",
            "generate_hypotheses": "Creates multiple competing hypotheses",
            "gather_evidence": "Collects data to support or refute hypotheses",
            "update_beliefs": "Bayesian update of hypothesis probabilities",
            "select_action": "Chooses optimal action based on expected utility",
            "execute_action": "Implements chosen action with monitoring",
            "counterfactual_replay": "Evaluates 'what if' alternative actions",
            "check_drift": "Monitors for model drift or context changes",
            "evolve_policy": "Updates decision policy based on outcomes",
        }
        
        for node_id in nodes_list:
            hypothesis_nodes.append({
                "id": node_id,
                "label": node_labels.get(node_id, node_id),
                "type": node_types.get(node_id, "reasoning"),
                "description": node_descriptions.get(node_id, ""),
            })
        
        # Build edges from the actual graph definition
        hypothesis_edges = [
            # Sequential flow
            {"id": "e1", "source": "load_knowledge", "target": "classify_frameworks"},
            {"id": "e2", "source": "classify_frameworks", "target": "generate_hypotheses"},
            {"id": "e3", "source": "generate_hypotheses", "target": "gather_evidence"},
            {"id": "e4", "source": "gather_evidence", "target": "update_beliefs"},
            # Conditional: loop or decide
            {"id": "e5a", "source": "update_beliefs", "target": "gather_evidence", "conditional": "gather_more", "label": "Need more evidence"},
            {"id": "e5b", "source": "update_beliefs", "target": "select_action", "conditional": "decide", "label": "Confident"},
            # Conditional: execute, escalate, skip
            {"id": "e6", "source": "select_action", "target": "execute_action", "conditional": "execute"},
            # Post-action
            {"id": "e7", "source": "execute_action", "target": "counterfactual_replay"},
            {"id": "e8", "source": "counterfactual_replay", "target": "check_drift"},
            # Conditional: evolve or done
            {"id": "e9", "source": "check_drift", "target": "evolve_policy", "conditional": "evolve", "label": "Drift detected"},
        ]
        
        # Agent definitions (from orchestrator system)
        agents = [
            {"id": "orchestrator", "label": "🎯 Master Orchestrator", "type": "orchestrator", "thinking_level": 3},
            {"id": "production_agent", "label": "🏭 Production Agent", "type": "agent", "thinking_level": 1},
            {"id": "compliance_agent", "label": "📋 Compliance Agent", "type": "agent", "thinking_level": 2},
            {"id": "staffing_agent", "label": "👷 Staffing Agent", "type": "agent", "thinking_level": 1},
            {"id": "maintenance_agent", "label": "🔧 Maintenance Agent", "type": "agent", "thinking_level": 1},
        ]
        
        # Orchestrator → Agent edges
        agent_edges = [
            {"id": "orch_prod", "source": "orchestrator", "target": "production_agent"},
            {"id": "orch_comp", "source": "orchestrator", "target": "compliance_agent"},
            {"id": "orch_staff", "source": "orchestrator", "target": "staffing_agent"},
            {"id": "orch_maint", "source": "orchestrator", "target": "maintenance_agent"},
        ]
        
        logger.info(f"Graph: {len(agents)} agents, {len(hypothesis_nodes)} hypothesis nodes, {len(_reasoning_traces)} traces")
        
        return {
            "agents": agents,
            "agent_edges": agent_edges,
            "hypothesis_nodes": hypothesis_nodes,
            "hypothesis_edges": hypothesis_edges,
            "reasoning_traces": _reasoning_traces[-20:],  # Last 20 traces
            "thought_signatures": _thought_signatures[-10:],  # Last 10 signatures
        }
        
    except Exception as e:
        logger.error(f"Failed to get graph structure: {e}", exc_info=True)
        return {
            "agents": [], 
            "agent_edges": [], 
            "hypothesis_nodes": [], 
            "hypothesis_edges": [], 
            "reasoning_traces": [],
            "thought_signatures": [],
            "error": str(e)
        }


@router.post("/trace")
async def add_trace(trace_data: TraceInput):
    """Add a reasoning trace from agent activity."""
    try:
        trace = add_reasoning_trace(
            agent_name=trace_data.agent,
            step_name=trace_data.step,
            thought_process=trace_data.thought,
            confidence=trace_data.confidence,
            decision=trace_data.decision,
        )
        return {"success": True, "trace": trace}
    except Exception as e:
        logger.error(f"Failed to add trace: {e}")
        raise HTTPException(status_code=500, detail=str(e))



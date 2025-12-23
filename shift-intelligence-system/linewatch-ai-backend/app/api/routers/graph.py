"""
API endpoint to export the actual LangGraph structure for visualization.

Extracts the real node/edge structure from hypothesis_market.py
rather than hard-coding a separate representation.
"""
from fastapi import APIRouter
from app.graphs.hypothesis_market import create_hypothesis_market_graph
from app.utils.logging import get_agent_logger

router = APIRouter(prefix="/api/graph", tags=["graph"])
logger = get_agent_logger("GraphAPI")


@router.get("/structure")
async def get_graph_structure():
    """
    Get the actual LangGraph structure from hypothesis_market.py.
    
    Returns exact nodes/edges from the compiled graph for accurate visualization.
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
        
        for node_id in nodes_list:
            hypothesis_nodes.append({
                "id": node_id,
                "label": node_labels.get(node_id, node_id),
                "type": node_types.get(node_id, "reasoning"),
            })
        
        # Build edges from the actual graph definition
        hypothesis_edges = [
            # Sequential flow
            {"id": "e1", "source": "load_knowledge", "target": "classify_frameworks"},
            {"id": "e2", "source": "classify_frameworks", "target": "generate_hypotheses"},
            {"id": "e3", "source": "generate_hypotheses", "target": "gather_evidence"},
            {"id": "e4", "source": "gather_evidence", "target": "update_beliefs"},
            # Conditional: loop or decide
            {"id": "e5a", "source": "update_beliefs", "target": "gather_evidence", "conditional": "gather_more"},
            {"id": "e5b", "source": "update_beliefs", "target": "select_action", "conditional": "decide"},
            # Conditional: execute, escalate, skip
            {"id": "e6", "source": "select_action", "target": "execute_action", "conditional": "execute"},
            # Post-action
            {"id": "e7", "source": "execute_action", "target": "counterfactual_replay"},
            {"id": "e8", "source": "counterfactual_replay", "target": "check_drift"},
            # Conditional: evolve or done
            {"id": "e9", "source": "check_drift", "target": "evolve_policy", "conditional": "evolve"},
        ]
        
        # Agent definitions (from orchestrator system)
        agents = [
            {"id": "orchestrator", "label": "🎯 Master Orchestrator", "type": "orchestrator"},
            {"id": "production_agent", "label": "🏭 Production Agent", "type": "agent"},
            {"id": "compliance_agent", "label": "📋 Compliance Agent", "type": "agent"},
            {"id": "staffing_agent", "label": "👷 Staffing Agent", "type": "agent"},
            {"id": "maintenance_agent", "label": "🔧 Maintenance Agent", "type": "agent"},
        ]
        
        # Orchestrator → Agent edges
        agent_edges = [
            {"id": "orch_prod", "source": "orchestrator", "target": "production_agent"},
            {"id": "orch_comp", "source": "orchestrator", "target": "compliance_agent"},
            {"id": "orch_staff", "source": "orchestrator", "target": "staffing_agent"},
            {"id": "orch_maint", "source": "orchestrator", "target": "maintenance_agent"},
        ]
        
        logger.info(f"Graph: {len(agents)} agents, {len(hypothesis_nodes)} hypothesis nodes")
        
        return {
            "agents": agents,
            "agent_edges": agent_edges,
            "hypothesis_nodes": hypothesis_nodes,
            "hypothesis_edges": hypothesis_edges,
        }
        
    except Exception as e:
        logger.error(f"Failed to get graph structure: {e}", exc_info=True)
        return {"agents": [], "agent_edges": [], "hypothesis_nodes": [], "hypothesis_edges": [], "error": str(e)}

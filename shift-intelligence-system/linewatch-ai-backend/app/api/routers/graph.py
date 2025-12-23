"""
API endpoint to export LangGraph structure for frontend visualization.

Uses LangGraph's graph introspection to get the exact node/edge structure,
which the frontend will mirror in React Flow.
"""
from fastapi import APIRouter
from app.graphs.hypothesis_market import compile_hypothesis_market
from app.utils.logging import get_agent_logger

router = APIRouter(prefix="/api/graph", tags=["graph"])
logger = get_agent_logger("GraphAPI")


@router.get("/structure")
async def get_graph_structure():
    """
    Get the complete multi-agent system structure with nested reasoning.
    
    Top level: 5 agents (Orchestrator + 4 domain agents)
    Nested: Each agent's internal hypothesis market reasoning
    """
    try:
        # TOP LEVEL: Agent Hierarchy
        agents = [
            {"id": "orchestrator", "label": "🎯 MASTER ORCHESTRATOR", "type": "orchestrator", "level": "top"},
            {"id": "production_agent", "label": "🏭 Production Agent", "type": "agent", "level": "top"},
            {"id": "compliance_agent", "label": "📋 Compliance Agent", "type": "agent", "level": "top"},
            {"id": "staffing_agent", "label": "👷 Staffing Agent", "type": "agent", "level": "top"},
            {"id": "maintenance_agent", "label": "🔧 Maintenance Agent", "type": "agent", "level": "top"},
        ]
        
        # Agent connections
        agent_edges = [
            {"id": "orch_prod", "source": "orchestrator", "target": "production_agent"},
            {"id": "orch_comp", "source": "orchestrator", "target": "compliance_agent"},
            {"id": "orch_staff", "source": "orchestrator", "target": "staffing_agent"},
            {"id": "orch_maint", "source": "orchestrator", "target": "maintenance_agent"},
        ]
        
        # NESTED: Each agent's internal reasoning process (hypothesis market)
        reasoning_template = [
            {"id": "load_knowledge", "label": "📚 Load Knowledge", "type": "reasoning"},
            {"id": "classify_frameworks", "label": "🏷️ Classify Frameworks", "type": "reasoning"},
            {"id": "generate_hypotheses", "label": "💡 Generate Hypotheses", "type": "hypothesis"},
            {"id": "gather_evidence", "label": "🔍 Gather Evidence", "type": "evidence"},
            {"id": "update_beliefs", "label": "🧮 Update Beliefs", "type": "belief"},
            {"id": "select_action", "label": "⚖️ Select Action", "type": "action"},
            {"id": "execute_action", "label": "⚡ Execute", "type": "execution"},
            {"id": "validate", "label": "✓ Validate", "type": "reasoning"},
        ]
        
        reasoning_edges_template = [
            {"source": "load_knowledge", "target": "classify_frameworks"},
            {"source": "classify_frameworks", "target": "generate_hypotheses"},
            {"source": "generate_hypotheses", "target": "gather_evidence"},
            {"source": "gather_evidence", "target": "update_beliefs"},
            {"source": "update_beliefs", "target": "select_action"},
            {"source": "update_beliefs", "target": "gather_evidence", "conditional": "gather_more"},
            {"source": "select_action", "target": "execute_action"},
            {"source": "execute_action", "target": "validate"},
        ]
        
        # Build nested reasoning for each agent
        all_nodes = agents.copy()
        all_edges = agent_edges.copy()
        
        for agent in agents:
            if agent["id"] != "orchestrator":  # Orchestrator coordinates, doesn't have its own reasoning
                # Add reasoning nodes for this agent
                for node in reasoning_template:
                    nested_node = {
                        **node,
                        "id": f"{agent['id']}_{node['id']}",
                        "parent": agent["id"],
                        "level": "nested"
                    }
                    all_nodes.append(nested_node)
                
                # Add reasoning edges for this agent
                for edge in reasoning_edges_template:
                    nested_edge = {
                        "id": f"{agent['id']}_{edge['source']}_{edge['target']}",
                        "source": f"{agent['id']}_{edge['source']}",
                        "target": f"{agent['id']}_{edge['target']}",
                        "parent": agent["id"],
                        "conditional": edge.get("conditional")
                    }
                    all_edges.append(nested_edge)
        
        logger.info(f"Returning hierarchical structure: {len(all_nodes)} nodes, {len(all_edges)} edges")
        
        return {
            "nodes": all_nodes,
            "edges": all_edges,
            "hierarchy": {
                "agents": [a["id"] for a in agents],
                "reasoning_steps": [n["id"] for n in reasoning_template]
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get graph structure: {e}", exc_info=True)
        return {
            "nodes": [],
            "edges": [],
            "error": str(e)
        }

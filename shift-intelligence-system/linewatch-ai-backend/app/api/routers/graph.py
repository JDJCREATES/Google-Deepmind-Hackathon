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
    Get the complete multi-agent system structure.
    
    Architecture:
    - Top: Master Orchestrator
    - Below: 4 Domain Agents, each with their OWN hypothesis market instance
    
    Each agent maintains separate state - they use the same PROCESS but different DATA.
    """
    try:
        # TOP: Master Orchestrator
        orchestrator = {
            "id": "orchestrator",
            "label": "🎯 MASTER ORCHESTRATOR",
            "type": "orchestrator",
        }
        
        # Domain Agents
        agents = [
            {"id": "production_agent", "label": "🏭 Production Agent"},
            {"id": "compliance_agent", "label": "📋 Compliance Agent"},
            {"id": "staffing_agent", "label": "👷 Staffing Agent"},
            {"id": "maintenance_agent", "label": "🔧 Maintenance Agent"},
        ]
        
        # Hypothesis market steps (each agent has its own instance)
        hypothesis_steps = [
            {"step": "load_knowledge", "label": "📚 Load Knowledge", "type": "reasoning"},
            {"step": "classify_frameworks", "label": "🏷️ Classify", "type": "reasoning"},
            {"step": "generate_hypotheses", "label": "💡 Hypotheses", "type": "hypothesis"},
            {"step": "gather_evidence", "label": "🔍 Evidence", "type": "evidence"},
            {"step": "update_beliefs", "label": "🧮 Beliefs", "type": "belief"},
            {"step": "select_action", "label": "⚖️ Action", "type": "action"},
            {"step": "execute_action", "label": "⚡ Execute", "type": "execution"},
            {"step": "validate", "label": "✓ Validate", "type": "reasoning"},
        ]
        
        # Build nodes
        all_nodes = [orchestrator]
        all_edges = []
        
        for agent in agents:
            # Add agent node
            all_nodes.append({
                "id": agent["id"],
                "label": agent["label"],
                "type": "agent",
            })
            
            # Orchestrator → Agent edge
            all_edges.append({
                "id": f"orch_{agent['id']}",
                "source": "orchestrator",
                "target": agent["id"],
                "type": "static",
            })
            
            # Add hypothesis steps for THIS agent
            for step in hypothesis_steps:
                step_id = f"{agent['id']}_{step['step']}"
                all_nodes.append({
                    "id": step_id,
                    "label": step["label"],
                    "type": step["type"],
                    "parent": agent["id"],
                })
            
            # Add edges for THIS agent's hypothesis flow
            for i in range(len(hypothesis_steps) - 1):
                source_step = f"{agent['id']}_{hypothesis_steps[i]['step']}"
                target_step = f"{agent['id']}_{hypothesis_steps[i+1]['step']}"
                all_edges.append({
                    "id": f"{source_step}_{target_step}",
                    "source": source_step,
                    "target": target_step,
                    "type": "pipeline",
                    "parent": agent["id"],
                })
            
            # Add feedback loop: update_beliefs → gather_evidence
            all_edges.append({
                "id": f"{agent['id']}_belief_loop",
                "source": f"{agent['id']}_update_beliefs",
                "target": f"{agent['id']}_gather_evidence",
                "type": "loop",
                "parent": agent["id"],
            })
        
        logger.info(f"Returning system structure: {len(all_nodes)} nodes, {len(all_edges)} edges")
        
        return {
            "nodes": all_nodes,
            "edges": all_edges,
            "agents": [a["id"] for a in agents],
        }
        
    except Exception as e:
        logger.error(f"Failed to get graph structure: {e}", exc_info=True)
        return {
            "nodes": [],
            "edges": [],
            "error": str(e)
        }

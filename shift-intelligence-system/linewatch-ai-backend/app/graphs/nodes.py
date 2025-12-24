"""
LangGraph nodes for hypothesis market.

Each node represents a step in the hypothesis-driven reasoning process:
1. Load knowledge
2. Classify frameworks
3. Generate hypotheses
4. Gather evidence
5. Update beliefs
6. Score decisions
7. Select/execute action
8. Counterfactual replay
9. Check drift
10. Evolve policy (if needed)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings
from app.hypothesis import (
    BeliefState,
    Evidence,
    Hypothesis,
    HypothesisFramework,
    create_hypothesis,
)
from app.knowledge import get_knowledge_base
from app.reasoning import (
    CounterfactualReplay,
    DecisionPolicy,
    FrameworkDriftDetector,
    StrategicMemory,
)
from app.utils.logging import get_agent_logger
from app.utils.llm import with_retry
from app.graphs.state import HypothesisMarketState


logger = get_agent_logger("HypothesisNodes")

# Shared instances
drift_detector = FrameworkDriftDetector()
strategic_memory = StrategicMemory()


# ==========================================
# Structured Output Models (Pydantic)
# ==========================================

class FrameworkClassification(BaseModel):
    """Result of framework classification."""
    frameworks: List[str] = Field(
        description="List of applicable epistemic frameworks (e.g. ['RCA', 'TOC'])",
        min_items=1
    )
    reasoning: str = Field(description="Brief explanation of why these frameworks apply")

class BeliefUpdateResult(BaseModel):
    """Result of Bayesian belief update."""
    posteriors: Dict[str, float] = Field(
        description="Map of hypothesis IDs to posterior probabilities"
    )
    leading_hypothesis_id: Optional[str] = Field(
        description="ID of the hypothesis with highest posterior",
        default=None
    )
    leader_confidence: float = Field(
        description="Posterior probability of the leading hypothesis",
        ge=0.0,
        le=1.0
    )
    converged: bool = Field(
        description="Whether confidence is high enough to act (>0.7)",
        default=False
    )
    reasoning: str = Field(description="Explanation of the belief update calculation")


async def load_knowledge_node(state: HypothesisMarketState) -> Dict[str, Any]:
    """
    Load relevant company knowledge for the signal.
    
    Retrieves policies, procedures, and SOPs relevant to the
    current signal type to ground Gemini's reasoning.
    """
    logger.info(f"📚 Loading knowledge for signal: {state['signal_type']}")
    
    kb = get_knowledge_base()
    context = kb.get_context_for_signal(
        state["signal_type"],
        keywords=list(state.get("signal_data", {}).keys())
    )
    
    return {"knowledge_context": context}


async def classify_frameworks_node(state: HypothesisMarketState) -> Dict[str, Any]:
    """
    Classify which epistemic frameworks apply to this signal.
    
    Uses Gemini to determine which of the 5 frameworks
    (RCA, COUNTERFACTUAL, FMEA, TOC, HACCP) are relevant.
    """
    logger.info(f"🏷️ Classifying frameworks for: {state['signal_description']}")
    
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=0.3,
    )
    
    # Use structured output for guaranteed schema compliance
    structured_llm = llm.with_structured_output(FrameworkClassification)
    
    prompt = f"""
Classify which epistemic frameworks apply to this manufacturing signal.

SIGNAL: {state['signal_description']}
DATA: {state['signal_data']}

AVAILABLE FRAMEWORKS:
1. RCA (Root Cause Analysis) - For "Why is this happening?" questions
2. COUNTERFACTUAL - For "What if we act/don't act?" analysis
3. FMEA (Failure Mode Effects Analysis) - For "What could go wrong?" risks
4. TOC (Theory of Constraints) - For "What's the bottleneck?" optimization
5. HACCP - For "Are we violating compliance?" food safety

Select at least 2 relevant frameworks.
"""

    try:
        result = await structured_llm.ainvoke(prompt)
        frameworks = result.frameworks
        reasoning = result.reasoning
        logger.info(f"✅ Classified frameworks: {frameworks} ({reasoning})")
    except Exception as e:
        logger.error(f"Failed to classify frameworks: {e}")
        frameworks = ["RCA", "TOC"]  # Fallback
    
    logger.info(f"✅ Applicable frameworks: {frameworks}")
    
    # Store in signal_data for downstream use
    updated_data = dict(state.get("signal_data", {}))
    updated_data["applicable_frameworks"] = frameworks
    
    return {"signal_data": updated_data}


async def generate_hypotheses_node(state: HypothesisMarketState) -> Dict[str, Any]:
    """
    Generate competing hypotheses by querying specialized agents.
    
    Instead of a single LLM call, this node acts as a market maker,
    soliciting hypotheses from Production, Staffing, Compliance, 
    and Maintenance agents based on their domain expertise.
    """
    logger.info("💡 Generating hypotheses via distributed agent market")
    
    # Broadcast start of hypothesis generation
    from app.services.websocket import manager
    await manager.broadcast({
        "type": "reasoning_phase",
        "data": {
            "phase": "hypothesis_generation",
            "signal": state["signal_description"],
            "timestamp": datetime.now().isoformat()
        }
    })
    
    # Import agents here to avoid circular imports at module level
    from app.agents.production.production_agent import ProductionAgent
    from app.agents.staffing.staffing_agent import StaffingAgent
    from app.agents.compliance.compliance_agent import ComplianceAgent
    from app.agents.maintenance.maintenance_agent import MaintenanceAgent
    from app.agents.orchestrator.orchestrator import MasterOrchestrator
    
    # Context for agents
    signal = {
        "description": state["signal_description"],
        "data": state.get("signal_data", {}),
        "knowledge": state.get("knowledge_context", "")
    }
    
    hypotheses = []
    
    # 1. Instantiate agents (lightweight initialization)
    # in a real app these typically would be singletons or dependency injected
    agents = [
        ProductionAgent(),
        StaffingAgent(),
        ComplianceAgent(),
        MaintenanceAgent()
    ]
    
    # 2. Solicit hypotheses from all agents in parallel
    import asyncio
    
    tasks = [agent.generate_hypotheses(signal) for agent in agents]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for result in results:
        if isinstance(result, list):
            hypotheses.extend(result)
        elif isinstance(result, Exception):
            logger.error(f"Agent failed to generate hypotheses: {result}")

    # 3. Master Orchestrator creates a synthesis/counterfactual hypothesis
    # if specific frameworks are requested (e.g. Counterfactual)
    if "COUNTERFACTUAL" in state.get("signal_data", {}).get("applicable_frameworks", []):
        orch = MasterOrchestrator()
        orch_hypos = await orch.generate_hypotheses(signal)
        hypotheses.extend(orch_hypos)
    
    # Checks for empty results
    if not hypotheses:
        # Fallback to generic generation if agents return nothing
        logger.warning("No hypotheses from agents - falling back to generic generation")
        from app.hypothesis import create_hypothesis
        hypotheses.append(create_hypothesis(
            framework="RCA",
            description=f"Generic investigation needed for {signal['description']}",
            initial_confidence=0.3,
            proposed_by="SystemFallback"
        ))
        
    logger.info(f"✅ Aggregated {len(hypotheses)} hypotheses from agents")
    
    # Broadcast generated hypotheses for frontend visualization
    await manager.broadcast({
        "type": "hypotheses_generated",
        "data": {
            "count": len(hypotheses),
            "hypotheses": [
                {
                    "id": h.hypothesis_id,
                    "description": h.description,
                    "confidence": h.initial_confidence,
                    "proposed_by": h.proposed_by,
                    "cost_if_wrong": h.reversibility
                }
                for h in hypotheses
            ],
            "timestamp": datetime.now().isoformat()
        }
    })
    
    return {"hypotheses": hypotheses}


async def gather_evidence_node(state: HypothesisMarketState) -> Dict[str, Any]:
    """
    Gather evidence for each hypothesis using dynamic agent tool proposals.
    
    Instead of hardcoded checks, this asks the relevant agent: 
    "How would you verify this?" and then simulates the tool execution.
    """
    logger.info("🔍 Gathering evidence via dynamic agent tooling")
    
    # Import agents (lazy import to avoid circular dep)
    from app.agents.production.production_agent import ProductionAgent
    from app.agents.staffing.staffing_agent import StaffingAgent
    from app.agents.compliance.compliance_agent import ComplianceAgent
    from app.agents.maintenance.maintenance_agent import MaintenanceAgent
    from app.agents.orchestrator.orchestrator import MasterOrchestrator
    
    # Agent map
    agent_map = {
        "ProductionAgent": ProductionAgent(),
        "ComplianceAgent": ComplianceAgent(),
        "MaintenanceAgent": MaintenanceAgent(),
        "StaffingAgent": StaffingAgent(),
        "MasterOrchestrator": MasterOrchestrator(),
    }
    
    hypotheses = state.get("hypotheses", [])
    evidence_list = []
    
    # Simulate tool execution (Mock Engine)
    def simulate_tool_output(tool_name: str, params: Dict, hypothesis_desc: str) -> Dict[str, Any]:
        """Simulate realistic tool output based on the tool and hypothesis context."""
        import random
        
        # Is this likely true? Bias towards the first hypothesis being true for simulation
        is_supported = "smoke" in hypothesis_desc.lower() or "fire" in hypothesis_desc.lower() or random.random() > 0.6
        strength = 0.8 + (random.random() * 0.15) if is_supported else 0.2
        
        if "check_sensors" in tool_name:
            return {
                "reading": 85.4 if is_supported else 24.1, 
                "threshold": 50.0, 
                "status": "CRITICAL" if is_supported else "NORMAL",
                "supports": is_supported
            }
        elif "camera" in tool_name:
            return {
                "visual_anomaly_detected": is_supported,
                "confidence": 0.92,
                "description": "Visible smoke plume" if is_supported else "Clear view",
                "supports": is_supported
            }
        elif "logs" in tool_name:
            return {
                "events_found": 12 if is_supported else 0,
                "pattern_match": is_supported,
                "supports": is_supported
            }
            
        return {"result": f"Simulated check for {tool_name}", "supports": is_supported}

    
    # For each hypothesis, ask the proposing agent how to verify it
    for hypothesis in hypotheses:
        # Determine responsible agent
        agent_name = hypothesis.proposed_by or "ProductionAgent"
        agent = agent_map.get(agent_name, agent_map["ProductionAgent"])
        
        # 1. Ask agent to propose verification
        logger.info(f"🤔 Asking {agent_name} to verify: {hypothesis.hypothesis_id}")
        verification_plan = await agent.propose_verification(hypothesis)
        
        tool_name = verification_plan.get("tool", "manual_check")
        rationale = verification_plan.get("reasoning", "Standard verification")
        params = verification_plan.get("params", {})
        
        # 2. "Execute" the tool (Simulated)
        sim_result = simulate_tool_output(tool_name, params, hypothesis.description)
        
        # 3. Create Evidence object
        evidence = Evidence(
            source=f"{tool_name}",
            data={
                "tool": tool_name,
                "params": params,
                "raw_output": sim_result
            },
            supports=sim_result["supports"],
            strength=0.85 if sim_result["supports"] else 0.4,
            gathered_by=agent_name,
            description=f"Tool '{tool_name}' returned: {sim_result.get('status', 'Done')}"
        )
        evidence_list.append(evidence)
        
        # Broadcast tool usage for frontend
        from app.services.websocket import manager
        await manager.broadcast({
            "type": "tool_execution",
            "data": {
                "agent": agent_name,
                "tool": tool_name,
                "rationale": rationale,
                "result": sim_result,
                "timestamp": datetime.now().isoformat()
            }
        })
    
    logger.info(f"✅ Gathered {len(evidence_list)} pieces of dynamic evidence")
    
    return {"evidence": evidence_list}


async def update_beliefs_node(state: HypothesisMarketState) -> Dict[str, Any]:
    """
    Update beliefs using Bayesian reasoning via Gemini.
    
    Analyzes evidence impact on each hypothesis and computes
    posterior probabilities.
    """
    logger.info("🧮 Updating beliefs")
    
    hypotheses = state.get("hypotheses", [])
    evidence = state.get("evidence", [])
    
    if not hypotheses:
        return {"converged": False}
    
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=0.2,  # Low for precise reasoning
    )
    
    # Use structured output for guaranteed schema compliance
    structured_llm = llm.with_structured_output(BeliefUpdateResult)
    
    prompt = f"""
Perform Bayesian belief update for these hypotheses given the evidence.

HYPOTHESES:
{[{"id": h.hypothesis_id, "desc": h.description, "prior": h.initial_confidence} for h in hypotheses]}

EVIDENCE:
{[{"source": e.source, "data": e.data, "supports": e.supports, "strength": e.strength} for e in evidence]}

For each hypothesis:
1. Analyze how evidence affects probability
2. Calculate posterior probability
3. Ensure posteriors sum to approximately 1.0

Output the detailed calculations and final posteriors according to the schema.
"""

    try:
        result = await structured_llm.ainvoke(prompt)
        posteriors = result.posteriors
        leading = result.leading_hypothesis_id
        confidence = result.leader_confidence
        converged = result.converged
        
        logger.info(f"✅ Beliefs updated. Leader confidence: {confidence:.2f} ({result.reasoning[:50]}...)")
        
    except Exception as e:
        logger.error(f"Failed to update beliefs: {e}")
        return {"converged": False}

    
    # Update hypothesis confidences
    for h in hypotheses:
        if h.hypothesis_id in posteriors:
            h.current_confidence = posteriors[h.hypothesis_id]
            h.last_updated = datetime.now()
    
    # Create belief state
    belief_state = BeliefState(
        signal_id=state["signal_id"],
        signal_description=state["signal_description"],
        hypotheses=hypotheses,
        posterior_probabilities=posteriors,
        leading_hypothesis_id=leading,
        confidence_in_leader=confidence,
        converged=converged,
    )
    
    logger.info(f"✅ Beliefs updated. Leader confidence: {confidence:.2f}")
    
    return {
        "belief_state": belief_state,
        "converged": converged,
        "iteration": state.get("iteration", 0) + 1,
    }


async def select_action_node(state: HypothesisMarketState) -> Dict[str, Any]:
    """
    Select action based on belief state and decision policy.
    
    Uses the active reasoning artifact to score hypotheses
    and select the optimal action.
    """
    logger.info("🎯 Selecting action")
    
    belief_state = state.get("belief_state")
    if not belief_state:
        return {"selected_action": None}
    
    leading = belief_state.get_leading_hypothesis()
    if not leading:
        return {"selected_action": None}
    
    # Invoke Master Orchestrator as Final Judge
    from app.agents.orchestrator.orchestrator import MasterOrchestrator
    orchestrator = MasterOrchestrator()
    
    logger.info("⚖️ Invoking Master Orchestrator for final judgment")
    verdict = await orchestrator.make_final_decision(belief_state)
    
    action = verdict.get("selected_action")
    reasoning = verdict.get("reasoning")
    
    logger.info(f"👨‍⚖️ Orchestrator Verdict: {action} ({reasoning[:50]}...)")
    
    # Check if we need human escalation based on Orchestrator's verdict
    if action == "ESCALATE_TO_HUMAN":
        return {
            "needs_human": True,
            "selected_action": "ESCALATE_TO_HUMAN",
        }
    
    return {
        "selected_action": action,
        "needs_human": False,
    }


async def execute_action_node(state: HypothesisMarketState) -> Dict[str, Any]:
    """
    Execute the selected action via appropriate agent.
    
    Routes action to the target agent specified in the
    leading hypothesis.
    """
    logger.info(f"⚡ Executing action: {state.get('selected_action')}")
    
    action = state.get("selected_action")
    if not action or action == "ESCALATE_TO_HUMAN":
        return {"action_result": None}
    
    # Simulate action execution
    # In production, would route to actual agent tools
    result = {
        "success": True,
        "action": action,
        "executed_at": datetime.now().isoformat(),
        "outcome": "Action completed successfully",
    }
    
    logger.info("✅ Action executed")
    
    return {"action_result": result}


async def counterfactual_replay_node(state: HypothesisMarketState) -> Dict[str, Any]:
    """
    Perform counterfactual analysis after action execution.
    
    Asks: "What if we had chosen the second-best hypothesis?"
    """
    logger.info("🔄 Running counterfactual replay")
    
    belief_state = state.get("belief_state")
    if not belief_state:
        return {}
    
    chosen = belief_state.get_leading_hypothesis()
    alternative = belief_state.get_second_best()
    
    if not chosen or not alternative:
        return {}
    
    # Use Gemini to predict alternative outcome
    llm = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
    )
    
    prompt = f"""
Counterfactual analysis for manufacturing decision.

WHAT WE DID:
- Hypothesis: {chosen.description}
- Action: {state.get('selected_action')}
- Outcome: {state.get('action_result')}

ALTERNATIVE WE DIDN'T CHOOSE:
- Hypothesis: {alternative.description}
- Would have taken: {alternative.recommended_action}

Analyze:
1. What would have happened if we chose the alternative?
2. Production delta (units saved/lost)?
3. Time delta (minutes faster/slower)?
4. Risk delta (higher/lower)?
5. Strategic insight for future decisions?

Output JSON with these fields.
"""

    result = await llm.ainvoke(prompt)
    
    # Create counterfactual replay
    replay = CounterfactualReplay(
        incident_id=state["signal_id"],
        chosen_hypothesis_id=chosen.hypothesis_id,
        chosen_hypothesis_description=chosen.description,
        action_taken=state.get("selected_action", ""),
        actual_outcome=state.get("action_result", {}),
        alternative_hypothesis_id=alternative.hypothesis_id,
        alternative_hypothesis_description=alternative.description,
        alternative_action=alternative.recommended_action or "",
        insight="Counterfactual analysis completed",
    )
    
    # Store in strategic memory
    strategic_memory.add_replay(replay)
    
    logger.info("✅ Counterfactual replay completed")
    
    return {"counterfactual": replay}


async def check_drift_node(state: HypothesisMarketState) -> Dict[str, Any]:
    """
    Check for framework drift and trigger rebalancing if needed.
    """
    logger.info("📊 Checking framework drift")
    
    drift = drift_detector.detect_drift()
    
    if drift:
        logger.warning(f"⚠️ Drift detected: {drift.drift_type} on {drift.framework}")
    
    return {"drift_alert": drift}


async def evolve_policy_node(state: HypothesisMarketState) -> Dict[str, Any]:
    """
    Check if policy should evolve based on accumulated learning.
    
    Triggers policy update when counterfactual analysis suggests
    systematic improvements are possible.
    """
    logger.info("📈 Checking policy evolution")
    
    candidates = strategic_memory.get_policy_update_candidates()
    
    if len(candidates) >= 5:
        logger.info("🔄 Policy evolution triggered")
        return {"policy_update_recommended": True}
    
    return {"policy_update_recommended": False}

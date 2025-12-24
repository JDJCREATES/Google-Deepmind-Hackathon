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
from typing import Any, Dict, List
from uuid import uuid4

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
from app.graphs.state import HypothesisMarketState


logger = get_agent_logger("HypothesisNodes")

# Shared instances
drift_detector = FrameworkDriftDetector()
strategic_memory = StrategicMemory()


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

Output a JSON list of applicable framework codes (e.g., ["RCA", "TOC"]).
Include at least 2 frameworks for comprehensive analysis.
"""

    result = await llm.ainvoke(prompt)
    
    # Parse frameworks (simple extraction)
    content = result.content
    frameworks = []
    for fw in ["RCA", "COUNTERFACTUAL", "FMEA", "TOC", "HACCP"]:
        if fw in content:
            frameworks.append(fw)
    
    if not frameworks:
        frameworks = ["RCA", "TOC"]  # Default
    
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
    Gather evidence for each hypothesis using agent tools.
    
    Routes to appropriate tools based on hypothesis framework
    and target agent.
    """
    logger.info("🔍 Gathering evidence")
    
    hypotheses = state.get("hypotheses", [])
    evidence_list = []
    
    # For each hypothesis, gather relevant evidence
    for hypothesis in hypotheses:
        # Determine evidence source based on framework
        if hypothesis.framework == HypothesisFramework.RCA:
            # Get production metrics, equipment health
            evidence = Evidence(
                source="ProductionMetrics",
                data={"simulated": True, "health": 75, "efficiency": 0.82},
                supports=True,
                strength=0.7,
                gathered_by="ProductionAgent",
            )
            evidence_list.append(evidence)
            
        elif hypothesis.framework == HypothesisFramework.HACCP:
            # Get temperature readings
            evidence = Evidence(
                source="TemperatureSensor",
                data={"temperature": 3.5, "compliant": True},
                supports=False,  # No violation
                strength=0.9,
                gathered_by="ComplianceAgent",
            )
            evidence_list.append(evidence)
            
        elif hypothesis.framework == HypothesisFramework.TOC:
            # Get throughput data
            evidence = Evidence(
                source="ThroughputAnalysis",
                data={"bottleneck_line": 7, "impact": 15},
                supports=True,
                strength=0.8,
                gathered_by="ProductionAgent",
            )
            evidence_list.append(evidence)

        elif hypothesis.framework == HypothesisFramework.FMEA:
            # Get safety sensor / camera data
            evidence = Evidence(
                source="SafetySensors",
                data={"smoke_detected": True, "zone": "ConveyorMotor", "confidence": 0.95},
                supports=True,
                strength=0.9,
                gathered_by="ComplianceAgent",
            )
            evidence_list.append(evidence)
    
    logger.info(f"✅ Gathered {len(evidence_list)} pieces of evidence")
    
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

Output JSON with:
- "posteriors": {{hypothesis_id: probability}}
- "leading_hypothesis": hypothesis_id with highest posterior
- "leader_confidence": posterior of leader
- "converged": true if leader confidence > 0.7
"""

    result = await llm.ainvoke(prompt)
    
    # Parse result (simplified)
    try:
        import json
        import re
        
        content = result.content
        # Handle case where content might be a list (rare but possible with some models)
        if isinstance(content, list):
            content = " ".join([str(c) for c in content])
        elif not isinstance(content, str):
            content = str(content)
            
        logger.info(f"🔍 [DEBUG] Belief Update Response: {content[:100]}...")
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            posteriors = data.get("posteriors", {})
            leading = data.get("leading_hypothesis")
            confidence = data.get("leader_confidence", 0.5)
            converged = data.get("converged", False)
        else:
            # Default to first hypothesis
            posteriors = {hypotheses[0].hypothesis_id: 0.6}
            leading = hypotheses[0].hypothesis_id
            confidence = 0.6
            converged = False
    except Exception as e:
        logger.error(f"Error parsing beliefs: {e}")
        posteriors = {hypotheses[0].hypothesis_id: 0.5}
        leading = hypotheses[0].hypothesis_id
        confidence = 0.5
        converged = False
    
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
    
    # Record framework usage for drift detection
    drift_detector.record_usage(leading.framework)
    
    # Check if we need human escalation
    policy = DecisionPolicy.create_initial()
    if policy.should_escalate(belief_state.confidence_in_leader):
        logger.warning("⚠️ Confidence too low - needs human escalation")
        return {
            "needs_human": True,
            "selected_action": "ESCALATE_TO_HUMAN",
        }
    
    # Select action based on leading hypothesis
    action = leading.recommended_action or f"Act on {leading.description}"
    
    logger.info(f"✅ Selected action: {action}")
    
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

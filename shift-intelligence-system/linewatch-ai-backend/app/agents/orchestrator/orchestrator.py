"""
Master Orchestrator - Central coordinator for all specialized agents.

This agent uses Gemini 3's deepest reasoning (Level 3) to make complex decisions,
resolve conflicts between agents, and escalate to humans when needed.
"""
from typing import Dict, Any, List
from datetime import datetime

from app.agents.base import BaseAgent
from app.prompts.orchestrator.system import ORCHESTRATOR_SYSTEM_PROMPT
from app.tools.orchestrator import (
    escalate_to_human,
    update_shift_plan,
    get_all_agent_status,
    alert_supervisor_to_check,
    read_kpis,
    request_agent_perspective,
    escalate_tradeoff_decision,
)
from app.tools.analysis import (
    query_facility_subsystem,
    get_facility_layout,
    query_system_logs,
)
from app.tools.actions import (
    query_available_resources,
    submit_resource_request,
    dispatch_personnel,
)
from app.utils.logging import get_agent_logger


logger = get_agent_logger("MasterOrchestrator")


class MasterOrchestrator(BaseAgent):
    """
    Master Orchestrator - Central coordination agent.
    
    Key Features:
    - Coordinates all 4 specialized agents
    - Resolves conflicts between competing priorities
    - Makes final decisions on complex issues
    - Escalates to humans when confidence < 70%
    - Maintains shift-level planning
    
    Thinking Level: 3 (Deepest reasoning for complex coordination)
    Model: gemini-3.0-pro-exp (Uses Pro model for best reasoning)
    """
    
    def __init__(self):
        tools = [
            # Orchestration tools
            escalate_to_human,
            update_shift_plan,
            get_all_agent_status,
            alert_supervisor_to_check,
            read_kpis,
            # Collaboration tools
            request_agent_perspective,
            escalate_tradeoff_decision,
            # Discovery tools - general purpose
            query_facility_subsystem,
            get_facility_layout,
            query_system_logs,
            # Action tools - general purpose
            query_available_resources,
            submit_resource_request,
            dispatch_personnel,
        ]
        
        super().__init__(
            agent_name="MasterOrchestrator",
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            tools=tools,
            use_flash_model=False,  # Use Pro model for deep reasoning
            thinking_level="high",  # Deepest level for complex decisions
        )
        
        logger.info("✅ Master Orchestrator initialized (Gemini 3 Pro)")
    
    async def run_investigation(self, signal_desc: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a full hypothesis-driven investigation for a complex signal.
        """
        from app.graphs.hypothesis_market import create_hypothesis_market_graph
        
        self.logger.info(f"🕵️‍♂️ Starting investigation: {signal_desc}")
        
        graph = create_hypothesis_market_graph()
        
        # Initialize state
        initial_state = {
            "signal_id": f"SIG-{datetime.now().timestamp()}",
            "signal_type": "PRODUCTION_ALERT",
            "signal_description": signal_desc,
            "signal_data": context,
            "hypotheses": [],
            "evidence": [],
            "iteration": 0,
            "max_iterations": 3,
        }
        
        # Run graph
        final_state = await graph.ainvoke(initial_state)
        
        return {
            "status": "COMPLETED",
            "action": final_state.get("selected_action"),
            "belief_state": final_state.get("belief_state"),
        }

    # ========== HYPOTHESIS GENERATION ==========
    
    async def generate_hypotheses(self, signal: Dict[str, Any]) -> List[Any]:
        """
        Generate Counterfactual hypotheses for strategic analysis.
        """
        from app.hypothesis import create_hypothesis, HypothesisFramework
        from uuid import uuid4
        
        hypotheses = []
        signal_desc = signal.get('description', '')
        
        # Counterfactual: Strategy shift
        hypotheses.append(create_hypothesis(
            framework=HypothesisFramework.COUNTERFACTUAL,
            hypothesis_id=f"H-STRAT-{uuid4().hex[:6]}",
            description="What if we prioritized quality over throughput?",
            initial_confidence=0.4, # Speculative
            impact=9.0,
            urgency=3.0,
            proposed_by=self.agent_name,
            recommended_action="Initiate Quality-First Protocol",
            target_agent="MasterOrchestrator"
        ))
            
        return hypotheses

    async def make_final_decision(self, belief_state: Any) -> Dict[str, Any]:
        """
        Act as the final Judge and Jury on the belief state.
        
        Reviews all evidence and the leading hypothesis to make a binding decision.
        Can override the mathematical leader if reasoning dictates.
        """
        self.logger.info("⚖️ Master Orchestrator deliberating on final decision...")
        
        leading = belief_state.get_leading_hypothesis()
        confidence = belief_state.confidence_in_leader
        
        # Get evidence from belief_state
        evidence_list = getattr(belief_state, 'evidence', [])
        evidence_summary = "\n".join([
            f"- {e.source}: {'Supports' if e.supports else 'Refutes'}" 
            for e in evidence_list
        ]) if evidence_list else "No evidence gathered yet"
        
        # Get strategic insights from persistent memory
        from app.reasoning.counterfactual import strategic_memory
        insights = strategic_memory.get_insights_for_prompt_sync()
        
        prompt = f"""
        You are the Master Orchestrator and Final Judge.
        {insights}
        SITUATION: {belief_state.signal_description}
        
        LEADING HYPOTHESIS (Math confidence: {confidence:.2f}):
        {leading.description if leading else "None"}
        
        EVIDENCE REVIEW:
        {evidence_summary}
        
        DECISION TASK:
        1. Review the evidence critically.
        2. Consider the strategic insights from past decisions.
        3. Decide if the leading hypothesis is truly proven.
        4. Select the best course of action.
        5. If confidence is too low (<0.7), mandate "GATHER MORE EVIDENCE" or "ESCALATE TO HUMAN".
        
        OUTPUT FORMAT:
        Write a decisive, authoritative verdict.
        - Avoid robotic phrases like "Based on the evidence..."
        - Use first-person active voice: "I have determined...", "The data confirms...", "We must immediately..."
        - Explain *why* you are making this decision.
        """
        
        # Use simple invoke for now, returning dict
        try:
            # Use unique thread ID to avoid history corruption from previous interrupted runs
            thread_id = f"orchestrator-decision-{datetime.now().timestamp()}"
            await self._ensure_agent_initialized()
            result = await self.agent.ainvoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config={"configurable": {"thread_id": thread_id}}
            )
            # Parse finding
            content = result["messages"][-1].content
            
            # Ensure content is a string
            if isinstance(content, list):
                content = str(content)
            
            # Simple heuristic parsing for action
            action = "ESCALATE_TO_HUMAN"
            if "GATHER MORE" in content.upper():
                action = "GATHER_MORE_EVIDENCE"
            elif leading and leading.recommended_action:
                action = leading.recommended_action
            
            return {
                "selected_action": action,
                "reasoning": content[:200] + "...",
                "override": False
            }
        except Exception as e:
            self.logger.error(f"Decision failed: {e}")
            return {"selected_action": "ESCALATE_TO_HUMAN", "reasoning": "Decision failure"}

    async def _execute_action(self, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute orchestrator actions."""
        action_lower = action.lower()
        
        if "investigate" in action_lower:
            return await self.run_investigation(action, context)
        
        elif "escalate" in action_lower:
            result = await escalate_to_human(
                alert_title=context.get("issue", "Complex situation detected"),
                description=action,
                severity=context.get("severity", "HIGH")
            )
            return {"status": "ESCALATED", "escalation": result, "side_effects": ["Human supervisor notified"]}
        
        elif "adjust" in action_lower or "plan" in action_lower:
            adjustment = context.get("adjustment_percent", 0)
            result = await update_shift_plan(adjustment, action)
            return {"status": "SUCCESS", "plan_update": result, "side_effects": ["Shift targets updated"]}
        
        return {"status": "UNKNOWN_ACTION", "side_effects": []}
    
    def _detect_critical_situation(self, context: Dict[str, Any]) -> bool:
        """Orchestrator rarely escalates - it IS the escalation point."""
        # Only escalate on catastrophic scenarios
        return context.get("catastrophic_failure", False)
    
    async def _create_subagent(self, subagent_type: str) -> BaseAgent:
        """Orchestrator doesn't spawn subagents - it coordinates main agents."""
        raise NotImplementedError("Orchestrator coordinates main agents, not subagents")

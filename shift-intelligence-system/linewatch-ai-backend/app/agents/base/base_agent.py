"""
Base agent framework leveraging Gemini 3's advanced reasoning capabilities.

This module provides the foundation for all specialized agents with:
- Explicit reasoning + action separation
- Gemini 3 thinking levels and thought signatures
- Nested subagent spawning
- Self-verification loops
- Escalation mechanisms
- Hypothesis generation for epistemic framework
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
import asyncio
from dataclasses import dataclass

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite import SqliteSaver

from app.config import settings
from app.utils.logging import get_agent_logger
from app.models.domain import Decision, Alert, AlertSeverity


@dataclass
class ReasoningResult:
    """Result from agent's reasoning phase."""
    thought_process: str  # Gemini 3's reasoning trace
    confidence: float  # 0.0 to 1.0
    proposed_actions: List[str]
    should_escalate: bool
    escalation_reason: Optional[str] = None
    requires_verification: bool = False


@dataclass
class ActionResult:
    """Result from agent's action execution."""
    actions_taken: List[str]
    success: bool
    verification_passed: bool
    side_effects: List[str]
    next_steps: List[str]


class BaseAgent(ABC):
    """
    Base class for all intelligent agents in the LineWatch AI system.
    
    Implements:
    - Gemini 3 integration with thinking levels
    - Reasoning + Action separation
    - Self-verification loops
    - Nested subagent spawning
    - Escalation to Master Orchestrator
    """
    
    def __init__(
        self,
        agent_name: str,
        system_prompt: str,
        tools: List[BaseTool],
        use_flash_model: bool = True,
        thinking_level: int = 1,
    ):
        """
        Initialize base agent.
        
        Args:
            agent_name: Unique identifier for agent
            system_prompt: Agent's system instructions
            tools: List of LangChain tools available to agent
            use_flash_model: Use gemini-3.0-flash (fast) vs gemini-3.0-pro (smart)
            thinking_level: Gemini 3 thinking depth (1-3)
                1 = Quick decisions
                2 = Standard reasoning
                3 = Deep analysis (for Orchestrator)
        """
        self.agent_name = agent_name
        self.system_prompt = system_prompt
        self.tools = tools
        self.thinking_level = thinking_level
        self.logger = get_agent_logger(agent_name)
        
        # Gemini 3 LLM with thinking configuration
        model_name = "gemini-3.0-flash-exp" if use_flash_model else "gemini-3.0-pro-exp"
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=settings.google_api_key,
            temperature=0.7,
            # Gemini 3 specific: Enable thinking mode
            extra_kwargs={
                "thinking_level": thinking_level,
                "include_thoughts": True,  # Get reasoning traces
            }
        )
        
        # LangGraph agent with checkpointing
        self.checkpointer = SqliteSaver.from_conn_string("linewatch_state.db")
        self.agent = create_react_agent(
            self.llm,
            tools=self.tools,
            state_modifier=self.system_prompt,
            checkpointer=self.checkpointer,
        )
        
        # Subagents for nested reasoning
        self.subagents: Dict[str, 'BaseAgent'] = {}
        
        # Decision history
        self.decisions: List[Decision] = []
        
        self.logger.info(f"✅ {agent_name} initialized with Gemini 3 ({model_name})")
    
    # ========== REASONING PHASE ==========
    
    async def reason(self, context: Dict[str, Any]) -> ReasoningResult:
        """
        Phase 1: Deep reasoning using Gemini 3's thinking capabilities.
        
        This is where the agent:
        - Analyzes the situation using tools
        - Uses Gemini 3's thinking mode for deep analysis
        - Proposes actions without executing them
        - Determines if escalation is needed
        
        Args:
            context: Current state and information for reasoning
            
        Returns:
            ReasoningResult with thought process and proposed actions
        """
        self.logger.info(f"🧠 [{self.agent_name}] Starting reasoning phase...")
        
        # Build reasoning prompt
        reasoning_prompt = self._build_reasoning_prompt(context)
        
        # Invoke Gemini 3 with thinking enabled
        result = await self.agent.ainvoke(
            {"messages": [HumanMessage(content=reasoning_prompt)]},
            config={
                "configurable": {
                    "thread_id": f"{self.agent_name}-reasoning",
                    "thinking_level": self.thinking_level,
                }
            }
        )
        
        # Extract Gemini 3's thoughts and reasoning
        thoughts = self._extract_thoughts(result)
        proposed_actions = self._extract_proposed_actions(result)
        confidence = self._calculate_confidence(result)
        
        # Determine if escalation needed
        should_escalate = confidence < 0.7 or self._detect_critical_situation(context)
        escalation_reason = None
        if should_escalate:
            escalation_reason = self._build_escalation_reason(context, thoughts)
        
        # Determine if verification needed
        requires_verification = self._needs_verification(proposed_actions)
        
        reasoning_result = ReasoningResult(
            thought_process=thoughts,
            confidence=confidence,
            proposed_actions=proposed_actions,
            should_escalate=should_escalate,
            escalation_reason=escalation_reason,
            requires_verification=requires_verification,
        )
        
        self.logger.info(
            f"💡 [{self.agent_name}] Reasoning complete. "
            f"Confidence: {confidence:.2f}, "
            f"Actions: {len(proposed_actions)}, "
            f"Escalate: {should_escalate}"
        )
        
        return reasoning_result
    
    # ========== ACTION PHASE ==========
    
    async def act(
        self,
        reasoning: ReasoningResult,
        context: Dict[str, Any]
    ) -> ActionResult:
        """
        Phase 2: Execute actions proposed by reasoning phase.
        
        This is where the agent:
        - Executes approved actions using tools
        - Monitors side effects
        - Verifies outcomes if needed
        
        Args:
            reasoning: Results from reasoning phase
            context: Current state
            
        Returns:
            ActionResult with execution details
        """
        self.logger.info(f"⚡ [{self.agent_name}] Starting action phase...")
        
        actions_taken = []
        side_effects = []
        
        # Execute each proposed action
        for action in reasoning.proposed_actions:
            try:
                result = await self._execute_action(action, context)
                actions_taken.append(f"{action}: {result['status']}")
                
                # Track side effects
                if 'side_effects' in result:
                    side_effects.extend(result['side_effects'])
                    
            except Exception as e:
                self.logger.error(f"❌ Action failed: {action} - {e}")
                actions_taken.append(f"{action}: FAILED - {str(e)}")
        
        # Verification if required
        verification_passed = True
        if reasoning.requires_verification:
            verification_passed = await self._verify_actions(
                actions_taken,
                context
            )
        
        # Determine next steps
        next_steps = await self._plan_next_steps(
            reasoning,
            actions_taken,
            verification_passed
        )
        
        action_result = ActionResult(
            actions_taken=actions_taken,
            success=len(actions_taken) > 0,
            verification_passed=verification_passed,
            side_effects=side_effects,
            next_steps=next_steps,
        )
        
        self.logger.info(
            f"✅ [{self.agent_name}] Actions completed. "
            f"Success: {action_result.success}, "
            f"Verified: {verification_passed}"
        )
        
        return action_result
    
    # ========== COMPLETE REASONING-ACTION LOOP ==========
    
    async def reason_and_act(self, context: Dict[str, Any]) -> Decision:
        """
        Complete reasoning-action loop with self-verification.
        
        This is the main entry point that:
        1. Reasons about the situation
        2. Checks if escalation needed
        3. Executes actions if confident
        4. Verifies outcomes
        5. Logs decision for audit trail
        
        Args:
            context: Current state and information
            
        Returns:
            Decision object with full reasoning trace
        """
        start_time = datetime.now()
        
        # Phase 1: Reasoning
        reasoning = await self.reason(context)
        
        # Check if escalation needed before acting
        if reasoning.should_escalate:
            self.logger.warning(
                f"⬆️ [{self.agent_name}] Escalating: {reasoning.escalation_reason}"
            )
            decision = self._create_escalation_decision(reasoning, start_time)
            await self._escalate_to_orchestrator(decision)
            return decision
        
        # Phase 2: Action
        action_result = await self.act(reasoning, context)
        
        # Phase 3: Self-verification failed? Try correction
        if reasoning.requires_verification and not action_result.verification_passed:
            self.logger.warning(
                f"⚠️ [{self.agent_name}] Verification failed, attempting correction..."
            )
            # Self-correcting loop: reason again with failure context
            correction_context = {
                **context,
                "previous_failure": action_result,
                "correction_attempt": True,
            }
            return await self.reason_and_act(correction_context)
        
        # Create decision record
        decision = Decision(
            decision_id=f"{self.agent_name}-{int(start_time.timestamp())}",
            timestamp=start_time,
            agent_name=self.agent_name,
            decision=f"Executed {len(action_result.actions_taken)} actions",
            reasoning=reasoning.thought_process,
            confidence=reasoning.confidence,
            actions_taken=action_result.actions_taken,
            escalated=False,
        )
        
        self.decisions.append(decision)
        
        # Log to shared context for other agents
        await self._log_decision(decision)
        
        return decision
    
    # ========== NESTED SUBAGENT SPAWNING ==========
    
    async def spawn_subagent(
        self,
        subagent_type: str,
        task_context: Dict[str, Any]
    ) -> Decision:
        """
        Spawn a specialized subagent for focused task.
        
        Example: Production Agent spawns Bottleneck Analyzer subagent
        
        Args:
            subagent_type: Type of subagent to spawn
            task_context: Specific context for subagent
            
        Returns:
            Decision from subagent
        """
        self.logger.info(
            f"🔀 [{self.agent_name}] Spawning subagent: {subagent_type}"
        )
        
        if subagent_type not in self.subagents:
            # Create subagent on-demand
            subagent = await self._create_subagent(subagent_type)
            self.subagents[subagent_type] = subagent
        
        # Subagent runs its own reasoning-action loop
        subagent_decision = await self.subagents[subagent_type].reason_and_act(
            task_context
        )
        
        self.logger.info(
            f"✅ [{self.agent_name}] Subagent {subagent_type} completed: "
            f"Confidence {subagent_decision.confidence:.2f}"
        )
        
        return subagent_decision
    
    # ========== ABSTRACT METHODS (Override in specialized agents) ==========
    
    @abstractmethod
    async def _execute_action(
        self,
        action: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a specific action (override in subclass)."""
        pass
    
    @abstractmethod
    def _detect_critical_situation(self, context: Dict[str, Any]) -> bool:
        """Detect if situation requires escalation (override in subclass)."""
        pass
    
    @abstractmethod
    async def _create_subagent(self, subagent_type: str) -> 'BaseAgent':
        """Create specialized subagent (override in subclass)."""
        pass

    async def generate_hypotheses(self, signal: Dict[str, Any]) -> List[Any]:
        """
        Generate domain-specific hypotheses for a given signal.
        
        Default implementation using Gemini to generate hypotheses
        based on agent's system prompt and expertise.
        """
        from app.hypothesis import create_hypothesis, Hypothesis
        
        prompt = f"""
        As the {self.agent_name}, generate hypotheses for this signal:
        Signal: {signal.get('description')}
        Data: {signal.get('data')}
        
        Generate 1-2 hypotheses specific to your domain expertise.
        """
        
        # This is a basic implementation - subclasses should override or
        # we can implement a generic one here using self.llm
        # For the hackathon, we'll keep it simple in the base and override in subclasses
        # where we want specific framework logic.
        return []
    
    # ========== HELPER METHODS ==========
    
    def _build_reasoning_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for reasoning phase."""
        return f"""Analyze the current situation and propose actions.

CONTEXT:
{self._format_context(context)}

INSTRUCTIONS:
1. Use your tools to gather necessary information
2. Analyze the situation deeply using your reasoning capabilities
3. Propose specific actions to take
4. Assess your confidence in these actions
5. Determine if escalation to Master Orchestrator is needed

Provide your reasoning and proposed actions clearly.
"""
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context for prompt."""
        lines = []
        for key, value in context.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)
    
    def _extract_thoughts(self, result: Dict) -> str:
        """Extract Gemini 3's thinking trace from result."""
        # Gemini 3 includes thoughts in response
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, 'thinking'):
                return msg.thinking
            if hasattr(msg, 'content') and "thinking:" in msg.content.lower():
                # Parse thinking from content
                return self._parse_thinking_from_content(msg.content)
        return "No explicit reasoning trace available"
    
    def _extract_proposed_actions(self, result: Dict) -> List[str]:
        """Extract proposed actions from agent result."""
        # Parse from agent's final message
        messages = result.get("messages", [])
        if messages:
            last_msg = messages[-1]
            if hasattr(last_msg, 'content'):
                return self._parse_actions_from_content(last_msg.content)
        return []
    
    def _calculate_confidence(self, result: Dict) -> float:
        """Calculate confidence score from result."""
        # Could be explicitly stated by Gemini 3 or inferred
        # For now, use simple heuristic
        messages = result.get("messages", [])
        if "high confidence" in str(messages).lower():
            return 0.9
        elif "medium confidence" in str(messages).lower():
            return 0.7
        elif "low confidence" in str(messages).lower():
            return 0.4
        return 0.75  # Default moderate confidence
    
    def _needs_verification(self, actions: List[str]) -> bool:
        """Determine if actions need verification."""
        # Critical keywords that require verification
        critical_keywords = ['shutdown', 'stop', 'alarm', 'emergency', 'critical']
        for action in actions:
            if any(keyword in action.lower() for keyword in critical_keywords):
                return True
        return len(actions) > 3  # Many actions = verify
    
    async def _verify_actions(
        self,
        actions_taken: List[str],
        context: Dict[str, Any]
    ) -> bool:
        """Verify that actions had intended effect."""
        self.logger.info(f"🔍 [{self.agent_name}] Verifying actions...")
        
        # Use Gemini 3 to verify outcomes
        verification_prompt = f"""Review the actions taken and verify outcomes:

ACTIONS TAKEN:
{chr(10).join(f'- {a}' for a in actions_taken)}

CURRENT CONTEXT:
{self._format_context(context)}

Did these actions have the intended effect? Verify and respond with YES or NO.
"""
        
        result = await self.agent.ainvoke(
            {"messages": [HumanMessage(content=verification_prompt)]},
            config={"configurable": {"thread_id": f"{self.agent_name}-verify"}}
        )
        
        # Parse verification result
        messages = result.get("messages", [])
        if messages:
            last_content = str(messages[-1].content).upper()
            return "YES" in last_content or "VERIFIED" in last_content
        
        return False
    
    async def _plan_next_steps(
        self,
        reasoning: ReasoningResult,
        actions_taken: List[str],
        verification_passed: bool
    ) -> List[str]:
        """Plan next steps based on results."""
        if not verification_passed:
            return ["Re-analyze situation", "Attempt correction"]
        
        if reasoning.confidence < 0.8:
            return ["Monitor situation closely", "Re-evaluate in 1 minute"]
        
        return ["Continue monitoring"]
    
    def _build_escalation_reason(
        self,
        context: Dict[str, Any],
        thoughts: str
    ) -> str:
        """Build escalation reason for Orchestrator."""
        return f"""Agent: {self.agent_name}
Situation: {context.get('situation', 'Complex situation detected')}
Reasoning: {thoughts[:200]}...
Needs: Higher-level coordination or human decision
"""
    
    def _create_escalation_decision(
        self,
        reasoning: ReasoningResult,
        start_time: datetime
    ) -> Decision:
        """Create decision record for escalation."""
        return Decision(
            decision_id=f"{self.agent_name}-escalate-{int(start_time.timestamp())}",
            timestamp=start_time,
            agent_name=self.agent_name,
            decision="ESCALATED TO ORCHESTRATOR",
            reasoning=reasoning.thought_process,
            confidence=reasoning.confidence,
            actions_taken=["Escalation initiated"],
            escalated=True,
        )
    
    async def _escalate_to_orchestrator(self, decision: Decision):
        """Send escalation to Master Orchestrator."""
        # TODO: Implement orchestrator notification
        self.logger.warning(f"⬆️ ESCALATION: {decision.decision}")
    
    async def _log_decision(self, decision: Decision):
        """Log decision to shared context."""
        from app.state.context import shared_context
        await shared_context.add_decision(decision)
    
    def _parse_thinking_from_content(self, content: str) -> str:
        """Parse thinking section from content."""
        # Simple parser - can be enhanced
        if "thinking:" in content.lower():
            parts = content.lower().split("thinking:")
            if len(parts) > 1:
                return parts[1].split("\n")[0]
        return content[:500]  # First 500 chars as fallback
    
    def _parse_actions_from_content(self, content: str) -> List[str]:
        """Parse proposed actions from content."""
        actions = []
        # Look for numbered lists or bullet points
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-") or line.startswith("•")):
                # Remove numbering/bullets
                clean_line = line.lstrip("0123456789.-• ")
                if clean_line:
                    actions.append(clean_line)
        return actions[:10]  # Max 10 actions

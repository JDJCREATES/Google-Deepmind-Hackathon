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
from langgraph.checkpoint.memory import MemorySaver

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
        model_name = "gemini-3-flash-preview" if use_flash_model else "gemini-3-pro-preview"
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=settings.google_api_key,
            temperature=0.7,
        )
        
        # LangGraph agent with in-memory checkpointing
        self.checkpointer = MemorySaver()
        self.agent = create_react_agent(
            self.llm,
            tools=self.tools,
            prompt=self.system_prompt,
            checkpointer=self.checkpointer,
        )
        
        # Subagents for nested reasoning
        self.subagents: Dict[str, 'BaseAgent'] = {}
        
        # Decision history
        self.decisions: List[Decision] = []
        
        # Token usage tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        
        # Thought signature tracking (Gemini 3 feature for maintaining reasoning state)
        self.thought_signatures: list = []  # Store all thought signatures over time
        self.latest_thought_signature: str | None = None  # Most recent signature to pass back
        
        self.logger.info(f"✅ {agent_name} initialized with Gemini 3 ({model_name})")
    
    async def _broadcast_thought(self, message: str, message_type: str = "agent_activity"):
        """Broadcast agent thought/activity to frontend via WebSocket."""
        try:
            from app.services.websocket import manager
            
            # 1. Send Legacy/Activity Log Entry (ONLY if it's NOT just a thought)
            # This prevents duplicate logs where we see both "Thinking..." and "Thinking..."
            if message_type != "agent_thinking":
                await manager.broadcast({
                    "type": message_type,
                    "data": {
                        "source": self.agent_name,
                        "description": message,
                        "timestamp": datetime.now().isoformat()
                    }
                })
            
            # 2. Send Thought Bubble / Reasoning Event
            # This is displayed in the graph bubbles AND the activity log (as "Thinking")
            should_broadcast_thought = (
                message_type == "agent_thinking" or 
                message_type == "agent_activity"
            )
            
            if should_broadcast_thought:
                noisy_patterns = [
                    "Starting action phase",
                    "Actions completed",
                    "Verify",
                ]
                is_noisy = any(p in message for p in noisy_patterns)
                
                if not is_noisy:
                    # Clean up the message for display if it's an internal log
                    clean_msg = message
                    if "Analyzing" in message and "context" in message:
                        clean_msg = "Checking context..."
                        
                    await manager.broadcast({
                        "type": "agent_thinking",
                        "data": {
                            "agent": self.agent_name.replace("Agent", "").lower(),
                            "thought": clean_msg,
                            "timestamp": datetime.now().isoformat()
                        }
                    })
        except Exception:
            pass  # Don't fail if websocket is down

    async def _broadcast_action(self, actions: List[str]):
        """Broadcast specific action event for UI emphasis."""
        try:
            from app.services.websocket import manager
            if not actions:
                return

            await manager.broadcast({
                "type": "agent_action",
                "data": {
                    "agent": self.agent_name.replace("Agent", "").lower(),
                    "actions": actions,
                    "timestamp": datetime.now().isoformat()
                }
            })
        except Exception:
            pass

    async def _track_tokens(self, result: Any):
        """Track token usage from LLM response and broadcast stats."""
        try:
            # Extract token usage from response metadata
            # For LangChain/Gemini, usage_metadata is a direct attribute on the message
            messages = result.get("messages", [])
            if messages:
                last_message = messages[-1]
                
                input_tokens = 0
                output_tokens = 0
                
                # Method 1: Check for usage_metadata attribute (Google Gemini style)
                usage_metadata = getattr(last_message, 'usage_metadata', None)
                if usage_metadata:
                    # Google Gemini uses these field names
                    input_tokens = getattr(usage_metadata, 'prompt_token_count', 0) or \
                                   getattr(usage_metadata, 'input_tokens', 0) or \
                                   usage_metadata.get('prompt_token_count', 0) if isinstance(usage_metadata, dict) else 0
                    output_tokens = getattr(usage_metadata, 'candidates_token_count', 0) or \
                                    getattr(usage_metadata, 'output_tokens', 0) or \
                                    usage_metadata.get('candidates_token_count', 0) if isinstance(usage_metadata, dict) else 0
                
                # Method 2: Check response_metadata.usage (OpenAI/fallback style)
                if not (input_tokens or output_tokens):
                    response_metadata = getattr(last_message, 'response_metadata', {})
                    usage = response_metadata.get('usage', {}) if isinstance(response_metadata, dict) else {}
                    
                    # Try various field name conventions
                    input_tokens = usage.get('prompt_tokens', 0) or \
                                   usage.get('input_tokens', 0) or \
                                   usage.get('prompt_token_count', 0)
                    output_tokens = usage.get('completion_tokens', 0) or \
                                    usage.get('output_tokens', 0) or \
                                    usage.get('candidates_token_count', 0)
                
                # Method 3: Check token_usage in response_metadata (some versions)
                if not (input_tokens or output_tokens):
                    response_metadata = getattr(last_message, 'response_metadata', {})
                    if isinstance(response_metadata, dict):
                        input_tokens = response_metadata.get('prompt_token_count', 0)
                        output_tokens = response_metadata.get('candidates_token_count', 0)
                
                if input_tokens or output_tokens:
                    self.total_input_tokens += input_tokens
                    self.total_output_tokens += output_tokens
                    
                    # Broadcast updated stats
                    from app.services.websocket import manager
                    
                    # Normalize agent name for frontend
                    agent_id = self.agent_name.replace("Agent", "").replace("Master", "").lower()
                    if agent_id == "orchestrator":
                        agent_id = "orchestrator"
                    
                    await manager.broadcast({
                        "type": "agent_stats_update",
                        "data": {
                            "agent": agent_id,
                            "input_tokens": self.total_input_tokens,
                            "output_tokens": self.total_output_tokens,
                            "timestamp": datetime.now().isoformat()
                        }
                    })
                    
                    self.logger.info(f"📊 Token stats: {agent_id} - In: {input_tokens} (total: {self.total_input_tokens}), Out: {output_tokens} (total: {self.total_output_tokens})")
                else:
                    self.logger.debug(f"No token usage found in message. Metadata: {getattr(last_message, 'usage_metadata', 'N/A')}, Response: {getattr(last_message, 'response_metadata', 'N/A')}")
        except Exception as e:
            self.logger.debug(f"Failed to track tokens: {e}")
            pass  # Non-critical, don't fail reasoning

    async def _extract_thought_signature(self, result: dict) -> None:
        """
        Extract thought signature from Gemini 3 response and store it.
        Thought signatures maintain reasoning state across API calls.
        """
        try:
            # Check if response contains thought_signature
            messages = result.get("messages", [])
            if not messages:
                return
            
            last_message = messages[-1]
            
            # Extract thought signature from content parts
            thought_sig = None
            if hasattr(last_message, 'content'):
                content = last_message.content
                
                # Handle different content formats
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and 'thought_signature' in part:
                            thought_sig = part['thought_signature']
                            break
                elif isinstance(content, dict) and 'thought_signature' in content:
                    thought_sig = content['thought_signature']
            
            if thought_sig:
                # Store signature with timestamp
                signature_data = {
                    'signature': thought_sig,
                    'timestamp': datetime.now().isoformat(),
                    'agent': self.agent_name
                }
                self.thought_signatures.append(signature_data)
                self.latest_thought_signature = thought_sig
                
                # Broadcast to frontend
                from app.services.websocket import manager
                agent_id = self.agent_name.replace("Agent", "").replace("Master", "").lower()
                if agent_id == "orchestrator":
                    agent_id = "orchestrator"
                
                await manager.broadcast({
                    "type": "thought_signature",
                    "data": {
                        "agent": agent_id,
                        "signature_preview": thought_sig[:50] + "..." if len(thought_sig) > 50 else thought_sig,
                        "timestamp": signature_data['timestamp'],
                        "total_signatures": len(self.thought_signatures)
                    }
                })
                
                self.logger.debug(f"[{self.agent_name}] Captured thought signature (total: {len(self.thought_signatures)})")
        except Exception as e:
            self.logger.error(f"Failed to extract thought signature: {e}")

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
        # Broadcast a cleaner 'analyzing' message
        await self._broadcast_thought(f"Analyzing {len(context)} context parameters...")
        
        # Build reasoning prompt
        reasoning_prompt = self._build_reasoning_prompt(context)
        
        # Prepare messages with thought signature if available
        messages = [HumanMessage(content=reasoning_prompt)]
        
        # Include latest thought signature to maintain reasoning continuity
        if self.latest_thought_signature:
            # Add thought signature to maintain context (Gemini 3 feature)
            messages.append({
                "role": "model",
                "parts": [{"thought_signature": self.latest_thought_signature}]
            })
        
        # Invoke Gemini 3 with thinking enabled
        result = await self.agent.ainvoke(
            {"messages": messages},
            config={
                "configurable": {
                    "thread_id": f"{self.agent_name}-reasoning",
                    "thinking_level": self.thinking_level,
                }
            }
        )
        
        # Track token usage
        await self._track_tokens(result)
        
        # Extract and store thought signature
        await self._extract_thought_signature(result)
        
        # Extract Gemini 3's thoughts and reasoning
        thoughts = self._extract_thoughts(result)
        proposed_actions = self._extract_proposed_actions(result)
        confidence = self._calculate_confidence(result)
        
        await self._broadcast_thought(f"Reasoning complete. Confidence: {confidence:.2f}")
        # Broadcast thoughts without "Thoughts:" prefix
        if thoughts and thoughts != "No explicit reasoning trace available":
             await self._broadcast_thought(thoughts[:200]) # Increased length
        else:
             await self._broadcast_thought(f"Plan: {len(proposed_actions)} actions proposed")

        # Determine if escalation needed
        should_escalate = confidence < 0.7 or self._detect_critical_situation(context)
        escalation_reason = None
        if should_escalate:
            escalation_reason = self._build_escalation_reason(context, thoughts)
            await self._broadcast_thought(f"Escalating: {escalation_reason}", "system_alert")
        
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
        
        # Log reasoning trace for frontend visualization
        try:
            from app.api.routers.graph import add_reasoning_trace
            add_reasoning_trace(
                agent_name=self.agent_name,
                step_name="reason",
                thought_process=thoughts[:300],
                confidence=confidence,
                decision=f"Proposed {len(proposed_actions)} actions" if proposed_actions else None
            )
        except Exception:
            pass  # Non-critical, don't fail reasoning
        
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
        
        # Broadcast actions for UI visualization
        if action_result.actions_taken:
            await self._broadcast_action(action_result.actions_taken)
        
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

    # ========== DYNAMIC VERIFICATION ==========

    async def propose_verification(self, hypothesis: Any) -> Dict[str, Any]:
        """
        Propose a tool call to verify a specific hypothesis.
        
        Uses Gemini to dynamically select the best tool and arguments
        to prove/disprove the hypothesis.
        """
        from pydantic import BaseModel, Field
        
        # Broadcast that we're working on this hypothesis
        await self._broadcast_thought(f"Proposing verification for hypothesis: {hypothesis.description[:100]}...")
        
        class VerificationTool(BaseModel):
            """Tool call to verify hypothesis."""
            tool_name: str = Field(description="Name of the tool to call (e.g. check_sensors, inspect_machine)")
            rationale: str = Field(description="Why this tool will verify the hypothesis")
            parameters: Dict[str, Any] = Field(description="Parameters for the tool call")
            
        system = f"""You are the {self.agent_name}. 
        Propose a specific tool call to verify this hypothesis: "{hypothesis.description}"
        
        Available Tools:
        - check_sensors(sensor_id, metric)
        - inspect_machine(machine_id, check_type)
        - review_camera(camera_id, duration_sec)
        - query_logs(query_pattern, time_range)
        - check_schedule(employee_id, shift_date)
        - verify_compliance(regulation_id, check_point)
        
        Select the most relevant tool and providing realistic simulation parameters.
        """
        
        llm = self.llm.with_structured_output(VerificationTool)
        
        try:
            result = await llm.ainvoke(system)
            
            # Note: with_structured_output doesn't expose token usage metadata
            # Token tracking happens in the reason() method where we have access to usage data
            
            # Broadcast the human-readable rationale instead of the tool name
            await self._broadcast_thought(f"{result.rationale}")
            
            return {
                "tool": result.tool_name,
                "reasoning": result.rationale,
                "params": result.parameters
            }
        except Exception as e:
            self.logger.error(f"Failed to propose verification: {e}")
            # Fallback
            return {
                "tool": "generic_check",
                "reasoning": "Fallback verification",
                "params": {"target": "general"}
            }

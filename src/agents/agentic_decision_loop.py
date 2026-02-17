"""
Agentic Decision Loop - Core LLM Interaction Layer

Implements the main decision-making loop for the agent.
Integrates PromptEngine, Metrics, and OpenAI Client with strict JSON schema enforcement.
Implements Phases 6, 9, 11, and 12 of the framework.
"""
import time
import json
import logging
import os
from typing import Dict, Any, Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # Handle missing dependency gracefully in tests

from src.agents.core.engine import PromptEngine, PromptContext
from src.agents.core.metrics import PromptMetrics
from src.agents.core.schema import AgentOutput, ActionType
from src.llm.context_manager import LLMContextManager

logger = logging.getLogger(__name__)

class AgenticDecisionLoop:
    """
    Core agent decision loop that executes the OODA (Observe-Orient-Decide-Act) cycle
    using optimized prompts and structured outputs.
    """

    def __init__(self, agent_id: str, prompt_engine: Optional[PromptEngine] = None):
        """
        Initialize the decision loop.

        Args:
            agent_id: Unique identifier for the agent
            prompt_engine: Optional PromptEngine instance (injected for testing)
        """
        self.agent_id = agent_id
        self.prompt_engine = prompt_engine or PromptEngine()
        self.metrics = PromptMetrics()
        self.context_manager = LLMContextManager()

        # Initialize OpenAI client (Phase 6 - Structured Outputs)
        api_key = os.getenv("OPENAI_API_KEY")
        if OpenAI and api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            self.client = None
            logger.warning("OpenAI client not initialized (missing key or library). Using MOCK mode.")

    def run(
        self,
        task: str,
        context: Dict[str, Any],
        complexity: float = 0.5,
        task_type: str = "analysis",
        session_id: Optional[str] = None
    ) -> AgentOutput:
        """
        Execute a single decision cycle.

        Args:
            task: Task description
            context: Dictionary of context data (telemetry, state, tools)
            complexity: Estimated task complexity (0.0 - 1.0)
            task_type: Type of task to execute (analysis, planning, execution)
            session_id: Optional session ID for maintaining conversation context

        Returns:
            Validated AgentOutput object
        """
        start_time = time.time()

        # 1. Build Context Object
        prompt_context = PromptContext(
            task_description=task,
            telemetry_data=context.get("telemetry"),
            system_state=context.get("system_state"),
            tools=context.get("tools"),
            memory_context=context.get("memory"),
            complexity_score=complexity
        )

        # 2. Construct Prompt (Phase 2, 4, 10)
        messages = self.prompt_engine.construct_prompt(
            task_type=task_type,
            context=prompt_context
        )

        # Context Management Integration
        if session_id:
            if not self.context_manager.has_session(session_id):
                self.context_manager.create_session(session_id, messages)
            else:
                # Append only the new user message (typically the last one)
                if messages:
                    last_msg = messages[-1]
                    # Ensure we are adding a user message
                    if last_msg.get('role') == 'user':
                        self.context_manager.add_message(session_id, last_msg['role'], last_msg['content'])

            # Use full context from session
            messages = self.context_manager.get_context(session_id)

        # 3. Execute LLM Call (Phase 6, 11)
        try:
            response_data = self._call_llm(messages)

            # Update Context with Assistant Response
            if session_id:
                self.context_manager.add_message(session_id, "assistant", json.dumps(response_data))
                self.context_manager.trim_context(session_id)

            # 4. Validate & Parse (Phase 6 - Pydantic)
            agent_output = AgentOutput(**response_data)

            # 5. Apply Guardrails (Phase 9)
            agent_output = self._apply_guardrails(agent_output)

            # Record Metrics
            latency = (time.time() - start_time) * 1000
            self.metrics.record(
                latency_ms=latency,
                success=True
            )

            return agent_output

        except Exception as e:
            logger.error(f"Agent decision failed: {e}")
            self.metrics.record(
                latency_ms=(time.time() - start_time) * 1000,
                success=False,
                error_type=type(e).__name__
            )
            # Fail-safe fallback
            return self._fallback_response(str(e))

    def _call_llm(self, messages: list) -> Dict[str, Any]:
        """Call OpenAI API with JSON mode enforcement."""
        if not self.client:
            return self._mock_response(messages)

        try:
            completion = self.client.chat.completions.create(
                model="gpt-4o",  # Or gpt-3.5-turbo based on config
                messages=messages,
                response_format={"type": "json_object"},  # Phase 6
                temperature=0.2,  # Low temp for determinism
            )

            content = completion.choices[0].message.content
            if not content:
                raise ValueError("Empty response from LLM")

            return json.loads(content)

        except Exception as e:
            logger.error(f"LLM API Error: {e}")
            raise

    def _mock_response(self, messages: Optional[list] = None) -> Dict[str, Any]:
        """Mock response for testing/offline mode."""
        # Simple heuristic for testing benchmarks without API key
        action = "analyze"
        confidence = 0.85

        if messages:
            last_msg = messages[-1]['content'].lower()
            logger.info(f"Mock analyzing message: '{last_msg}'")
            if "critical" in last_msg:
                logger.info("Matched CRITICAL")
                action = "execute"
                confidence = 0.95
            elif "execute" in last_msg:
                logger.info("Matched EXECUTE")
                action = "execute"
                confidence = 0.95
            elif "ambiguous" in last_msg or "clarification" in last_msg or "thing" in last_msg:
                action = "request_clarification"
                confidence = 0.2  # Trigger guardrail

        return {
            "analysis": {
                "observation": "Mock observation of system state.",
                "reasoning": "Mock reasoning chain based on inputs.",
                "key_factors": ["Factor A", "Factor B"]
            },
            "action": action,
            "confidence": confidence,
            "tool_calls": []
        }

    def _apply_guardrails(self, output: AgentOutput) -> AgentOutput:
        """
        Apply safety guardrails (Phase 9).
        - Force clarification on low confidence.
        - Prevent hazardous actions in critical phases (future logic).
        """
        # Guardrail 1: Low Confidence -> Request Clarification
        if output.confidence < 0.3:
            logger.warning(f"Guardrail triggered: Low confidence ({output.confidence}). Switch to CLARIFY.")
            output.action = ActionType.REQUEST_CLARIFICATION
            output.next_step_hint = "Insufficient data to proceed safely."

        return output

    def _fallback_response(self, error_msg: str) -> AgentOutput:
        """Generate a safe fallback response on failure."""
        return AgentOutput(
            analysis={
                "observation": "System error during decision process.",
                "reasoning": f"Exception occurred: {error_msg}",
                "key_factors": ["Internal Error"]
            },
            action=ActionType.WAIT,
            confidence=0.0,
            next_step_hint="Manual intervention required."
        )

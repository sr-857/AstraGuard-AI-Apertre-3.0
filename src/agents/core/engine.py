"""
Prompt Engine - Modular Prompt Construction & Optimization

Handles template loading, assembly, optimization (compression), and adaptation based on task complexity.
Implements Phases 2, 4, 5, 7, 8, and 10 of the Prompt Optimization Framework.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from src.agents.core.schema import AgentOutput

logger = logging.getLogger(__name__)

# Constants for Adaptive Prompting
COMPLEXITY_THRESHOLD = 0.7
MAX_CONTEXT_TOKENS = 2000  # Soft limit for context compression

@dataclass
class PromptContext:
    """Context data for prompt rendering."""
    task_description: str
    telemetry_data: Optional[Dict[str, Any]] = None
    system_state: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    memory_context: Optional[str] = None
    complexity_score: float = 0.5  # 0.0 - 1.0

class PromptEngine:
    """
    Core engine for constructing optimized LLM prompts.
    """

    def __init__(self, template_dir: str = "src/agents/prompts"):
        """
        Initialize PromptEngine with template directory.

        Args:
            template_dir: Path to prompt templates
        """
        self.template_dir = Path(template_dir)
        self.system_templates = {}
        self.task_templates = {}
        self.examples = []
        self._load_templates()

    def _load_templates(self):
        """Load templates and examples from disk."""
        try:
            # Load System Components
            sys_path = self.template_dir / "system"
            self.system_templates['base'] = (sys_path / "base.txt").read_text()
            self.system_templates['tools'] = (sys_path / "tools.txt").read_text()
            self.system_templates['reasoning'] = (sys_path / "reasoning.txt").read_text()

            # Load Task Templates
            task_path = self.template_dir / "tasks"
            if task_path.exists():
                for f in task_path.glob("*.txt"):
                    self.task_templates[f.stem] = f.read_text()

            # Load Few-Shot Examples
            ex_path = self.template_dir / "examples.json"
            if ex_path.exists():
                self.examples = json.loads(ex_path.read_text())

        except Exception as e:
            logger.error(f"Failed to load prompt templates: {e}")
            raise

    def construct_prompt(
        self,
        task_type: str,
        context: PromptContext,
        version: str = "v1"  # A/B Testing Hook (Phase 8)
    ) -> List[Dict[str, str]]:
        """
        Construct a full prompt message list for LLM.

        Args:
            task_type: Type of task (analysis, planning, execution)
            context: Data context for the prompt
            version: Prompt version for A/B testing

        Returns:
            List of message dicts (role, content)
        """
        messages = []

        # 1. System Prompt Construction
        system_content = self._build_system_prompt(context, version)
        messages.append({"role": "system", "content": system_content})

        # 2. Few-Shot Examples (Phase 4)
        if self.examples:
            messages.extend(self._build_few_shot_examples())

        # 3. Task Prompt (User Message)
        user_content = self._build_task_prompt(task_type, context)
        messages.append({"role": "user", "content": user_content})

        return messages

    def _build_system_prompt(self, context: PromptContext, version: str) -> str:
        """Combine system templates based on context and version."""
        # Format base template first to avoid conflicts with JSON braces later
        parts = [self.system_templates['base'].format(task_description=context.task_description)]

        # Tool injection
        if context.tools:
            tool_desc = json.dumps([t['name'] for t in context.tools], indent=2)  # Simplified tool list
            parts.append(self.system_templates['tools'].format(tool_descriptions=tool_desc))

        # Adaptive Logic (Phase 10)
        # Only include heavy reasoning instructions if complexity is high
        if context.complexity_score > COMPLEXITY_THRESHOLD:
            schema_desc = AgentOutput.model_json_schema()
            parts.append(self.system_templates['reasoning'].format(
                schema_description=json.dumps(schema_desc, indent=2)
            ))
        else:
            # Lightweight instructions for simple tasks
            parts.append("Provide a concise JSON response strictly adhering to the schema.")

        return "\n\n".join(parts)

    def _build_few_shot_examples(self) -> List[Dict[str, str]]:
        """Format loaded examples into message history."""
        msgs = []
        for ex in self.examples[:2]: # Limit to 2 examples (Phase 4)
            msgs.append({"role": "user", "content": ex['input']})
            msgs.append({"role": "assistant", "content": json.dumps(ex['output'])})
        return msgs

    def _build_task_prompt(self, task_type: str, context: PromptContext) -> str:
        """Render the specific task template."""
        template = self.task_templates.get(task_type)
        if not template:
            logger.warning(f"Task template '{task_type}' not found, using generic.")
            return f"Execute task: {context.task_description}"

        # Context Compression (Phase 7)
        compressed_memory = self._compress_context(context.memory_context)

        return template.format(
            telemetry_data=json.dumps(context.telemetry_data, indent=2) if context.telemetry_data else "None",
            system_state=context.system_state or "Unknown",
            directive=context.task_description,
            tool_names=[t['name'] for t in (context.tools or [])],
            memory_context=compressed_memory
        )

    def _compress_context(self, context_str: Optional[str]) -> str:
        """
        Simple context compression strategy (Phase 7).
        Truncates or summarizes context to fit token budget.
        """
        if not context_str:
            return ""

        # Simple character-based truncation as a proxy for token limits
        # In production, use tiktoken here.
        limit_chars = MAX_CONTEXT_TOKENS * 4
        if len(context_str) > limit_chars:
            return context_str[:limit_chars] + "...[TRUNCATED]"
        return context_str

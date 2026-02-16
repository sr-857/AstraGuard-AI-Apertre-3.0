"""
Unit tests for the Prompt Optimization Framework.
Tests PromptEngine, Schema Validation, and AgenticDecisionLoop (mocked).
"""
import pytest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.agents.core.engine import PromptEngine, PromptContext
from src.agents.core.schema import AgentOutput, ActionType
from src.agents.agentic_decision_loop import AgenticDecisionLoop

# Fixtures
@pytest.fixture
def mock_template_dir(tmp_path):
    """Create a temporary template directory structure."""
    system_dir = tmp_path / "system"
    system_dir.mkdir(parents=True)
    (system_dir / "base.txt").write_text("Base System Prompt. Task: {task_description}")
    (system_dir / "tools.txt").write_text("Tools: {tool_descriptions}")
    (system_dir / "reasoning.txt").write_text("Reasoning Schema: {schema_description}")

    task_dir = tmp_path / "tasks"
    task_dir.mkdir(parents=True)
    (task_dir / "analysis.txt").write_text("Analyze: {telemetry_data}")

    (tmp_path / "examples.json").write_text('[{"input": "in", "output": {"analysis": {"observation": "obs", "reasoning": "reas", "key_factors": ["f1"]}, "action": "analyze", "confidence": 0.9}}]')

    return str(tmp_path)

@pytest.fixture
def prompt_engine(mock_template_dir):
    return PromptEngine(template_dir=mock_template_dir)

# Tests for PromptEngine
def test_prompt_engine_load_templates(prompt_engine):
    assert "Base System Prompt" in prompt_engine.system_templates['base']
    assert "Analyze" in prompt_engine.task_templates['analysis']
    assert len(prompt_engine.examples) == 1

def test_prompt_construction_simple(prompt_engine):
    context = PromptContext(task_description="Test Task", complexity_score=0.2)
    messages = prompt_engine.construct_prompt("analysis", context)

    # 1 System + 2 Example Messages (User/Asst) + 1 Task Message = 4
    assert len(messages) == 4
    assert messages[0]['role'] == "system"
    assert "Test Task" in messages[0]['content']
    # Low complexity -> lightweight instruction
    assert "concise JSON response" in messages[0]['content']

def test_prompt_construction_complex(prompt_engine):
    context = PromptContext(task_description="Complex Task", complexity_score=0.9)
    messages = prompt_engine.construct_prompt("analysis", context)

    # High complexity -> reasoning schema injection
    assert "Reasoning Schema" in messages[0]['content']

def test_context_compression(prompt_engine):
    long_context = "a" * 10000
    compressed = prompt_engine._compress_context(long_context)
    assert len(compressed) < 10000
    assert "[TRUNCATED]" in compressed

# Tests for Schema
def test_agent_output_validation_valid():
    data = {
        "analysis": {
            "observation": "All nominal",
            "reasoning": "Sensors green",
            "key_factors": ["temp ok"]
        },
        "action": "wait",
        "confidence": 0.95
    }
    output = AgentOutput(**data)
    assert output.action == ActionType.WAIT
    assert output.is_confident()

def test_agent_output_validation_invalid_confidence():
    data = {
        "analysis": {"observation": "o", "reasoning": "r", "key_factors": []},
        "action": "wait",
        "confidence": 1.5 # Invalid
    }
    with pytest.raises(ValueError):
        AgentOutput(**data)

# Tests for AgenticDecisionLoop
def test_agent_loop_mock_execution(mock_template_dir):
    loop = AgenticDecisionLoop("agent-1", prompt_engine=PromptEngine(mock_template_dir))

    # Mocking client to be None ensures fallback to internal mock
    loop.client = None

    context = {"telemetry": {"temp": 50}}
    output = loop.run("Check stats", context)

    assert isinstance(output, AgentOutput)
    assert output.action == ActionType.ANALYZE # From internal mock
    assert loop.metrics.total_requests == 1
    assert loop.metrics.success_count == 1

def test_agent_loop_guardrails(mock_template_dir):
    loop = AgenticDecisionLoop("agent-1", prompt_engine=PromptEngine(mock_template_dir))

    # Mock return with low confidence
    mock_low_conf = {
        "analysis": {"observation": "obs", "reasoning": "reas", "key_factors": []},
        "action": "execute",
        "confidence": 0.1
    }

    with patch.object(loop, '_call_llm', return_value=mock_low_conf):
        loop.client = MagicMock() # Enable client path
        output = loop.run("Risky task", {})

        # Guardrail should flip action to REQUEST_CLARIFICATION
        assert output.action == ActionType.REQUEST_CLARIFICATION
        assert "Guardrail triggered" in str(output.next_step_hint) or output.confidence < 0.3

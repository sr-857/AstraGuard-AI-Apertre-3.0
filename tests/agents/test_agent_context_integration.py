import pytest
from unittest.mock import MagicMock
from src.agents.agentic_decision_loop import AgenticDecisionLoop
from src.agents.core.engine import PromptEngine
from src.agents.core.schema import AgentOutput

@pytest.fixture
def mock_prompt_engine():
    engine = MagicMock(spec=PromptEngine)
    # Mock construct_prompt to return a predictable list
    engine.construct_prompt.return_value = [
        {"role": "system", "content": "Sys"},
        {"role": "user", "content": "Task"}
    ]
    return engine

def test_agent_run_with_session(mock_prompt_engine):
    agent = AgenticDecisionLoop("agent-1", prompt_engine=mock_prompt_engine)
    agent.client = None # Force mock response

    session_id = "sess-1"

    # First run: should create session
    agent.run("Task 1", {}, session_id=session_id)

    assert agent.context_manager.has_session(session_id)
    ctx = agent.context_manager.get_context(session_id)
    # Initial: Sys, User(Task 1), Assistant(Mock Response)
    assert len(ctx) == 3
    assert ctx[0]['content'] == "Sys"
    assert ctx[1]['content'] == "Task"

    # Second run: should append
    # Update mock engine to return new task
    mock_prompt_engine.construct_prompt.return_value = [
        {"role": "system", "content": "Sys"},
        {"role": "user", "content": "Task 2"}
    ]

    agent.run("Task 2", {}, session_id=session_id)

    ctx = agent.context_manager.get_context(session_id)
    # Should have: Sys, User1, Asst1, User2, Asst2
    assert len(ctx) == 5
    assert ctx[3]['content'] == "Task 2"
    assert ctx[4]['role'] == "assistant"

def test_agent_run_without_session(mock_prompt_engine):
    agent = AgenticDecisionLoop("agent-1", prompt_engine=mock_prompt_engine)
    agent.client = None

    agent.run("Task 1", {})

    # Should not create any session in context manager
    assert not agent.context_manager.sessions

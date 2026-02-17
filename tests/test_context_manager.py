"""
Tests for LLM Context Manager.
"""
import pytest
from src.llm.context_manager import LLMContextManager

@pytest.fixture
def context_manager():
    return LLMContextManager()

def test_create_session(context_manager):
    session_id = "test-session-1"
    initial_messages = [{"role": "system", "content": "You are a helpful assistant."}]

    context_manager.create_session(session_id, initial_messages)

    assert context_manager.has_session(session_id)
    assert len(context_manager.get_context(session_id)) == 1
    assert context_manager.get_context(session_id)[0]["content"] == "You are a helpful assistant."

def test_add_message(context_manager):
    session_id = "test-session-2"
    context_manager.create_session(session_id)

    context_manager.add_message(session_id, "user", "Hello")
    context_manager.add_message(session_id, "assistant", "Hi there!")

    context = context_manager.get_context(session_id)
    assert len(context) == 2
    assert context[0]["role"] == "user"
    assert context[1]["role"] == "assistant"

def test_add_message_invalid_session(context_manager):
    with pytest.raises(ValueError):
        context_manager.add_message("invalid-session", "user", "Hello")

def test_trim_context(context_manager):
    session_id = "test-session-3"
    context_manager.create_session(session_id)

    # Add 25 messages
    for i in range(25):
        context_manager.add_message(session_id, "user", f"Message {i}")

    context_manager.trim_context(session_id, max_messages=20)

    context = context_manager.get_context(session_id)
    assert len(context) == 20
    # Check that we kept the LAST 20 messages (5 to 24)
    # The messages are 0-indexed, so removing first 5 means starting at index 5.
    assert context[0]["content"] == "Message 5"
    assert context[-1]["content"] == "Message 24"

def test_session_isolation(context_manager):
    session1 = "session-1"
    session2 = "session-2"

    context_manager.create_session(session1)
    context_manager.create_session(session2)

    context_manager.add_message(session1, "user", "Hello Session 1")
    context_manager.add_message(session2, "user", "Hello Session 2")

    context1 = context_manager.get_context(session1)
    context2 = context_manager.get_context(session2)

    assert len(context1) == 1
    assert context1[0]["content"] == "Hello Session 1"

    assert len(context2) == 1
    assert context2[0]["content"] == "Hello Session 2"

def test_get_context_nonexistent(context_manager):
    assert context_manager.get_context("nonexistent") == []

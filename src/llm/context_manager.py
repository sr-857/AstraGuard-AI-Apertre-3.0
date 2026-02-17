"""
Context Manager for LLM Interactions.

Handles conversation memory, token limits (via message count), and session management.
Designed to be modular and isolated from core agent logic.
"""
from typing import Dict, List, Any, Optional
import time
import logging

logger = logging.getLogger(__name__)

class LLMContextManager:
    """
    Manages LLM conversation context, sessions, and memory limits.
    """
    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, session_id: str, initial_messages: Optional[List[Dict[str, str]]] = None) -> None:
        """
        Create a new session with optional initial messages.

        Args:
            session_id: Unique identifier for the session.
            initial_messages: List of message dicts to initialize the session with.
        """
        self.sessions[session_id] = {
            "messages": initial_messages or [],
            "created_at": time.time()
        }
        logger.debug(f"Created LLM session: {session_id}")

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """
        Add a message to a session.

        Args:
            session_id: Session identifier.
            role: Message role (system, user, assistant).
            content: Message content.
        """
        if session_id not in self.sessions:
            logger.warning(f"Attempted to add message to non-existent session: {session_id}")
            # Fallback: create session? No, strict failure for v1 to avoid hidden bugs.
            raise ValueError(f"Session {session_id} not found.")

        self.sessions[session_id]["messages"].append({
            "role": role,
            "content": content
        })

    def get_context(self, session_id: str) -> List[Dict[str, str]]:
        """
        Retrieve the full message history for a session.

        Args:
            session_id: Session identifier.

        Returns:
            List of message dictionaries.
        """
        if session_id not in self.sessions:
            return []
        return self.sessions[session_id]["messages"]

    def trim_context(self, session_id: str, max_messages: int = 20) -> None:
        """
        Keep only the last N messages to manage context window.

        Args:
            session_id: Session identifier.
            max_messages: Maximum number of messages to retain.
        """
        if session_id not in self.sessions:
            return

        messages = self.sessions[session_id]["messages"]
        if len(messages) > max_messages:
            # Simple trimming: Keep last N messages.
            # Note: This might drop the system prompt if it's old.
            # For v2, we should preserve the first message if it's 'system'.
            self.sessions[session_id]["messages"] = messages[-max_messages:]
            logger.debug(f"Trimmed context for session {session_id} to {max_messages} messages.")

    def has_session(self, session_id: str) -> bool:
        """Check if a session exists."""
        return session_id in self.sessions

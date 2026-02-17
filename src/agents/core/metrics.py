"""
Prompt Metrics Tracking

Tracks token usage, latency, and success rates for LLM interactions.
Designed for observability integration (Prometheus/logging).
"""
import time
from dataclasses import dataclass, field
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)

@dataclass
class PromptMetrics:
    """Metrics container for prompt execution."""

    # Token Counts
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    # Execution Stats
    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0

    # Latency (ms)
    total_latency_ms: float = 0.0

    # Detailed tracking
    latency_history: List[float] = field(default_factory=list)
    token_history: List[int] = field(default_factory=list)

    def record(
        self,
        latency_ms: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        success: bool = True,
        error_type: Optional[str] = None
    ):
        """
        Record a single prompt execution event.

        Args:
            latency_ms: Execution time in milliseconds
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            success: Whether the request was successful
            error_type: Optional error classification string
        """
        self.total_requests += 1

        # Token tracking
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        total = prompt_tokens + completion_tokens
        self.total_tokens += total
        self.token_history.append(total)

        # Latency tracking
        self.total_latency_ms += latency_ms
        self.latency_history.append(latency_ms)

        # Success/Failure
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
            if error_type:
                logger.warning(f"Prompt failure recorded: {error_type}")

        # Limit history size to prevent memory leaks (keep last 1000)
        if len(self.latency_history) > 1000:
            self.latency_history.pop(0)
            self.token_history.pop(0)

    @property
    def avg_latency(self) -> float:
        """Calculate average latency in ms."""
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests

    @property
    def avg_tokens(self) -> float:
        """Calculate average tokens per request."""
        if self.total_requests == 0:
            return 0.0
        return self.total_tokens / self.total_requests

    @property
    def error_rate(self) -> float:
        """Calculate error rate (0.0 - 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.failure_count / self.total_requests

    def to_dict(self) -> Dict[str, float]:
        """Export metrics for logging/monitoring."""
        return {
            "total_requests": self.total_requests,
            "success_rate": 1.0 - self.error_rate,
            "avg_latency_ms": self.avg_latency,
            "avg_tokens": self.avg_tokens,
            "total_tokens": self.total_tokens
        }

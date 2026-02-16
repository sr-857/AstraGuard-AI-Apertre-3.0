"""
Prompt Evaluation Benchmark (Phase 12)

Measures response accuracy, schema compliance, and latency across test cases.
Can run in 'mock' mode (default) or 'live' mode (with OPENAI_API_KEY).
"""
import sys
import os
import json
import time
import logging
from typing import List, Dict

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.agents.agentic_decision_loop import AgenticDecisionLoop
from src.agents.core.schema import ActionType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PromptBenchmark")

TEST_CASES = [
    {
        "id": "TC001",
        "description": "Nominal telemetry analysis",
        "input": "Analyze telemetry for Battery 1. Temp: 25C (Nominal), Voltage: 12.0V.",
        "context": {"telemetry": {"temp": 25, "voltage": 12.0}},
        "expected_action": ActionType.ANALYZE,
        "complexity": 0.2
    },
    {
        "id": "TC002",
        "description": "Critical thermal event",
        "input": "Battery 1 at 85C! Critical thermal runaway imminent.",
        "context": {"telemetry": {"temp": 85, "status": "CRITICAL"}},
        "expected_action": [ActionType.EXECUTE, ActionType.ESCALATE],
        "complexity": 0.8
    },
    {
        "id": "TC003",
        "description": "Ambiguous instruction",
        "input": "Do the thing with the thing.",
        "context": {},
        "expected_action": ActionType.REQUEST_CLARIFICATION,
        "complexity": 0.5
    }
]

def run_benchmark(iterations: int = 1):
    """Run the benchmark suite."""
    logger.info(f"Starting Benchmark: {iterations} iterations per case")

    agent = AgenticDecisionLoop("benchmark-agent")
    results = []

    for case in TEST_CASES:
        logger.info(f"Running Case {case['id']}: {case['description']}")

        latencies = []
        successes = 0
        matches = 0

        for i in range(iterations):
            try:
                start = time.time()
                output = agent.run(
                    task=case['input'],
                    context=case['context'],
                    complexity=case['complexity']
                )
                duration = (time.time() - start) * 1000
                latencies.append(duration)
                successes += 1

                # Verify Expected Action
                expected = case['expected_action']
                if isinstance(expected, list):
                    match = output.action in expected
                else:
                    match = output.action == expected

                if match:
                    matches += 1
                else:
                    logger.warning(f"Mismatch: Got {output.action} ({type(output.action)}), Expected {expected}")

            except Exception as e:
                logger.error(f"Case {case['id']} failed: {e}")

        # Metrics
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        accuracy = (matches / iterations) * 100

        results.append({
            "case_id": case['id'],
            "avg_latency_ms": avg_latency,
            "success_rate": (successes / iterations) * 100,
            "accuracy": accuracy
        })

    # Print Summary
    print("\n" + "="*40)
    print("BENCHMARK RESULTS")
    print("="*40)
    print(f"{'Case ID':<10} | {'Latency (ms)':<15} | {'Success %':<10} | {'Accuracy %':<10}")
    print("-" * 55)
    for res in results:
        print(f"{res['case_id']:<10} | {res['avg_latency_ms']:<15.2f} | {res['success_rate']:<10.1f} | {res['accuracy']:<10.1f}")
    print("="*40)

if __name__ == "__main__":
    # If run directly
    run_benchmark(iterations=3)

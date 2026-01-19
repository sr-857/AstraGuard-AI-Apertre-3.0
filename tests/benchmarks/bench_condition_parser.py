#!/usr/bin/env python3
"""
Microbenchmarks for Safe Condition Parser

Benchmarks expression parsing and evaluation performance.
Run with: pytest benchmarks/bench_condition_parser.py --benchmark-only
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.safe_condition_parser import safe_evaluate_condition as evaluate, SafeConditionParser


# Sample conditions of varying complexity
SIMPLE_CONDITION = "severity >= 0.5"
MEDIUM_CONDITION = "severity >= 0.5 and recurrence_count > 2"
COMPLEX_CONDITION = "(severity >= 0.8 or (confidence > 0.9 and recurrence_count >= 3)) and step < 10"
NUMERIC_CONDITION = "duration > 100 and step >= 5"

# Sample context for evaluation
CONTEXT = {
    "severity": 0.75,
    "recurrence_count": 4,
    "confidence": 0.92,
    "step": 7,
    "duration": 150,
}


def test_evaluate_simple_condition(benchmark):
    """Benchmark evaluation of simple condition."""
    
    def eval_simple():
        return evaluate(SIMPLE_CONDITION, CONTEXT)
    
    result = benchmark(eval_simple)
    assert result is True


def test_evaluate_medium_condition(benchmark):
    """Benchmark evaluation of medium complexity condition."""
    
    def eval_medium():
        return evaluate(MEDIUM_CONDITION, CONTEXT)
    
    result = benchmark(eval_medium)
    assert result is True


def test_evaluate_complex_condition(benchmark):
    """Benchmark evaluation of complex condition with parentheses."""
    
    def eval_complex():
        return evaluate(COMPLEX_CONDITION, CONTEXT)
    
    result = benchmark(eval_complex)
    assert result is True


def test_evaluate_numeric_condition(benchmark):
    """Benchmark evaluation of numeric-only condition."""
    
    def eval_numeric():
        return evaluate(NUMERIC_CONDITION, CONTEXT)
    
    result = benchmark(eval_numeric)
    assert result is True


def test_parse_simple_condition(benchmark):
    """Benchmark parsing of simple condition (via full evaluation)."""
    parser = SafeConditionParser()
    
    def parse_simple():
        return parser.evaluate(SIMPLE_CONDITION, CONTEXT)
    
    result = benchmark(parse_simple)
    assert result is not None


def test_parse_complex_condition(benchmark):
    """Benchmark parsing of complex condition (via full evaluation)."""
    parser = SafeConditionParser()
    
    def parse_complex():
        return parser.evaluate(COMPLEX_CONDITION, CONTEXT)
    
    result = benchmark(parse_complex)
    assert result is not None


def test_parser_reuse(benchmark):
    """Benchmark using parser object for multiple evaluations."""
    
    parser = SafeConditionParser()
    
    def evaluate_multiple():
        results = []
        for condition in [SIMPLE_CONDITION, MEDIUM_CONDITION, COMPLEX_CONDITION]:
            results.append(parser.evaluate(condition, CONTEXT))
        return results
    
    result = benchmark(evaluate_multiple)
    assert all(r is True for r in result)


def test_evaluate_false_conditions(benchmark):
    """Benchmark evaluation of conditions that return False."""
    
    low_severity_context = {"severity": 0.2, "recurrence_count": 1, "confidence": 0.3, "step": 1, "duration": 10}
    
    def eval_false():
        return evaluate(MEDIUM_CONDITION, low_severity_context)
    
    result = benchmark(eval_false)
    assert result is False


def test_evaluate_with_or_operators(benchmark):
    """Benchmark OR operator evaluation (short-circuit)."""
    
    or_condition = "severity >= 0.5 or recurrence_count > 10 or confidence > 0.99"
    
    def eval_or():
        return evaluate(or_condition, CONTEXT)
    
    result = benchmark(eval_or)
    assert result is True  # First clause is true


def test_evaluate_repeated_same_condition(benchmark):
    """Benchmark repeated evaluation of same condition (cache effectiveness)."""
    
    def eval_repeated():
        results = []
        for _ in range(10):
            results.append(evaluate(SIMPLE_CONDITION, CONTEXT))
        return results
    
    result = benchmark(eval_repeated)
    assert all(r is True for r in result)


def test_evaluate_edge_case_equality(benchmark):
    """Benchmark equality operators."""
    
    equality_condition = "step == 7 and recurrence_count == 4"
    
    def eval_equality():
        return evaluate(equality_condition, CONTEXT)
    
    result = benchmark(eval_equality)
    assert result is True


def test_evaluate_inequality(benchmark):
    """Benchmark inequality operators."""
    
    inequality_condition = "severity != 0.5 and confidence != 0.0"
    
    def eval_inequality():
        return evaluate(inequality_condition, CONTEXT)
    
    result = benchmark(eval_inequality)
    assert result is True

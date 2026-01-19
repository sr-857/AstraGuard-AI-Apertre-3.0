#!/usr/bin/env python3
"""Quick test runner to check all tests."""

import subprocess
import sys

# Run all tests
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=line", "-q"],
    cwd="d:\\Elite_Coders\\AstraGuard-AI"
)

sys.exit(result.returncode)

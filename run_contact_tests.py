#!/usr/bin/env python3
"""
Run Contact Form API Tests

Executes the test suite for the contact form functionality.
"""

import sys
import pytest

if __name__ == "__main__":
    # Run tests with verbose output
    exit_code = pytest.main([
        "tests/test_contact.py",
        "-v",
        "--tb=short",
        "--color=yes"
    ])
    
    sys.exit(exit_code)

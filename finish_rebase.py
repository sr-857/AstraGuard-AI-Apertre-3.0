#!/usr/bin/env python3
import subprocess
import os

os.chdir(r"c:\Open Source Project\AstraGuard-AI-Apertre-3.0")

# Set environment variables to bypass editor
env = os.environ.copy()
env['GIT_EDITOR'] = 'true'
env['GIT_SEQUENCE_EDITOR'] = 'true'
env['GIT_MERGE_VERIFYSIG'] = 'false'

# Try to continue the rebase
try:
    result = subprocess.run(['git', 'rebase', '--continue'], env=env, capture_output=True, text=True, timeout=10)
    print("STDOUT:", result.stdout)
    print("STDERR:", result.stderr)
    print("Return code:", result.returncode)
except Exception as e:
    print(f"Error: {e}")

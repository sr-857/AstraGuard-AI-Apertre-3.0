import subprocess
import os
import shutil
import json

os.chdir(r"c:\Open Source Project\AstraGuard-AI-Apertre-3.0")

# Read the rebase state
with open(r".git\rebase-merge\orig-head", 'r') as f:
    orig_head = f.read().strip()

with open(r".git\rebase-merge\onto", 'r') as f:
    onto = f.read().strip()

print(f"Original HEAD: {orig_head}")
print(f"Rebasing onto: {onto}")

# Use subprocess to call git commands
# First check if we still have staged changes
result = subprocess.run(['git', 'diff', '--cached', '--name-only'], capture_output=True, text=True)
print(f"\nStaged files:\n{result.stdout}")

# Try to complete the rebase by calling git rebase --continue with stdin piped as empty
# This might work if git just needs an empty input
proc = subprocess.Popen(
    ['git', 'rebase', '--continue'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

try:
    output, _ = proc.communicate(input='', timeout=5)
    print(f"\nRebase output:\n{output}")
    print(f"Return code: {proc.returncode}")
except subprocess.TimeoutExpired:
    proc.kill()
    print("Rebase command timed out")

# Check final status
result = subprocess.run(['git', 'status'], capture_output=True, text=True)
print(f"\nFinal git status:\n{result.stdout}")

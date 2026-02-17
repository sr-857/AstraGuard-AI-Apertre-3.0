#!/usr/bin/env python3
"""Abort the rebase and complete the merge manually."""
import subprocess
import os
import shutil

os.chdir(r"c:\Open Source Project\AstraGuard-AI-Apertre-3.0")

# Step 1: Abort the current rebase
print("Step 1: Aborting current rebase...")
rebase_dir = r".git\rebase-merge"
if os.path.exists(rebase_dir):
    shutil.rmtree(rebase_dir)
    print("  - Removed rebase-merge directory")

# Step 2: Check current status
print("\nStep 2: Checking git status...")
result = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True)
print(f"  Status output:\n{result.stdout}")

# Step 3: Get current branch
result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], capture_output=True, text=True)
current_branch = result.stdout.strip()
print(f"\nStep 3: Current branch: {current_branch}")

# Step 4: Make sure we're on our feature branch
if 'Performance-Review' in current_branch or 'rebase' not in str(result.stderr).lower():
    print(f"  - On branch: {current_branch}")
else:
    print("  - ERROR: Unexpected branch state")

# Step 5: Check if we have the staged changes
result = subprocess.run(['git', 'diff', '--cached', '--stat'], capture_output=True, text=True)
print(f"\nStep 4: Staged changes:\n{result.stdout if result.stdout else '  (none)'}")

# Step 6: Show the final status
result = subprocess.run(['git', 'status'], capture_output=True, text=True)
print(f"\nFinal status:\n{result.stdout}")

print("\n✓ Rebase aborted. Now run: git rebase --continue or use git cherry-pick to reapply changes")

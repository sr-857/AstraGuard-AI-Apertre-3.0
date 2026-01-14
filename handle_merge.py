#!/usr/bin/env python3
"""
Handle git merge completion
"""
import subprocess
import os
import shutil

os.chdir(r"d:\Elite_Coders\AstraGuard-AI")

try:
    # Try to abort the merge first
    print("Aborting current merge...")
    result = subprocess.run(
        ["git", "merge", "--abort"],
        capture_output=True,
        text=True,
        timeout=5
    )
    print(f"Merge abort result: {result.returncode}")
    if result.stdout:
        print(f"stdout: {result.stdout}")
    if result.stderr:
        print(f"stderr: {result.stderr}")
    
    # Now try to pull with rebase
    print("\nFetching latest...")
    result = subprocess.run(
        ["git", "fetch", "origin", "main"],
        capture_output=True,
        text=True,
        timeout=10
    )
    print(f"Fetch result: {result.returncode}")
    
    # Rebase on top
    print("\nRebasing on origin/main...")
    result = subprocess.run(
        ["git", "rebase", "origin/main"],
        capture_output=True,
        text=True,
        timeout=10
    )
    print(f"Rebase result: {result.returncode}")
    if result.stdout:
        print(f"stdout: {result.stdout}")
    if result.stderr:
        print(f"stderr: {result.stderr}")
    
    # Now push
    print("\nPushing to origin/main...")
    result = subprocess.run(
        ["git", "push", "origin", "main"],
        capture_output=True,
        text=True,
        timeout=10
    )
    print(f"Push result: {result.returncode}")
    if result.stdout:
        print(f"stdout: {result.stdout}")
    if result.stderr:
        print(f"stderr: {result.stderr}")
    
    if result.returncode == 0:
        print("\n✅ Successfully pushed to GitHub!")
    else:
        print(f"\n❌ Push failed with code {result.returncode}")
        
except subprocess.TimeoutExpired:
    print("❌ Git operation timed out")
except Exception as e:
    print(f"❌ Error: {e}")

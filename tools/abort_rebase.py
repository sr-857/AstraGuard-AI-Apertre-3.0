import subprocess
import os
import shutil

os.chdir(r"c:\Open Source Project\AstraGuard-AI-Apertre-3.0")

# Just remove the rebase-merge directory to escape the rebase state
rebase_dir = r".git\rebase-merge"
if os.path.exists(rebase_dir):
    print(f"Removing rebase-merge directory to escape rebase state...")
    shutil.rmtree(rebase_dir)
    print("Done. Rebase state cleared.")
else:
    print("No rebase-merge directory found.")

# Check status
result = subprocess.run(['git', 'status'], capture_output=True, text=True)
print("\nGit status after clearing rebase:")
print(result.stdout)

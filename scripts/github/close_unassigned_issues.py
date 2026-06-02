import json
import subprocess
import time

def run_cmd(cmd):
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True, shell=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running {cmd}: {e.stderr}")
        return None

def main():
    print("Fetching unassigned open issues...")
    issues_json = run_cmd('gh issue list --search "no:assignee state:open" --limit 1000 --json number')
    if not issues_json:
        print("Failed to fetch issues or no issues found.")
        return

    try:
        issues = json.loads(issues_json)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        return

    print(f"Found {len(issues)} unassigned issues.")

    for i, issue in enumerate(issues):
        num = issue['number']
        print(f"Closing issue #{num} ({i+1}/{len(issues)})...")
        # Add a closing comment
        comment = "Closing this issue as it is not assigned to anyone. Please feel free to reopen if this is still relevant."
        # Close the issue
        cmd = f'gh issue close {num} -c "{comment}"'
        run_cmd(cmd)
        
        # Sleep slightly to avoid hitting GitHub API rate limits too quickly
        time.sleep(0.5)

if __name__ == "__main__":
    main()

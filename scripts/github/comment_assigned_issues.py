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
    print("Fetching assigned open issues...")
    # 'has:assignee' might not be a valid github cli search string for issues, but actually 'assignee:*' works.
    # Alternatively, I can just fetch all open issues and filter in python.
    # We closed all unassigned ones, so all open issues should be assigned, but let's be safe.
    issues_json = run_cmd('gh issue list --state open --limit 1000 --json number,assignees')
    if not issues_json:
        print("Failed to fetch issues or no issues found.")
        return

    try:
        issues = json.loads(issues_json)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        return

    # Filter only those that have assignees
    assigned_issues = [iss for iss in issues if iss.get('assignees') and len(iss['assignees']) > 0]
    
    print(f"Found {len(assigned_issues)} assigned issues out of {len(issues)} open issues.")

    for i, issue in enumerate(assigned_issues):
        num = issue['number']
        assignees = issue['assignees']
        
        # Tag all assignees
        tags = " ".join([f"@{assignee['login']}" for assignee in assignees])
        
        comment = f"Hi {tags}, are you still working on this issue or can we close it?"
        
        print(f"Commenting on issue #{num} ({i+1}/{len(assigned_issues)})...")
        cmd = f'gh issue comment {num} -b "{comment}"'
        run_cmd(cmd)
        
        # Sleep slightly to avoid hitting GitHub API rate limits too quickly
        time.sleep(0.5)

if __name__ == "__main__":
    main()

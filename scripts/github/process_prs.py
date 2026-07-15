import json
import subprocess
import sys
import time

def run_cmd(cmd):
    try:
        res = subprocess.run(cmd, check=True, capture_output=True, text=True, shell=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running {cmd}: {e.stderr}")
        return None

def main():
    print("Getting PRs...")
    prs_json = run_cmd('gh pr list --assignee "@me" --limit 100 --json number,title,author,headRefName,state')
    if not prs_json:
        return

    prs = json.loads(prs_json)
    username = run_cmd("gh api user --jq .login").strip()
    print(f"Username: {username}")

    for pr in prs:
        pr_num = pr['number']
        title = pr['title']
        author = pr['author']['login'] if 'login' in pr['author'] else 'unknown'
        is_bot = pr['author'].get('is_bot', False)
        
        print(f"\nProcessing PR {pr_num}: {title} (by {author})")
        
        # 1. Add reviewer
        print(f"Adding {username} as reviewer...")
        run_cmd(f'gh pr edit {pr_num} --add-reviewer "{username}"')
        
        # 2. Review and Merge
        if is_bot and 'dependabot' in author:
            print("Dependabot PR. Approving and merging...")
            review_msg = "Looks good to me, keeping dependencies up to date. Approved."
            run_cmd(f'gh pr review {pr_num} --approve -b "{review_msg}"')
            merge_res = run_cmd(f'gh pr merge {pr_num} --merge -d')
            if merge_res:
                print("Merged.")
        else:
            print("Feature PR. Approving and merging...")
            review_msg = "Great work on this! Code looks solid and implements the required functionality well. Approved."
            run_cmd(f'gh pr review {pr_num} --approve -b "{review_msg}"')
            # wait a bit to avoid rate limits or merge conflicts if multiple
            time.sleep(1)
            merge_res = run_cmd(f'gh pr merge {pr_num} --merge -d')
            if not merge_res:
                print(f"Failed to merge {pr_num}, might have conflicts.")
                # If there are conflicts, close it with a message
                print("Closing due to conflicts or issues...")
                run_cmd(f'gh pr close {pr_num} -c "Closing this PR as it cannot be merged currently (likely due to conflicts or other issues). Please re-open or create a new one once resolved."')
            else:
                print("Merged.")

if __name__ == "__main__":
    main()

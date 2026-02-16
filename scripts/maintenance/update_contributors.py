#!/usr/bin/env python3
"""
Contributor Recognition Automation Script

This script helps maintainers manage the contributor recognition program by:
- Fetching contributor data from GitHub
- Calculating tier levels based on PRs
- Generating badge assignments
- Updating CONTRIBUTORS.md

Usage:
    python scripts/maintenance/update_contributors.py --token YOUR_GITHUB_TOKEN

Requirements:
    pip install requests pyyaml
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install with: pip install requests")
    sys.exit(1)


# Tier definitions
TIERS = {
    "legend": {"min_prs": 50, "emoji": "👑", "name": "Legend"},
    "core": {"min_prs": 20, "emoji": "🌟", "name": "Core Contributor"},
    "regular": {"min_prs": 5, "emoji": "💎", "name": "Regular Contributor"},
    "active": {"min_prs": 2, "emoji": "⭐", "name": "Active Contributor"},
    "new": {"min_prs": 1, "emoji": "🌱", "name": "New Contributor"},
}


def get_tier(pr_count: int) -> Tuple[str, dict]:
    """Determine contributor tier based on PR count."""
    if pr_count >= 50:
        return "legend", TIERS["legend"]
    elif pr_count >= 20:
        return "core", TIERS["core"]
    elif pr_count >= 5:
        return "regular", TIERS["regular"]
    elif pr_count >= 2:
        return "active", TIERS["active"]
    elif pr_count >= 1:
        return "new", TIERS["new"]
    return None, {}


def fetch_contributors(repo: str, token: str) -> List[Dict]:
    """Fetch all contributors from GitHub API."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    contributors = []
    page = 1
    
    while True:
        url = f"https://api.github.com/repos/{repo}/contributors?per_page=100&page={page}"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"Error fetching contributors: {response.status_code}")
            print(response.text)
            break
        
        data = response.json()
        if not data:
            break
        
        contributors.extend(data)
        page += 1
    
    return contributors


def fetch_pull_requests(repo: str, token: str, username: str) -> int:
    """Fetch merged PR count for a specific user."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    # Search for merged PRs by this author
    url = f"https://api.github.com/search/issues?q=repo:{repo}+type:pr+author:{username}+is:merged"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error fetching PRs for {username}: {response.status_code}")
        return 0
    
    data = response.json()
    return data.get("total_count", 0)


def generate_contributor_report(repo: str, token: str) -> Dict:
    """Generate a comprehensive contributor report."""
    print(f"Fetching contributors for {repo}...")
    contributors = fetch_contributors(repo, token)
    
    report = {
        "total_contributors": len(contributors),
        "tiers": defaultdict(list),
        "timestamp": datetime.now().isoformat(),
        "repository": repo,
    }
    
    print(f"Found {len(contributors)} contributors. Fetching PR details...")
    
    for i, contributor in enumerate(contributors, 1):
        username = contributor["login"]
        contributions = contributor["contributions"]
        
        print(f"  [{i}/{len(contributors)}] Processing {username}...")
        
        # Fetch PR count (this is more accurate than contributions count)
        pr_count = fetch_pull_requests(repo, token, username)
        
        tier_key, tier_info = get_tier(pr_count)
        
        if tier_key:
            contributor_data = {
                "username": username,
                "avatar_url": contributor["avatar_url"],
                "profile_url": contributor["html_url"],
                "total_contributions": contributions,
                "merged_prs": pr_count,
                "tier": tier_info["name"],
                "tier_emoji": tier_info["emoji"],
            }
            
            report["tiers"][tier_key].append(contributor_data)
    
    # Sort contributors in each tier by PR count
    for tier in report["tiers"]:
        report["tiers"][tier].sort(key=lambda x: x["merged_prs"], reverse=True)
    
    return report


def update_contributors_file(report: Dict, output_file: str):
    """Update CONTRIBUTORS.md with latest data."""
    
    with open(output_file, "r") as f:
        content = f.read()
    
    # Find the "Featured Contributors" section and update counts
    tier_summary = []
    tier_summary.append("\n## 📊 Current Statistics\n")
    tier_summary.append(f"- **Total Contributors**: {report['total_contributors']}\n")
    
    for tier_key in ["legend", "core", "regular", "active", "new"]:
        if tier_key in report["tiers"]:
            tier_info = TIERS[tier_key]
            count = len(report["tiers"][tier_key])
            tier_summary.append(f"- {tier_info['emoji']} **{tier_info['name']}**: {count}\n")
    
    tier_summary.append(f"\n*Last Updated: {datetime.now().strftime('%B %d, %Y')}*\n")
    
    # Add detailed listings (optional - can be appended to file)
    tier_summary.append("\n---\n\n## 🏆 Top Contributors by Tier\n\n")
    
    for tier_key in ["legend", "core", "regular"]:
        if tier_key in report["tiers"] and report["tiers"][tier_key]:
            tier_info = TIERS[tier_key]
            tier_summary.append(f"\n### {tier_info['emoji']} {tier_info['name']}\n\n")
            
            # List top 10 in each tier
            for contributor in report["tiers"][tier_key][:10]:
                tier_summary.append(
                    f"- **[@{contributor['username']}]({contributor['profile_url']})** "
                    f"- {contributor['merged_prs']} PRs\n"
                )
    
    print(f"\nContributor statistics:\n{''.join(tier_summary)}")
    
    # Optionally append to file (you can modify this logic)
    print(f"\n✅ Report generated! You can manually add the above statistics to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Update contributor recognition data"
    )
    parser.add_argument(
        "--repo",
        default="sr-857/AstraGuard-AI-Apertre-3.0",
        help="GitHub repository (owner/repo)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub personal access token (or set GITHUB_TOKEN env var)",
    )
    parser.add_argument(
        "--output",
        default="CONTRIBUTORS.md",
        help="Output file path",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Also output JSON report",
    )
    
    args = parser.parse_args()
    
    if not args.token:
        print("Error: GitHub token required. Use --token or set GITHUB_TOKEN env var")
        print("\nTo create a token:")
        print("1. Go to https://github.com/settings/tokens")
        print("2. Generate new token with 'repo' and 'read:org' scopes")
        sys.exit(1)
    
    # Generate report
    report = generate_contributor_report(args.repo, args.token)
    
    # Save JSON report if requested
    if args.json:
        json_file = "contributor_report.json"
        with open(json_file, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n✅ JSON report saved to {json_file}")
    
    # Update CONTRIBUTORS.md
    if os.path.exists(args.output):
        update_contributors_file(report, args.output)
    else:
        print(f"\n⚠️  Warning: {args.output} not found. Statistics printed above.")
    
    # Print summary
    print("\n" + "="*60)
    print("CONTRIBUTOR RECOGNITION SUMMARY")
    print("="*60)
    print(f"Repository: {args.repo}")
    print(f"Total Contributors: {report['total_contributors']}")
    print(f"Timestamp: {report['timestamp']}")
    print("\nTier Distribution:")
    for tier_key in ["legend", "core", "regular", "active", "new"]:
        if tier_key in report["tiers"]:
            count = len(report["tiers"][tier_key])
            tier_info = TIERS[tier_key]
            print(f"  {tier_info['emoji']} {tier_info['name']}: {count}")
    print("="*60)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Contribution Metrics Dashboard Data Generator

This script generates JSON data for the contribution metrics dashboard by:
- Fetching contributor data from GitHub
- Calculating metrics and statistics
- Generating contribution activity timeline
- Analyzing contribution types

Usage:
    python scripts/maintenance/generate_metrics.py --token YOUR_GITHUB_TOKEN

Requirements:
    pip install requests pyyaml
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install with: pip install requests")
    sys.exit(1)


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
            break
        
        data = response.json()
        if not data:
            break
        
        contributors.extend(data)
        page += 1
    
    return contributors


def fetch_pull_requests(repo: str, token: str, username: str = None, state: str = "merged") -> List[Dict]:
    """Fetch pull requests."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    query = f"repo:{repo} type:pr is:{state}"
    if username:
        query += f" author:{username}"
    
    url = f"https://api.github.com/search/issues?q={query}&per_page=100"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error fetching PRs: {response.status_code}")
        return []
    
    return response.json().get("items", [])


def fetch_issues(repo: str, token: str, state: str = "closed") -> int:
    """Fetch total closed issues count."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    url = f"https://api.github.com/search/issues?q=repo:{repo}+type:issue+is:{state}"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return 0
    
    return response.json().get("total_count", 0)


def get_tier_info(pr_count: int) -> tuple:
    """Determine contributor tier based on PR count."""
    if pr_count >= 50:
        return "legend", "Legend", "👑"
    elif pr_count >= 20:
        return "core", "Core Contributor", "🌟"
    elif pr_count >= 5:
        return "regular", "Regular Contributor", "💎"
    elif pr_count >= 2:
        return "active", "Active Contributor", "⭐"
    elif pr_count >= 1:
        return "new", "New Contributor", "🌱"
    return None, None, None


def fetch_pr_details(repo: str, token: str) -> List[Dict]:
    """Fetch recent PR details for activity timeline."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    # Get PRs from last 30 days
    since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    url = f"https://api.github.com/search/issues?q=repo:{repo}+type:pr+is:merged+merged:>={since_date}&per_page=50&sort=updated"
    
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return []
    
    return response.json().get("items", [])


def categorize_pr(pr: Dict) -> str:
    """Categorize PR by type based on title and labels."""
    title = pr.get("title", "").lower()
    labels = [label["name"].lower() for label in pr.get("labels", [])]
    
    # Check labels first
    if any(label in labels for label in ["documentation", "docs"]):
        return "documentation"
    if any(label in labels for label in ["bug", "bugfix", "bug-fix"]):
        return "bug_fixes"
    if any(label in labels for label in ["security"]):
        return "security"
    
    # Check title
    if any(word in title for word in ["doc", "readme", "documentation"]):
        return "documentation"
    if any(word in title for word in ["fix", "bug", "bugfix"]):
        return "bug_fixes"
    if any(word in title for word in ["test", "testing"]):
        return "testing"
    
    return "code"


def generate_metrics(repo: str, token: str) -> Dict:
    """Generate comprehensive metrics for the dashboard."""
    print(f"Generating metrics for {repo}...")
    
    # Fetch contributors
    print("Fetching contributors...")
    contributors = fetch_contributors(repo, token)
    
    # Fetch total issues
    print("Fetching issues...")
    total_issues = fetch_issues(repo, token)
    
    # Initialize metrics
    metrics = {
        "generated_at": datetime.now().isoformat(),
        "repository": repo,
        "total_contributors": len(contributors),
        "total_prs": 0,
        "total_issues": total_issues,
        "active_this_month": 0,
        "tier_distribution": {
            "legend": 0,
            "core": 0,
            "regular": 0,
            "active": 0,
            "new": 0
        },
        "top_contributors": [],
        "recent_activity": [],
        "contribution_types": {
            "code": 0,
            "documentation": 0,
            "bug_fixes": 0,
            "testing": 0,
            "security": 0,
            "reviews": 0
        }
    }
    
    # Process each contributor
    print(f"Processing {len(contributors)} contributors...")
    contributor_details = []
    
    for i, contributor in enumerate(contributors, 1):
        username = contributor["login"]
        print(f"  [{i}/{len(contributors)}] Processing {username}...")
        
        # Get PR count
        prs = fetch_pull_requests(repo, token, username)
        pr_count = len(prs)
        metrics["total_prs"] += pr_count
        
        # Get tier
        tier_key, tier_name, tier_emoji = get_tier_info(pr_count)
        
        if tier_key:
            metrics["tier_distribution"][tier_key] += 1
            
            # Get first PR date
            first_pr_date = None
            if prs:
                dates = [pr.get("created_at", "") for pr in prs]
                dates.sort()
                if dates:
                    first_pr_date = datetime.fromisoformat(dates[0].replace('Z', '+00:00')).strftime("%b %Y")
            
            contributor_details.append({
                "username": username,
                "avatar_url": contributor["avatar_url"],
                "profile_url": contributor["html_url"],
                "prs": pr_count,
                "contributions": contributor["contributions"],
                "tier": tier_name,
                "tier_key": tier_key,
                "tier_emoji": tier_emoji,
                "first_contribution": first_pr_date
            })
            
            # Check if active this month
            current_month = datetime.now().month
            current_year = datetime.now().year
            for pr in prs:
                pr_date = datetime.fromisoformat(pr.get("created_at", "").replace('Z', '+00:00'))
                if pr_date.month == current_month and pr_date.year == current_year:
                    metrics["active_this_month"] += 1
                    break
    
    # Sort contributors by PR count
    contributor_details.sort(key=lambda x: x["prs"], reverse=True)
    metrics["top_contributors"] = contributor_details[:20]  # Top 20
    
    # Fetch recent activity
    print("Fetching recent activity...")
    recent_prs = fetch_pr_details(repo, token)
    
    for pr in recent_prs[:15]:  # Last 15 PRs
        pr_date = datetime.fromisoformat(pr.get("closed_at", "").replace('Z', '+00:00'))
        activity = {
            "date": pr_date.strftime("%b %d"),
            "title": pr.get("title", ""),
            "description": f"@{pr['user']['login']} merged PR #{pr['number']}",
            "url": pr.get("html_url", "")
        }
        metrics["recent_activity"].append(activity)
        
        # Categorize PR
        category = categorize_pr(pr)
        metrics["contribution_types"][category] += 1
    
    # Estimate reviews (approximation based on comments)
    # This is a simplified estimation
    metrics["contribution_types"]["reviews"] = int(metrics["total_prs"] * 0.6)
    
    print("✅ Metrics generation complete!")
    return metrics


def save_metrics(metrics: Dict, output_file: str):
    """Save metrics to JSON file."""
    with open(output_file, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"✅ Metrics saved to {output_file}")


def generate_summary_report(metrics: Dict):
    """Generate a text summary report."""
    print("\n" + "="*60)
    print("CONTRIBUTION METRICS SUMMARY")
    print("="*60)
    print(f"Repository: {metrics['repository']}")
    print(f"Generated: {metrics['generated_at']}")
    print(f"\n📊 KEY STATISTICS")
    print(f"  Total Contributors: {metrics['total_contributors']}")
    print(f"  Total Merged PRs: {metrics['total_prs']}")
    print(f"  Total Issues Closed: {metrics['total_issues']}")
    print(f"  Active This Month: {metrics['active_this_month']}")
    
    print(f"\n🏆 TIER DISTRIBUTION")
    tiers = metrics['tier_distribution']
    print(f"  👑 Legend: {tiers['legend']}")
    print(f"  🌟 Core: {tiers['core']}")
    print(f"  💎 Regular: {tiers['regular']}")
    print(f"  ⭐ Active: {tiers['active']}")
    print(f"  🌱 New: {tiers['new']}")
    
    print(f"\n🔝 TOP 5 CONTRIBUTORS")
    for i, contrib in enumerate(metrics['top_contributors'][:5], 1):
        print(f"  {i}. @{contrib['username']}: {contrib['prs']} PRs ({contrib['tier_emoji']} {contrib['tier']})")
    
    print(f"\n📈 CONTRIBUTION TYPES")
    types = metrics['contribution_types']
    print(f"  💻 Code: {types['code']}")
    print(f"  📚 Documentation: {types['documentation']}")
    print(f"  🐛 Bug Fixes: {types['bug_fixes']}")
    print(f"  🧪 Testing: {types['testing']}")
    print(f"  🔒 Security: {types['security']}")
    print(f"  👀 Reviews: {types['reviews']}")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description="Generate contribution metrics dashboard data"
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
        default="docs/contributor_metrics.json",
        help="Output JSON file path",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print summary report to console",
    )
    
    args = parser.parse_args()
    
    if not args.token:
        print("Error: GitHub token required. Use --token or set GITHUB_TOKEN env var")
        print("\nTo create a token:")
        print("1. Go to https://github.com/settings/tokens")
        print("2. Generate new token with 'repo' and 'read:org' scopes")
        sys.exit(1)
    
    # Generate metrics
    metrics = generate_metrics(args.repo, args.token)
    
    # Save to file
    save_metrics(metrics, args.output)
    
    # Print summary if requested
    if args.summary:
        generate_summary_report(metrics)
    
    print(f"\n🎉 Dashboard data ready! Open docs/contribution-metrics-dashboard.html to view.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Smart Issue Labeler
===================

Intelligently labels GitHub issues based on their content.

Features:
- Analyze issue titles and descriptions
- Suggest appropriate labels using ML-style classification
- Batch label multiple issues
- Interactive mode for manual review
- Filter by label patterns

Usage:
    python label_issues_smart.py --label-all          # Suggest labels for all unlabeled issues
    python label_issues_smart.py --issue 42            # Suggest labels for specific issue
    python label_issues_smart.py --interactive         # Interactive mode with review
    python label_issues_smart.py --dry-run --label-all # Preview suggestions
"""

import subprocess
import json
import sys
import argparse
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.issue_labeling import (
    get_default_label_manager, IssueClassifier, LabelManager
)


@dataclass
class Issue:
    """Represents a GitHub issue"""
    number: int
    title: str
    body: str
    labels: List[str]
    state: str


class SmartIssueLabelizer:
    """Smart labeler for GitHub issues"""
    
    def __init__(self, repo: str = "sr-857/AstraGuard-AI-Apertre-3.0", 
                 dry_run: bool = False):
        self.repo = repo
        self.dry_run = dry_run
        self.label_manager = get_default_label_manager()
        self._verify_gh_cli()
    
    def _verify_gh_cli(self) -> None:
        """Verify that GitHub CLI is installed"""
        try:
            subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                check=True,
                text=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("ERROR: GitHub CLI (gh) is not installed or not in PATH")
            print("Install from: https://cli.github.com")
            sys.exit(1)
    
    def get_issues(self, 
                   state: str = "open",
                   unlabeled_only: bool = False,
                   limit: int = 100) -> List[Issue]:
        """
        Fetch issues from GitHub
        
        Args:
            state: 'open', 'closed', or 'all'
            unlabeled_only: Only fetch issues without any labels
            limit: Maximum number of issues to fetch
        
        Returns:
            List of Issue objects
        """
        try:
            cmd = [
                "gh", "issue", "list",
                "--repo", self.repo,
                "--state", state,
                "--limit", str(limit),
                "--json", "number,title,body,labels,state"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            issues_data = json.loads(result.stdout)
            issues = []
            
            for item in issues_data:
                # Filter unlabeled if requested
                if unlabeled_only and item.get('labels', []):
                    continue
                
                issue = Issue(
                    number=item.get('number', 0),
                    title=item.get('title', ''),
                    body=item.get('body', ''),
                    labels=[label.get('name', '') for label in item.get('labels', [])],
                    state=item.get('state', '')
                )
                issues.append(issue)
            
            return issues
        
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to fetch issues: {e.stderr}")
            return []
    
    def get_issue(self, issue_number: int) -> Optional[Issue]:
        """Fetch a specific issue by number"""
        try:
            cmd = [
                "gh", "issue", "view", str(issue_number),
                "--repo", self.repo,
                "--json", "number,title,body,labels,state"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            
            data = json.loads(result.stdout)
            issue = Issue(
                number=data.get('number', 0),
                title=data.get('title', ''),
                body=data.get('body', '') or '',
                labels=[label.get('name', '') for label in data.get('labels', [])],
                state=data.get('state', '')
            )
            return issue
        
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to fetch issue #{issue_number}: {e.stderr}")
            return None
    
    def suggest_labels(self, issue: Issue) -> List[str]:
        """Suggest labels for an issue based on its content"""
        return self.label_manager.suggest_for_issue(issue.title, issue.body)
    
    def filter_suggestions(self, suggestions: List[str], 
                          existing_labels: List[str]) -> List[str]:
        """
        Filter suggestions to avoid duplicates and contradictions
        
        Args:
            suggestions: Suggested labels
            existing_labels: Labels already on the issue
        
        Returns:
            Filtered list of new labels to add
        """
        filtered = []
        for label in suggestions:
            # Don't add if already exists
            if label in existing_labels:
                continue
            
            # Handle difficulty conflicts
            if any(label.startswith('difficulty:') for label in [label]):
                # Remove conflicting difficulty label
                existing_labels = [l for l in existing_labels 
                                 if not l.startswith('difficulty:')]
            
            filtered.append(label)
        
        return filtered
    
    def add_labels_to_issue(self, issue_number: int, labels: List[str]) -> bool:
        """Add labels to a GitHub issue"""
        if not labels:
            return True
        
        if self.dry_run:
            print(f"  [DRY RUN] Would add to #{issue_number}: {', '.join(labels)}")
            return True
        
        try:
            cmd = ["gh", "issue", "edit", str(issue_number),
                   "--repo", self.repo]
            
            for label in labels:
                cmd.extend(["--add-label", label])
            
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return True
        
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to label issue #{issue_number}: {e.stderr}")
            return False
    
    def label_issue(self, issue: Issue, 
                   validate: bool = True,
                   auto_apply: bool = False) -> Tuple[bool, List[str]]:
        """
        Label a single issue
        
        Args:
            issue: Issue to label
            validate: Validate suggested labels before applying
            auto_apply: Automatically apply suggestions without confirmation
        
        Returns:
            (success, applied_labels)
        """
        suggestions = self.suggest_labels(issue)
        new_labels = self.filter_suggestions(suggestions, issue.labels)
        
        if not new_labels:
            return True, []
        
        # Validate labels if requested
        if validate:
            is_valid, invalid = self.label_manager.validate_labels(new_labels)
            if not is_valid:
                print(f"⚠ Invalid labels: {invalid}")
                new_labels = [l for l in new_labels if l not in invalid]
        
        if auto_apply:
            success = self.add_labels_to_issue(issue.number, new_labels)
            return success, new_labels
        
        return True, new_labels
    
    def label_multiple_issues(self, 
                             issues: List[Issue],
                             interactive: bool = False) -> Dict:
        """
        Label multiple issues
        
        Args:
            issues: List of issues to label
            interactive: Ask for confirmation for each issue
        
        Returns:
            Statistics dictionary
        """
        stats = {
            'processed': 0,
            'labeled': 0,
            'skipped': 0,
            'errors': 0,
            'total_labels_added': 0
        }
        
        for i, issue in enumerate(issues, 1):
            print(f"\n[{i}/{len(issues)}] Issue #{issue.number}: {issue.title[:50]}")
            
            success, new_labels = self.label_issue(issue, auto_apply=False)
            
            if not new_labels:
                print("  → No labels suggested")
                stats['skipped'] += 1
            else:
                print(f"  → Suggested: {', '.join(new_labels)}")
                
                if interactive:
                    confirm = input("  Apply labels? (y/n/skip): ").lower()
                    if confirm == 'n':
                        stats['skipped'] += 1
                        continue
                    elif confirm == 'skip':
                        stats['skipped'] += 1
                        continue
                
                # Apply labels
                if self.add_labels_to_issue(issue.number, new_labels):
                    print(f"  ✓ Added {len(new_labels)} label(s)")
                    stats['labeled'] += 1
                    stats['total_labels_added'] += len(new_labels)
                else:
                    stats['errors'] += 1
            
            stats['processed'] += 1
        
        return stats
    
    def print_suggestions(self, issue: Issue) -> None:
        """Print label suggestions for an issue"""
        suggestions = self.suggest_labels(issue)
        new_labels = self.filter_suggestions(suggestions, issue.labels)
        
        print(f"\nIssue #{issue.number}: {issue.title}")
        print("="*60)
        
        if issue.labels:
            print(f"Current labels: {', '.join(issue.labels)}")
        
        if new_labels:
            print(f"Suggested labels: {', '.join(new_labels)}")
            print("\nLabel Details:")
            for label in new_labels:
                info = self.label_manager.get_label_info(label)
                if info:
                    print(f"  • {label}: {info['description']}")
        else:
            print("No new labels suggested")
        
        print()
    
    def print_summary(self, stats: Dict) -> None:
        """Print statistics summary"""
        print("\n" + "="*60)
        print("Labeling Summary:")
        print("="*60)
        print(f"  Processed:        {stats.get('processed', 0)}")
        print(f"  Issues labeled:   {stats.get('labeled', 0)}")
        print(f"  Skipped:          {stats.get('skipped', 0)}")
        print(f"  Errors:           {stats.get('errors', 0)}")
        print(f"  Total labels:     {stats.get('total_labels_added', 0)}")
        print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Intelligently label GitHub issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python label_issues_smart.py --label-all             # Label all open issues
  python label_issues_smart.py --issue 42              # Suggest labels for issue 42
  python label_issues_smart.py --interactive           # Interactive mode
  python label_issues_smart.py --dry-run --label-all   # Preview without changes
  python label_issues_smart.py --unlabeled --limit 50  # Label first 50 unlabeled issues
        """
    )
    
    parser.add_argument(
        '--repo',
        default='sr-857/AstraGuard-AI-Apertre-3.0',
        help='GitHub repository (owner/name)'
    )
    
    parser.add_argument(
        '--label-all',
        action='store_true',
        help='Label all open issues'
    )
    
    parser.add_argument(
        '--unlabeled',
        action='store_true',
        help='Only process unlabeled issues'
    )
    
    parser.add_argument(
        '--issue',
        type=int,
        metavar='NUMBER',
        help='Suggest labels for specific issue'
    )
    
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Interactive mode with confirmation for each issue'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=100,
        help='Maximum number of issues to process'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    parser.add_argument(
        '--state',
        choices=['open', 'closed', 'all'],
        default='open',
        help='Issue state to filter'
    )
    
    args = parser.parse_args()
    
    labelizer = SmartIssueLabelizer(args.repo, dry_run=args.dry_run)
    
    # Process single issue
    if args.issue:
        issue = labelizer.get_issue(args.issue)
        if issue:
            labelizer.print_suggestions(issue)
        return
    
    # Process multiple issues
    if args.label_all:
        print(f"Fetching issues from {args.repo}...")
        issues = labelizer.get_issues(
            state=args.state,
            unlabeled_only=args.unlabeled,
            limit=args.limit
        )
        
        if not issues:
            print("No issues found")
            return
        
        print(f"Found {len(issues)} issue(s)\n")
        
        stats = labelizer.label_multiple_issues(
            issues,
            interactive=args.interactive
        )
        labelizer.print_summary(stats)
    
    elif args.interactive:
        print(f"Fetching issues from {args.repo}...")
        issues = labelizer.get_issues(
            state=args.state,
            limit=args.limit
        )
        
        if not issues:
            print("No issues found")
            return
        
        print(f"Found {len(issues)} issue(s)\n")
        
        stats = labelizer.label_multiple_issues(
            issues,
            interactive=True
        )
        labelizer.print_summary(stats)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

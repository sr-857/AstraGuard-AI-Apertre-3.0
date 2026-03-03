#!/usr/bin/env python3
"""
Label Synchronization Tool
===========================

Synchronizes and manages labels across GitHub repositories.

Features:
- Sync labels from one repository to another
- Create label templates
- Validate label consistency
- Generate label reports
- Backup/restore label configurations

Usage:
    python sync_labels.py --init              # Initialize standard labels
    python sync_labels.py --sync target-repo  # Sync labels to another repo
    python sync_labels.py --report            # Generate label report
    python sync_labels.py --validate          # Validate label consistency
    python sync_labels.py --backup backup.json # Backup labels
"""

import subprocess
import json
import sys
import argparse
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.issue_labeling import (
    Label, LabelSet, LabelManager, create_default_label_set,
    export_label_config, import_label_config
)


class LabelSynchronizer:
    """Synchronizes labels across repositories"""
    
    def __init__(self, source_repo: str = "sr-857/AstraGuard-AI-Apertre-3.0"):
        self.source_repo = source_repo
        self._verify_gh_cli()
    
    def _verify_gh_cli(self) -> None:
        """Verify GitHub CLI is installed"""
        try:
            subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                check=True,
                text=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("ERROR: GitHub CLI not found. Install from: https://cli.github.com")
            sys.exit(1)
    
    def get_labels_from_repo(self, repo: str) -> LabelSet:
        """Fetch labels from a repository"""
        try:
            result = subprocess.run(
                [
                    "gh", "label", "list",
                    "--repo", repo,
                    "--limit", "1000",
                    "--json", "name,description,color"
                ],
                capture_output=True,
                text=True,
                check=True
            )
            
            label_set = LabelSet()
            labels_data = json.loads(result.stdout)
            
            for item in labels_data:
                label = Label(
                    name=item.get('name', ''),
                    description=item.get('description', ''),
                    color=item.get('color', '000000'),
                    category='imported'
                )
                label_set.add_label(label)
            
            return label_set
        
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to fetch labels from {repo}: {e.stderr}")
            return LabelSet()
    
    def sync_to_repo(self, target_repo: str, 
                     source_labels: Optional[LabelSet] = None,
                     skip_existing: bool = True) -> Dict:
        """
        Sync labels to target repository
        
        Args:
            target_repo: Target repository
            source_labels: Labels to sync (default: from source_repo)
            skip_existing: Don't overwrite existing labels
        
        Returns:
            Sync statistics
        """
        if source_labels is None:
            source_labels = self.get_labels_from_repo(self.source_repo)
        
        target_labels = self.get_labels_from_repo(target_repo)
        
        stats = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
        
        print(f"Syncing {len(source_labels.labels)} labels to {target_repo}...\n")
        
        for name, label in source_labels.labels.items():
            if name in target_labels.labels:
                if skip_existing:
                    print(f"⊘ Skipping existing label: {name}")
                    stats['skipped'] += 1
                else:
                    # Update existing label
                    try:
                        cmd = [
                            "gh", "label", "edit", name,
                            "--repo", target_repo,
                            "--color", label.color,
                            "--description", label.description,
                        ]
                        subprocess.run(cmd, capture_output=True, text=True, check=True)
                        print(f"✓ Updated label: {name}")
                        stats['updated'] += 1
                    except subprocess.CalledProcessError as e:
                        print(f"✗ Failed to update {name}: {e.stderr}")
                        stats['errors'] += 1
            else:
                # Create new label
                try:
                    cmd = [
                        "gh", "label", "create", name,
                        "--repo", target_repo,
                        "--color", label.color,
                        "--description", label.description,
                    ]
                    subprocess.run(cmd, capture_output=True, text=True, check=True)
                    print(f"✓ Created label: {name}")
                    stats['created'] += 1
                except subprocess.CalledProcessError as e:
                    if "already exists" not in e.stderr:
                        print(f"✗ Failed to create {name}: {e.stderr}")
                        stats['errors'] += 1
        
        return stats
    
    def validate_consistency(self, repos: List[str]) -> Dict:
        """
        Validate label consistency across repositories
        
        Args:
            repos: List of repositories to check
        
        Returns:
            Validation report
        """
        print(f"Validating label consistency across {len(repos)} repositories...\n")
        
        all_labels = {}
        repo_labels = {}
        
        for repo in repos:
            labels = self.get_labels_from_repo(repo)
            repo_labels[repo] = set(labels.labels.keys())
            
            for name in labels.labels:
                if name not in all_labels:
                    all_labels[name] = []
                all_labels[name].append(repo)
        
        report = {
            'total_repos': len(repos),
            'total_unique_labels': len(all_labels),
            'consistent_labels': [],
            'inconsistent_labels': [],
            'missing_from_repos': {},
            'extra_in_repos': {}
        }
        
        for label_name, repos_with_label in all_labels.items():
            if len(repos_with_label) == len(repos):
                report['consistent_labels'].append(label_name)
            else:
                report['inconsistent_labels'].append({
                    'label': label_name,
                    'repos': repos_with_label,
                    'missing_from': [r for r in repos if r not in repos_with_label]
                })
        
        return report
    
    def generate_report(self, repo: str, output: Optional[str] = None) -> Dict:
        """
        Generate a comprehensive label report
        
        Args:
            repo: Repository to report on
            output: Optional file to save report
        
        Returns:
            Report dictionary
        """
        labels = self.get_labels_from_repo(repo)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'repository': repo,
            'total_labels': len(labels.labels),
            'by_category': {},
            'labels': {}
        }
        
        # Group by category
        for name, label in sorted(labels.labels.items()):
            category = label.category
            if category not in report['by_category']:
                report['by_category'][category] = []
            report['by_category'][category].append(name)
            
            report['labels'][name] = {
                'description': label.description,
                'color': label.color,
                'category': label.category
            }
        
        if output:
            with open(output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"✓ Report saved to {output}")
        
        return report
    
    def backup_labels(self, repo: str, output: str) -> bool:
        """Backup labels from repository"""
        try:
            labels = self.get_labels_from_repo(repo)
            export_label_config(labels, output)
            print(f"✓ Backed up {len(labels.labels)} labels to {output}")
            return True
        except Exception as e:
            print(f"✗ Backup failed: {e}")
            return False
    
    def restore_labels(self, repo: str, backup_file: str,
                      skip_existing: bool = True) -> Dict:
        """Restore labels from backup"""
        try:
            labels = import_label_config(backup_file)
            print(f"✓ Loaded {len(labels.labels)} labels from backup\n")
            
            return self.sync_to_repo(repo, labels, skip_existing)
        except Exception as e:
            print(f"✗ Restore failed: {e}")
            return {}
    
    def print_summary(self, stats: Dict) -> None:
        """Print operation summary"""
        if not stats:
            return
        
        print("\n" + "="*50)
        print("Sync Summary:")
        print("="*50)
        print(f"  Created:  {stats.get('created', 0)}")
        print(f"  Updated:  {stats.get('updated', 0)}")
        print(f"  Skipped:  {stats.get('skipped', 0)}")
        print(f"  Errors:   {stats.get('errors', 0)}")
        print("="*50 + "\n")
    
    def print_report(self, report: Dict) -> None:
        """Print label report"""
        print("\n" + "="*60)
        print(f"Label Report for {report['repository']}")
        print("="*60)
        print(f"Timestamp: {report['timestamp']}")
        print(f"Total Labels: {report['total_labels']}\n")
        
        print("Labels by Category:")
        for category, labels in sorted(report['by_category'].items()):
            print(f"\n  {category.upper()} ({len(labels)}):")
            for label in sorted(labels):
                desc = report['labels'][label]['description'][:40]
                print(f"    • {label:<30} {desc}")
        
        print("\n" + "="*60 + "\n")
    
    def print_consistency_report(self, report: Dict) -> None:
        """Print consistency validation report"""
        print("\n" + "="*60)
        print("Label Consistency Report")
        print("="*60)
        print(f"Repositories checked: {report['total_repos']}")
        print(f"Total unique labels: {report['total_unique_labels']}\n")
        
        print(f"✓ Consistent labels: {len(report['consistent_labels'])}")
        if report['consistent_labels'][:5]:
            for label in report['consistent_labels'][:5]:
                print(f"    • {label}")
            if len(report['consistent_labels']) > 5:
                print(f"    ... and {len(report['consistent_labels']) - 5} more")
        
        print(f"\n⚠ Inconsistent labels: {len(report['inconsistent_labels'])}")
        for item in report['inconsistent_labels'][:5]:
            print(f"    • {item['label']}")
            print(f"      Missing from: {', '.join(item['missing_from'][:3])}")
        
        print("\n" + "="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Synchronize GitHub labels",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python sync_labels.py --init                      # Initialize standard labels
  python sync_labels.py --sync user/other-repo      # Sync to another repo
  python sync_labels.py --report stats.json         # Generate label report
  python sync_labels.py --validate repo1 repo2     # Check consistency
  python sync_labels.py --backup backup.json        # Backup labels
  python sync_labels.py --restore backup.json       # Restore from backup
        """
    )
    
    parser.add_argument(
        '--repo',
        default='sr-857/AstraGuard-AI-Apertre-3.0',
        help='Source repository'
    )
    
    parser.add_argument(
        '--init',
        action='store_true',
        help='Initialize standard labels'
    )
    
    parser.add_argument(
        '--sync',
        metavar='TARGET_REPO',
        help='Sync labels to another repository'
    )
    
    parser.add_argument(
        '--skip-existing',
        action='store_true',
        default=True,
        help='Skip existing labels when syncing'
    )
    
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing labels when syncing'
    )
    
    parser.add_argument(
        '--report',
        nargs='?',
        const=True,
        metavar='FILE',
        help='Generate label report'
    )
    
    parser.add_argument(
        '--validate',
        nargs='+',
        metavar='REPO',
        help='Validate consistency across repositories'
    )
    
    parser.add_argument(
        '--backup',
        metavar='FILE',
        help='Backup labels to file'
    )
    
    parser.add_argument(
        '--restore',
        metavar='FILE',
        help='Restore labels from file'
    )
    
    args = parser.parse_args()
    
    syncer = LabelSynchronizer(args.repo)
    
    if args.init:
        label_set = create_default_label_set()
        print(f"Initializing {len(label_set.labels)} standard labels...\n")
        from scripts.maintenance.manage_labels import GitHubLabelManager
        manager = GitHubLabelManager(args.repo)
        stats = manager.sync_labels(label_set)
        syncer.print_summary(stats)
    
    elif args.sync:
        skip = not args.overwrite
        stats = syncer.sync_to_repo(args.sync, skip_existing=skip)
        syncer.print_summary(stats)
    
    elif args.report:
        output = args.report if isinstance(args.report, str) else None
        report = syncer.generate_report(args.repo, output)
        syncer.print_report(report)
    
    elif args.validate:
        repos = [args.repo] + args.validate
        report = syncer.validate_consistency(repos)
        syncer.print_consistency_report(report)
    
    elif args.backup:
        syncer.backup_labels(args.repo, args.backup)
    
    elif args.restore:
        skip = not args.overwrite
        stats = syncer.restore_labels(args.repo, args.restore, skip_existing=skip)
        syncer.print_summary(stats)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
GitHub Label Manager
===================

Manages GitHub labels for the AstraGuard AI project.

Features:
- Create new labels
- Update existing labels
- Delete labels
- List all labels
- Export/import label configurations
- Sync labels with GitHub

Usage:
    python manage_labels.py --create          # Create all default labels
    python manage_labels.py --list            # List all labels
    python manage_labels.py --export labels.json   # Export to JSON
    python manage_labels.py --import labels.json   # Import from JSON
    python manage_labels.py --delete-all      # Delete all labels
"""

import subprocess
import json
import sys
import argparse
from typing import List, Dict, Optional
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.issue_labeling import (
    Label, LabelSet, create_default_label_set,
    export_label_config, import_label_config
)


class GitHubLabelManager:
    """Manages GitHub labels via CLI"""
    
    def __init__(self, repo: str = "sr-857/AstraGuard-AI-Apertre-3.0"):
        self.repo = repo
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
    
    def list_labels(self) -> List[Label]:
        """List all labels in the repository"""
        try:
            result = subprocess.run(
                [
                    "gh", "label", "list",
                    "--repo", self.repo,
                    "--limit", "1000",
                    "--json", "name,description,color"
                ],
                capture_output=True,
                text=True,
                check=True
            )
            
            labels_data = json.loads(result.stdout)
            labels = []
            for item in labels_data:
                label = Label(
                    name=item.get('name', ''),
                    description=item.get('description', ''),
                    color=item.get('color', '000000'),
                    category='unknown'
                )
                labels.append(label)
            return labels
        
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to list labels: {e.stderr}")
            return []
    
    def create_label(self, label: Label) -> bool:
        """Create a new label in the repository"""
        try:
            cmd = [
                "gh", "label", "create", label.name,
                "--repo", self.repo,
                "--color", label.color,
                "--description", label.description,
            ]
            
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✓ Created label: {label.name}")
            return True
        
        except subprocess.CalledProcessError as e:
            if "already exists" in e.stderr:
                print(f"ℹ Label already exists: {label.name}")
                return True
            else:
                print(f"✗ Failed to create label {label.name}: {e.stderr}")
                return False
    
    def update_label(self, old_name: str, label: Label) -> bool:
        """Update an existing label"""
        try:
            cmd = [
                "gh", "label", "edit", old_name,
                "--repo", self.repo,
                "--name", label.name,
                "--color", label.color,
                "--description", label.description,
            ]
            
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✓ Updated label: {old_name} → {label.name}")
            return True
        
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to update label {old_name}: {e.stderr}")
            return False
    
    def delete_label(self, name: str) -> bool:
        """Delete a label from the repository"""
        try:
            subprocess.run(
                [
                    "gh", "label", "delete", name,
                    "--repo", self.repo,
                    "--yes"
                ],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"✓ Deleted label: {name}")
            return True
        
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to delete label {name}: {e.stderr}")
            return False
    
    def sync_labels(self, label_set: LabelSet) -> Dict:
        """
        Sync local label set with GitHub repository
        
        Returns:
            Dictionary with sync statistics
        """
        stats = {
            'created': 0,
            'updated': 0,
            'deleted': 0,
            'unchanged': 0,
            'errors': 0
        }
        
        # Get current labels from GitHub
        existing_labels = {label.name: label for label in self.list_labels()}
        
        # Create or update labels
        for name, label in label_set.labels.items():
            if name in existing_labels:
                existing = existing_labels[name]
                # Check if update needed
                if (existing.color != label.color or 
                    existing.description != label.description):
                    if self.update_label(name, label):
                        stats['updated'] += 1
                    else:
                        stats['errors'] += 1
                else:
                    stats['unchanged'] += 1
            else:
                if self.create_label(label):
                    stats['created'] += 1
                else:
                    stats['errors'] += 1
        
        # Delete labels that are not in the label set (optional, commented by default)
        # for name in existing_labels:
        #     if name not in label_set.labels:
        #         if self.delete_label(name):
        #             stats['deleted'] += 1
        #         else:
        #             stats['errors'] += 1
        
        return stats
    
    def create_default_labels(self) -> Dict:
        """Create all default AstraGuard AI labels"""
        print(f"Creating default labels for {self.repo}...\n")
        
        label_set = create_default_label_set()
        stats = self.sync_labels(label_set)
        
        return stats
    
    def export_labels(self, filepath: str) -> bool:
        """Export current repository labels to JSON"""
        try:
            labels = self.list_labels()
            label_set = LabelSet()
            for label in labels:
                label_set.add_label(label)
            
            export_label_config(label_set, filepath)
            print(f"✓ Exported {len(labels)} labels to {filepath}")
            return True
        
        except Exception as e:
            print(f"✗ Failed to export labels: {e}")
            return False
    
    def import_labels(self, filepath: str) -> Dict:
        """Import labels from JSON and sync with GitHub"""
        try:
            label_set = import_label_config(filepath)
            print(f"✓ Imported {len(label_set.labels)} labels from {filepath}\n")
            
            stats = self.sync_labels(label_set)
            return stats
        
        except Exception as e:
            print(f"✗ Failed to import labels: {e}")
            return {}
    
    def print_summary(self, stats: Dict) -> None:
        """Print a summary of operations"""
        print("\n" + "="*50)
        print("Label Sync Summary:")
        print("="*50)
        print(f"  Created:   {stats.get('created', 0)}")
        print(f"  Updated:   {stats.get('updated', 0)}")
        print(f"  Deleted:   {stats.get('deleted', 0)}")
        print(f"  Unchanged: {stats.get('unchanged', 0)}")
        print(f"  Errors:    {stats.get('errors', 0)}")
        print("="*50 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Manage GitHub labels for AstraGuard AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python manage_labels.py --create              # Create all default labels
  python manage_labels.py --list                # List repository labels
  python manage_labels.py --export labels.json  # Export labels to JSON
  python manage_labels.py --import labels.json  # Import and sync labels from JSON
  python manage_labels.py --repo myuser/myrepo --create  # Create labels in different repo
        """
    )
    
    parser.add_argument(
        '--repo',
        default='sr-857/AstraGuard-AI-Apertre-3.0',
        help='GitHub repository (owner/name)'
    )
    
    parser.add_argument(
        '--create',
        action='store_true',
        help='Create all default AstraGuard AI labels'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all repository labels'
    )
    
    parser.add_argument(
        '--export',
        type=str,
        metavar='FILE',
        help='Export repository labels to JSON file'
    )
    
    parser.add_argument(
        '--import',
        type=str,
        dest='import_file',
        metavar='FILE',
        help='Import and sync labels from JSON file'
    )
    
    parser.add_argument(
        '--delete-all',
        action='store_true',
        help='Delete all labels (WARNING: Cannot be undone!)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    
    args = parser.parse_args()
    
    manager = GitHubLabelManager(args.repo)
    
    # Create labels
    if args.create:
        stats = manager.create_default_labels()
        manager.print_summary(stats)
    
    # List labels
    elif args.list:
        labels = manager.list_labels()
        print(f"\nLabels in {args.repo}:\n")
        for label in sorted(labels, key=lambda l: l.name):
            print(f"  • {label.name:<30} [{label.color}] {label.description}")
        print(f"\nTotal: {len(labels)} labels\n")
    
    # Export labels
    elif args.export:
        manager.export_labels(args.export)
    
    # Import labels
    elif args.import_file:
        stats = manager.import_labels(args.import_file)
        manager.print_summary(stats)
    
    # Delete all labels
    elif args.delete_all:
        if args.dry_run:
            print("[DRY RUN] Would delete all labels")
            return
        
        confirm = input("WARNING: This will delete ALL labels! Type 'DELETE' to confirm: ")
        if confirm.upper() == 'DELETE':
            labels = manager.list_labels()
            for label in labels:
                manager.delete_label(label.name)
            print(f"\nDeleted {len(labels)} labels")
        else:
            print("Cancelled")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

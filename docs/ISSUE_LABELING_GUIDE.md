# 🏷️ Issue Labeling System - Complete Guide

**Status**: ✅ Production-Ready  
**Last Updated**: February 2026  
**Maintainer**: AstraGuard AI Team

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Label Categories](#label-categories)
4. [Components](#components)
5. [Quick Start](#quick-start)
6. [Tools & Scripts](#tools--scripts)
7. [Best Practices](#best-practices)
8. [API Reference](#api-reference)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The **Issue Labeling System** provides a comprehensive framework for organizing, categorizing, and managing GitHub issues in the AstraGuard AI project. The system includes:

### Key Features

✅ **Predefined Label Set**: 50+ carefully designed labels organized by category  
✅ **Intelligent Classification**: ML-style keyword matching for automatic label suggestions  
✅ **GitHub Integration**: Seamless integration with GitHub CLI for label management  
✅ **Validation Framework**: Ensures label consistency and prevents conflicts  
✅ **Synchronization Tools**: Sync labels across repositories and maintain backups  
✅ **Comprehensive Reporting**: Generate label statistics and consistency reports  

### Benefits

- **Consistency**: Standardized labels across all issues
- **Discoverability**: Easy to find related issues
- **Automation**: Reduce manual labeling with smart suggestions
- **Workflow**: Clear issue categorization for project management
- **Contributor Experience**: Helps newcomers understand issue types

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────┐
│     GitHub Issues                           │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  Smart Labeler (label_issues_smart.py)      │
│  - Analyzes issue content                   │
│  - Suggests appropriate labels              │
│  - Batch labels multiple issues             │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  Label Manager (manage_labels.py)           │
│  - Creates/updates/deletes labels           │
│  - Sync with GitHub                         │
│  - Import/export configurations             │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  Label Synchronizer (sync_labels.py)        │
│  - Cross-repo synchronization               │
│  - Backup/restore operations                │
│  - Consistency validation                   │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  Core Module (src/tools/issue_labeling.py)  │
│  - Label definitions                        │
│  - Classification logic                     │
│  - Data models                              │
└─────────────────────────────────────────────┘
```

### Data Flow

```
GitHub Issue
    ↓
Extract: Title + Body
    ↓
IssueClassifier
    ├─ Classify Difficulty
    ├─ Classify Category
    ├─ Identify Type
    └─ Check for "Good First Issue"
    ↓
Suggest Labels
    ↓
Validate Against LabelSet
    ↓
Filter Duplicates & Conflicts
    ↓
Apply to GitHub
```

---

## Label Categories

### 📊 Organization

Labels are organized into **7 main categories**:

#### 1. **Difficulty** (3 labels)
Indicates the relative complexity of an issue.

| Label | Color | Use Case |
|-------|-------|----------|
| `difficulty: easy` | 🔵 Blue | Beginners, simple tasks, 2-4 hours |
| `difficulty: medium` | 🟢 Green | Intermediate, 4-8 hours |
| `difficulty: hard` | 🔴 Red | Complex, expert level, 8+ hours |

**Mutually Exclusive**: Only one difficulty label per issue

#### 2. **Category** (12 labels)
Describes what type of work the issue involves.

| Label | Color | Description |
|-------|-------|-------------|
| `documentation` | 📚 Yellow | Docs, comments, guides |
| `frontend` | 🎨 Purple | UI/UX, React, CSS |
| `backend` | 🔵 Blue | API, services, database |
| `testing` | 💙 Light Blue | Tests, coverage, QA |
| `configuration` | 💛 Light Yellow | Config, setup, environment |
| `code-quality` | 🩵 Cyan | Refactoring, cleanup |
| `bug` | 🔴 Red | Defects, crashes, issues |
| `feature` | 🔵 Blue | New functionality |
| `security` | 🔴 Red | Vulnerabilities, auth |
| `performance` | 💗 Pink | Optimization, speed |
| `devops` | 💂 Dark Red | Deployment, CI/CD, infra |
| `community` | 💎 Cyan | Community, contribution |

#### 3. **Status** (6 labels)
Tracks the current state of an issue.

| Label | Color | Meaning |
|-------|-------|---------|
| `good first issue` | 💜 Purple | Great for newcomers |
| `help wanted` | 💚 Green | Project needs help |
| `in-progress` | 🟠 Orange | Being worked on |
| `blocked` | ⚪ Gray | Waiting for something |
| `duplicate` | ⚪ Light Gray | Duplicate of another |
| `wontfix` | ⚪ White | Won't be addressed |

#### 4. **Priority** (4 labels)
Urgency and importance levels.

| Label | Color | Urgency |
|-------|-------|---------|
| `priority: critical` | 🔴 Red | Blocker, deploy-critical |
| `priority: high` | 🟣 Purple | Should be soon |
| `priority: medium` | 🟡 Yellow | Normal priority |
| `priority: low` | 🟢 Green | Nice to have |

#### 5. **Type** (16 labels)
Specific issue subcategories for detailed classification.

```
Documentation Types:
  • type: docstring       - Add/improve docstrings
  • type: comment         - Comment improvements
  • type: readme          - README updates
  • type: api-docs        - API documentation

Code Types:
  • type: refactor        - Refactoring work
  • type: typing          - Type hints/annotations
  • type: linting         - Code style/linting

Testing Types:
  • type: unit-test       - Unit testing
  • type: integration-test - Integration testing
  • type: e2e-test        - End-to-end testing

Bug Types:
  • type: bug-logic       - Logic error
  • type: bug-crash       - Crash/hang
  • type: bug-security    - Security vulnerability

Feature Types:
  • type: feature-new     - New functionality
  • type: feature-enhance - Enhancement

Performance Types:
  • type: optimization    - Performance optimization
  • type: profiling       - Performance profiling
```

#### 6. **Project** (1 label)
Release/project tracking.

| Label | Purpose |
|-------|---------|
| `apertre3.0` | Apertre 3.0 release milestone |

#### 7. **Skills** (5 labels)
Required expertise areas.

| Label | Expertise |
|-------|-----------|
| `enhancement` | Code enhancement |
| `optimization` | Performance optimization |
| `refactor` | Code refactoring |
| `quality` | Quality improvement |
| `monitoring` | Observability/monitoring |

---

## Components

### 1. Core Module: `src/tools/issue_labeling.py`

The foundation of the system. Provides:

**Data Models:**
- `Label`: Single label with metadata
- `LabelSet`: Collection of labels
- `Issue*` Enums: Label categories, difficulties, types

**Classification:**
- `IssueClassifier`: Analyzes issue content and suggests labels
- Keyword-based matching (ML-style)
- Multi-label support

**Management:**
- `LabelManager`: Orchestrates label operations
- Validation framework
- Export/import functionality

**Example Usage:**

```python
from src.tools.issue_labeling import get_default_label_manager

# Get the label manager
manager = get_default_label_manager()

# Suggest labels for an issue
title = "Add type hints to detector.py"
body = "We need full type annotation coverage for reliability."

suggestions = manager.suggest_for_issue(title, body)
# Returns: ['difficulty: easy', 'code-quality', 'type: typing', 'good first issue']

# Validate labels
labels = ['difficulty: easy', 'documentation', 'apertre3.0']
is_valid, invalid = manager.validate_labels(labels)

# Get label information
info = manager.get_label_info('difficulty: easy')
# Returns: {
#   'name': 'difficulty: easy',
#   'description': 'Good for beginners',
#   'color': 'a2eeef',
#   'category': 'difficulty'
# }
```

### 2. Management Tool: `scripts/maintenance/manage_labels.py`

**Purpose:** Create, update, and delete labels on GitHub

**Commands:**

```bash
# Create all default labels
python manage_labels.py --create

# List repository labels
python manage_labels.py --list

# Export labels to JSON
python manage_labels.py --export labels.json

# Import and sync labels from JSON
python manage_labels.py --import labels.json

# Use custom repository
python manage_labels.py --repo owner/repo --create
```

**Features:**
- ✅ Create labels with colors and descriptions
- ✅ Update existing labels
- ✅ Batch operations
- ✅ Export/import JSON configurations
- ✅ Error handling for already-existing labels

### 3. Smart Labeler: `scripts/maintenance/label_issues_smart.py`

**Purpose:** Intelligently suggest and apply labels to issues

**Commands:**

```bash
# Suggest labels for a specific issue
python label_issues_smart.py --issue 42

# Label all open issues
python label_issues_smart.py --label-all

# Interactive mode with confirmation
python label_issues_smart.py --interactive

# Preview changes without applying
python label_issues_smart.py --dry-run --label-all

# Only process unlabeled issues
python label_issues_smart.py --unlabeled --limit 50
```

**Features:**
- 🤖 Keyword-based classification
- ✅ Duplicate prevention
- ✅ Conflict resolution
- ✅ Batch or interactive processing
- ✅ Dry-run mode for testing

**Example Output:**

```
[1/50] Issue #42: Add type hints to detector.py
  → Suggested: difficulty: easy, code-quality, type: typing, good first issue
  Apply labels? (y/n/skip): y
  ✓ Added 4 label(s)
```

### 4. Synchronization Tool: `scripts/maintenance/sync_labels.py`

**Purpose:** Sync labels across repositories and maintain consistency

**Commands:**

```bash
# Initialize standard labels
python sync_labels.py --init

# Sync to another repository
python sync_labels.py --sync owner/other-repo

# Generate label report
python sync_labels.py --report report.json

# Validate consistency across repos
python sync_labels.py --validate repo1 repo2 repo3

# Backup labels
python sync_labels.py --backup backup.json

# Restore from backup
python sync_labels.py --restore backup.json
```

**Features:**
- 🔄 Cross-repo synchronization
- 📊 Comprehensive reporting
- ✅ Consistency validation
- 💾 Backup/restore operations
- 🛡️ Skip-existing mode

---

## Quick Start

### Setup (One-time)

```bash
# 1. Navigate to project root
cd AstraGuard-AI-Apertre-3.0

# 2. Create all default labels
python scripts/maintenance/manage_labels.py --create

# 3. Verify labels were created
python scripts/maintenance/manage_labels.py --list
```

### Label Existing Issues

```bash
# Option A: Batch mode (recommended)
python scripts/maintenance/label_issues_smart.py --label-all

# Option B: Interactive mode (safer)
python scripts/maintenance/label_issues_smart.py --interactive

# Option C: Preview first, then apply
python scripts/maintenance/label_issues_smart.py --dry-run --label-all
python scripts/maintenance/label_issues_smart.py --label-all
```

### Label a New Issue

```bash
# When creating an issue on GitHub:
# 1. Write clear title and description
# 2. Use the smart labeler to get suggestions:

python scripts/maintenance/label_issues_smart.py --issue <NUMBER>

# 3. Review and apply suggested labels:
python scripts/maintenance/label_issues_smart.py --issue <NUMBER>
```

---

## Tools & Scripts

### `manage_labels.py` - Label Management

**Full API:**

```bash
python scripts/maintenance/manage_labels.py [OPTIONS]

Options:
  --repo REPO              GitHub repository (default: sr-857/AstraGuard-AI-Apertre-3.0)
  --create                 Create all default labeled
  --list                   List all repository labels
  --export FILE            Export labels to JSON
  --import FILE            Import and sync labels from JSON
  --delete-all             Delete all labels (DANGEROUS!)
  --dry-run                Show what would be done
  -h, --help              Show this help message
```

**Example Workflow:**

```bash
# Backup current labels
python manage_labels.py --export backup.json

# Update labels to latest standard
python manage_labels.py --import backup.json

# View all labels
python manage_labels.py --list
```

### `label_issues_smart.py` - Smart Labeling

**Full API:**

```bash
python scripts/maintenance/label_issues_smart.py [OPTIONS]

Options:
  --repo REPO              GitHub repository
  --issue NUMBER           Analyze specific issue
  --label-all              Label all issues
  --unlabeled              Only process unlabeled issues
  --interactive            Ask for confirmation
  --limit N                Max issues to process (default: 100)
  --state STATE            Issue state: open|closed|all (default: open)
  --dry-run                Preview without changes
```

**Workflow Examples:**

```bash
# Label first 20 unlabeled issues interactively
python label_issues_smart.py --unlabeled --limit 20 --interactive

# Batch label all with dry-run preview
python label_issues_smart.py --dry-run --label-all

# Apply the changes
python label_issues_smart.py --label-all

# Check specific issue
python label_issues_smart.py --issue 100
```

### `sync_labels.py` - Synchronization

**Full API:**

```bash
python scripts/maintenance/sync_labels.py [OPTIONS]

Options:
  --repo REPO              Source repository
  --init                   Initialize standard labels
  --sync REPO              Sync to target repository
  --skip-existing          Don't overwrite existing (default)
  --overwrite              Overwrite existing labels
  --report [FILE]          Generate report
  --validate REPO ...      Validate consistency
  --backup FILE            Backup labels
  --restore FILE           Restore from backup
```

**Synchronization Examples:**

```bash
# Setup new repository with all labels
python sync_labels.py --repo new-owner/new-repo --init

# Sync labels from source to target
python sync_labels.py --repo src-repo --sync target-repo

# Validate consistency across all forks
python sync_labels.py --validate repo1 repo2 repo3

# Backup for disaster recovery
python sync_labels.py --backup labels-feb2026.json

# Restore backup
python sync_labels.py --restore labels-feb2026.json --overwrite
```

---

## Best Practices

### Creating Issues

#### 1. **Write Clear Titles**

✅ **Good:**
- "Add type hints to `anomaly_detector.py`"
- "Documentation: Improve README for new contributors"
- "Bug: Crash on empty input in state machine"

❌ **Bad:**
- "Fix stuff"
- "Random improvements"
- "Something broken"

#### 2. **Provide Detailed Description**

Include:
- **What**: What needs to be done
- **Why**: Why it's important
- **How**: Suggested approach
- **Files**: Files to modify
- **Acceptance Criteria**: How to verify completion

#### 3. **Use Templates** (GitHub Issue Templates)

Existing templates in `.github/ISSUE_TEMPLATE/`:
- `bug_report.yml`
- `feature_request.yml`
- `documentation.yml`
- `question.yml`

#### 4. **Enable Label Suggestions**

When creating an issue:
1. Write description
2. Run smart labeler for suggestions
3. Review and apply labels
4. Submit issue

### Managing Labels

#### 1. **Regular Cleanup**

Monthly:
```bash
# Generate report
python sync_labels.py --report monthly-report.json

# Check for unused labels
python sync_labels.py --report - | grep unused
```

#### 2. **Consistency Checks**

Weekly:
```bash
# Validate label consistency
python sync_labels.py --validate owner/repo1 owner/repo2

# Fix any inconsistencies
python sync_labels.py --sync owner/repo1 --repo owner/repo2
```

#### 3. **Backup Strategy**

Quarterly:
```bash
# Backup current state
python sync_labels.py --backup labels-q1-2026.json

# Store in safe location
git add backups/labels-*.json
git commit -m "Label configuration backup: Q1 2026"
```

### Labeling Issues

#### 1. **Accuracy**

- Use the smart labeler for consistency
- Review suggestions manually
- Don't force incorrect labels
- Ask maintainers when unsure

#### 2. **Completeness**

Each issue should have:
- ✅ At least 1 **category** label
- ✅ At most 1 **difficulty** label
- ✅ 0 or more **type** labels
- ✅ Optionally: **priority** and **status** labels

#### 3. **Conflicts to Avoid**

❌ Don't combine:
- Multiple difficulty labels
- Contradictory statuses (`wontfix` + `in-progress`)
- Conflicting priorities

### For Maintainers

#### Before Merging PR

1. ✅ Issue has appropriate difficulty label
2. ✅ Issue has category label
3. ✅ Issue has type label (if applicable)
4. ✅ No label conflicts
5. ✅ `apertre3.0` label applied (if in phase)

#### Closing Issues

1. 🏷️ Add `duplicate` if closing as duplicate
2. 🏷️ Add `wontfix` if deciding not to fix
3. 📝 Link to related issues
4. 💬 Explain decision in comment

---

## API Reference

### Core Module: `issue_labeling.py`

#### Classes

**`Label`**
```python
@dataclass
class Label:
    name: str              # Label name
    description: str       # Label description
    color: str            # Hex color (without #)
    category: str         # Category name
```

**`LabelSet`**
```python
class LabelSet:
    def add_label(label: Label) -> None
    def get_label(name: str) -> Optional[Label]
    def get_labels_by_category(category: str) -> List[Label]
    def validate_labels(labels: List[str]) -> Tuple[bool, List[str]]
    def to_dict() -> Dict
    @classmethod
    def from_dict(data: Dict) -> LabelSet
```

**`IssueClassifier`**
```python
class IssueClassifier:
    def classify_difficulty(title: str, body: str) -> Optional[str]
    def classify_category(title: str, body: str) -> Optional[str]
    def classify_issue_type(title: str, body: str) -> List[str]
    def suggest_labels(title: str, body: str, 
                      difficulty: Optional[str] = None,
                      category: Optional[str] = None) -> List[str]
```

**`LabelManager`**
```python
class LabelManager:
    def get_all_labels() -> List[Label]
    def get_labels_by_category(category: str) -> List[Label]
    def suggest_for_issue(title: str, body: str) -> List[str]
    def validate_labels(labels: List[str]) -> Tuple[bool, List[str]]
    def get_label_info(label_name: str) -> Optional[Dict]
```

#### Functions

```python
# Create default label set
create_default_label_set() -> LabelSet

# Get default label manager
get_default_label_manager() -> LabelManager

# Import/export
export_label_config(label_set: LabelSet, filepath: str) -> None
import_label_config(filepath: str) -> LabelSet
```

### Usage Examples

```python
from src.tools.issue_labeling import (
    get_default_label_manager,
    Label,
    LabelSet,
    IssueClassifier,
    create_default_label_set,
    export_label_config,
    import_label_config
)

# Example 1: Get label manager and suggest labels
manager = get_default_label_manager()
suggestions = manager.suggest_for_issue(
    "Add type hints to detector.py",
    "We need full type coverage for reliability."
)
# Returns: ['difficulty: easy', 'code-quality', 'type: typing']

# Example 2: Validate labels
is_valid, invalid = manager.validate_labels([
    'difficulty: easy',
    'documentation',
    'apertre3.0'
])
# Returns: (True, [])

# Example 3: Export labels
label_set = create_default_label_set()
export_label_config(label_set, 'labels.json')

# Example 4: Create custom label set
custom_labels = LabelSet()
custom_labels.add_label(Label(
    name='custom',
    description='Custom label',
    color='FF0000',
    category='custom'
))
```

---

## Troubleshooting

### GitHub CLI Issues

**Problem:** `ERROR: GitHub CLI (gh) is not installed`

**Solution:**
```bash
# Install GitHub CLI
# On Windows:
choco install gh

# On macOS:
brew install gh

# On Linux:
sudo apt install gh  # Debian/Ubuntu
```

**Verify installation:**
```bash
gh --version
gh auth status
```

### Label Creation Fails

**Problem:** `Error creating label 'docstring': already exists`

**Solution:** The label already exists. Use `--import` with `--skip-existing` flag, or manually delete and recreate.

### Suggestions Seem Wrong

**Problem:** Smart labeler suggests incorrect labels

**Solution:**
1. Check issue title and body are descriptive
2. Verify keywords match expected patterns
3. Manually add labels if needed
4. Update keywords in `IssueClassifier` if pattern is common

```python
# Check/update in issue_labeling.py
classifier.keywords_category['documentation'] = [
    'doc', 'docstring', 'readme', 'comment',
    # Add more keywords here
]
```

### Permission Denied

**Problem:** `Error: Authentication required`

**Solution:**
```bash
# Login to GitHub
gh auth login

# Follow prompts to authenticate
# After login, retry your command
```

### Repository Not Found

**Problem:** `Error: Repository not found`

**Solution:**
1. Verify repository name format: `owner/repo`
2. Ensure you have access to the repository
3. Use correct repository:

```bash
# List your repositories
gh repo list

# Use correct one in commands
python myscript.py --repo owner/repo-name
```

### Label Sync Issues

**Problem:** Labels not syncing to target repository

**Solution:**
1. Verify target repository name
2. Check authentication
3. Try explicit skip/overwrite:

```bash
# Skip existing labels
python sync_labels.py --sync target-repo --skip-existing

# Or overwrite existing
python sync_labels.py --sync target-repo --overwrite
```

---

## Examples

### Example 1: Complete Issue Labeling Workflow

```bash
# 1. Create default labels (one-time)
python scripts/maintenance/manage_labels.py --create

# 2. View current labels
python scripts/maintenance/manage_labels.py --list

# 3. Check specific issue for suggestions
python scripts/maintenance/label_issues_smart.py --issue 42

# 4. Review suggestions manually
# (Output shows: difficulty: easy, documentation, type: docstring)

# 5. Apply to the issue
# (Use --label-all or apply manually via GitHub UI)

# 6. Verify (should see labels on issue)
gh issue view 42 --repo sr-857/AstraGuard-AI-Apertre-3.0
```

### Example 2: Batch Processing Unlabeled Issues

```bash
# 1. Preview what would happen (dry-run)
python scripts/maintenance/label_issues_smart.py \
  --unlabeled \
  --limit 10 \
  --dry-run

# 2. If preview looks good, process with confirmation
python scripts/maintenance/label_issues_smart.py \
  --unlabeled \
  --limit 10 \
  --interactive

# 3. For each issue, review and confirm
# (Type 'y' to apply, 'n' to skip, or 'skip' to move on)

# 4. Check results
gh issue list --repo sr-857/AstraGuard-AI-Apertre-3.0 --limit 10
```

### Example 3: Maintaining Multiple Repositories

```bash
# 1. Backup source repository labels
python scripts/maintenance/sync_labels.py \
  --repo original/repo \
  --backup labels-backup.json

# 2. Create labels in new repository
python scripts/maintenance/sync_labels.py \
  --repo owner/new-repo \
  --init

# 3. Verify consistency across both
python scripts/maintenance/sync_labels.py \
  --validate original/repo owner/new-repo

# 4. If differences found, sync them
python scripts/maintenance/sync_labels.py \
  --repo original/repo \
  --sync owner/new-repo
```

---

## Contributing

Have ideas to improve the labeling system?

1. 💡 **Suggest**: Open an issue with tag `enhancement`
2. 🔧 **Implement**: Submit a PR with changes
3. ✅ **Review**: We'll review and provide feedback
4. 📦 **Deploy**: Merged changes take effect immediately

---

## Resources

### Related Documents
- [Good First Issue Criteria](GOOD_FIRST_ISSUE_CRITERIA.md)
- [PR Review Guidelines](PR_REVIEW_GUIDELINES.md)
- [Contributing Guidelines](CONTRIBUTING.md)

### External Links
- [GitHub Labels Best Practices](https://github.com/blog/2119-add-an-extra-set-of-eyes-with-pull-request-reviews)
- [GitHub CLI Documentation](https://cli.github.com/manual/)
- [Semantic Commit Messages](https://www.conventionalcommits.org/)

---

## FAQ

**Q: Can I have multiple difficulty labels?**  
A: No. Use only ONE difficulty label per issue.

**Q: What if no label fits my issue?**  
A: Contact maintainers. We may need to add a new category.

**Q: How often are labels backed up?**  
A: Quarterly, but you can manually backup anytime using `--backup`.

**Q: Can I customize the label set?**  
A: Yes! Modify `create_default_label_set()` in `issue_labeling.py` and re-sync.

**Q: Do I need GitHub CLI installed?**  
A: Yes, for all scripts. Install from https://cli.github.com

---

## Support

Having issues with the labeling system?

- 📝 **Check documentation**: https://github.com/sr-857/AstraGuard-AI-Apertre-3.0/docs/
- 🐛 **Report bug**: Use `bug_report.yml` template
- 💬 **Ask question**: Open issue with `question` label
- 👥 **Join community**: [WhatsApp Group](https://chat.whatsapp.com/Ka6WKpDdKIxInvpLBO1nCB)

---

## License

This documentation and all related code is part of **AstraGuard AI**, licensed under the [MIT License](../../LICENSE).

© 2026 AstraGuard AI Team. All rights reserved.

---

**Last Updated**: February 2026  
**Status**: ✅ Production-Ready  
**Maintainer**: AstraGuard AI Team

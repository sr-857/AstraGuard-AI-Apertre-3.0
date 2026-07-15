# 🏷️ Issue Labeling System - Quick Reference

**TL;DR Version of the Complete Guide**

---

## 🚀 Quick Start (30 seconds)

### First Time Only
```bash
# Navigate to project root
cd AstraGuard-AI-Apertre-3.0

# Create all default labels once
python scripts/maintenance/manage_labels.py --create
```

### How to Label New Issues

**Option A: Smart Auto-Labels (Recommended)**
```bash
# Get suggestions for an issue
python scripts/maintenance/label_issues_smart.py --issue 42

# Or label all unlabeled issues
python scripts/maintenance/label_issues_smart.py --unlabeled
```

**Option B: Manually**
1. Open issue on GitHub
2. Click "Labels" on the right sidebar
3. Select appropriate labels from the list

---

## 📊 Label Categories at a Glance

### Pick ONE Difficulty
- `difficulty: easy` → Beginner-friendly, 2-4 hours
- `difficulty: medium` → Intermediate, 4-8 hours  
- `difficulty: hard` → Expert-level, 8+ hours

### Pick ONE Category (Required)
```
📚 documentation    📝 bug           🎨 frontend
💻 backend         🧪 testing      🔧 configuration
⚡ code-quality    ✨ feature      🔒 security
⚙️ devops          🚀 performance  👥 community
```

### Optional Additions
```
Status:           Type:                Priority:
✓ good first      • type: docstring   ↑ priority: critical
✓ help wanted     • type: typing       ↑ priority: high
✓ in-progress     • type: testing      ↑ priority: medium
✓ blocked         • type: refactor     ↑ priority: low
↓ duplicate       • type: optimization
↓ wontfix

Project:
◆ apertre3.0
```

---

## 📝 Common Patterns

### Documentation Issue
```
Labels: documentation + difficulty: easy + type: docstring + apertre3.0 + good first issue
```

### Bug Report
```
Labels: bug + priority: high + apertre3.0
(add type: bug-crash, type: bug-security, etc. if applicable)
```

### Feature Request
```
Labels: feature + difficulty: medium + apertre3.0 + help wanted
```

### Good First Issue
```
Labels: (any category) + difficulty: easy + good first issue + apertre3.0
```

### Performance Optimization
```
Labels: performance + difficulty: hard + type: optimization + apertre3.0
```

---

## 💻 Scripts at a Glance

### Manage Labels
```bash
manage_labels.py --create              # Create all default labels
manage_labels.py --list                # List all labels
manage_labels.py --export labels.json  # Backup labels
manage_labels.py --import labels.json  # Restore labels
```

### Smart Labeler
```bash
label_issues_smart.py --issue 42       # Suggest labels for #42
label_issues_smart.py --label-all      # Label all issues
label_issues_smart.py --interactive    # Ask before labeling
label_issues_smart.py --dry-run --label-all  # Preview only
label_issues_smart.py --unlabeled      # Only unlabeled issues
```

### Synchronize
```bash
sync_labels.py --init                  # Initialize standard labels
sync_labels.py --report report.json    # Generate report
sync_labels.py --validate repo1 repo2  # Check consistency
sync_labels.py --backup backup.json    # Backup labels
sync_labels.py --restore backup.json   # Restore labels
```

---

## 🎯 Workflow Examples

### I'm Creating a New Issue
```bash
# 1. Create issue on GitHub with good description
# 2. Get suggestions:
python scripts/maintenance/label_issues_smart.py --issue <NUMBER>

# 3. Apply the suggested labels via GitHub UI
# Done!
```

### I Need to Label Existing Issues
```bash
# Option A: Label all (safe - skips already labeled)
python scripts/maintenance/label_issues_smart.py --label-all

# Option B: Interactive (review each one)
python scripts/maintenance/label_issues_smart.py --interactive

# Option C: Only unlabeled ones
python scripts/maintenance/label_issues_smart.py --unlabeled --limit 50
```

### I'm a Maintainer Closing an Issue
```bash
# If duplicate:
gh issue edit <NUMBER> --add-label "duplicate"
gh issue edit <NUMBER> --add-label "apertre3.0"  # if needed

# If won't fix:
gh issue edit <NUMBER> --add-label "wontfix"
gh issue edit <NUMBER> --add-label "apertre3.0"  # if needed

# Close it
gh issue close <NUMBER>
```

### Setting Up a New Repository
```bash
# Initialize with standard labels
python sync_labels.py --repo newowner/newrepo --init

# Verify it worked
python manage_labels.py --repo newowner/newrepo --list
```

---

## ❌ Common Mistakes to Avoid

| ❌ Wrong | ✅ Correct |
|---------|-----------|
| Multiple difficulty labels | Pick ONE difficulty |
| `difficulty: easy` + `difficulty: medium` | Choose only one |
| No category label | Always pick a category |
| Wrong category for issue | Review and use smart-labeler |
| Label a typo fix as `help wanted` | Use `good first issue` instead |
| Forgetting `apertre3.0` label | Always add if in Apertre 3.0 |

---

## 🆘 Troubleshooting

### "gh: command not found"
```bash
# Install GitHub CLI from: https://cli.github.com
```

### "Error: Repository not found"
```bash
# Check repo format: owner/repo-name
# Make sure you have access
# Use: gh repo list (to find correct name)
```

### Label suggestions seem wrong
```bash
# The issue title/description might be unclear
# Write more descriptive text
# Or manually add labels via GitHub UI
```

### "Error: Authentication required"
```bash
# Login to GitHub:
gh auth login
# Follow prompts to authenticate
```

---

## 📊 Label Statistics Command

```bash
# See how many issues per label
gh issue list --limit 1000 --json labels | jq '.[] | .labels[] | .name' | sort | uniq -c | sort -rn
```

---

## 🔗 Full Resources

- **Complete Guide**: `docs/ISSUE_LABELING_GUIDE.md`
- **Good First Issues**: `docs/GOOD_FIRST_ISSUE_CRITERIA.md`
- **PR Review**: `docs/PR_REVIEW_GUIDELINES.md`
- **Contributing**: `docs/CONTRIBUTING.md`

---

## 💡 Tips & Tricks

**Tip 1: Use smart labeler before creating issues**
```bash
# Draft your issue description, then:
python scripts/maintenance/label_issues_smart.py --issue 999  # See what labels fit
```

**Tip 2: Batch label with dry-run first**
```bash
# Preview what would happen:
python scripts/maintenance/label_issues_smart.py --dry-run --label-all

# Then apply for real:
python scripts/maintenance/label_issues_smart.py --label-all
```

**Tip 3: Export labels for backup**
```bash
# Monthly backup:
python manage_labels.py --export labels-$(date +%B-%Y).json
```

**Tip 4: Check issue details before labeling**
```bash
# View issue details:
gh issue view <NUMBER>

# Then decide on labels:
gh issue edit <NUMBER> --add-label label1 --add-label label2
```

---

## 📋 Checklist: Before Merging PR

- [ ] Issue has appropriate difficulty label
- [ ] Issue has category label
- [ ] Issue has type label (if applicable)
- [ ] No conflicting labels
- [ ] `apertre3.0` added (if applicable)

---

## 🎓 Learning Path

1. **Beginner**: Read this quick reference
2. **Intermediate**: Try labeling a few issues manually
3. **Advanced**: Run smart labeler and review suggestions
4. **Expert**: Customize classifiers in `issue_labeling.py`

---

## 📞 Need Help?

- **Read**: `docs/ISSUE_LABELING_GUIDE.md` (full guide)
- **Try**: `python <script> --help` (for any script)
- **Ask**: Open issue with `question` label
- **Chat**: [WhatsApp Community](https://chat.whatsapp.com/Ka6WKpDdKIxInvpLBO1nCB)

---

## 🎯 One-Liner Commands

```bash
# Quick label check
gh issue list --limit 50 | awk '{print $1}' | while read issue; do echo "Issue $issue"; python label_issues_smart.py --issue $issue; done

# Get unlabeled issue count
gh issue list --limit 1000 --json labels -q '.[] | select(.labels == []) | .number' | wc -l

# Export all labels
python manage_labels.py --export labels.json && cat labels.json

# List all labels
python manage_labels.py --list

# Dry-run label all
python label_issues_smart.py --dry-run --label-all | head -20
```

---

**Version**: 1.0  
**Last Updated**: February 2026  
**Status**: ✅ Production-Ready

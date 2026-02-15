# Maintainer's Guide: Contributor Recognition

Quick reference for managing the AstraGuard AI contributor recognition program.

---

## 🚀 Quick Start

### Daily Tasks

**Review New PRs:**
```bash
# Check PRs waiting for review
gh pr list --state open

# Review and merge eligible PRs
gh pr review <PR-NUMBER> --approve
gh pr merge <PR-NUMBER> --squash
```

**Welcome New Contributors:**
- GitHub Action automatically posts welcome message
- Manually thank contributors in PR comments
- Add personal touch to first-time contributor interactions

---

## 📅 Weekly Tasks

### Monday: Contributor Check-in

**1. Review Last Week's Contributions:**
```bash
# See merged PRs from last week
gh pr list --state merged --search "merged:>=2026-02-08"

# Check new contributors
gh pr list --state merged --search "author:@new"
```

**2. Update Recognition Status:**
- Check if anyone reached new tier milestones
- Manually assign specialty badges if warranted
- Note outstanding contributions for monthly spotlight

---

## 📊 Monthly Tasks

### First Week of Month: Spotlight Selection

**1. Review Previous Month's Contributions:**
```bash
# PRs merged in January 2026
gh pr list --state merged --search "merged:2026-01-01..2026-01-31" --limit 100
```

**2. Select Spotlight Contributors (1-3 people):**

Criteria:
- Innovation and creativity
- Quality of contributions
- Community engagement
- Mentorship activities

**3. Update CONTRIBUTORS.md:**
```markdown
### Monthly Contributor Spotlight - February 2026

- **[@username](link)** - [Description of contribution]
  - Implemented groundbreaking feature X
  - Mentored 5 new contributors
  - 🚀 Innovation Award recipient
```

**4. Announce Spotlight:**
- GitHub Discussion post
- README.md update
- Social media (if applicable)

### Generate Monthly Report:
```bash
# Run the automation script
python scripts/maintenance/update_contributors.py \
  --token $GITHUB_TOKEN \
  --json

# Review the output
cat contributor_report.json | jq '.'
```

---

## 🏆 Quarterly Tasks

### Last Week of Quarter: Awards Selection

**1. Review Quarter's Contributions:**
```bash
# Q1 2026 (Jan-Mar)
gh pr list --state merged --search "merged:2026-01-01..2026-03-31" --limit 500
```

**2. Award Categories:**

#### 🚀 Innovation Award
**Look for:**
- Creative solutions to complex problems
- New feature implementations
- Novel approaches to existing challenges

**Selection Process:**
1. Compile nominations from maintainers
2. Review top 3-5 candidates
3. Vote via GitHub Discussion (maintainers + core contributors)

#### 🐛 Bug Hunter Award
**Metrics:**
- Number of critical bugs found
- Quality of bug reports
- Bug fix PRs merged

**Auto-generate candidates:**
```bash
gh issue list --search "label:bug author:USERNAME is:closed"
gh pr list --search "label:bug-fix author:USERNAME is:merged"
```

#### 📚 Documentation Hero
**Look for:**
- Comprehensive documentation additions
- Tutorial creation
- README improvements
- API documentation

#### 🤝 Community Champion
**Look for:**
- Answering questions in discussions
- Helping new contributors
- Issue triaging
- Code review participation

#### 🔒 Security Guardian
**Look for:**
- Security vulnerability reports
- Security feature implementations
- Security audit contributions

**3. Announcement:**
```markdown
# Q1 2026 Contributor Awards 🏆

We're thrilled to announce our Q1 2026 award winners!

## 🚀 Innovation Award
**[@username](link)** - For implementing [feature]

## 🐛 Bug Hunter Award
**[@username](link)** - 15 critical bugs found and fixed

## 📚 Documentation Hero
**[@username](link)** - Overhauled entire documentation structure

## 🤝 Community Champion
**[@username](link)** - Helped 30+ new contributors get started

## 🔒 Security Guardian
**[@username](link)** - Discovered and patched critical vulnerability

Congratulations to all winners! 🎉
```

---

## 🎖️ Badge Management

### Assigning Tier Badges

**Automatic (via GitHub Action):**
- Tier badges assigned automatically on PR merge
- Welcome messages sent automatically

**Manual Assignment:**
Edit CONTRIBUTORS.md to update tier status:
```markdown
### 🌟 Core Contributors
- **[@username](link)** - 25 PRs | Security Expert
```

### Assigning Specialty Badges

**Security Researcher:**
```bash
# Requirements: 
# - 3+ security-related PRs OR
# - 1 critical vulnerability report
```

**Documentation Hero:**
```bash
# Requirements:
# - 5+ documentation PRs OR
# - Major documentation overhaul
```

**Testing Champion:**
```bash
# Requirements:
# - 10+ test-related PRs OR
# - Significantly improved test coverage
```

**Community Mentor:**
```bash
# Requirements:
# - Actively mentoring 3+ new contributors
# - Regular participation in discussions
# - 10+ helpful comments or reviews
```

---

## 🔧 Automation Management

### Running Manual Updates

**Update Contributor Data:**
```bash
# Set your GitHub token
export GITHUB_TOKEN="your_token_here"

# Run update script
python scripts/maintenance/update_contributors.py \
  --repo sr-857/AstraGuard-AI-Apertre-3.0 \
  --token $GITHUB_TOKEN \
  --json
```

**Trigger GitHub Action Manually:**
```bash
# Via GitHub CLI
gh workflow run contributor-recognition.yml

# Via web interface
# Go to: Actions → Update Contributor Recognition → Run workflow
```

### Monitoring Automation

**Check GitHub Action Logs:**
```bash
# List recent runs
gh run list --workflow=contributor-recognition.yml

# View specific run
gh run view <RUN-ID>
```

---

## 📝 Document Updates

### Update CONTRIBUTORS.md

**Add Featured Contributors:**
```markdown
### Event Contributors
#### Elite Coders Winter of Code (Apertre 3.0) - 2026
- **[@username](link)** - Brief description of contribution
```

**Update Statistics:**
```markdown
## 📊 Current Statistics
- **Total Contributors**: 150
- 👑 **Legend**: 2
- 🌟 **Core Contributor**: 8
- 💎 **Regular Contributor**: 25
- ⭐ **Active Contributor**: 45
- 🌱 **New Contributor**: 70

*Last Updated: February 15, 2026*
```

### Update Recognition Program

When updating [.github/CONTRIBUTOR_RECOGNITION.md](.github/CONTRIBUTOR_RECOGNITION.md):
1. Document any new recognition criteria
2. Add new badge types if introduced
3. Update version and date at bottom
4. Announce changes in GitHub Discussions

---

## 🎯 Best Practices

### DO:
- ✅ Respond to first-time contributors within 24 hours
- ✅ Provide encouraging, constructive feedback
- ✅ Celebrate milestones publicly
- ✅ Be transparent about criteria
- ✅ Update recognition promptly
- ✅ Thank contributors often
- ✅ Highlight diverse contribution types

### DON'T:
- ❌ Show favoritism or bias
- ❌ Ignore non-code contributions
- ❌ Delay recognition unnecessarily
- ❌ Make criteria too complex
- ❌ Forget to acknowledge efforts
- ❌ Create competition between contributors

---

## 🚨 Common Issues

### Issue: Contributor Not Showing in List
**Solution:**
```bash
# Check if their PRs are merged (not just closed)
gh pr list --author USERNAME --state merged

# Manually add to CONTRIBUTORS.md if system missed them
```

### Issue: GitHub Action Not Running
**Solution:**
```bash
# Check workflow status
gh workflow view contributor-recognition.yml

# Check for errors in last run
gh run list --workflow=contributor-recognition.yml | head -n 5

# Re-run failed workflow
gh run rerun <RUN-ID>
```

### Issue: Badge Not Appearing
**Solution:**
1. Verify badge markdown syntax in CONTRIBUTORS.md
2. Check shields.io is accessible
3. Clear browser cache
4. Verify URL encoding for special characters

---

## 📞 Need Help?

### Resources
- [Full Recognition Program](.github/CONTRIBUTOR_RECOGNITION.md)
- [Badge System Documentation](docs/CONTRIBUTOR_BADGES.md)
- [CONTRIBUTORS.md](../CONTRIBUTORS.md)

### Contact
- **Project Lead**: [@sr-857](https://github.com/sr-857)
- **Email**: subhajitroy857@gmail.com
- **Discussions**: [GitHub Discussions](https://github.com/sr-857/AstraGuard-AI-Apertre-3.0/discussions)

---

## 📊 Recognition Committee

**Current Composition:**
- Project maintainers (permanent)
- 2-3 core contributors (rotating every 6 months)

**Responsibilities:**
1. Review and approve spotlight selections
2. Determine quarterly award winners
3. Resolve recognition disputes
4. Update recognition criteria
5. Ensure fair and inclusive process

**Meeting Schedule:**
- Monthly: Spotlight selection
- Quarterly: Award selection
- Annually: Program review and updates

---

## 🎓 Training New Maintainers

### Onboarding Checklist:
- [ ] Review full recognition program documentation
- [ ] Understand tier system and criteria
- [ ] Learn how to run automation scripts
- [ ] Set up GitHub token for API access
- [ ] Join recognition committee discussions
- [ ] Shadow current maintainer for one month
- [ ] Complete first spotlight selection
- [ ] Complete first quarterly award selection

### Key Skills:
- GitHub API and CLI usage
- Python scripting (for automation)
- Community management
- Fair and unbiased decision-making
- Clear communication

---

*Maintainer's Guide Version: 1.0*
*Last Updated: February 15, 2026*
*For updates, contact the project lead*

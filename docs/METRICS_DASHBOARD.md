# Contribution Metrics Dashboard

## 📊 Overview

The **Contribution Metrics Dashboard** provides real-time insights into AstraGuard AI's community contributions. It tracks contributor activity, tier distribution, contribution types, and recent activity in a beautiful, interactive web interface.

**Live Dashboard**: [View Dashboard](contribution-metrics-dashboard.html)

---

## ✨ Features

### Real-Time Metrics
- **Total Contributors**: Complete count of all contributors
- **Merged PRs**: Total number of merged pull requests
- **Closed Issues**: Issues resolved by the community
- **Active Contributors**: Contributors active in the current month

### Tier Distribution Visualization
Interactive bar chart showing distribution across 5 tiers:
- 👑 **Legend** (50+ PRs)
- 🌟 **Core** (20-49 PRs)
- 💎 **Regular** (5-19 PRs)
- ⭐ **Active** (2-4 PRs)
- 🌱 **New** (1 PR)

### Top Contributors Leaderboard
- Ranked list of top 10 contributors
- Profile pictures and GitHub links
- PR count and tier badges
- First contribution date

### Recent Activity Timeline
- Last 10 major contributions
- PR merges and milestones
- Contributor mentions
- Chronological order

### Contribution Types Breakdown
- 💻 Code contributions
- 📚 Documentation
- 🐛 Bug fixes
- 👀 Code reviews

---

## 🚀 How to Use

### Viewing the Dashboard

**Option 1: Local Viewing**
```bash
# Open the HTML file directly
open docs/contribution-metrics-dashboard.html

# Or use a local server
python -m http.server 8000
# Then visit: http://localhost:8000/docs/contribution-metrics-dashboard.html
```

**Option 2: GitHub Pages** (if enabled)
```
https://[username].github.io/AstraGuard-AI-Apertre-3.0/docs/contribution-metrics-dashboard.html
```

### Generating Metrics Data

The dashboard reads data from `contributor_metrics.json`. Generate it using:

```bash
# Set your GitHub token
export GITHUB_TOKEN="your_token_here"

# Generate metrics
python scripts/maintenance/generate_metrics.py \
  --repo sr-857/AstraGuard-AI-Apertre-3.0 \
  --token $GITHUB_TOKEN \
  --output docs/contributor_metrics.json \
  --summary

# The --summary flag prints a console report
```

**Output:**
```json
{
  "generated_at": "2026-02-15T10:30:00",
  "repository": "sr-857/AstraGuard-AI-Apertre-3.0",
  "total_contributors": 42,
  "total_prs": 156,
  "total_issues": 89,
  "active_this_month": 18,
  "tier_distribution": { ... },
  "top_contributors": [ ... ],
  "recent_activity": [ ... ],
  "contribution_types": { ... }
}
```

---

## 🤖 Automation

### GitHub Action

The dashboard data is automatically updated:
- **Weekly**: Every Sunday at midnight UTC
- **On PR Merge**: Triggers when PRs are merged to main
- **Manual**: Can be triggered anytime

**Workflow**: `.github/workflows/metrics-dashboard.yml`

### Manual Update

```bash
# Trigger GitHub Action manually
gh workflow run metrics-dashboard.yml

# Or via web interface
# Actions → Metrics Dashboard Update → Run workflow
```

---

## 📋 Metrics Explained

### Total Contributors
All unique users who have contributed at least one merged PR to the repository.

### Merged PRs
Total number of pull requests successfully merged into the main branch.

### Closed Issues
Issues that have been resolved and closed (not just any closed issue).

### Active This Month
Contributors who have had at least one PR merged in the current calendar month.

### Tier Distribution
Breakdown of contributors across the 5-tier recognition system. Calculated based on total merged PR count.

### Contribution Types

**Code Contributions**: PRs primarily containing code changes (new features, enhancements).

**Documentation**: PRs focused on documentation improvements (README, guides, API docs).

**Bug Fixes**: PRs labeled with `bug`, `bugfix`, or containing "fix" in the title.

**Reviews**: Estimated based on code review activity (approximate).

---

## 🎨 Customization

### Styling

Edit the `<style>` section in `contribution-metrics-dashboard.html`:

```css
/* Change color scheme */
body {
    background: linear-gradient(135deg, #your-colors);
}

/* Modify stat cards */
.stat-card {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 15px;
}
```

### Data Source

The dashboard reads from `contributor_metrics.json` by default. To use a different source:

```javascript
// In the loadMetrics() function
async function loadMetrics() {
    const response = await fetch('YOUR_API_ENDPOINT');
    const data = await response.json();
    updateDashboard(data);
}
```

### Refresh Interval

Auto-refresh is set to 5 minutes. To change:

```javascript
// Change 5 * 60 * 1000 to your desired interval (in milliseconds)
setInterval(loadMetrics, 10 * 60 * 1000); // 10 minutes
```

---

## 🔧 Troubleshooting

### Issue: Dashboard shows "Loading..." forever

**Cause**: `contributor_metrics.json` file not found.

**Solution**:
```bash
# Generate the metrics file
python scripts/maintenance/generate_metrics.py --token $GITHUB_TOKEN
```

### Issue: Data looks outdated

**Cause**: Metrics haven't been regenerated recently.

**Solution**:
```bash
# Manually regenerate
python scripts/maintenance/generate_metrics.py --token $GITHUB_TOKEN

# Or trigger GitHub Action
gh workflow run metrics-dashboard.yml
```

### Issue: GitHub API rate limit exceeded

**Cause**: Too many requests without authentication.

**Solution**:
- Always use an authenticated token
- Token provides 5000 req/hour (vs 60 without)
- Wait for rate limit reset

### Issue: Some contributors missing

**Cause**: GitHub API pagination limits.

**Solution**:
- Script already handles pagination automatically
- If still missing, check contributor hasn't opted out
- Verify PRs are actually merged (not just closed)

---

## 📊 Data Sources

### GitHub REST API Endpoints

The dashboard uses these GitHub API endpoints:

```
GET /repos/:owner/:repo/contributors
GET /search/issues?q=repo:...+type:pr+is:merged
GET /search/issues?q=repo:...+type:issue+is:closed
```

**Rate Limits**:
- Authenticated: 5,000 requests/hour
- Unauthenticated: 60 requests/hour

### Data Caching

Metrics are cached in JSON file to:
- Reduce API calls
- Improve dashboard load time
- Provide offline viewing

**Recommended Update Frequency**: Weekly or on significant changes

---

## 🎯 Best Practices

### For Maintainers

**DO:**
- ✅ Update metrics weekly
- ✅ Verify data accuracy monthly
- ✅ Share dashboard link with community
- ✅ Celebrate milestones shown in metrics

**DON'T:**
- ❌ Update too frequently (API limits)
- ❌ Manually edit JSON (use generation script)
- ❌ Forget to commit updated metrics
- ❌ Ignore data anomalies

### For Contributors

**View Your Stats:**
1. Open the dashboard
2. Find your username in Top Contributors
3. Check your tier badge and rank
4. Track your progress over time

**Improve Your Ranking:**
- Make quality contributions
- Help with code reviews
- Improve documentation
- Fix bugs and issues

---

## 🔗 Integration

### Embedding in Website

```html
<iframe 
  src="contribution-metrics-dashboard.html" 
  width="100%" 
  height="800px" 
  frameborder="0">
</iframe>
```

### Linking from README

```markdown
## 📊 Contribution Metrics

Check out our [Contribution Metrics Dashboard](docs/contribution-metrics-dashboard.html) 
to see real-time community statistics!
```

### API Endpoint (Optional)

Create a simple API to serve metrics:

```python
from flask import Flask, jsonify
import json

app = Flask(__name__)

@app.route('/api/metrics')
def get_metrics():
    with open('docs/contributor_metrics.json') as f:
        return jsonify(json.load(f))

if __name__ == '__main__':
    app.run(port=5000)
```

---

## 📈 Future Enhancements

### Planned Features

- [ ] **Historical Trends**: Track metrics over time with charts
- [ ] **Contributor Profiles**: Detailed individual contribution pages
- [ ] **Compare Periods**: Month-over-month, year-over-year comparisons
- [ ] **Export Reports**: PDF/CSV export functionality
- [ ] **Badges**: Auto-generate contributor badge images
- [ ] **Leaderboard Categories**: By contribution type
- [ ] **Interactive Charts**: Click to drill down into details
- [ ] **Mobile Optimization**: Better responsive design

### Community Suggestions

Have ideas for the dashboard? 
- Open an issue with label `metrics-dashboard`
- Submit a PR with your enhancement
- Discuss in [GitHub Discussions](https://github.com/sr-857/AstraGuard-AI-Apertre-3.0/discussions)

---

## 📞 Support

### Need Help?

**Documentation:**
- [Contributor Recognition Program](../.github/CONTRIBUTOR_RECOGNITION.md)
- [CONTRIBUTORS.md](../CONTRIBUTORS.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)

**Questions:**
- Open a [GitHub Discussion](https://github.com/sr-857/AstraGuard-AI-Apertre-3.0/discussions)
- Tag maintainers: @sr-857
- Email: subhajitroy857@gmail.com

### Reporting Issues

Found a bug in the dashboard?
1. Check existing issues
2. Create new issue with `dashboard` label
3. Include:
   - Screenshot of the problem
   - Browser and version
   - Console errors (F12 → Console)
   - Steps to reproduce

---

## 📜 Technical Details

### Technology Stack

- **Frontend**: Pure HTML/CSS/JavaScript (no frameworks)
- **Styling**: Custom CSS with gradients and animations
- **Data Format**: JSON
- **Data Generation**: Python 3.8+
- **API**: GitHub REST API v3

### Browser Compatibility

- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+
- ⚠️ IE 11 (limited support)

### Performance

- **Load Time**: < 1 second (with cached data)
- **File Size**: ~15KB HTML + ~50KB JSON (typical)
- **API Calls**: Zero (reads from static JSON)
- **Refresh Rate**: 5 minutes (configurable)

---

## 🎓 Learning Resources

### For Developers

**Understanding the Code:**
- `generate_metrics.py`: Python script with GitHub API integration
- `contribution-metrics-dashboard.html`: Self-contained dashboard
- Well-commented code for learning

**Extending the Dashboard:**
1. Fork the repository
2. Modify the HTML/CSS/JS as needed
3. Test with sample data
4. Submit PR with your enhancements

### For Data Scientists

**Available Data:**
- Contributor counts and tiers
- PR merge frequency
- Contribution type distribution
- Temporal activity patterns

**Analysis Opportunities:**
- Contributor retention analysis
- Seasonal activity patterns
- Contribution quality metrics
- Community growth trends

---

## 🏆 Credits

**Created for**: Issue #700 - Create contribution metrics dashboard  
**Event**: Elite Coders Winter of Code (Apertre 3.0) 2026  
**Category**: Community  
**Created by**: [@Yashaswini-V21](https://github.com/Yashaswini-V21)

---

## 📄 License

This dashboard and associated scripts are part of the AstraGuard AI project and licensed under the same terms (see [LICENSE](../LICENSE)).

---

*Version: 1.0*  
*Last Updated: February 15, 2026*  
*Status: Production Ready ✅*

# Contributing to AstraGuard AI for Apertre-3.0

Welcome to the AstraGuard AI project! We are thrilled to have you as part of Elite Coders Winter of Code '26.

## 👥 Contributor Roles & Focus Areas

We are looking for contributions in specific areas. Please identify your role and focus on relevant issues:

### 🎨 Frontend (React / Streamlit)
- **Focus**: Integrating the dashboard with the API, enhancing UI/UX, and visualizing real-time threat data.
- **Requirements**: Clean component structure, responsive design, and proper state management.
- **Mission-Phase Awareness**: When adding new UI elements for anomaly response, consider the mission phase constraints. Ensure the dashboard shows which actions are available/forbidden in the current phase.

### ⚙️ Backend (Node.js / FastAPI / Python)
- **Focus**: API development, data aggregation, authentication, and connecting the AI engine to the frontend.
- **Requirements**: Efficient endpoints, proper error handling, and comprehensive API documentation.
- **Mission-Phase Awareness**: When adding new anomaly detection or response logic, integrate it with the mission-phase policy engine (see `state_machine/mission_phase_policy_engine.py`). Your anomaly type should be evaluated against the current mission phase.

### 🛡️ Security Engine & Anomaly Detection (Python)
- **Focus**: Enhancing the anomaly detection logic, adding new fault classifiers, and improving the memory engine.
- **Requirements**: Security-first mindset, modular code, and rigorous testing.
- **Mission-Phase Awareness**: New anomaly types must be integrated into the policy system. Update `config/mission_phase_response_policy.yaml` with severity thresholds and escalation rules for your new anomaly type across all mission phases.

### 📋 Policy & Configuration (YAML)
- **Focus**: Defining and refining mission-phase policies, threat severity thresholds, and response escalation rules.
- **Requirements**: Clear documentation, realistic CubeSat constraints, and validation against test scenarios.
- **Key Files**:
  - `config/mission_phase_response_policy.yaml` - Main policy configuration
  - `config/mission_phase_policy_loader.py` - Policy parser and validator

## Understanding Mission Phases

AstraGuard now operates with **mission-phase awareness**. Before contributing, understand the five mission phases:

| Phase | Purpose | Key Constraint | Response Style |
|-------|---------|-----------------|-----------------|
| **LAUNCH** | Rocket ascent | Minimize disruption | Log-only |
| **DEPLOYMENT** | System stabilization | Avoid aggressive recovery | Alert operators |
| **NOMINAL_OPS** | Standard mission | Maximize reliability | Full automation |
| **PAYLOAD_OPS** | Science mission | Protect mission data | Balanced |
| **SAFE_MODE** | Survival mode | Minimal power draw | Passive monitoring |

**When adding new features:**
1. Identify which phases your feature affects
2. Update the policy config with appropriate thresholds and actions
3. Add tests covering at least LAUNCH, NOMINAL_OPS, and SAFE_MODE phases
4. Document the phase-specific behavior in your PR description

## 🚫 What We Do NOT Accept
- **Random PRs for streaks**: Submissions that just fix a typo or add a comment solely to keep a GitHub streak alive will be closed.
- **Unscoped work**: Please do not start working on a massive feature without discussing it in an issue first.
- **Low-quality code**: Code without types, tests, or documentation will not be merged.

## 📝 How to Contribute

1.  **Find an Issue**: Look for issues tagged with your role (e.g., `role:frontend`, `role:security`).
2.  **Claim the Issue**: Comment on the issue to let us know you are working on it.
3.  **Fork & Branch**: 
    ```bash
    git checkout -b feature/issue-id-short-description
    ```
4.  **Implement**: Write clean, tested code.
5.  **Submit PR**: detailed description of your changes.

## 👋 First Time Contributing?

New to AstraGuard or open source? Start with a **Good First Issue**!

### Finding Good First Issues

Look for issues labeled with:
- `good first issue` - Perfect for newcomers
- `easy` - Can be completed in 2-4 hours
- `apertre3.0` - Part of the Winter of Code event

**Browse Good First Issues**: [View all good first issues](https://github.com/sr-857/AstraGuard-AI-Apertre-3.0/labels/good%20first%20issue)

### What Makes a Good First Issue?

Good first issues are:
- ✅ **Well-defined** with clear acceptance criteria
- ✅ **Beginner-friendly** requiring minimal context
- ✅ **Quick wins** completable in 2-4 hours
- ✅ **Guided** with suggested approach and resources

For detailed criteria and examples, see:
- 📋 [Good First Issue Criteria](GOOD_FIRST_ISSUE_CRITERIA.md) - Full selection criteria
- 🛠️ [Good First Issue Maintainer Guide](../.github/GOOD_FIRST_ISSUE_MAINTAINER_GUIDE.md) - For maintainers

### Getting Help

Stuck on your first issue? We're here to help!

- 💬 **Comment on the issue** - Ask questions directly
- 📖 **Check the docs** - Review relevant documentation
- 🤝 **Join the discussion** - Connect with other contributors
- 📧 **Reach out** - Contact maintainers if needed

**Remember**: There are no silly questions! We all started somewhere. 🌱

## 🧪 Testing Guidelines
- Run existing tests before submitting.
- Add new tests for any new logic.
- Ensure the linter is happy (we use `black` for Python and `eslint` for JS).

## 📜 Code of Conduct
Be respectful, constructive, and inclusive. We are all here to learn and build something awesome together.

Happy Coding! 🚀

## 🏆 Contributor Recognition

We value and recognize all contributions! Check out our recognition program:

- **[CONTRIBUTORS.md](../CONTRIBUTORS.md)** - See all contributors and their tiers
- **[Metrics Dashboard](contribution-metrics-dashboard.html)** - View real-time contribution statistics
- **[Recognition Program](../.github/CONTRIBUTOR_RECOGNITION.md)** - Learn about recognition criteria and benefits
- **[Badge System](CONTRIBUTOR_BADGES.md)** - Explore available badges and how to earn them

### Recognition Tiers
- 🌱 **New Contributor** (1 PR): Welcome to the community!
- ⭐ **Active Contributor** (2-4 PRs): Regular engagement
- 💎 **Regular Contributor** (5-19 PRs): Consistent quality contributions
- 🌟 **Core Contributor** (20-49 PRs): Leadership and sustained excellence
- 👑 **Legend** (50+ PRs): Exceptional long-term commitment

### Get Recognized
Every merged PR counts toward your tier! Quality contributions can also earn specialty badges like:
- 🔒 Security Researcher
- 📚 Documentation Hero
- 🧪 Testing Champion
- 🤝 Community Mentor

---

## Apertre-3.0 2026 Contribution Guidelines

For participants in the **Elite Coders Winter of Code (Apertre-3.0) 2026** event:

### PR Requirements for Apertre-3.0 Scoring

To ensure your contribution is eligible for Apertre-3.0 scoring, your pull request **MUST**:

1. **Include the Apertre-3.0 Label**: All PRs must be labeled with `Apertre-3.0` for automatic tracking and scoring
2. **Reference an Issue**: Link your PR to an existing issue (e.g., "Closes #20")
3. **Clear Description**: Provide a detailed description of changes, motivation, and testing approach
4. **Follow Code Standards**: Adhere to project style guides and maintain code quality
5. **Pass All Checks**: Ensure CI/CD pipelines pass before submission

### Apertre-3.0 Scoring Criteria

- **Code Quality**: Well-written, tested, and maintainable code
- **Documentation**: Clear commit messages and PR descriptions
- **Testing**: Comprehensive test coverage for new features
- **Impact**: Meaningful contributions that address open issues or add value
- **Community**: Respectful collaboration and adherence to Code of Conduct

### Resources

- [Apertre-3.0 Official Website](https://code.elitecoders.xyz/)
- [AstraGuard-AI Issues](https://github.com/sr-857/AstraGuard-AI/issues)
- [AstraGuard-AI Discussions](https://github.com/sr-857/AstraGuard-AI/discussions)
- [Community Discussion Guidelines](./COMMUNITY_DISCUSSION_GUIDELINES.md)
- [Code of Conduct](./CODE_OF_CONDUCT.md)
- [PR Review Guidelines](./PR_REVIEW_GUIDELINES.md)
- [Project Documentation](../docs/)

### Questions About Contributing?

**Before you contribute, check out:**
- 📖 [Community Discussion Guidelines](./COMMUNITY_DISCUSSION_GUIDELINES.md) — How to ask questions and participate in the community
- 🤝 [Code of Conduct](./CODE_OF_CONDUCT.md) — Our community values
- ✅ [PR Review Guidelines](./PR_REVIEW_GUIDELINES.md) — What reviewers look for

Not sure where to start? Post your questions in [GitHub Discussions](https://github.com/sr-857/AstraGuard-AI/discussions) in the **Questions** category!

Good luck with your contributions! We're excited to see what you build. 🚀

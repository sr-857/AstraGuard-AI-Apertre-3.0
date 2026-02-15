# PR Review Guidelines for AstraGuard AI

This document provides clear guidelines for reviewers and contributors to ensure consistent, high-quality peer reviews that maintain project standards and foster a positive contributor experience.
1
---

## 📋 What Reviewers Should Check

### 1. **Scope & Correctness**
- [ ] PR addresses the linked issue(s) completely
- [ ] Changes are scoped appropriately — not mixing unrelated concerns
- [ ] Implementation logic is correct and follows the intended design
- [ ] No unintended side effects or breaking changes
- [ ] Changes align with project architecture and patterns

### 2. **Code Quality**
- [ ] Code follows project style guides (Black for Python, ESLint for JS/React)
- [ ] Code is readable and maintainable
- [ ] Functions/classes have clear purposes (avoid overly complex logic)
- [ ] Type hints are present (Python) and types are correct
- [ ] No commented-out code or debug statements left behind
- [ ] Naming conventions are consistent with the codebase

### 3. **Testing**
- [ ] New features have corresponding tests (unit and/or integration)
- [ ] Tests cover happy paths, edge cases, and error scenarios
- [ ] Existing tests still pass (review CI results)
- [ ] Test coverage doesn't decrease significantly
- [ ] Tests are meaningful and not just "check if code runs"

### 4. **Documentation**
- [ ] Code changes include updated docstrings/comments where appropriate
- [ ] README or relevant docs are updated if behavior changes
- [ ] API changes are documented (new endpoints, parameter changes, etc.)
- [ ] Complex logic includes inline comments explaining "why"
- [ ] YAML/config changes include explanations of new fields

### 5. **CI/CD Status**
- [ ] All CI checks pass (tests, linting, static analysis)
- [ ] CodeQL security analysis passes
- [ ] Any warnings or issues are explained in the PR description
- [ ] Pre-existing failures (unrelated to this PR) are documented

### 6. **Mission-Phase Awareness** *(AstraGuard specific)*
- [ ] If adding anomaly detection or response logic: integrated with mission phase policy engine
- [ ] New anomaly types: `config/mission_phase_response_policy.yaml` is updated
- [ ] Response behavior varies appropriately across phases (LAUNCH, DEPLOYMENT, NOMINAL_OPS, PAYLOAD_OPS, SAFE_MODE)
- [ ] Tests cover at least LAUNCH, NOMINAL_OPS, and SAFE_MODE phases

---

## 📐 PR Size & Focus Expectations

### Best Practices
- **Size**: 200-400 lines of code changes is ideal; 600+ warrants discussion
- **Focus**: One feature or bug fix per PR (avoid combining unrelated changes)
- **Commits**: Logical, atomic commits with clear messages
- **Branch**: Created from `main`, branch name follows pattern: `feature/issue-number-description` or `fix/issue-number-description`

### Red Flags
- ❌ "Fix typo + refactor entire module + add new feature" in one PR
- ❌ Massive PRs (1000+ lines) without discussion
- ❌ Multiple unrelated issues combined
- ❌ Commits with vague messages ("update stuff", "fixes")

### When to Split or Combine
| Scenario | Action |
|----------|--------|
| Large feature with clear sub-tasks | Split into multiple PRs with clear dependencies |
| Typo in file + related bug fixes | Combine only if the file scope is tightly related |
| Unrelated features | **Always** separate PRs |
| Dependency upgrade + bugfix in same module | Can combine if coordinated |

---

## ⚙️ Handling CI Failures & Pre-existing Issues

### If CI Fails on Your PR
1. **Review the failure**: Check the CI logs to understand what failed
2. **Fix in your PR**: Make changes to resolve the failure, then push
3. **Push and re-run**: CI will automatically re-run on new commits
4. **No force-push**: Avoid force-pushing unless asked; history helps reviewers

### Pre-existing CI Failures
- If a test was already failing in `main`, document this:
  - Reference the issue number in your PR description
  - Example: "⚠️ Pre-existing failure: #456 - test_old_component.py fails on main"
- This helps reviewers distinguish your changes from existing issues
- Work with maintainers to resolve pre-existing failures in separate PRs

### When to Exclude Pre-existing Unrelated Tests
- If your change doesn't touch code related to a failing test, it's acceptable for that test to still fail
- Always note this clearly in the PR description
- Example: "My changes don't affect the legacy API; pre-existing test_legacy_api.py failure remains"

---

## 💬 Review Etiquette & Guidelines

### For Reviewers: Giving Feedback

#### ✅ **Constructive Feedback**
- **Be specific**: Instead of "This is wrong," say "This will fail when X happens because Y. Consider using Z instead."
- **Explain the why**: Help contributors understand the reasoning, not just the correction
- **Offer alternatives**: When suggesting changes, provide options or examples
- **Acknowledge good work**: Praise well-written code, clever solutions, or thorough tests

#### ✅ **Types of Comments**
- **🎯 Must-fix**: Use blocking comments; these prevent merge until addressed
- **💡 Nice-to-have**: Use non-blocking suggestions for improvements
- **❓ Questions**: Ask clarifying questions if you're unsure about logic
- **📚 Reference docs**: Link to style guides, related PRs, or architecture docs

#### ✅ **Tone**
- Assume good intent — the contributor is trying their best
- Use collaborative language: "Could we" instead of "You need to"
- Celebrate effort: "Great test coverage!" or "Nice refactoring!"

#### ❌ **What to Avoid**
- Nitpicking style issues when the code is already linted
- Requesting changes outside the PR's scope
- Critical comments without constructive solutions
- Personal criticism ("This code is terrible" vs. "This could be clearer")

### For Contributors: Responding to Feedback

#### ✅ **Best Practices**
1. **Thank reviewers** for their time and feedback
2. **Clarify concerns** if you don't understand a comment
3. **Explain decisions** if you disagree respectfully ("I chose Y because Z, but I'm open to alternatives")
4. **Push fixes promptly** and use the "Re-request review" button after changes
5. **Mark conversations** as resolved only after reviewer confirms

#### ❌ **What to Avoid**
- Dismissing feedback without discussion
- Committing changes without responding to comments
- Taking criticism personally
- Long defensive explanations; short, clear responses are better

### Approval Guidelines

#### Ready to Approve
- All must-fix comments are addressed
- CI passes
- Code quality meets standards
- No ongoing discussion that needs resolution

#### Conditional Approval
- Use "Changes requested" for blocking issues
- Use "Comment" for non-blocking observations
- Use "Approve" only when satisfied with the current state

---

## ✅ Requirements for "Ready to Merge"

A PR is considered **ready to merge** when ALL of the following are true:

### Code & Functionality
- ✅ Linked issue is fully addressed
- ✅ Implementation is correct and tested
- ✅ Code follows project standards and conventions
- ✅ No unintended side effects or regressions

### Testing & Quality
- ✅ All new code has corresponding tests
- ✅ All CI checks pass (unit tests, linting, security)
- ✅ Test coverage does not decrease
- ✅ Pre-existing failures are documented (if any)

### Documentation
- ✅ Code is documented where appropriate
- ✅ User-facing changes have documentation updates
- ✅ API changes are clearly described
- ✅ Mission-phase implications are addressed (if applicable)

### Review & Approval
- ✅ At least one approval from a maintainer or code owner
- ✅ All blocking comments are resolved
- ✅ No ongoing discussion or "Changes requested"
- ✅ Apertre-3.0 label applied (for scoring eligibility)

### Final Checks
- ✅ Branch is up-to-date with `main` (no merge conflicts)
- ✅ PR title and description clearly summarize changes
- ✅ Commit history is clean and logical
- ✅ No security vulnerabilities introduced (CodeQL passes)

---

## 🔄 Review Timeline Expectations

- **Initial review**: Typically within 24-48 hours of PR creation
- **Follow-up on changes**: Reviewer will re-check within 24 hours of updates
- **Urgent PRs**: Tag with `priority:critical` for faster review (within 4 hours)
- **Weekend/holiday delays**: Be patient; maintainers are volunteers

### Accelerating Your Review
- Write clear, descriptive PR descriptions (reviewers spend less time understanding context)
- Keep PRs focused and reasonably sized
- Ensure CI is passing before requesting review
- Be responsive to feedback

---

## 🌟 Example: Good PR Review Cycle

**Contributor submits PR:**
- Clear description: "Adds anomaly detection for power spikes in NOMINAL_OPS phase"
- Linked to issue: "Closes #215"
- CI passes, focused changes (120 lines added)

**Reviewer comments** (constructive, specific):
- ✅ "Great test coverage! I like the edge case for phase transitions."
- 💡 "Consider updating `OPTIMIZATION_SUMMARY_PHASE_AWARE_HANDLER.md` with this new detection type for future maintainers."
- ❓ "Is the threshold value (150W) derived from CubeSat specs? Should this be configurable in the policy file?"

**Contributor responds:**
- "Thanks for the feedback! I've added a comment explaining the 150W threshold. I'll open a separate issue to make it configurable in future PRs."
- Updates doc file in the same PR

**Reviewer approves:**
- "Looks good! Merging now. Thanks for the thorough implementation."

**PR is merged** ✅

---

## 📞 Questions or Disagreements?

If you disagree with feedback:
1. **Respectfully explain** your perspective in a comment
2. **Ask for clarification** if the suggestion is unclear
3. **Suggest alternatives** if you see a better approach
4. **Escalate if needed**: Tag a maintainer or open a discussion

The goal is consensus and quality—not winning an argument. Maintainers have final say on merge decisions.

---

## 🔗 Related Resources

- [CONTRIBUTING.md](CONTRIBUTING.md) — How to contribute
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — Community standards
- [TECHNICAL.md](TECHNICAL.md) — Architecture and design patterns
- [QUICKSTART_412.md](QUICKSTART_412.md) — Getting started

---

**Last Updated**: February 2026  
**For questions or improvements to these guidelines, open an issue or discussion on GitHub.**

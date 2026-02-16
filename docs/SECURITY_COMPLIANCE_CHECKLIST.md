# Security & Compliance Checklist

**Version:** 1.0  
**Last Updated:** February 14, 2026  
**Purpose:** Pre-release security and compliance verification for AstraGuard AI

This checklist ensures that security, compliance, and operational best practices are followed before each release. It is designed specifically for AstraGuard AI's architecture and workflows.

---

## How to Use This Checklist

- [ ] **Before each release:** Review every section and check off completed items
- [ ] **Track issues:** Create GitHub issues for any unchecked items that need remediation
- [ ] **Document exceptions:** Note any items that don't apply with justification
- [ ] **Update regularly:** Revise this checklist as new security practices emerge

---

## 1. Dependency Security

### Python Dependencies

- [ ] All Python dependencies are pinned to specific versions in `requirements*.txt` files
- [ ] No dependencies with known critical/high CVEs (verify with `safety check`)
- [ ] Dependencies are from trusted sources (PyPI official packages)
- [ ] Unused dependencies have been removed from requirements files
- [ ] Development dependencies are separated from production (`requirements.txt` vs `requirements-dev.txt`)
- [ ] `dependabot` or similar automated dependency updates enabled in GitHub
- [ ] Regular dependency audit scheduled (monthly minimum)

**Verification Commands:**
```bash
# Check for known vulnerabilities
safety check --file=src/config/requirements.txt
safety check --file=src/config/requirements-dev.txt

# Check for outdated packages
pip list --outdated
```

**Reference Files:**
- [src/config/requirements.txt](../src/config/requirements.txt)
- [src/config/requirements-dev.txt](../src/config/requirements-dev.txt)
- [src/config/requirements-ci.txt](../src/config/requirements-ci.txt)

---

### Node.js/JavaScript Dependencies

- [ ] `package-lock.json` is committed to version control (ensures reproducible builds)
- [ ] No dependencies with known critical/high CVEs (verify with `npm audit`)
- [ ] Dependencies are from trusted npm registry
- [ ] Unused npm packages have been removed
- [ ] Frontend dependencies are updated regularly
- [ ] `npm audit fix` has been run and reviewed

**Verification Commands:**
```bash
# Check for vulnerabilities in Node.js dependencies
cd ui/frontend/as_lp && npm audit

# Check for outdated packages
npm outdated

# Automated fix for non-breaking vulnerabilities
npm audit fix
```

**Reference Files:**
- [package.json](../package.json)
- [ui/frontend/as_lp/package.json](../ui/frontend/as_lp/package.json)

---

### Docker Base Images

- [ ] All Docker base images use specific tags (not `latest`)
- [ ] Base images are from official/verified publishers
- [ ] Images are scanned for vulnerabilities (Trivy, Snyk, or similar)
- [ ] Multi-stage builds are used to minimize final image size
- [ ] No secrets embedded in Docker images

**Verification Commands:**
```bash
# Scan Docker image for vulnerabilities (install trivy if needed)
trivy image <image-name>:<tag>

# Check Dockerfile for best practices
docker run --rm -i hadolint/hadolint < infra/docker/Dockerfile
```

**Reference Files:**
- [infra/docker/Dockerfile](../infra/docker/Dockerfile)

---

### Dependency Update Policy

- [ ] Documented process for reviewing and applying security patches
- [ ] Critical vulnerabilities patched within 7 days
- [ ] High vulnerabilities patched within 30 days
- [ ] Regular update cycle scheduled (quarterly for non-security updates)
- [ ] Change log reviewed before updating major versions

**Action Items:**
- Enable GitHub Dependabot alerts and security updates
- Set up automated PR creation for dependency updates
- Subscribe to security advisories for critical dependencies (PyTorch, FastAPI, React)

---

## 2. Secrets Management

### Environment Variables & Configuration

- [ ] No hardcoded secrets in source code (API keys, passwords, tokens)
- [ ] All `.env` files are in `.gitignore`
- [ ] `.env.example` files provided with placeholder values (no real secrets)
- [ ] Secrets are loaded from environment variables or secure vaults
- [ ] Production secrets never committed to version control

**Verification Commands:**
```bash
# Search for potential hardcoded secrets
git grep -i "api_key\s*=\s*['\"](?!.*secret)" 
git grep -i "password\s*=\s*['\"](?!.*your_|<)"
git grep -i "token\s*=\s*['\"](?!.*example)"

# Check git history for accidentally committed secrets
git log -p -S "API_KEY" --source --all
```

**Reference Files:**
- [.gitignore](../.gitignore) - Verify `.env` is excluded
- [docs/AUTH_SECRETS.md](AUTH_SECRETS.md) - Secrets management documentation
- [config/.env.example](../config/.env.example) - Template with no real secrets

---

### GitHub Secrets Configuration

- [ ] All CI/CD secrets stored in GitHub Secrets (not in workflow files)
- [ ] Secrets have minimal necessary permissions
- [ ] Unused secrets removed from repository settings
- [ ] Secret rotation policy documented and followed
- [ ] Personal Access Tokens (PATs) use fine-grained permissions

**Check GitHub Settings:**
- Navigate to: `Settings > Secrets and variables > Actions`
- Verify: All secrets are documented and necessary
- Review: Expiration dates for tokens/credentials

---

### API Keys & Authentication Tokens

- [ ] API keys are environment-specific (dev/staging/prod separated)
- [ ] API keys have scoped permissions (principle of least privilege)
- [ ] Expired or unused API keys have been revoked
- [ ] API key rotation schedule documented (at least annually)
- [ ] Keys are never logged in application outputs

**Files to Review:**
- [config/api_keys.json](../config/api_keys.json) - Should NOT contain real keys
- Application logs - Verify no secrets are logged

---

### Secret Scanning

- [ ] GitHub secret scanning enabled on repository
- [ ] Pre-commit hooks prevent accidental secret commits (optional but recommended)
- [ ] Regular audits of commit history for leaked secrets
- [ ] Immediate rotation procedure documented for leaked secrets

**Verification:**
- Check: `Settings > Code security and analysis > Secret scanning`
- Status: Should be enabled with alerts active

**Tools:**
```bash
# Install and run gitleaks to scan for secrets
docker run -v $(pwd):/repo zricethezav/gitleaks:latest detect --source /repo --verbose

# Or use trufflehog
docker run --rm -v $(pwd):/repo trufflesecurity/trufflehog:latest filesystem /repo
```

---

## 3. Access Control & Permissions

### Repository Access

- [ ] Branch protection rules enabled on `main` and `develop` branches
- [ ] Required pull request reviews before merging (minimum 1 reviewer)
- [ ] "Require status checks to pass" enabled for CI/CD workflows
- [ ] "Require signed commits" considered/enabled for sensitive changes
- [ ] Admin access limited to core maintainers only
- [ ] Inactive collaborators removed from repository

**Check GitHub Settings:**
- Navigate to: `Settings > Branches > Branch protection rules`
- Required rules for `main` branch:
  - ✅ Require pull request before merging
  - ✅ Require status checks to pass (tests, linting, security)
  - ✅ Require conversation resolution before merging
  - ✅ Do not allow bypassing the above settings

---

### GitHub Actions Permissions

- [ ] Workflow permissions set to least privilege (read-only by default)
- [ ] Token permissions explicitly defined in each workflow file
- [ ] No workflows have unnecessary `write` access
- [ ] Third-party actions are pinned to specific commit SHAs (not tags)
- [ ] Third-party actions are from verified/trusted publishers

**Verification:**
```bash
# Check workflow files for permissions
grep -r "permissions:" .github/workflows/

# Check for unpinned actions (should use @sha, not @v1)
grep -r "uses:.*@v[0-9]" .github/workflows/
```

**Reference Files:**
- Review all files in [.github/workflows/](.github/workflows/)

---

### Container & Infrastructure Access

- [ ] Container registry access limited to CI/CD pipelines and authorized users
- [ ] Kubernetes cluster access follows RBAC (Role-Based Access Control)
- [ ] Service accounts have minimal required permissions
- [ ] No shared credentials across environments (dev/staging/prod)
- [ ] Infrastructure access logs are monitored

**Files to Review:**
- [infra/k8s/](../infra/k8s/) - Check RBAC configurations
- [infra/helm/](../infra/helm/) - Review service account permissions

---

### API Authentication & Authorization

- [ ] All API endpoints require authentication (except public endpoints)
- [ ] JWT tokens have reasonable expiration times (not excessive)
- [ ] Authorization checks verify user permissions before actions
- [ ] Rate limiting implemented on public/authenticated endpoints
- [ ] API tokens can be revoked independently

**Code Review:**
- [src/api/](../src/api/) - Review authentication middleware
- [src/security/](../src/security/) - Verify authentication logic

**Test:**
```bash
# Test unauthenticated access to protected endpoints
curl -X GET http://localhost:8000/api/protected-endpoint
# Should return 401 Unauthorized
```

---

## 4. CI/CD Security Checks

### Automated Testing

- [ ] Unit tests run on every pull request
- [ ] Integration tests verify critical workflows
- [ ] Test coverage tracked (minimum 70% recommended)
- [ ] Tests include security-specific test cases
- [ ] Failed tests block merging to main branch

**Verification:**
- Check workflow: [.github/workflows/tests.yml](../.github/workflows/tests.yml)
- Review test files in [tests/](../tests/)

**Commands:**
```bash
# Run tests locally
pytest tests/ --cov=src --cov-report=html

# Check test coverage
coverage report --fail-under=70
```

---

### Static Code Analysis

- [ ] Linting enabled (Black, Flake8 for Python; ESLint for JavaScript)
- [ ] Type checking enforced (MyPy for Python; TypeScript for JS)
- [ ] Security linting enabled (Bandit for Python)
- [ ] Code quality gates configured (blocking on critical issues)
- [ ] Linting rules documented and consistent across team

**Current Tools in Use:**
- Python: Black, Flake8, MyPy, Pylint, Bandit
- Configured in: [.github/workflows/tests.yml](../.github/workflows/tests.yml)

---

### Security Scanning

- [ ] CodeQL analysis enabled and running on schedule
- [ ] Dependency vulnerability scanning active (Safety for Python, npm audit)
- [ ] Container image scanning before deployment
- [ ] SAST (Static Application Security Testing) results reviewed
- [ ] No critical/high vulnerabilities in production code

**Active Scans:**
- CodeQL: [.github/workflows/codeql.yml](../.github/workflows/codeql.yml)
- Safety: [.github/workflows/tests.yml](../.github/workflows/tests.yml) (security job)

**Verify:**
```bash
# Run security scan locally
bandit -r src/ -f json -o bandit-report.json
safety check
```

---

### Build & Deployment Pipeline

- [ ] Build artifacts are reproducible (pinned dependencies, locked versions)
- [ ] Builds run in isolated environments (containers)
- [ ] No secrets embedded in build artifacts
- [ ] Deployment to production requires manual approval
- [ ] Rollback procedure documented and tested
- [ ] All deployments are logged and traceable

**Reference:**
- Build workflow: [.github/workflows/ci-cd.yml](../.github/workflows/ci-cd.yml)
- Deployment workflow: [.github/workflows/cd.yml](../.github/workflows/cd.yml)

---

### Pipeline Security Best Practices

- [ ] Workflow files use `concurrency` to prevent race conditions
- [ ] Sensitive operations use `environment` protection rules
- [ ] Pipeline logs don't expose secrets (mask secrets in outputs)
- [ ] Third-party GitHub Actions verified and pinned to commit SHAs
- [ ] Pipeline failures alert maintainers

**Check:**
```yaml
# Example of proper secret masking
- name: Use secret safely
  run: |
    echo "::add-mask::${{ secrets.SECRET_KEY }}"
    # Use secret without exposing it
```

---

## 5. Logging & Auditability

### Application Logging

- [ ] Structured logging implemented (JSON format recommended)
- [ ] Log levels configured appropriately (DEBUG for dev, INFO/WARNING for prod)
- [ ] No sensitive data logged (passwords, tokens, PII)
- [ ] Errors and exceptions logged with sufficient context
- [ ] Request/response logging includes correlation IDs for tracing

**Implementation Check:**
- Structured logging library: `structlog` (configured in requirements.txt)
- Review logging in: [src/](../src/)

**Test:**
```python
# Example of safe logging
import structlog
logger = structlog.get_logger()

# Good: No sensitive data
logger.info("user_login", user_id="12345", action="login")

# Bad: Exposes password (DON'T DO THIS)
# logger.info("login", password="secret123")  # NEVER LOG SECRETS
```

---

### Monitoring & Observability

- [ ] Application metrics exported (Prometheus format)
- [ ] OpenTelemetry tracing configured for distributed requests
- [ ] Health check endpoints exposed and monitored
- [ ] Error rates and latency tracked
- [ ] Alerts configured for anomalous behavior

**Active Monitoring:**
- Prometheus: Client library configured in requirements.txt
- OpenTelemetry: Instrumentation libraries installed
- Reference: [infra/prometheus/](../infra/prometheus/), [infra/grafana/](../infra/grafana/)

---

### Audit Trails

- [ ] Critical actions logged (authentication, authorization failures, data changes)
- [ ] Audit logs immutable (append-only, tamper-evident)
- [ ] Audit logs retained for compliance period (minimum 90 days)
- [ ] User actions traceable to specific accounts
- [ ] Administrative actions logged separately

**Files to Review:**
- [logs/audit/](../logs/audit/) - Audit log storage
- Audit implementation: Check authentication/authorization modules

---

### Log Security & Retention

- [ ] Logs stored securely (encrypted at rest in production)
- [ ] Log access restricted to authorized personnel
- [ ] Log retention policy documented and automated
- [ ] Old logs archived or securely deleted
- [ ] No log injection vulnerabilities (input sanitization)

**Best Practices:**
```python
# Prevent log injection
import re

def sanitize_log_input(user_input: str) -> str:
    """Remove newlines and control characters to prevent log injection."""
    return re.sub(r'[\n\r\t]', '', user_input)

logger.info("user_action", username=sanitize_log_input(username))
```

---

### Centralized Logging (Production)

- [ ] Logs aggregated to centralized system (ELK, Loki, CloudWatch, etc.)
- [ ] Log search and filtering capabilities available
- [ ] Real-time log monitoring for security events
- [ ] Log correlation across services enabled
- [ ] Log dashboard accessible to operations team

---

## 6. Open Source License Compliance

### License Documentation

- [ ] Project license clearly specified (LICENSE file in root)
- [ ] License type is MIT (verified in [LICENSE](../LICENSE))
- [ ] Copyright notice up to date
- [ ] License badge displayed in README
- [ ] Third-party license attributions included

**Current License:** MIT License (permissive open source)

---

### Dependency License Compatibility

- [ ] All dependencies use licenses compatible with MIT
- [ ] Copyleft licenses (GPL) avoided or properly isolated
- [ ] Commercial/proprietary dependencies documented
- [ ] License compatibility reviewed before adding new dependencies

**Check Licenses:**
```bash
# Python dependencies
pip-licenses --format=markdown --output-file=LICENSES_PYTHON.md

# Node.js dependencies
cd ui/frontend/as_lp
npx license-checker --summary
```

**Common Compatible Licenses:**
- ✅ MIT, BSD, Apache 2.0, ISC (permissive, fully compatible)
- ⚠️ LGPL (weak copyleft, use with caution)
- ❌ GPL v2/v3 (strong copyleft, avoid for libraries)

---

### Attribution & Notices

- [ ] NOTICE file created if required by dependencies (Apache 2.0)
- [ ] Third-party code properly attributed
- [ ] Modified third-party code marked clearly
- [ ] Copyright headers in source files (if required by policy)

**Sample NOTICE Entry:**
```
This software includes code from:
- Project Name (https://github.com/org/repo)
  License: Apache 2.0
  Copyright: (c) 2024 Author Name
```

---

### Contributor Agreements

- [ ] Contributing guidelines documented ([CONTRIBUTING.md](CONTRIBUTING.md))
- [ ] Contributor License Agreement (CLA) not required for MIT projects
- [ ] Contributors retain copyright (standard for MIT)
- [ ] Code of Conduct enforced ([CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md))

---

### License Headers (Optional)

For projects requiring license headers in source files:

```python
# Copyright (c) 2024 AstraGuard AI Team
# Licensed under the MIT License
# See LICENSE file in the project root for full license information.
```

**Note:** Not mandatory for MIT license but recommended for clarity.

---

## 7. Data Handling & Privacy

### Data Security

- [ ] User data encrypted at rest (databases, file storage)
- [ ] Data encrypted in transit (TLS/HTTPS only)
- [ ] Database credentials rotated regularly
- [ ] Database backups encrypted and tested
- [ ] Data anonymization applied where appropriate

**Implementation:**
- TLS configuration: Check Kubernetes ingress/load balancer settings
- Database encryption: Verify in [infra/k8s/](../infra/k8s/)

---

### Data Retention & Deletion

- [ ] Data retention policy documented
- [ ] Automated data deletion for expired records
- [ ] User data deletion process implemented (if applicable)
- [ ] Backup retention limits configured
- [ ] Compliance with relevant data protection regulations

---

### Privacy Considerations

- [ ] Privacy policy published (if collecting user data)
- [ ] User consent obtained for data collection
- [ ] Minimal data collection (only what's necessary)
- [ ] Third-party data sharing documented
- [ ] Data breach response plan documented

---

## 8. Incident Response & Recovery

### Incident Response Plan

- [ ] Security incident response plan documented
- [ ] Contact information for security team maintained
- [ ] Escalation procedures defined
- [ ] Post-incident review process established
- [ ] Security incidents tracked and analyzed

**Reference:**
- Security contact: Check [docs/](../docs/) for security policies

---

### Disaster Recovery

- [ ] Backup and restore procedures documented
- [ ] Recovery Time Objective (RTO) defined
- [ ] Recovery Point Objective (RPO) defined
- [ ] Disaster recovery plan tested regularly
- [ ] Backup integrity verified periodically

**Files:**
- [docs/e2e-recovery-pipeline.md](e2e-recovery-pipeline.md)

---

### Rollback Procedures

- [ ] Deployment rollback procedure documented
- [ ] Database migration rollback scripts available
- [ ] Feature flags for gradual rollouts
- [ ] Canary deployments configured
- [ ] Blue-green deployment capability

**Reference:**
- [.github/workflows/canary-deploy.yml](../.github/workflows/canary-deploy.yml)

---

## 9. Pre-Release Verification

### Final Security Review

- [ ] All sections of this checklist reviewed
- [ ] Critical/high vulnerabilities resolved
- [ ] Security scan results reviewed and accepted
- [ ] Penetration testing completed (for major releases)
- [ ] Third-party security audit (if required)

---

### Documentation Review

- [ ] API documentation up to date
- [ ] Security documentation reviewed
- [ ] Deployment guides current
- [ ] Runbooks for operations team complete
- [ ] Change log updated for release

---

### Communication

- [ ] Security advisories drafted for vulnerabilities
- [ ] Release notes include security fixes
- [ ] Known issues documented
- [ ] Breaking changes communicated to users
- [ ] Migration guides provided if needed

---

## Compliance Checklist Summary

**Before each release, ensure:**

1. ✅ All dependencies are up-to-date and scanned
2. ✅ No secrets in code or commits
3. ✅ Access controls and permissions reviewed
4. ✅ CI/CD security checks passing
5. ✅ Logging and monitoring operational
6. ✅ Licenses verified and compatible
7. ✅ Data handling secure and compliant
8. ✅ Incident response plan current

---

## Quick Reference Commands

```bash
# Full security check (run before release)
./scripts/security-check.sh  # Create this script to automate checks

# Individual checks
safety check --file=src/config/requirements.txt
npm audit
bandit -r src/
docker scan <image>
git log -p -S "API_KEY"
```

---

## Maintenance Schedule

- **Weekly:** Review critical security advisories
- **Monthly:** Update dependencies, review access logs
- **Quarterly:** Full security audit, test disaster recovery
- **Annually:** Comprehensive penetration test, license review

---

## Contacts

**Security Issues:** Report via GitHub Security Advisories or email (configure in repository settings)

**Maintainers:** See [CONTRIBUTING.md](CONTRIBUTING.md) for current maintainer list

**Security Team:** Define security@astraguard.ai or equivalent

---

**Document Status:** ✅ Active  
**Next Review:** May 14, 2026 (3 months from creation)  
**Owner:** sr-857 / AstraGuard AI Security Team

---

*This checklist is a living document. Update it as security practices evolve and new threats emerge.*


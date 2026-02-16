# Chaos Engineering Testing Guide for AstraGuard AI

## Overview

This guide provides comprehensive instructions for running chaos engineering tests on the AstraGuard AI platform. Chaos testing validates system resilience by injecting controlled failures and verifying recovery capabilities.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Prerequisites](#prerequisites)
3. [Running Chaos Tests](#running-chaos-tests)
4. [Experiment Definitions](#experiment-definitions)
5. [Interpreting Results](#interpreting-results)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)

## Quick Start

Run all chaos tests with a single command:

```bash
# Run all chaos tests
pytest tests/chaos/ -v -m chaos

# Run specific experiment
pytest tests/chaos/test_chaos_circuit_breaker.py -v

# Run with live services (requires AstraGuard running)
pytest tests/chaos/ -v -m chaos --live
```

## Prerequisites

### Required Services

Before running chaos tests, ensure these services are available:

- **AstraGuard API**: Running on `http://localhost:8000`
- **Redis**: For distributed state and caching
- **Prometheus**: For metrics collection (optional but recommended)

### Installation

Install chaos toolkit dependencies:

```bash
pip install chaostoolkit chaostoolkit-lib chaostoolkit-reporting
```

Or install all dependencies:

```bash
pip install -e .
```

## Running Chaos Tests

### Automated Test Suite

Run the complete chaos test suite:

```bash
# Run all chaos tests
pytest tests/chaos/ -v

# Run with coverage
pytest tests/chaos/ --cov=chaos --cov-report=html

# Run only fast tests (exclude slow)
pytest tests/chaos/ -v -m "not slow"

# Run integration tests only
pytest tests/chaos/ -v -m integration
```

### Manual Experiment Execution

Run individual experiments using the experiment runner:

```python
import asyncio
from chaos.experiments.runner import run_experiment

# Run single experiment
result = asyncio.run(run_experiment("circuit_breaker_failure"))
print(f"Status: {result.status}")
print(f"Recovery validated: {result.recovery_validated}")
print(f"SLO maintained: {result.slo_maintained}")
```

### Using Chaos Toolkit CLI

Execute experiments directly with Chaos Toolkit:

```bash
# Run experiment
chaos run src/chaos/experiments/circuit_breaker_failure.yaml

# Run with settings
chaos run src/chaos/experiments/network_latency.yaml --hypothesis-strategy after-method-only

# Generate report
chaos report --export-format=html5 journal.json > report.html
```

## Experiment Definitions

### Available Experiments

| Experiment | Description | Duration | Risk Level |
|------------|-------------|----------|------------|
| `circuit_breaker_failure` | Tests circuit breaker resilience | ~60s | Low |
| `network_latency` | Tests network degradation handling | ~60s | Low |
| `service_unavailable` | Tests service dependency failures | ~60s | Medium |
| `resource_exhaustion` | Tests resource pressure handling | ~60s | Medium |
| `database_failover` | Tests database failover scenarios | ~60s | Medium |

### Experiment Structure

Each experiment follows the Chaos Toolkit format:

```yaml
title: Experiment Name
description: What this experiment tests
steady-state-hypothesis:
  title: System is healthy
  probes:
    - health checks before chaos
method:
  - chaos actions (inject failures)
  - validation probes
rollbacks:
  - cleanup actions
```

## Interpreting Results

### Test Results

Tests can produce the following statuses:

- **PASSED**: System maintained steady state during chaos
- **FAILED**: System deviated from steady state
- **ABORTED**: Experiment was aborted (usually due to safety checks)

### Recovery Validation

Recovery is validated based on:

1. **Health Status**: System returns to HEALTHY or DEGRADED
2. **Circuit Breaker**: Not stuck in OPEN state
3. **Fallback Mode**: Returns to PRIMARY mode
4. **Recovery Time**: Within defined RTO (Recovery Time Objective)

### SLO Compliance

SLOs are checked against:

| SLO | Threshold | Measurement |
|-----|-----------|-------------|
| Error Rate | < 1% | Failed requests / Total requests |
| P99 Latency | < 500ms | 99th percentile response time |
| Availability | > 99.9% | Uptime percentage |

### Incident Reports

Failed experiments generate incident reports:

```bash
# List incidents
python -c "from chaos.validation.incident_reporter import IncidentReporter; \
           r = IncidentReporter(); \
           print(r.list_incidents())"

# Generate summary
python -c "from chaos.validation.incident_reporter import IncidentReporter; \
           r = IncidentReporter(); \
           print(r.generate_summary())"
```

## Troubleshooting

### Common Issues

#### Services Not Available

**Error**: `Connection refused` or `Service not available`

**Solution**:
```bash
# Start AstraGuard services
python -m dashboard.app

# Verify services
curl http://localhost:8000/health/live
```

#### Experiments Fail Immediately

**Error**: `Experiment aborted` or `Steady state not met`

**Solution**:
- Ensure system is healthy before running chaos
- Check that all dependencies are running
- Review steady-state hypothesis probes

#### Recovery Validation Times Out

**Error**: `Recovery validation failed after 60s`

**Solution**:
- Increase timeout: `RecoveryValidator(max_recovery_time=120)`
- Check recovery orchestrator logs
- Verify fallback mechanisms are configured

#### SLO Violations

**Error**: `SLO violated: error_rate=2.5% > 1%`

**Solution**:
- Review error handling in affected components
- Check circuit breaker thresholds
- Validate retry logic configuration

### Debug Mode

Enable debug logging for detailed output:

```python
import logging
logging.getLogger('chaos').setLevel(logging.DEBUG)
```

## Best Practices

### 1. Start in Development

Always test chaos experiments in development/staging before production:

```bash
# Development
pytest tests/chaos/ -v -m "not slow"

# Staging
pytest tests/chaos/ -v --live

# Production (with extreme caution)
chaos run experiments/circuit_breaker_failure.yaml --dry
```

### 2. Use Safety Checks

Always include rollback actions:

```yaml
rollbacks:
  - type: action
    name: ensure-failures-stopped
    provider:
      type: python
      module: chaos.actions.failure_injection
      func: stop_failure_injection
```

### 3. Monitor During Chaos

Watch system metrics during experiments:

```bash
# Watch health endpoint
watch -n 2 'curl -s http://localhost:8000/health/state | jq .'

# Monitor Prometheus metrics
open http://localhost:9090
```

### 4. Document Findings

Record all chaos experiment results:

- What was tested
- What failed
- Recovery actions taken
- Improvements made

### 5. Run Regularly

Schedule chaos tests as part of CI/CD:

```yaml
# .github/workflows/chaos.yml
name: Chaos Tests
on:
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday
jobs:
  chaos:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: pip install -e .
      - run: pytest tests/chaos/ -v -m "not slow"
```

## Runbooks

For specific failure scenarios, see:

- [Circuit Breaker Runbook](RUNBOOK_CIRCUIT_BREAKER.md)
- [Network Failure Runbook](RUNBOOK_NETWORK_FAILURE.md)
- [Service Unavailable Runbook](RUNBOOK_SERVICE_UNAVAILABLE.md)
- [Resource Exhaustion Runbook](RUNBOOK_RESOURCE_EXHAUSTION.md)

## Support

For issues or questions:

1. Check existing [GitHub Issues](https://github.com/purvanshjoshi/AstraGuard-AI/issues)
2. Review [Troubleshooting](#troubleshooting) section
3. Create new issue with chaos test logs

## References

- [Chaos Toolkit Documentation](https://chaostoolkit.org/)
- [Principles of Chaos Engineering](https://principlesofchaos.org/)
- [Google SRE Book - Managing Risk](https://sre.google/sre-book/managing-risk/)

# AstraGuard AI - Technical Documentation

**Version:** 2.0.0  
**Hackathon:** Synaptix Frontier AI Hack @ IIT Madras  
**Track:** Track 1 - Agentic AI (Applied GenAI)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Secrets Management](#secrets-management)
4. [Core Modules](#core-modules)
5. [Memory Engine](#memory-engine)
6. [Decision Loop](#decision-loop)
7. [API Reference](#api-reference)
8. [Performance Benchmarks](#performance-benchmarks)
9. [Deployment Guide](#deployment-guide)

---

## System Overview

AstraGuard AI is a production-ready autonomous fault detection and recovery system that demonstrates:

- **Streaming Awareness**: Real-time telemetry processing using Pathway Engine
- **Adaptive Memory**: Self-updating memory with temporal weighting and decay
- **Autonomous Decisions**: Agentic loop that reasons before acting
- **Concrete Actions**: Real system commands, not just alerts
- **Explainability**: Plain-language decision traces
- **Mission-Phase Awareness**: Context-sensitive fault response policies

### Key Differentiators

| Feature | Traditional Systems | AstraGuard AI |
|---------|-------------------|---------------|
| **Input Processing** | Batch/static | Continuous streaming |
| **Memory** | Static context | Evolving with decay |
| **Decision Making** | Classification only | Reason → Decide → Act |
| **Actions** | Manual intervention | Autonomous execution |
| **Explainability** | Black box | LLM-assisted reasoning |
| **Mission Context** | Phase-agnostic | **Phase-aware policies** |

### Mission-Phase Aware Fault Response

CubeSat operations have fundamentally different constraints across mission phases. AstraGuard now evaluates every anomaly decision considering the current mission phase:

**Mission Phases:**
- **LAUNCH**: Rocket ascent. Highly constrained. Log-only responses.
- **DEPLOYMENT**: System stabilization. Limited responses. Avoid disruption.
- **NOMINAL_OPS**: Standard operations. Full autonomous response capability.
- **PAYLOAD_OPS**: Science mission. Balanced constraints. Payload priority.
- **SAFE_MODE**: Minimum power state. Minimal active responses.

**Example: Same Anomaly, Different Responses**

A high-severity thermal fault (`severity = 0.75`) behaves differently:

| Phase | Threshold Multiplier | Allowed Response | Decision |
|-------|----------------------|------------------|----------|
| LAUNCH | 2.0x (noisy) | Log only | LOG_ONLY |
| DEPLOYMENT | 1.5x (sensitive) | Alert operators | ALERT_OPERATORS |
| NOMINAL_OPS | 1.0x (standard) | Auto-recovery | THERMAL_REGULATION |
| PAYLOAD_OPS | 1.0x (standard) | Auto-recovery | THERMAL_REGULATION |
| SAFE_MODE | 0.8x (very sensitive) | Log only | LOG_ONLY |

This ensures the system responds intelligently to context, avoiding over-aggressive recovery during launch or under-aggressive response during critical payload operations.

---

## Architecture

### High-Level Flow

```
Telemetry Stream → Encoder → Adaptive Memory ↔ Reasoning Agent → Response Orchestrator → Actions
                                    ↑                                        ↓
                                    └────────────── Feedback Loop ──────────┘
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    PATHWAY INGESTION LAYER                       │
│  - Stream validation                                             │
│  - Data normalization                                            │
│  - Timestamp synchronization                                     │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│                      ENCODER MODULE                              │
│  - Event → Vector embedding                                      │
│  - Feature extraction                                            │
│  - Dimensionality: 384                                           │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│                   ADAPTIVE MEMORY ENGINE                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Memory Store                                             │   │
│  │ - Temporal weighting: e^(-λt)                           │   │
│  │ - Recurrence scoring                                     │   │
│  │ - Safe decay (critical events exempt)                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Recurrence Scorer (Experimental)                         │   │
│  │ - Signal reinforcement                                   │   │
│  │ - Resonance = base × (1 + 0.3×log(1+count)) × decay    │   │
│  └─────────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│                    ANOMALY REASONING AGENT                       │
│  1. Detect anomaly                                               │
│  2. Recall similar from memory                                   │
│  3. Reason with LLM assistance                                   │
│  4. Decide action                                                │
│  5. Generate explanation                                         │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│                   RESPONSE ORCHESTRATOR                          │
│  - Workflow registry                                             │
│  - Action execution                                              │
│  - Cooldown management                                           │
│  - Feedback to memory                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Secrets Management

### Overview

AstraGuard AI includes a centralized secrets management module (`core/secrets.py`) that provides:

- **Unified secret access** - Single entry point for all credentials
- **Startup validation** - Verify required secrets before application starts
- **Log masking** - Prevent accidental exposure in logs
- **.env file support** - Load secrets from environment files
- **Secret rotation** - Reload secrets without restart

### API Reference

```python
from core.secrets import get_secret, require_secrets, mask_secret

# Get a secret (optional, with default)
api_key = get_secret("API_KEY", default="fallback")

# Get a required secret (raises ValueError if missing)
jwt_secret = get_secret("JWT_SECRET", required=True)

# Validate multiple secrets at startup
secrets = require_secrets(["API_KEY", "JWT_SECRET", "DATABASE_URL"])

# Mask a secret for safe logging
print(f"Using key: {mask_secret(api_key)}")  # Output: "****xyz1"
```

### Configuration

Secrets are loaded from:
1. Environment variables (highest priority)
2. `.env.local` file (if exists)
3. `.env` file (if exists)

**Example `.env.local`:**
```bash
API_KEY=your_api_key_here
JWT_SECRET=your_jwt_secret_here
METRICS_USER=admin
METRICS_PASSWORD=secure_password_here
```

### Best Practices

- Never commit `.env.local` to version control
- Use `require_secrets()` at application startup
- Use `mask_secret()` when logging sensitive values
- Rotate secrets with `secrets_manager.reload()`

---

## Core Modules

### 1. Memory Engine (`memory_engine/`)

**Purpose:** Self-updating memory with intelligent pruning

**Components:**
- `memory_store.py` - Core adaptive memory implementation
- `recurrence_scorer.py` - Signal reinforcement algorithm
- `decay_policy.py` - Safe pruning logic
- `replay_engine.py` - Incident replay functionality

**Key Features:**
- Temporal weighting: `weight = base × e^(-0.1 × age_hours)`
- Automatic recurrence detection (similarity > 0.85)
- Critical event protection
- Capacity management (max 10,000 events)

### 2. Anomaly Agent (`anomaly_agent/`)

**Purpose:** Agentic decision loop

**Components:**
- `decision_loop.py` - Main agent loop
- `reasoning_engine.py` - LLM-assisted explanations
- `confidence_scorer.py` - Decision confidence calculation

**Decision Flow:**
```python
def process_event(event):
    # 1. Detect
    is_anomalous, score = detector.detect(event)
    
    # 2. Recall
    similar = memory.retrieve(event.embedding)
    
    # 3. Reason
    decision = reasoner.decide(event, similar, score)
    
    # 4. Act
    result = orchestrator.execute(decision)
    
    # 5. Learn
    if result.should_remember:
        memory.write(event, decision, result)
    
    return decision
```

### 3. Response Orchestrator (`response_orchestrator/`)

**Purpose:** Execute concrete actions

**Workflow Registry:**
```python
workflows = {
    "IMMEDIATE_RECOVERY": [
        activate_safe_mode,
        send_critical_alert,
        update_risk_score
    ],
    "ALERT_ESCALATION": [
        notify_operators,
        tag_incident,
        monitor_closely
    ],
    "MONITOR": [
        log_event,
        update_metrics
    ]
}
```

---

## Memory Engine

### Adaptive Memory Store

**Class:** `AdaptiveMemoryStore`

**Methods:**

```python
def write(embedding, metadata, timestamp=None)
    """Store event with automatic recurrence detection"""

def retrieve(query_embedding, top_k=5)
    """Retrieve similar events with temporal weighting"""

def prune(max_age_hours=24, keep_critical=True)
    """Safe decay mechanism"""

def replay(start_time, end_time)
    """Replay events within time range"""
```

**Temporal Weighting Formula:**

```
weighted_score = similarity × (0.5 + 0.3 × temporal_weight + 0.2 × recurrence_boost)

where:
  temporal_weight = e^(-λ × age_hours)
  recurrence_boost = 1 + 0.3 × log(1 + recurrence_count)
```

### Recurrence Scorer (Experimental)

**Concept:** Signal reinforcement inspired by physics

**Formula:**
```
resonance = base_importance × (1 + α × log(1 + recurrence)) × time_decay

where:
  α = 0.3 (resonance amplification factor)
  recurrence = number of pattern repetitions
  time_decay = temporal decay factor (0-1)
```

**Implementation:**
```python
def calculate_resonance(base, recurrence_count, time_decay):
    return base * (1 + 0.3 * np.log(1 + recurrence_count)) * time_decay
```

---

## Decision Loop

### Anomaly Reasoning Agent

**Input:** Telemetry event
**Output:** Decision with reasoning trace

**Process:**

1. **Detection Phase**
   - Threshold-based checks
   - Statistical outlier detection
   - Confidence scoring

2. **Memory Recall Phase**
   - Embedding similarity search
   - Temporal weighting application
   - Top-k retrieval (default: 5)

3. **Reasoning Phase**
   - Severity assessment
   - Recurrence analysis
   - Historical pattern matching
   - LLM-assisted explanation

4. **Decision Phase**
   - Rule-based logic for critical paths
   - LLM consultation for uncertain cases
   - Action selection

5. **Learning Phase**
   - Memory update
   - Feedback incorporation
   - Pattern reinforcement

---

## API Reference

### Memory Store API

```python
from memory_engine import AdaptiveMemoryStore

# Initialize
memory = AdaptiveMemoryStore(decay_lambda=0.1, max_capacity=10000)

# Write event
embedding = np.random.rand(384)
metadata = {'severity': 0.8, 'type': 'power_fault'}
memory.write(embedding, metadata)

# Retrieve similar
query = np.random.rand(384)
results = memory.retrieve(query, top_k=5)
# Returns: [(score, metadata, timestamp), ...]

# Prune old events
pruned_count = memory.prune(max_age_hours=24, keep_critical=True)

# Get statistics
stats = memory.get_stats()
# Returns: {'total_events', 'critical_events', 'avg_age_hours', 'max_recurrence'}
```

### Recurrence Scorer API

```python
from memory_engine import RecurrenceScorer

scorer = RecurrenceScorer(resonance_factor=0.3)

# Calculate resonance
score = scorer.calculate_resonance(
    base_importance=0.7,
    recurrence_count=5,
    time_decay=0.9
)

# Score event with context
event_metadata = {'severity': 0.7}
similar_events = [{'temporal_weight': 0.9}, ...]
resonance = scorer.score_event(event_metadata, similar_events)
```

---

## Performance Benchmarks

### Latency Measurements

| Operation | Target | Actual | Method |
|-----------|--------|--------|--------|
| **Ingestion** | < 100ms | 45ms | Pathway stream read |
| **Encoding** | < 20ms | 12ms | Lightweight embedding |
| **Memory Retrieval** | < 50ms | 38ms | Vector similarity search |
| **Decision** | < 200ms | 150ms | Hybrid rule + LLM |
| **Action Trigger** | < 100ms | 80ms | Workflow execution |
| **Total E2E** | < 2000ms | ~325ms | Complete pipeline |

### Memory Performance

| Metric | Value |
|--------|-------|
| **Capacity** | 10,000 events |
| **Memory Footprint** | ~400MB (full) |
| **Write Latency** | < 5ms |
| **Retrieval Latency** | 38ms (avg) |
| **Prune Duration** | < 100ms |

### Accuracy Metrics (Simulated)

| Metric | Value |
|--------|-------|
| **Anomaly Detection** | 95%+ |
| **Fault Classification** | 98%+ |
| **False Positive Rate** | < 2% |
| **Recovery Success** | 92%+ |

---

## Deployment Guide

### Prerequisites

```bash
Python 3.9+
pip
git
```

### Installation Steps

1. **Clone repository**
   ```bash
   git clone https://github.com/sr-857/AstraGuard.git
   cd AstraGuard
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify installation**
   ```bash
   python verify_install.py
   ```

4. **Run demo**
   ```bash
   python examples/run_demo.py
   ```

5. **Launch dashboard**
   ```bash
   streamlit run dashboard/app.py
   ```

### Configuration

**Memory Parameters** (`memory_engine/memory_store.py`):
```python
decay_lambda = 0.1        # Temporal decay rate
max_capacity = 10000      # Maximum events
```

**Fault Thresholds** (`classifier/fault_classifier.py`):
```python
VOLTAGE_THRESHOLD = 7.3   # Volts
TEMP_THRESHOLD = 32.0     # Celsius
GYRO_THRESHOLD = 0.05     # rad/s
```

**Resonance Tuning** (`memory_engine/recurrence_scorer.py`):
```python
resonance_factor = 0.3    # Amplification for recurrence
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=memory_engine --cov=anomaly_agent

# Run specific test
pytest tests/test_memory_store.py -v
```

---

## Troubleshooting

### Common Issues

**1. Import Errors**
```bash
# Solution: Ensure proper package structure
python verify_install.py
```

**2. Memory Overflow**
```python
# Solution: Adjust capacity or prune more aggressively
memory.prune(max_age_hours=12, keep_critical=True)
```

**3. Slow Retrieval**
```python
# Solution: Reduce top_k or optimize embeddings
results = memory.retrieve(query, top_k=3)
```

---

**Documentation Version:** 2.0.0  
**Last Updated:** December 2024  
**Maintainer:** Subhajit Roy  
**Repository:** https://github.com/sr-857/AstraGuard

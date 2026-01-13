"""E2E Recovery Pipeline Testing Module.

Complete end-to-end validation of swarm recovery pipeline:
- Anomaly injection (battery, attitude, thermal, memory, comm)
- Full pipeline execution (#397-413)
- Recovery validation (MTTR <30s)
- Safety gate verification

Success criteria:
- Mean MTTR <25s, p95 <30s
- Consensus >95% during recovery
- Safety blocks prevent dangerous recovery
- All stages complete <30s total
"""

from .anomaly_injector import (
    AnomalyInjector,
    AnomalySeverity,
    AnomalyInjectionRequest,
    AnomalyEvent,
)
from .test_recovery_pipeline import (
    RecoveryPipelineTest,
    RecoveryTestResult,
    RecoveryStage,
    PipelineLatency,
)

__all__ = [
    "AnomalyInjector",
    "AnomalySeverity",
    "AnomalyInjectionRequest",
    "AnomalyEvent",
    "RecoveryPipelineTest",
    "RecoveryTestResult",
    "RecoveryStage",
    "PipelineLatency",
]

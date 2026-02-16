from prometheus_client import Counter
from astraguard.observability import _safe_create_metric

try:
    print("Attempting to create metric...")
    m = _safe_create_metric(
        Counter,
        'test_metric_name',
        'Test documentation',
        labelnames=['label']
    )
    print(f"Success: {m}")
except Exception as e:
    print(f"Failed: {e}")

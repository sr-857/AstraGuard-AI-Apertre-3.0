# AstraGuard Monitoring

This directory contains configuration files for AstraGuard observability stack, including Grafana dashboards and Prometheus alerts.

## Structure

```
infra/monitoring/
├── grafana/
│   └── astraguard-dashboard.json  # Grafana Dashboard JSON
├── alerts/
│   └── anomaly-alerts.yaml        # Prometheus Alert Rules
└── README.md
```

## Metrics

The application exposes Prometheus metrics at `/metrics` (authenticated).

### Key Metrics

*   **HTTP Requests**: `astra_http_requests_total`
*   **Latency**: `astra_http_request_duration_seconds`
*   **Anomalies**: `astraguard_anomaly_detections_total`
*   **Anomaly Scores**: `astraguard_anomaly_score_distribution`
*   **Model Info**: `astraguard_model_info`
*   **Circuit Breakers**: `astraguard_circuit_state`

## Grafana Dashboard

### Importing

1.  Open Grafana.
2.  Go to **Dashboards** -> **New** -> **Import**.
3.  Upload `grafana/astraguard-dashboard.json`.
4.  Select your Prometheus datasource when prompted.

### Panels

*   **Overview**: Key stats (Requests, Anomalies, Errors, Latency).
*   **Anomaly Insights**: Real-time anomaly rate and score distribution heatmap.
*   **System Health**: CPU, Memory, and Pod Restarts (requires standard Kubernetes metrics).
*   **Model Monitoring**: Active model version and metadata.

## Alerts

Alert rules are defined in `alerts/anomaly-alerts.yaml`.

### Rules

*   **HighAnomalyRate**: > 5/sec for 2m (Warning)
*   **CriticalAnomalyRate**: > 20/sec for 1m (Critical)
*   **HighErrorRate**: > 5% 5xx errors (Warning)
*   **HighLatency**: p95 > 2.0s (Warning)
*   **ModelFallbackActive**: Any fallback usage (Warning)

## Setup

Ensure your Prometheus configuration scrapes the AstraGuard service:

```yaml
scrape_configs:
  - job_name: 'astraguard'
    scrape_interval: 5s
    static_configs:
      - targets: ['astraguard-service:8000']
    basic_auth:
      username: 'metrics_user'
      password: 'metrics_password'
```

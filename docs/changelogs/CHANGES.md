# Changelog

## 2026-01-08 — feat: Explainability in anomaly investigation (PR #184)
- Add `AnomalyInvestigator` explainability UI with feature importances and SHAP values
- Added deterministic mock fallback for explainability when analysis service is unavailable
- Added `AnalysisResult` and `FeatureImportance` types
- Included `analysis_response_example.json` mock
- Updated README to mention explainability feature

## 2026-01-08 — feat: Pluggable monitoring integrations (PR #183)
- Add `backend.monitoring_integrations` package with `MonitoringAdapter` base
- Implement `DatadogAdapter` and `NewRelicAdapter`
- Add FastAPI endpoints to register integrations and accept webhooks (`/monitoring/*`)
- Add unit tests and docs (tests/test_monitoring_integrations.py, docs/monitoring_integrations.md)
- PoC stores integration configs in-memory and maps alert severities to component health


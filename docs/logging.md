# Logging and Observability Guide

AstraGuard-AI uses a centralized logging stack powered by **Loki, Promtail, and Grafana**. This setup ensures that all container logs are collected, structured, and searchable from a single interface.

## 🚀 How to Run

To start the full stack including the logging infrastructure, run the following command from the `infra/docker/` directory:

```bash
cd infra/docker
docker compose -f docker-compose.yml -f docker-compose.logs.yml up -d
```

This will spin up:
- **API Service** (with structured JSON logging)
- **Redis** & **Prometheus**
- **Loki** (Log aggregation)
- **Promtail** (Log collector)
- **Grafana** (Visualization)

## 📊 Accessing Grafana

- **URL:** [http://localhost:3000](http://localhost:3000)
- **Default Credentials:** `admin` / `admin` (or check `.env` for `GRAFANA_PASSWORD`)

## 🔍 querying Logs

1.  Open Grafana and go to **Explore** (compass icon).
2.  Select **Loki** as the datasource.
3.  Use LogQL to query logs.

### Common Queries

**View all container logs:**
```logql
{job="containerlogs"}
```

**Filter by Service (API):**
Since our logs are structured JSON, you can filter specifically for the API service:
```logql
{job="containerlogs"} | json | service="api-service"
```

**Find Errors:**
```logql
{job="containerlogs"} | json | service="api-service" | level="ERROR"
```

**Search for a keyword:**
```logql
{job="containerlogs"} |= "connection refused"
```

## 🔒 Retention Policy

- **Retention Period:** 168 hours (7 days).
- **Storage:** Logs are stored locally in the `loki` volume.
- **Limits:** Old chunks are automatically deleted to prevent disk bloat.

## 🛠 Configuration

- **Loki Config:** `infra/logging/loki-config.yaml`
- **Promtail Config:** `infra/logging/promtail-config.yml`
- **Compose File:** `infra/docker/docker-compose.logs.yml`

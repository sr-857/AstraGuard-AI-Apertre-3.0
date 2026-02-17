# Security Policies

This document outlines the network security policies implemented for the AstraGuard AI cluster.

## Network Security Model

We enforce a **Default Deny** ingress policy for the `astraguard` namespace. All traffic must be explicitly allowed.

### Policies Implemented

1.  **Default Deny All Ingress (`00-default-deny-ingress.yaml`)**
    *   **Scope:** All pods in `astraguard` namespace.
    *   **Effect:** Blocks all incoming connections.

2.  **Allow Backend Access (`01-allow-backend-ingress.yaml`)**
    *   **Target:** `astra-guard` API pods.
    *   **Source:** Ingress Controller (Namespace `ingress-nginx`).
    *   **Port:** 8000 (TCP).

3.  **Allow Database Access (`02-allow-redis-access.yaml`)**
    *   **Target:** `redis` pods.
    *   **Source:** `astra-guard` API pods.
    *   **Port:** 6379 (TCP).

4.  **Allow Monitoring (`03-allow-monitoring.yaml`)**
    *   **Target:** `astra-guard` and `redis` pods.
    *   **Source:** `prometheus` pods.
    *   **Ports:** 9090 (API Metrics), 9121 (Redis Metrics).

### Deployment Requirements

For these policies to function correctly, deployments must use standard Kubernetes labels:

*   **Astra Guard API:** `app.kubernetes.io/name: astra-guard`
*   **Redis:** `app.kubernetes.io/name: redis`
*   **Prometheus:** `app.kubernetes.io/name: prometheus`
*   **Ingress Controller:** Namespace label `name: ingress-nginx` (or matching selector).

### Applying Policies

Policies are located in `infra/k8s/network-policies/`. Apply them using:

```bash
kubectl apply -f infra/k8s/network-policies/
```

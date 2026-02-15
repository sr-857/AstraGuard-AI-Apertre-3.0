# AstraGuard Service Mesh (Istio) Configuration

This directory contains the Istio configuration for the AstraGuard application. It enables mTLS, traffic management, and security policies.

## Prerequisites

*   Kubernetes Cluster (v1.25+)
*   Istio installed (v1.16+)
*   `kubectl` configured

## Configuration Files

*   `namespace.yaml`: Creates the `astraguard` namespace with sidecar injection enabled.
*   `gateway.yaml`: Configures the Ingress Gateway for `astraguard.local`.
*   `virtual-service.yaml`: Routes traffic from the Gateway to the AstraGuard Service.
*   `destination-rule.yaml`: Configures circuit breaking and outlier detection.
*   `peer-authentication.yaml`: Enforces STRICT mTLS within the namespace.
*   `authorization-policy.yaml`: Restricts access to AstraGuard pods to the `default` service account in the `astraguard` namespace.

## Installation

1.  **Create Namespace & Enable Injection:**
    ```bash
    kubectl apply -f namespace.yaml
    ```

2.  **Deploy Application:**
    Ensure you deploy the AstraGuard Helm chart to the `astraguard` namespace.
    ```bash
    helm upgrade --install astraguard infra/helm/astraguard -n astraguard
    ```
    *Note: The Istio configurations assume the Helm release name is `astraguard` and the namespace is `astraguard`. If you use different names, you must update `virtual-service.yaml` and `destination-rule.yaml` hosts.*

3.  **Apply Traffic Management:**
    ```bash
    kubectl apply -f gateway.yaml
    kubectl apply -f virtual-service.yaml
    kubectl apply -f destination-rule.yaml
    ```

4.  **Apply Security Policies:**
    ```bash
    kubectl apply -f peer-authentication.yaml
    kubectl apply -f authorization-policy.yaml
    ```

## Validation

1.  **Check Sidecar Injection:**
    ```bash
    kubectl get pods -n astraguard -l app.kubernetes.io/name=astra-guard -o jsonpath='{.items[*].spec.containers[*].name}'
    ```
    Output should include `istio-proxy`.

2.  **Verify mTLS:**
    Check Kiali dashboard or use `istioctl` to verify mTLS status.
    ```bash
    istioctl authn tls-check <pod-name> -n astraguard
    ```

3.  **Test Access:**
    Access the service via the Gateway IP/Hostname (`astraguard.local`).
    ```bash
    curl -v -H "Host: astraguard.local" http://<INGRESS_GATEWAY_IP>/health/live
    ```

## Rollback

To remove Istio configurations:

```bash
kubectl delete -f authorization-policy.yaml
kubectl delete -f peer-authentication.yaml
kubectl delete -f destination-rule.yaml
kubectl delete -f virtual-service.yaml
kubectl delete -f gateway.yaml
```

To disable sidecar injection:

```bash
kubectl label namespace astraguard istio-injection-
# Restart pods to remove sidecars
kubectl rollout restart deployment -n astraguard
```

## Customization

*   **Hosts:** Update `gateway.yaml` and `virtual-service.yaml` if your domain is not `astraguard.local`.
*   **Service Name:** If your Helm release name is not `astraguard`, update the destination host in `virtual-service.yaml` and `destination-rule.yaml` (format: `<release>-astra-guard.astraguard.svc.cluster.local`).

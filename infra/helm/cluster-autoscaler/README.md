# Cluster Autoscaler for AstraGuard (AWS EKS)

This Helm chart deploys the Kubernetes Cluster Autoscaler for AWS EKS. The Cluster Autoscaler automatically adjusts the size of the Kubernetes cluster when:
* There are pods that failed to run in the cluster due to insufficient resources.
* There are nodes in the cluster that have been underutilized for an extended period of time and their pods can be placed on other existing nodes.

## Prerequisites

### 1. IAM Policy
Create an IAM policy (e.g., `AmazonEKSClusterAutoscalerPolicy`) with the following permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "autoscaling:DescribeAutoScalingGroups",
                "autoscaling:DescribeAutoScalingInstances",
                "autoscaling:DescribeLaunchConfigurations",
                "autoscaling:DescribeTags",
                "autoscaling:SetDesiredCapacity",
                "autoscaling:TerminateInstanceInAutoScalingGroup",
                "ec2:DescribeLaunchTemplateVersions"
            ],
            "Resource": "*"
        }
    ]
}
```

### 2. IAM Role for Service Account (IRSA)
Create an IAM role associated with the cluster's OIDC provider.
* Attach the policy created above.
* Trust relationship should allow `system:serviceaccount:kube-system:cluster-autoscaler`.

Annotate the Service Account in `values.yaml`:

```yaml
rbac:
  serviceAccount:
    annotations:
      eks.amazonaws.com/role-arn: arn:aws:iam::<YOUR_ACCOUNT_ID>:role/<YOUR_ROLE_NAME>
```

### 3. Auto Scaling Group (ASG) Tags
Your EKS Node Groups (ASGs) must have the following tags:

| Key | Value |
| --- | --- |
| `k8s.io/cluster-autoscaler/enabled` | `true` |
| `k8s.io/cluster-autoscaler/<CLUSTER_NAME>` | `owned` |

Replace `<CLUSTER_NAME>` with your actual cluster name (default: `apertre-cluster`).

## Installation

1.  **Configure Values:**
    Update `infra/helm/cluster-autoscaler/values.yaml` with your region and cluster name.

    ```yaml
    awsRegion: us-east-1
    autoDiscovery:
      clusterName: apertre-cluster
    ```

2.  **Deploy:**
    ```bash
    helm install cluster-autoscaler infra/helm/cluster-autoscaler \
      --namespace kube-system \
      --create-namespace \
      -f infra/helm/cluster-autoscaler/values.yaml
    ```

## Verification

Check if the pods are running:
```bash
kubectl get pods -n kube-system -l app.kubernetes.io/name=cluster-autoscaler
```

View logs to ensure it found the ASGs:
```bash
kubectl logs -f deployment/cluster-autoscaler -n kube-system
```

You should see logs like `I0920 ... monitor.go:81] Target 2 nodes, but found 2 nodes`.

## Configuration Reference

| Parameter | Description | Default |
| --- | --- | --- |
| `cloudProvider` | Cloud provider (aws, azure, gcp) | `aws` |
| `awsRegion` | AWS Region | `us-east-1` |
| `autoDiscovery.clusterName` | Cluster name for auto-discovery | `apertre-cluster` |
| `rbac.serviceAccount.annotations` | Annotations for IRSA | `{}` |
| `extraArgs` | Additional command line arguments | (See values.yaml) |

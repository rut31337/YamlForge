# CNV Provider Documentation

The Container Native Virtualization (CNV) provider enables you to deploy virtual machines on Kubernetes and OpenShift clusters using KubeVirt technology.

## Overview

The CNV provider supports two deployment modes:
- **Kubernetes**: Uses KubeVirt operator for virtual machine management
- **OpenShift**: Uses Red Hat's CNV operator for enhanced OpenShift integration

## Prerequisites

### For Kubernetes Clusters
- KubeVirt operator installed and running
- Containerized Data Importer (CDI) for DataVolume support
- Local storage provisioner (e.g., local-path-provisioner)

### For OpenShift Clusters
- CNV operator installed via OperatorHub
- HyperConverged Cluster Operator (HCO) configured
- Local storage class available

## Environment Variables

### Kubernetes Cluster Access
```bash
# Standard kubeconfig file
export KUBECONFIG="~/.kube/config"

# Alternative: Direct cluster credentials
export KUBERNETES_HOST="https://api.my-cluster.com:6443"
export KUBERNETES_TOKEN="your-kubernetes-token"
export KUBERNETES_CA_CERT="$(cat ~/.kube/ca.crt)"
```

### OpenShift Cluster Access
```bash
# OpenShift cluster credentials
export OPENSHIFT_CLUSTER_URL="https://api.cluster.example.com:6443"
export OPENSHIFT_CLUSTER_TOKEN="your_openshift_token"
export OPENSHIFT_USERNAME="your_username"
export OPENSHIFT_PASSWORD="your_password"
export OPENSHIFT_NAMESPACE="default"

# Alternative: Kubeconfig for OpenShift
export OPENSHIFT_KUBECONFIG="$(cat ~/.kube/config)"
```

## Configuration

CNV instances can be configured using either predefined sizes or custom CPU/memory specifications:

### Using Predefined Flavors

```yaml
yamlforge:
  cloud_workspace:
    name: "my-cnv-workspace"
  
  instances:
    - name: "my-vm-{guid}"
      provider: "cnv"
      flavor: "medium"  # small, medium, large, xlarge, etc.
      image: "kubevirt/fedora-cloud-container-disk-demo:latest"
```

### Using Custom CPU/Memory Specifications

```yaml
yamlforge:
  cloud_workspace:
    name: "my-cnv-workspace"
  
  instances:
    - name: "my-vm-{guid}"
      provider: "cnv"
      cores: 4        # Number of CPU cores
      memory: 8192    # Memory in MB (8GB)
      image: "kubevirt/fedora-cloud-container-disk-demo:latest"
```

**Note:** You must specify either `flavor` OR both `cores` and `memory`, but not both.

### Namespace Management
**Important**: CNV VMs are automatically deployed in a namespace derived from `yamlforge.cloud_workspace.name`. This field is required for all YamlForge configurations.

The workspace name is automatically converted to a valid Kubernetes namespace:
- Converted to lowercase
- Special characters replaced with hyphens
- Length limited to 63 characters (Kubernetes limit)
- Example: `"My CNV Workspace"` → `"my-cnv-workspace"`

**Note**: The instance-level `namespace` field is no longer used. All VMs in a YamlForge configuration share the same namespace based on the workspace name.

### Region and Location
**CNV instances do not require region or location fields** since they deploy to local Kubernetes/OpenShift clusters. The region field is ignored for CNV provider instances.

### Available Flavors
CNV supports predefined flavors or custom CPU/memory specifications:

#### Predefined Flavors
- `small`: 1 vCPU, 1GB RAM
- `medium`: 2 vCPU, 4GB RAM
- `large`: 4 vCPU, 8GB RAM
- `xlarge`: 8 vCPU, 16GB RAM
- `gpu-small`: 2 vCPU, 8GB RAM, 1 GPU
- `gpu-large`: 8 vCPU, 32GB RAM, 2 GPU
- `memory-optimized`: 4 vCPU, 32GB RAM
- `storage-optimized`: 2 vCPU, 4GB RAM, 100GB storage
- `network-optimized`: 4 vCPU, 8GB RAM, 5Gbps network

#### Custom Specifications
Instead of using predefined flavors, you can specify exact CPU and memory requirements:

```yaml
instances:
  - name: "custom-vm"
    provider: "cnv"
    cores: 6        # 6 CPU cores
    memory: 12288   # 12GB RAM (in MB)
    image: "kubevirt/fedora-cloud-container-disk-demo:latest"
```

**Note**: Memory is specified in MB and will be converted to Gi for Kubernetes (minimum 1Gi).

### Container Disk Images
The CNV provider supports container disk images for VM deployment:

```yaml
# Fedora Cloud (recommended for testing)
image: "kubevirt/fedora-cloud-container-disk-demo:latest"

# Ubuntu Cloud
image: "kubevirt/ubuntu:20.04"

# Custom container disk
image: "my-registry.com/my-custom-image:v1.0"
```

## Cluster Type Detection

The CNV provider automatically detects whether to use Kubernetes or OpenShift mode based on your YAML configuration:

### Kubernetes Mode
```yaml
yamlforge:
  cloud_workspace:
    name: "kubevirt-workspace"
  
  instances:
    - name: "kubevirt-vm"
      provider: "cnv"
      flavor: "small"
```

### OpenShift Mode
```yaml
yamlforge:
  cloud_workspace:
    name: "openshift-cnv-workspace"
  
  openshift_clusters:
    - name: "my-openshift-cluster"
      type: "self-managed"
      provider: "aws"
  
  instances:
    - name: "cnv-vm"
      provider: "cnv"
      flavor: "small"
```

## Generated Resources

### Kubernetes Mode
- `kubernetes_namespace`: Namespace for CNV resources
- `kubectl_manifest`: VirtualMachine resource
- `kubectl_manifest`: VirtualMachineInstance resource

### OpenShift Mode
- `kubernetes_namespace`: OpenShift project
- `kubectl_manifest`: CNV VirtualMachine with OpenShift optimizations
- `kubectl_manifest`: VirtualMachineInstance with OpenShift features

## Cost Analysis

CNV instances have minimal costs since they use local cluster resources:
- `small`: $0.001/hour
- `medium`: $0.002/hour
- `large`: $0.004/hour
- `xlarge`: $0.008/hour
- `gpu-small`: $0.005/hour
- `gpu-large`: $0.015/hour

## Security

### Network Isolation
- VMs run in isolated namespaces
- Pod network connectivity by default
- Optional Multus network attachment for advanced networking

### Storage
- Container disk images for boot volumes
- Optional DataVolumes for persistent storage
- Local storage class for data persistence

### Access Control
- Kubernetes RBAC for namespace access
- OpenShift project-based isolation
- Service account-based authentication

## Troubleshooting

### Common Issues

1. **KubeVirt Operator Not Installed**
   ```bash
   # Install KubeVirt operator
   kubectl apply -f https://github.com/kubevirt/kubevirt/releases/latest/download/kubevirt-operator.yaml
   kubectl apply -f https://github.com/kubevirt/kubevirt/releases/latest/download/kubevirt-cr.yaml
   ```

2. **CNV Operator Not Installed on OpenShift**
   ```bash
   # Install via OperatorHub or CLI
   oc apply -f - <<EOF
   apiVersion: operators.coreos.com/v1alpha1
   kind: Subscription
   metadata:
     name: hco-operatorhub
     namespace: openshift-cnv
   spec:
     channel: stable
     name: hco-operatorhub
     source: redhat-operators
     sourceNamespace: openshift-marketplace
   EOF
   ```

3. **Storage Class Not Available**
   ```bash
   # Install local-path-provisioner
   kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml
   ```

### Verification Commands

```bash
# Check KubeVirt installation
kubectl get pods -n kubevirt

# Check CNV installation (OpenShift)
oc get pods -n openshift-cnv

# Check VM resources
kubectl get vms -A
kubectl get vmis -A

# Check storage classes
kubectl get storageclass
```

## Examples

See [cnv-example.yaml](../../examples/cloud-specific/cnv-example.yaml) for a complete working example.

## Migration

### From Cloud Providers to CNV
```yaml
# Change provider from cloud to CNV
instances:
  - name: "my-vm"
    provider: "cnv"  # Was "aws", "azure", etc.
    size: "medium"
    namespace: "default"
```

### Between Kubernetes and OpenShift
The same YAML configuration works for both Kubernetes and OpenShift - the provider automatically adapts based on the target cluster.

## Best Practices

1. **Use namespaces** to organize VMs by purpose
2. **Choose appropriate sizes** based on workload requirements
3. **Use container disk images** for consistent deployments
4. **Monitor resource usage** as VMs consume cluster resources
5. **Implement backup strategies** for persistent data
6. **Use GPU instances** only when GPU support is available

## Limitations

- VMs consume cluster CPU and memory resources
- Limited to cluster capacity
- No automatic scaling (manual VM creation required)
- GPU support depends on cluster configuration
- Network performance limited by cluster networking

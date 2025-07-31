# Azure Red Hat OpenShift (ARO) Guide

This guide covers deploying Azure Red Hat OpenShift (ARO) clusters using YamlForge.

## Quick Start

### Basic ARO Cluster

```yaml
guid: "aro01"

yamlforge:
  openshift_clusters:
    - name: "my-aro-cluster"
      type: "aro"
      region: "eastus"
      version: "latest"
      size: "medium"  # Cluster size (not instance size)
      worker_count: 3
```

### ARO with Custom Networking

```yaml
guid: "aro02"

yamlforge:
  openshift_clusters:
    - name: "custom-aro-cluster"
      type: "aro"
      region: "eastus"
      version: "4.14.15"
      size: "large"  # Cluster size (not instance size)
      worker_count: 6
      networking:
        vnet_cidr: "10.0.0.0/16"
        master_subnet_cidr: "10.0.1.0/24"
        worker_subnet_cidr: "10.0.2.0/24"
```

## Environment Variables

### Required Azure Credentials

```bash
# Azure Service Principal (required for ARO)
export ARM_CLIENT_ID=your_service_principal_client_id
export ARM_CLIENT_SECRET=your_service_principal_client_secret
export ARM_SUBSCRIPTION_ID=your_azure_subscription_id
export ARM_TENANT_ID=your_azure_tenant_id

# Red Hat OpenShift Token
export REDHAT_OPENSHIFT_TOKEN=your_redhat_token

# SSH Public Key
export SSH_PUBLIC_KEY="ssh-rsa your_public_key_here"
```

### Creating Azure Service Principal

```bash
# Create service principal with Contributor role
az ad sp create-for-rbac \
  --name "yamlforge-aro-sp" \
  --role "Contributor" \
  --scopes "/subscriptions/YOUR_SUBSCRIPTION_ID" \
  --sdk-auth
```

## Cluster Sizing

### Available Cluster Sizes

```yaml
openshift_clusters:
  - name: "small-cluster"
    type: "aro"
    size: "small"    # 3 master + 3 worker nodes
    worker_count: 3
    
  - name: "medium-cluster"
    type: "aro"
    size: "medium"   # 3 master + 6 worker nodes
    worker_count: 6
    
  - name: "large-cluster"
    type: "aro"
    size: "large"    # 3 master + 12 worker nodes
    worker_count: 12
    
  - name: "xlarge-cluster"
    type: "aro"
    size: "xlarge"   # 3 master + 24 worker nodes
    worker_count: 24
```

### VM Size Mappings

ARO automatically selects appropriate VM sizes based on cluster size:

```yaml
# Small cluster configuration
size: "small"  # Standard_D4s_v3 (4 vCPU, 16GB)
worker_disk_size: 128  # Disk size in GB

# Medium cluster configuration
size: "medium"  # Standard_D8s_v3 (8 vCPU, 32GB)
worker_disk_size: 256  # Disk size in GB

# Large cluster configuration
size: "large"  # Standard_D16s_v3 (16 vCPU, 64GB)
worker_disk_size: 512  # Disk size in GB

# XLarge cluster configuration
size: "xlarge"  # Standard_D32s_v3 (32 vCPU, 128GB)
worker_disk_size: 1024  # Disk size in GB
```

## Advanced Configuration

### Custom VM Sizes

```yaml
guid: "aro03"

yamlforge:
  openshift_clusters:
    - name: "custom-vm-aro"
      type: "aro"
      region: "eastus"
      version: "latest"
      size: "medium"  # Cluster size (not instance size)
      worker_count: 6
      master_machine_type: "Standard_D8s_v3"  # Custom master VM size
      worker_machine_type: "Standard_D4s_v3"  # Custom worker VM size
      worker_disk_size: 256  # Custom disk size in GB
```

### Autoscaling Configuration

```yaml
guid: "aro04"

yamlforge:
  openshift_clusters:
    - name: "autoscale-aro"
      type: "aro"
      region: "eastus"
      version: "latest"
      size: "medium"  # Cluster size (not instance size)
      worker_count: 3
      auto_scaling:
        enabled: true
        min_replicas: 3
        max_replicas: 10
```

### Multi-Zone Deployment

```yaml
guid: "aro05"

yamlforge:
  openshift_clusters:
    - name: "multi-zone-aro"
      type: "aro"
      region: "eastus"
      version: "latest"
      size: "large"  # Cluster size (not instance size)
      worker_count: 6
      availability_zones:
        - "1"
        - "2"
        - "3"
```

## Integration with Instances

### ARO with Supporting Instances

```yaml
guid: "aro06"

yamlforge:
  openshift_clusters:
    - name: "production-aro"
      type: "aro"
      region: "eastus"
      version: "latest"
      size: "large"  # Cluster size (not instance size)
      worker_count: 6
      
  instances:
    - name: "monitoring-server-{guid}"
      provider: "azure"
      flavor: "medium"  # Instance flavor (not cluster size)
      image: "RHEL9-latest"
      region: "eastus"
      
    - name: "backup-server-{guid}"
      provider: "azure"
      flavor: "large"  # Instance flavor (not cluster size)
      image: "RHEL9-latest"
      region: "eastus"
```

## Cost Optimization

### Using Cheapest Provider for Supporting Infrastructure

```yaml
guid: "aro07"

yamlforge:
  openshift_clusters:
    - name: "cost-optimized-aro"
      type: "aro"
      region: "eastus"
      version: "latest"
      size: "medium"  # Cluster size (not instance size)
      worker_count: 3
      
  instances:
    - name: "cheapest-monitoring-{guid}"
      provider: "cheapest"  # Automatically finds cheapest provider
      flavor: "medium"  # Instance flavor (not cluster size)
      image: "RHEL9-latest"
      region: "us-east-1"
```

## Troubleshooting

### Common Issues

1. **Service Principal Permissions**
   ```bash
   # Verify service principal has Contributor role
   az role assignment list --assignee $ARM_CLIENT_ID
   ```

2. **Red Hat Token Issues**
   ```bash
   # Verify Red Hat token is valid
   curl -H "Authorization: Bearer $REDHAT_OPENSHIFT_TOKEN" \
        https://api.openshift.com/api/accounts_mgmt/v1/current_account
   ```

3. **Region Availability**
   ```bash
   # Check ARO availability in regions
   az provider show -n Microsoft.RedHatOpenShift -o table
   ```

### Best Practices

1. **Use Latest Version**: Always use `version: "latest"` for production
2. **Plan for Growth**: Start with medium size and use autoscaling
3. **Network Planning**: Use custom networking for production deployments
4. **Cost Management**: Monitor cluster usage and adjust worker count

## Next Steps

- [OpenShift Overview](overview.md)
- [ROSA Guide](rosa-guide.md)
- [Multi-Cloud OpenShift](multi-cloud-openshift.md)
- [Troubleshooting Guide](../troubleshooting.md) 

# ARO Authentication

## Azure Service Principal

ARO requires Azure service principal credentials:

```bash
export ARM_CLIENT_ID=your_client_id
export ARM_CLIENT_SECRET=your_client_secret
export ARM_SUBSCRIPTION_ID=your_subscription_id
export ARM_TENANT_ID=your_tenant_id
```

## Red Hat Pull Secret (Optional but Recommended)

For enhanced content access to Red Hat container registries and additional content:

```bash
export OCP_PULL_SECRET='{"auths":{"fake":{"auth":"fake"}}}'
```

Get your pull secret from: https://console.redhat.com/openshift/install/pull-secret

**Benefits of using a pull secret:**
- Access to Red Hat container registries
- Additional content and operators
- Enhanced cluster functionality
- Better integration with Red Hat ecosystem 

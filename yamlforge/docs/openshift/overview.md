# OpenShift Overview

YamlForge provides comprehensive support for deploying and managing OpenShift clusters across multiple cloud providers.

## Supported OpenShift Types

### Managed OpenShift Services

- **ROSA (Red Hat OpenShift Service on AWS)**
  - ROSA Classic: Traditional managed OpenShift
  - ROSA HCP: Hosted Control Plane (preview)
- **ARO (Azure Red Hat OpenShift)**
- **OpenShift Dedicated**: Red Hat's managed service

### Self-Managed OpenShift

- **Self-Managed**: Full control over OpenShift deployment
- **HyperShift**: Hosted control planes for multi-cluster management

## Quick Start

### Basic ROSA Cluster

```yaml
guid: "ros01"

yamlforge:
  cloud_workspace:
    name: "rosa-cluster-{guid}"
    description: "Basic ROSA cluster deployment"
  
  openshift_clusters:
    - name: "my-rosa-cluster"
      type: "rosa-classic"
      location: "us-east-1"
      version: "latest"
      flavor: "medium"  # Cluster size (not instance size)
      worker_count: 3
```

### Basic ARO Cluster

```yaml
guid: "aro01"

yamlforge:
  cloud_workspace:
    name: "aro-cluster-{guid}"
    description: "Basic ARO cluster deployment"
  
  openshift_clusters:
    - name: "my-aro-cluster"
      type: "aro"
      location: "eastus"
      version: "latest"
      flavor: "medium"  # Cluster size (not instance size)
      worker_count: 3
```

## Cluster Sizing

### Available Cluster Sizes

```yaml
openshift_clusters:
  - name: "small-cluster"
    type: "rosa-classic"
    flavor: "small"    # 3 controlplane + 3 worker nodes
    worker_count: 3
    
  - name: "medium-cluster"
    type: "rosa-classic"
    flavor: "medium"   # 3 controlplane + 6 worker nodes
    worker_count: 6
    
  - name: "large-cluster"
    type: "rosa-classic"
    flavor: "large"    # 3 controlplane + 12 worker nodes
    worker_count: 12
    
  - name: "xlarge-cluster"
    type: "rosa-classic"
    flavor: "xlarge"   # 3 controlplane + 24 worker nodes
    worker_count: 24
```

## Integration with Instances

### OpenShift with Supporting Infrastructure

```yaml
guid: "full1"

yamlforge:
  cloud_workspace:
    name: "full-openshift-{guid}"
    description: "OpenShift with supporting infrastructure"
  
  openshift_clusters:
    - name: "production-cluster"
      type: "rosa-classic"
      location: "us-east-1"
      version: "latest"
      flavor: "large"  # Cluster size (not instance size)
      worker_count: 6
      
  instances:
    - name: "monitoring-server-{guid}"
      provider: "aws"
      flavor: "medium"  # Instance flavor (not cluster size)
      image: "RHEL9-latest"
      location: "us-east-1"
      
    - name: "backup-server-{guid}"
      provider: "aws"
      flavor: "large"  # Instance flavor (not cluster size)
      image: "RHEL9-latest"
      location: "us-east-1"
```

## Environment Variables

### Required Credentials

```bash
# AWS (for ROSA)
export AWS_ACCESS_KEY_ID=your_aws_access_key
export AWS_SECRET_ACCESS_KEY=your_aws_secret_key
export AWS_BILLING_ACCOUNT_ID=your_aws_billing_account_id

# Azure (for ARO)
export ARM_CLIENT_ID=your_azure_client_id
export ARM_CLIENT_SECRET=your_azure_client_secret
export ARM_SUBSCRIPTION_ID=your_azure_subscription_id
export ARM_TENANT_ID=your_azure_tenant_id

# Red Hat OpenShift Token (required for all OpenShift deployments)
export REDHAT_OPENSHIFT_TOKEN=your_redhat_token

# SSH Public Key
export SSH_PUBLIC_KEY="ssh-rsa your_public_key_here"
```

## Advanced Configuration

### Multi-Cluster Deployment

```yaml
guid: "mul01"

yamlforge:
  cloud_workspace:
    name: "multi-cluster-{guid}"
    description: "Multi-cluster OpenShift deployment"
  
  openshift_clusters:
    - name: "prod-cluster"
      type: "rosa-classic"
      location: "us-east-1"
      version: "latest"
      flavor: "large"  # Cluster size (not instance size)
      worker_count: 6
      
    - name: "staging-cluster"
      type: "aro"
      location: "eastus"
      version: "latest"
      flavor: "medium"  # Cluster size (not instance size)
      worker_count: 3
      
    - name: "dev-cluster"
      type: "self-managed"
      provider: "gcp"
      location: "us-central1"
      version: "latest"
      flavor: "small"  # Cluster size (not instance size)
      worker_count: 3
```

### Custom Networking

```yaml
guid: "net01"

yamlforge:
  cloud_workspace:
    name: "custom-networking-{guid}"
    description: "OpenShift cluster with custom networking"
  
  openshift_clusters:
    - name: "custom-network-cluster"
      type: "rosa-classic"
      location: "us-east-1"
      version: "latest"
      flavor: "medium"  # Cluster size (not instance size)
      worker_count: 3
      networking:
        machine_cidr: "10.0.0.0/16"
        service_cidr: "172.30.0.0/16"
        pod_cidr: "10.128.0.0/14"
        host_prefix: 23
```

## Cost Optimization

### Using Cheapest Provider for Supporting Infrastructure

```yaml
guid: "cst01"

yamlforge:
  cloud_workspace:
    name: "cost-optimized-{guid}"
    description: "Cost-optimized OpenShift with supporting infrastructure"
  
  openshift_clusters:
    - name: "cost-optimized-cluster"
      type: "rosa-classic"
      location: "us-east-1"
      version: "latest"
      flavor: "medium"  # Cluster size (not instance size)
      worker_count: 3
      
  instances:
    - name: "cheapest-monitoring-{guid}"
      provider: "cheapest"  # Automatically finds cheapest provider
      flavor: "medium"  # Instance flavor (not cluster size)
      image: "RHEL9-latest"
      location: "us-east-1"
```

## Troubleshooting

### Common Issues

1. **Red Hat Token Issues**
   ```bash
   # Verify Red Hat token is valid
   curl -H "Authorization: Bearer $REDHAT_OPENSHIFT_TOKEN" \
        https://api.openshift.com/api/accounts_mgmt/v1/current_account
   ```

2. **Cloud Provider Permissions**
   ```bash
   # AWS - Verify billing account access
   aws sts get-caller-identity
   
   # Azure - Verify service principal permissions
   az role assignment list --assignee $ARM_CLIENT_ID
   ```

3. **Region Availability**
   ```bash
   # Check OpenShift availability in regions
   # ROSA: Check AWS regions
   # ARO: Check Azure regions
   ```

### Best Practices

1. **Use Latest Version**: Always use `version: "latest"` for production
2. **Plan for Growth**: Start with medium size and use autoscaling
3. **Network Planning**: Use custom networking for production deployments
4. **Cost Management**: Monitor cluster usage and adjust worker count
5. **Security**: Use private clusters for production workloads

## Next Steps

- [ROSA Guide](rosa-guide.md)
- [ARO Guide](aro-guide.md)
- [Multi-Cloud OpenShift](multi-cloud-openshift.md)
- [Troubleshooting Guide](../troubleshooting.md) 

# OpenShift Authentication

## Red Hat OpenShift Token

For ROSA and other Red Hat managed OpenShift clusters, you need a Red Hat OpenShift token:

```bash
export REDHAT_OPENSHIFT_TOKEN=your_redhat_token
```

Get your token from: https://console.redhat.com/openshift/token/rosa

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

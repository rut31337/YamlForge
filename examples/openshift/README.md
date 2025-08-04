# OpenShift Examples

This directory contains examples and documentation for deploying OpenShift clusters using YamlForge's comprehensive OpenShift provider.

## OpenShift Provider Overview

YamlForge supports **complete OpenShift deployments** across multiple cloud providers, including:

- **ROSA (Red Hat OpenShift Service on AWS)** - Classic and HCP variants
- **ARO (Azure Red Hat OpenShift)** - Managed OpenShift on Azure  
- **OpenShift Dedicated** - Managed service across clouds
- **Self-Managed OpenShift** - Customer-managed clusters
- **HyperShift** - Hosted control planes for all providers

## Example Structure

```
openshift/
├── aws_openshift_simple_example.yaml   # ROSA Classic + HCP deployment
├── aws_openshift_comprehensive_example.yaml # Full enterprise setup
├── rosa_automatic_phases_example.yaml  # ROSA with Day-2 operations
├── hypershift_example.yaml            # HyperShift hosted control planes
├── day2_operations_example.yaml       # OpenShift operators and apps
├── multi_cloud_openshift_example.yaml # Multi-cloud deployment
└── applications_example.yaml          # Application deployments
```

## Quick Start Examples

### ROSA (Red Hat OpenShift Service on AWS)
```yaml
guid: "prod1"

yamlforge:
  cloud_workspace:
    name: "production-openshift"
    description: "Production ROSA deployment"

  openshift_clusters:
    - name: "production-rosa"
      type: "rosa-classic"
      region: "us-east-1"
      version: "latest"
      size: "large"
```

### ROSA HCP (Hosted Control Plane)
```yaml
guid: "hcp01"

yamlforge:
  cloud_workspace:
    name: "production-hcp"
    description: "Production ROSA HCP deployment"

  openshift_clusters:
    - name: "production-hcp"
      type: "rosa-hcp"
      region: "us-east-1"
      version: "latest"
      size: "large"
      worker_count: 6
```

### Self-Managed OpenShift (Custom Infrastructure)
```yaml
guid: "self1"

yamlforge:
  cloud_workspace:
    name: "self-managed-openshift"
    description: "Self-managed OpenShift cluster"

  openshift_clusters:
    - name: "custom-openshift"
      type: "self-managed"
      provider: "aws"
      region: "us-east-1"
      version: "4.15"
      controlplane_count: 3
      controlplane_machine_type: "m5.xlarge"
      worker_count: 5
      worker_machine_type: "m5.large"
```

## Unified Deployment Model

YamlForge uses a **unified deployment model** - no complex phased deployments or conditional variables:

### Analyze Configuration (Recommended First Step)
```bash
# Analyze OpenShift configuration without generating Terraform
python yamlforge.py aws_openshift_simple_example.yaml --analyze
```

This shows you:
- Required cloud providers
- Instance types and costs
- OpenShift cluster configurations
- Resource requirements

### Simple Deployment
```bash
# Generate and deploy everything at once
python yamlforge.py aws_openshift_simple_example.yaml -d output/ --auto-deploy
```

### Manual Deployment  
```bash
# Generate Terraform configuration
python yamlforge.py aws_openshift_simple_example.yaml -d output/

# Deploy everything together
cd output/
terraform init
terraform apply
```

## Key Features

- **Automated ROSA Role Creation** - YamlForge automatically creates ROSA account roles via CLI
- **Unified Terraform Generation** - Infrastructure and clusters deploy together with proper dependencies
- **Role Separation** - Correct Classic vs HCP role naming and references
- **Billing Account Override** - Support for different billing accounts via environment variables
- **Worker Count Validation** - Automatic adjustment for HCP cluster requirements 

## OpenShift Cluster Field Reference

YamlForge uses a simplified, consistent field structure for OpenShift clusters:

### Required Fields
- `name`: Unique cluster name
- `type`: Cluster type (`rosa-classic`, `rosa-hcp`, `aro`, `self-managed`, etc.)
- `region`/`location`: Cloud region for deployment
- `version`: OpenShift version (e.g., "4.15", "latest")

### Node Configuration (Simplified)
- `controlplane_count`: Number of control plane nodes (for self-managed clusters)
- `controlplane_machine_type`: Machine type for control plane nodes (e.g., "m5.xlarge", "Standard_D4s_v3")
- `worker_count`: Number of worker nodes
- `worker_machine_type`: Machine type for workers (e.g., "m5.large", "Standard_D2s_v3")

### Example Self-Managed Cluster
```yaml
openshift_clusters:
  - name: "production-cluster"
    type: "self-managed"
    provider: "aws"
    region: "us-east-1"
    version: "4.15"
    controlplane_count: 3              # Control plane nodes
    controlplane_machine_type: "m5.xlarge"
    worker_count: 5              # Application nodes
    worker_machine_type: "m5.large"
```

**Note**: Control plane nodes run the control plane, worker nodes run applications. For managed services (ROSA, ARO), only worker node configuration is needed as the control plane is managed by the cloud provider. 

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

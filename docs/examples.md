# Examples Gallery

Comprehensive collection of YamlForge examples for every use case.

## Getting Started Examples

### Basic Single-Cloud
```bash
# Simple AWS deployment
python yamlforge.py examples/testing/simple_test.yaml -d aws-output/ --auto-deploy

# Basic Azure deployment  
python yamlforge.py examples/testing/fedora_example.yaml -d azure-output/ --auto-deploy
```

### Multi-Cloud Basics
```bash
# Multi-cloud RHEL deployment
python yamlforge.py examples/multi-cloud/hybrid_rhel_deployment.yaml -d hybrid-output/ --auto-deploy

# Cross-cloud comparison
python yamlforge.py examples/testing/multi_provider_example.yaml -d multi-output/ --auto-deploy
```

## Cost Optimization Examples

### Cheapest Provider Selection
```bash
# Automatic cost optimization
python yamlforge.py examples/cost-conscious/cheapest_provider_example.yaml -d cost-output/ --auto-deploy

# Mixed deployment strategies
python yamlforge.py examples/cost-conscious/mixed_cheapest_example.yaml -d mixed-output/ --auto-deploy

# Cost optimization with exclusions
python yamlforge.py examples/extended-providers/cost_optimization_with_exclusions.yaml -d excluded-output/ --auto-deploy
```

### GPU Cost Optimization
```bash
# Cheapest GPU across clouds
python yamlforge.py examples/cheapest_gpu_example.yaml -d gpu-cost-output/

# GPU type-specific optimization
python yamlforge.py examples/gpu_type_specific_example.yaml -d gpu-type-output/
```

## GPU & AI/ML Examples

### Basic GPU Workloads
```bash
# Simple GPU deployment
python yamlforge.py examples/quick_gpu_test.yaml -d gpu-output/

# GPU across multiple clouds
python yamlforge.py examples/minimal_gpu_across_clouds_example.yaml -d multi-gpu-output/
```

### Advanced GPU Features
```bash
# GPU validation and error handling
python yamlforge.py examples/gpu_validation_demo.yaml -d gpu-validation-output/

# GPU error handling demonstration
python yamlforge.py examples/gpu_error_handling_demo.yaml -d gpu-error-output/

# GPU workloads example
python yamlforge.py examples/gpu_workloads_example.yaml -d gpu-workloads-output/
```

### GPU Discovery & Optimization
```bash
# Auto flavor discovery for GPU
python yamlforge.py examples/auto_flavor_discovery_example.yaml -d auto-discovery-output/

# Micro GPU testing
python yamlforge.py examples/micro_gpu_test.yaml -d micro-gpu-output/
```

## OpenShift Examples

### Basic OpenShift Clusters
```bash
# Complete OpenShift deployment
python yamlforge.py examples/openshift/complete_multicloud_openshift_example.yaml -d openshift-output/ --auto-deploy

# Enterprise platform example
python yamlforge.py examples/openshift/complete_enterprise_platform_example.yaml -d enterprise-output/ --auto-deploy
```

### OpenShift Applications
```bash
# Application deployment
python yamlforge.py examples/openshift/applications_example.yaml -d apps-output/ --auto-deploy

# Day 2 operations
python yamlforge.py examples/openshift/day2_operations_example.yaml -d day2-output/ --auto-deploy
```

### Multi-Provider OpenShift
```bash
# Multi-cloud OpenShift
python yamlforge.py examples/openshift/multi_cloud_openshift_example.yaml -d multi-openshift-output/

# Self-managed across providers
python yamlforge.py examples/openshift/multi_provider_self_managed_example.yaml -d self-managed-output/
```

### OpenShift Networking
```bash
# Network override example
python yamlforge.py examples/openshift/network_override_example.yaml -d network-output/

# HyperShift deployment
python yamlforge.py examples/openshift/hypershift_example.yaml -d hypershift-output/
```

### Provider-Specific OpenShift
```bash
# GCP OpenShift
python yamlforge.py examples/openshift/gcp_openshift_example.yaml -d gcp-openshift-output/

# ROSA Classic vs HCP comparison
python yamlforge.py examples/openshift/rosa_classic_vs_hcp_example.yaml -d rosa-comparison-output/
```

## Cloud-Specific Examples

### GCP Examples
```bash
# GCP-specific deployment
python yamlforge.py examples/cloud-specific/gcp_example.yaml -d gcp-output/

# GCP dynamic image discovery
python yamlforge.py examples/cloud-specific/gcp_dynamic_example.yaml -d gcp-dynamic-output/
```

### IBM Cloud Examples
```bash
# IBM Classic infrastructure
python yamlforge.py examples/cloud-specific/ibm_classic_example.yaml -d ibm-classic-output/

# IBM VPC (modern) deployment
python yamlforge.py examples/cloud-specific/ibm_modern_example.yaml -d ibm-vpc-output/

# IBM VPC example
python yamlforge.py examples/cloud-specific/ibm_vpc_example.yaml -d ibm-vpc-alt-output/
```

### Architecture Examples
```bash
# Architecture specification
python yamlforge.py examples/cloud-specific/architecture_example.yaml -d arch-output/
```

## Networking Examples

### Security Groups
```bash
# Security group configuration
python yamlforge.py examples/region-and-networking/security_groups_example.yaml -d security-output/
```

### Subnets & Regions
```bash
# Subnet management
python yamlforge.py examples/region-and-networking/subnets_example.yaml -d subnet-output/

# Region specification
python yamlforge.py examples/region-and-networking/region_specification_example.yaml -d region-output/
```

### SSH Keys
```bash
# SSH key management
python yamlforge.py examples/ssh_keys_example.yaml -d ssh-output/
```

## Red Hat & Enterprise Examples

### Red Hat Cloud Access
```bash
# RHEL Gold vs Public comparison
python yamlforge.py examples/multi-cloud/rhel_gold_vs_public_test.yaml -d rhel-comparison-output/

# Cloud access testing
python yamlforge.py examples/multi-cloud/cloud_access_test.yaml -d cloud-access-output/
```

### Enterprise Testing
```bash
# RHEL Gold testing
python yamlforge.py examples/testing/rhel_gold_test.yaml -d rhel-gold-output/

# RHEL latest testing
python yamlforge.py examples/testing/rhel_latest_test.yaml -d rhel-latest-output/

# Tags example
python yamlforge.py examples/testing/tags_example.yaml -d tags-output/
```

## Advanced Features Examples

### Auto Discovery
```bash
# Automatic flavor discovery
python yamlforge.py examples/auto_flavor_discovery_example.yaml -d auto-flavor-output/

# Auto delegation testing
python yamlforge.py examples/auto_delegation_test.yaml -d auto-delegation-output/
```

### DNS & Domain Management
```bash
# Cross-project DNS
python yamlforge.py examples/cross_project_dns_test.yaml -d cross-dns-output/

# Default project DNS
python yamlforge.py examples/default_project_dns_test.yaml -d default-dns-output/

# Domain ownership testing
python yamlforge.py examples/domain_ownership_test.yaml -d domain-output/

# Minimal DNS testing
python yamlforge.py examples/minimal_dns_test.yaml -d minimal-dns-output/

# No DNS configuration
python yamlforge.py examples/no_dns_test.yaml -d no-dns-output/

# Separate domains testing
python yamlforge.py examples/separate_domains_test.yaml -d separate-domains-output/
```

### Validation & Testing
```bash
# Instance name validation
python yamlforge.py examples/instance_name_validation_example.yaml -d validation-output/

# Project management testing
python yamlforge.py examples/project_management_test.yaml -d project-mgmt-output/

# Provider selection testing
python yamlforge.py examples/testing/provider_selection_example.yaml -d provider-selection-output/

# Cloud workspace example
python yamlforge.py examples/testing/cloud_workspace_example.yaml -d workspace-output/
```

## Example Categories by Use Case

### 🚀 **Getting Started**
- `simple_test.yaml` - Basic single-cloud
- `testing/fedora_example.yaml` - Simple Fedora deployment
- `testing/simple_test.yaml` - Minimal configuration

### 💰 **Cost Optimization**
- `cost-conscious/cheapest_provider_example.yaml` - Auto cost optimization
- `cost-conscious/mixed_cheapest_example.yaml` - Mixed strategies
- `cheapest_gpu_example.yaml` - GPU cost optimization

### 🎮 **GPU & AI/ML**
- `gpu_workloads_example.yaml` - GPU workloads
- `gpu_type_specific_example.yaml` - Specific GPU types
- `minimal_gpu_across_clouds_example.yaml` - Multi-cloud GPU

### 🌐 **Multi-Cloud**
- `multi-cloud/hybrid_rhel_deployment.yaml` - RHEL across clouds
- `testing/multi_provider_example.yaml` - Multi-provider testing
- `extended-providers/multi_provider_new_example.yaml` - Extended providers

### OpenShift
- `openshift/complete_multicloud_openshift_example.yaml` - Complete deployment
- `openshift/applications_example.yaml` - Application deployment
- `openshift/multi_cloud_openshift_example.yaml` - Multi-cloud OpenShift

### 🔧 **Advanced Features**
- `auto_flavor_discovery_example.yaml` - Auto discovery
- `gpu_validation_demo.yaml` - GPU validation
- `instance_name_validation_example.yaml` - Name validation

## Running Examples

### Quick Test
```bash
# Set GUID
export GUID=test1

# Pick any example
python yamlforge.py examples/simple_test.yaml -d output/

# Review generated Terraform
ls output/
```

### Production Use
```bash
# Copy and customize
cp examples/multi-cloud/hybrid_rhel_deployment.yaml my-production.yaml

# Edit for your needs
vim my-production.yaml

# Generate Terraform
python yamlforge.py my-production.yaml -d production-terraform/
```

## Example File Structure

```
examples/
├── cost-conscious/          # Cost optimization examples
├── cloud-specific/         # Provider-specific examples  
├── extended-providers/     # Extended provider examples
├── multi-cloud/           # Multi-cloud deployments
├── openshift/             # OpenShift examples
├── region-and-networking/ # Network configuration
└── testing/               # Test configurations
```

## Next Steps

After exploring examples:
- [Quick Start Guide](quickstart.md) - Get started quickly
- [Configuration Guide](configuration/mappings.md) - Understand mappings
- [OpenShift Guide](openshift/overview.md) - Deep dive into OpenShift
- [Troubleshooting](troubleshooting.md) - Common issues 
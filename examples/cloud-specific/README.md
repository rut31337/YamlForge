# Cloud-Specific Examples

This directory contains examples for each supported cloud provider, demonstrating provider-specific features and configurations.

## Examples

### AWS
- **[aws-example.yaml](aws-example.yaml)** - Basic AWS deployment with EC2 instances and security groups

### Azure
- **[azure-example.yaml](azure-example.yaml)** - Basic Azure deployment with resource groups and network security groups

### Google Cloud Platform (GCP)
- **[gcp_example.yaml](gcp_example.yaml)** - Basic GCP deployment with Compute Engine instances and firewall rules

### IBM Cloud
- **[ibm_vpc_example.yaml](ibm_vpc_example.yaml)** - IBM VPC deployment with resource groups and security groups
- **[ibm_classic_example.yaml](ibm_classic_example.yaml)** - IBM Classic Infrastructure deployment with tagging

## Usage

```bash
# Deploy to specific cloud providers
yamlforge examples/cloud-specific/aws-example.yaml
yamlforge examples/cloud-specific/azure-example.yaml
yamlforge examples/cloud-specific/gcp_example.yaml
yamlforge examples/cloud-specific/ibm_vpc_example.yaml
yamlforge examples/cloud-specific/ibm_classic_example.yaml
```

## Provider-Specific Features

### AWS
- EC2 instances with various instance types
- Security groups for network access control
- VPC and subnet configuration
- IAM roles and policies

### Azure
- Virtual machines with different sizes
- Resource groups for organization
- Network security groups
- Azure-specific configurations

### GCP
- Compute Engine instances
- Firewall rules
- Project and network configuration
- GCP-specific instance types

### IBM Cloud
- **IBM VPC**: Resource groups, VPC networking, security groups
- **IBM Classic**: Full account access, tagging, classic infrastructure

## Configuration Patterns

Each example demonstrates:
- Basic instance deployment
- Security group configuration
- Provider-specific settings
- Resource tagging
- GUID-based naming

## Customization

All examples can be customized by:
1. Changing the `guid` for unique resource naming
2. Modifying instance sizes and regions
3. Adjusting security group rules
4. Adding provider-specific configurations
5. Changing images and operating systems 
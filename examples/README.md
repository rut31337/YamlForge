# YamlForge Examples

This directory contains examples demonstrating how to use YamlForge for multi-cloud infrastructure deployment.

## Quick Start Examples

### Basic Examples
- **[simple.yaml](simple.yaml)** - Basic single instance deployment
- **[multi-cloud.yaml](multi-cloud.yaml)** - Multi-cloud deployment demonstration
- **[3tier.yaml](3tier.yaml)** - Classic 3-tier architecture
- **[gpu-example.yaml](gpu-example.yaml)** - GPU workloads and AI/ML deployments
- **[security-groups.yaml](security-groups.yaml)** - Security group configuration examples

### Cloud-Specific Examples
- **[cloud-specific/aws-example.yaml](cloud-specific/aws-example.yaml)** - AWS deployment
- **[cloud-specific/azure-example.yaml](cloud-specific/azure-example.yaml)** - Azure deployment
- **[cloud-specific/gcp_example.yaml](cloud-specific/gcp_example.yaml)** - GCP deployment
- **[cloud-specific/ibm_vpc_example.yaml](cloud-specific/ibm_vpc_example.yaml)** - IBM VPC deployment
- **[cloud-specific/ibm_classic_example.yaml](cloud-specific/ibm_classic_example.yaml)** - IBM Classic deployment

### Advanced Examples
- **[advanced/cost-optimization.yaml](advanced/cost-optimization.yaml)** - Cost-optimized deployments using `cheapest` provider
- **[advanced/enterprise.yaml](advanced/enterprise.yaml)** - Enterprise features with resource groups and compliance

### OpenShift Examples
- **[openshift/](openshift/)** - OpenShift cluster deployment examples

## Usage

### Deploy a Simple Example
```bash
# Deploy a basic single instance
yamlforge examples/simple.yaml

# Deploy multi-cloud infrastructure
yamlforge examples/multi-cloud.yaml

# Deploy 3-tier architecture
yamlforge examples/3tier.yaml

# Deploy security groups example
yamlforge examples/security-groups.yaml
```

### Deploy Cloud-Specific Examples
```bash
# Deploy to specific cloud providers
yamlforge examples/cloud-specific/aws-example.yaml
yamlforge examples/cloud-specific/azure-example.yaml
yamlforge examples/cloud-specific/gcp_example.yaml
yamlforge examples/cloud-specific/ibm_vpc_example.yaml
yamlforge examples/cloud-specific/ibm_classic_example.yaml
```

### Deploy Advanced Examples
```bash
# Deploy cost-optimized infrastructure
yamlforge examples/advanced/cost-optimization.yaml

# Deploy enterprise infrastructure
yamlforge examples/advanced/enterprise.yaml
```

## Example Features

### Core Features
- **Multi-cloud deployment** - Deploy across AWS, Azure, GCP, IBM Cloud
- **Cost optimization** - Use `cheapest` provider for automatic cost optimization
- **Security groups** - Define network security rules
- **Resource tagging** - Organize resources with tags
- **GUID templating** - Unique resource naming with `{guid}` placeholders

### Advanced Features
- **Resource groups** - Azure and IBM VPC resource group management
- **Existing projects** - GCP project reuse
- **GPU workloads** - AI/ML instance types and configurations
- **Enterprise compliance** - SOX-ready configurations
- **Custom specifications** - CPU, memory, and GPU requirements

## Configuration

Each example demonstrates different configuration patterns:

- **Simple deployments** - Basic single-instance setups
- **Multi-cloud** - Cross-provider deployments
- **Enterprise** - Resource groups, compliance, and advanced features
- **Cost optimization** - Automatic provider selection for best pricing
- **GPU workloads** - AI/ML infrastructure with specialized instances

## Customization

All examples can be customized by:
1. Changing the `guid` for unique resource naming
2. Modifying instance sizes and regions
3. Adjusting security group rules
4. Adding or removing instances
5. Changing cloud providers

## Best Practices

1. **Always use unique GUIDs** - Prevents resource naming conflicts
2. **Use appropriate security groups** - Follow least-privilege access
3. **Tag resources** - Organize and track costs
4. **Consider cost optimization** - Use `cheapest` provider when appropriate
5. **Plan for scaling** - Design for future growth 
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
  - Configurable cloud-user creation (`create_cloud_user: true/false`)
  - SSH access configuration
  - Resource group management
- **[ibm_classic_example.yaml](ibm_classic_example.yaml)** - IBM Classic Infrastructure deployment with tagging

### Container Native Virtualization (CNV)
- **[cnv-example.yaml](cnv-example.yaml)** - CNV/KubeVirt deployment for Kubernetes and OpenShift clusters
  - Virtual machines using container disk images
  - Support for both Kubernetes (KubeVirt) and OpenShift (CNV) clusters
  - GPU-enabled instances (when available)
  - Namespace-based organization

## Usage

### Analyze Examples (Recommended First Step)
```bash
# Analyze cloud-specific configurations
python yamlforge.py examples/cloud-specific/aws-example.yaml --analyze
python yamlforge.py examples/cloud-specific/azure-example.yaml --analyze
python yamlforge.py examples/cloud-specific/gcp_example.yaml --analyze
python yamlforge.py examples/cloud-specific/ibm_vpc_example.yaml --analyze
python yamlforge.py examples/cloud-specific/ibm_classic_example.yaml --analyze
python yamlforge.py examples/cloud-specific/cnv-example.yaml --analyze
```

### Deploy to Specific Cloud Providers
```bash
# Deploy to specific cloud providers
python yamlforge.py examples/cloud-specific/aws-example.yaml -d output/ --auto-deploy
python yamlforge.py examples/cloud-specific/azure-example.yaml -d output/ --auto-deploy
python yamlforge.py examples/cloud-specific/gcp_example.yaml -d output/ --auto-deploy
python yamlforge.py examples/cloud-specific/ibm_vpc_example.yaml -d output/ --auto-deploy
python yamlforge.py examples/cloud-specific/ibm_classic_example.yaml -d output/ --auto-deploy
python yamlforge.py examples/cloud-specific/cnv-example.yaml -d output/ --auto-deploy
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
  - `create_cloud_user`: Boolean to control cloud-user account creation (default: true)
  - `use_existing_resource_group`: Use existing resource group instead of creating new ones
- **IBM Classic**: Full account access, tagging, classic infrastructure

### CNV (Container Native Virtualization)
- **Kubernetes**: KubeVirt-based virtual machines
  - Requires KubeVirt operator installation
  - Uses `KUBECONFIG` environment variable for cluster access
- **OpenShift**: CNV-based virtual machines
  - Requires CNV operator installation
  - Uses OpenShift cluster credentials
- **Features**: Container disk images, GPU support, namespace isolation
- **No cloud provider credentials required** - uses local cluster resources only

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

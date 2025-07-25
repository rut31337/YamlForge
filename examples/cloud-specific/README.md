# Cloud-Specific Examples

This directory contains examples focused on individual cloud providers, showcasing provider-specific features and configurations.

## Available Examples

### **AWS Examples**
- **`architecture_example.yaml`** - Basic AWS deployment with EC2, VPC, and security groups
  - Single-cloud AWS architecture
  - RHEL 9 instances with user data scripts
  - Basic web and application server setup

### **GCP Examples**
- **`gcp_example.yaml`** - Standard GCP deployment with Compute Engine
  - GCP-specific machine types and networking
  - Cloud-native GCP resource configuration
  - Basic instance and firewall setup

- **`gcp_dynamic_example.yaml`** - Advanced GCP with dynamic image discovery
  - Dynamic RHEL Gold image resolution via GCP API
  - Latest Red Hat Cloud Access images
  - Demonstrates automatic image discovery features

- **`gcp_existing_project_example.yaml`** - Use existing GCP project
  - Deploy to an existing GCP project instead of creating new one
  - Ideal for users with limited organization-level permissions
  - Uses data sources instead of project creation

### **Azure Examples**
- **`azure_full_subscription_example.yaml`** - Use entire Azure subscription (default)
  - Deploy with automatic resource group creation per region
  - Ideal for users with full subscription permissions
  - Creates and manages resource groups automatically

- **`azure_shared_subscription_example.yaml`** - Use existing Azure resource group
  - Deploy to an existing resource group in a shared subscription
  - Ideal for enterprise scenarios with limited Azure permissions
  - Uses data sources instead of resource group creation

### **IBM Cloud Examples**
- **`ibm_classic_example.yaml`** - IBM Classic Infrastructure deployment
  - IBM Cloud Classic infrastructure model
  - Classic instance types (B1.*, C1.*, M1.*)
  - Traditional datacenter-style deployment

- **`ibm_vpc_example.yaml`** - IBM VPC Infrastructure deployment
  - Modern IBM Cloud VPC (Generation 2)
  - VPC instance profiles (bx2-*, cx2-*, mx2-*)
  - Cloud-native IBM infrastructure

- **`ibm_modern_example.yaml`** - Additional IBM VPC examples
  - Extended IBM Cloud VPC configurations
  - Multiple instance types and configurations

## Usage

```bash
# Deploy AWS example
python yamlforge.py examples/cloud-specific/architecture_example.yaml -d terraform-aws/

# Deploy GCP with dynamic images
python yamlforge.py examples/cloud-specific/gcp_dynamic_example.yaml -d terraform-gcp/

# Deploy to existing GCP project (requires GCP_EXISTING_PROJECT_ID env var)
python yamlforge.py examples/cloud-specific/gcp_existing_project_example.yaml -d terraform-gcp-existing/

# Deploy with full Azure subscription access (default behavior)
python yamlforge.py examples/cloud-specific/azure_full_subscription_example.yaml -d terraform-azure-full/

# Deploy to existing Azure resource group (requires AZURE_EXISTING_RESOURCE_GROUP_NAME env var)
python yamlforge.py examples/cloud-specific/azure_shared_subscription_example.yaml -d terraform-azure-shared/

# Deploy IBM VPC infrastructure
python yamlforge.py examples/cloud-specific/ibm_vpc_example.yaml -d terraform-ibm/
```

## Key Features Demonstrated

- **Provider-specific instance types** and configurations
- **Native cloud networking** (VPC, VNet, etc.)
- **Cloud-specific image handling** (AMIs, images, etc.)
- **Provider-unique features** (dynamic discovery, etc.)
- **Single-cloud best practices** for each provider

## Learning Path

1. **Start with `architecture_example.yaml`** for basic concepts
2. **Try `gcp_example.yaml`** to see GCP differences
3. **Explore `ibm_vpc_example.yaml`** for IBM Cloud modern approach
4. **Compare with `ibm_classic_example.yaml`** to understand infrastructure evolution
5. **Use `gcp_dynamic_example.yaml`** for advanced image discovery features 
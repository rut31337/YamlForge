# Azure Red Hat OpenShift (ARO) Guide

Complete guide for deploying Azure Red Hat OpenShift clusters using YamlForge with full Terraform automation.

## Overview

Azure Red Hat OpenShift (ARO) is a fully managed OpenShift service jointly engineered and operated by Microsoft and Red Hat. YamlForge provides **complete Terraform automation** for ARO cluster deployment, including automatic service principal creation, networking, and security configuration.

## Key Features

### ✅ **Complete Terraform Automation**
- **No CLI tools required** - Pure Terraform implementation
- **Automatic service principal creation** and configuration
- **Enhanced networking** with Network Security Groups
- **Resource provider registration** handled automatically
- **90-minute deployment timeouts** for reliable cluster creation

### ✅ **Enterprise Security**
- **Automatic Azure AD integration** with service principals
- **Role-based access control** with proper permissions
- **Network security groups** for master and worker subnets
- **Service endpoints** for Azure Container Registry and Storage

### ✅ **Production Ready**
- **GUID-based resource naming** for uniqueness
- **Comprehensive outputs** for integration
- **Proper dependency management** for reliable deployments
- **FIPS validation support** for compliance requirements

## Prerequisites

### Required Azure Permissions
ARO clusters **require full Azure subscription access** and are **not compatible** with resource group-based credentials.

### Environment Variables
```bash
# Required Azure credentials (full subscription access)
export ARM_CLIENT_ID="your-service-principal-client-id"
export ARM_CLIENT_SECRET="your-service-principal-secret"
export ARM_SUBSCRIPTION_ID="your-azure-subscription-id"
export ARM_TENANT_ID="your-azure-tenant-id"

# Required: Global unique identifier
export GUID="aro01"

# Optional: SSH key for cluster access
export SSH_PUBLIC_KEY="ssh-rsa AAAAB3NzaC1yc2E... your-email@example.com"
```

### Get Azure Credentials
```bash
# Create service principal with Contributor role
az ad sp create-for-rbac --role="Contributor" --scopes="/subscriptions/YOUR_SUBSCRIPTION_ID"

# Output will include:
# - appId (use as ARM_CLIENT_ID)
# - password (use as ARM_CLIENT_SECRET)  
# - tenant (use as ARM_TENANT_ID)
```

## Basic Configuration

### Simple ARO Cluster
```yaml
guid: "aro01"

yamlforge:
  cloud_workspace:
    name: "aro-production"
    description: "Production ARO cluster deployment"

  openshift_clusters:
    - name: "prod-aro"
      type: "aro"                    # Azure Red Hat OpenShift
      region: "eastus"               # Azure region
      version: "4.18.19"             # OpenShift version
      size: "medium"                 # Cluster size (small/medium/large)
```

### Advanced ARO Configuration
```yaml
guid: "aro02"

yamlforge:
  cloud_workspace:
    name: "enterprise-aro"
    description: "Enterprise ARO with advanced configuration"

  openshift_clusters:
    - name: "enterprise-aro"
      type: "aro"
      region: "eastus2"
      version: "4.18.19"
      size: "large"
      
      # Worker configuration
      worker_count: 6                # Number of worker nodes
      worker_disk_size: 256          # Disk size in GB
      
      # Security options
      private: false                 # Public/private cluster
      fips_enabled: true             # FIPS validation
      
      # Networking customization
      networking:
        vnet_cidr: "10.2.0.0/16"
        master_subnet_cidr: "10.2.0.0/24"
        worker_subnet_cidr: "10.2.1.0/24"
        pod_cidr: "10.128.0.0/14"
        service_cidr: "172.30.0.0/16"
```

## Cluster Sizes

ARO cluster sizes are defined in `mappings/flavors_openshift/openshift_azure.yaml`:

### Small Cluster
```yaml
small:
  master_size: "medium"    # Standard_D4s_v3 (4 vCPU, 16GB)
  worker_size: "medium"    # Standard_D4s_v3 (4 vCPU, 16GB)
  worker_count: 3          # Minimum for production
```

### Medium Cluster  
```yaml
medium:
  master_size: "large"     # Standard_D8s_v3 (8 vCPU, 32GB)
  worker_size: "large"     # Standard_D8s_v3 (8 vCPU, 32GB)
  worker_count: 4
```

### Large Cluster
```yaml
large:
  master_size: "xlarge"    # Standard_D16s_v3 (16 vCPU, 64GB)
  worker_size: "xlarge"    # Standard_D16s_v3 (16 vCPU, 64GB)  
  worker_count: 6
```

## Networking Configuration

### Default Networking
ARO automatically creates:
- **Virtual Network** with proper CIDR ranges
- **Master Subnet** for control plane nodes
- **Worker Subnet** for compute nodes
- **Network Security Groups** with appropriate rules
- **Service Endpoints** for Azure Container Registry and Storage

### Custom Networking
```yaml
openshift_clusters:
  - name: "custom-network-aro"
    type: "aro"
    region: "westus2"
    version: "4.18.19"
    size: "medium"
    
    networking:
      # Custom VNet CIDR
      vnet_cidr: "192.168.0.0/16"
      
      # Custom subnet CIDRs
      master_subnet_cidr: "192.168.10.0/24"
      worker_subnet_cidr: "192.168.20.0/24"
      
      # OpenShift network configuration
      pod_cidr: "10.128.0.0/14"
      service_cidr: "172.30.0.0/16"
```

### Network Security
Automatic security configuration includes:

**Master Subnet NSG:**
- Allow HTTPS (443) inbound for API access
- Proper outbound rules for cluster communication

**Worker Subnet NSG:**
- Allow HTTP (80) and HTTPS (443) inbound for applications
- Container registry and storage access

## Authentication & Service Principals

### Automatic Service Principal Creation
YamlForge automatically creates and configures:

1. **Azure AD Application** for the ARO cluster
2. **Service Principal** with proper permissions
3. **Service Principal Password** with secure generation
4. **Role Assignment** (Contributor) to the resource group

### Service Principal Configuration
```hcl
# Automatically generated by YamlForge
resource "azuread_application" "aro_app" {
  display_name = "aro-${cluster_name}-sp-${guid}"
  owners       = [data.azurerm_client_config.current.object_id]
}

resource "azuread_service_principal" "aro_sp" {
  client_id = azuread_application.aro_app.client_id
  owners    = [data.azurerm_client_config.current.object_id]
}
```

## Resource Management

### Automatic Resource Naming
All resources use GUID-based naming for uniqueness:

```yaml
# Resource naming pattern
aro_rg_name: "rg-aro-${cluster_name}-${guid}"
aro_cluster_name: "aro-${cluster_name}-${guid}"
aro_vnet_name: "vnet-aro-${cluster_name}-${guid}"
```

### Resource Tags
Comprehensive tagging for resource management:

```hcl
tags = {
  Environment = var.environment
  ManagedBy   = "yamlforge"
  Cloud       = "azure"
  Platform    = "aro"
  Cluster     = "${cluster_name}"
  GUID        = "${guid}"
}
```

### Dependency Management
Proper Terraform dependencies ensure resources are created in the correct order:

```hcl
depends_on = [
  azurerm_resource_provider_registration.aro_providers,
  azurerm_role_assignment.sp_contributor,
  azurerm_subnet_network_security_group_association.master_nsg_assoc,
  azurerm_subnet_network_security_group_association.worker_nsg_assoc
]
```

## Deployment Process

### Step 1: Environment Setup
```bash
# Source your environment variables
source envvars.sh

# Verify Azure authentication
az account show
```

### Step 2: Generate Configuration
```bash
# Create ARO deployment
python yamlforge.py aro-config.yaml -d aro-terraform/
```

### Step 3: Deploy Infrastructure
```bash
# Deploy with Terraform
cd aro-terraform/
terraform init
terraform plan
terraform apply
```

### Step 4: Access Cluster
```bash
# Get cluster credentials from outputs
terraform output aro_api_server_url
terraform output aro_console_url

# Access via Azure Portal or oc CLI
```

## Cluster Outputs

YamlForge provides comprehensive outputs for integration:

### Basic Cluster Information
```hcl
output "aro_cluster_id" {
  description = "ARO cluster resource ID"
  value       = azapi_resource.aro_cluster.id
}

output "aro_cluster_name" {
  description = "ARO cluster name"  
  value       = azapi_resource.aro_cluster.name
}

output "aro_resource_group" {
  description = "ARO cluster resource group"
  value       = azurerm_resource_group.aro_rg.name
}
```

### Access Information
```hcl
output "aro_api_server_url" {
  description = "ARO cluster API server URL"
  value       = jsondecode(azapi_resource.aro_cluster.output).properties.apiserverProfile.url
}

output "aro_console_url" {
  description = "ARO cluster console URL"
  value       = jsondecode(azapi_resource.aro_cluster.output).properties.consoleProfile.url
}
```

### Integration Details
```hcl
output "aro_service_principal_client_id" {
  description = "ARO cluster service principal client ID"
  value       = azuread_service_principal.aro_sp.client_id
}

output "aro_master_subnet_id" {
  description = "ARO cluster master subnet ID"
  value       = azurerm_subnet.aro_master_subnet.id
}

output "aro_worker_subnet_id" {
  description = "ARO cluster worker subnet ID"
  value       = azurerm_subnet.aro_worker_subnet.id
}
```

## Troubleshooting

### Common Issues

#### Authentication Errors
```bash
# Error: Insufficient privileges
# Solution: Ensure service principal has Contributor role on subscription
az role assignment create --assignee $ARM_CLIENT_ID --role "Contributor" --scope "/subscriptions/$ARM_SUBSCRIPTION_ID"
```

#### Resource Provider Registration
```bash
# Error: The subscription is not registered to use namespace 'Microsoft.RedHatOpenShift'
# Solution: ARO provider automatically registers required providers
# If manual registration needed:
az provider register --namespace Microsoft.RedHatOpenShift
```

#### Network Configuration Issues
```bash
# Error: Subnet overlaps with existing subnets
# Solution: Use different CIDR ranges in networking configuration
```

### Validation Checklist

**Before Deployment:**
- [ ] Azure subscription access verified
- [ ] Service principal has Contributor permissions
- [ ] GUID is unique and valid (5 chars, lowercase alphanumeric)
- [ ] Network CIDRs don't overlap with existing resources

**After Deployment:**
- [ ] ARO cluster shows "Succeeded" status in Azure Portal
- [ ] API server URL is accessible
- [ ] Console URL loads OpenShift web console
- [ ] `oc login` works with cluster credentials

## Security Considerations

### Private Clusters
```yaml
openshift_clusters:
  - name: "private-aro"
    type: "aro"
    region: "eastus"
    version: "4.18.19"
    size: "medium"
    private: true              # Private API server and ingress
```

### FIPS Compliance
```yaml
openshift_clusters:
  - name: "fips-aro"
    type: "aro"
    region: "eastus"
    version: "4.18.19"
    size: "medium"
    fips_enabled: true         # FIPS validation enabled
```

### Network Isolation
- ARO automatically creates isolated networking
- Network Security Groups provide layered security
- Service endpoints for secure Azure service access

## Cost Optimization

### Regional Pricing
Different Azure regions have different pricing. Consider:
- **East US**: Often lowest cost
- **West US 2**: Good performance and cost balance
- **North Europe**: EU data residency requirements

### Instance Sizing
- **Small**: Development and testing
- **Medium**: Small production workloads
- **Large**: High-performance production workloads

### Cost Monitoring
```bash
# View ARO cluster costs in Azure Cost Management
az consumption usage list --scope "/subscriptions/$ARM_SUBSCRIPTION_ID"
```

## Best Practices

### Production Deployments
1. **Use large cluster size** for production workloads
2. **Enable FIPS validation** for compliance requirements
3. **Use private clusters** for enhanced security
4. **Implement proper RBAC** for cluster access
5. **Monitor costs** regularly

### Development Environments
1. **Use small cluster size** to minimize costs
2. **Public clusters** for easier access during development
3. **Shared resource groups** for team collaboration
4. **Regular cleanup** of unused clusters

### Multi-Region Strategy
```yaml
openshift_clusters:
  # Primary region
  - name: "prod-aro-east"
    type: "aro"
    region: "eastus"
    version: "4.18.19"
    size: "large"
    
  # Disaster recovery region
  - name: "prod-aro-west"
    type: "aro"
    region: "westus2"
    version: "4.18.19"
    size: "large"
```

## Related Documentation

- [OpenShift Overview](overview.md)
- [ROSA Guide](rosa-guide.md)
- [Multi-Cloud OpenShift](multi-cloud-openshift.md)
- [Cost Optimization](../features/cost-optimization.md)
- [Troubleshooting](../troubleshooting.md)

---

**ARO Provider Location**: `yamlforge/providers/openshift/aro.py`
**Configuration Mappings**: `mappings/flavors_openshift/openshift_azure.yaml`
**Default Settings**: `defaults/openshift.yaml` 
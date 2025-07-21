"""
ARO (Azure Red Hat OpenShift) Provider for yamlforge
Supports Azure Red Hat OpenShift managed service
"""

from typing import Dict
from .base import BaseOpenShiftProvider


class AROProvider(BaseOpenShiftProvider):
    """Azure Red Hat OpenShift (ARO) Provider"""
    
    def generate_aro_cluster(self, cluster_config: Dict) -> str:
        """Generate ARO cluster Terraform configuration"""
        
        cluster_name = cluster_config.get('name', 'aro-cluster')
        clean_name = self.clean_name(cluster_name)
        location = cluster_config.get('region', 'East US')
        version = self.validate_openshift_version(cluster_config.get('version', ''))
        size_config = self.get_cluster_size_config(
            cluster_config.get('size', 'medium'), 'aro'
        )
        
        # Get machine sizes using OpenShift-optimized flavor mappings
        worker_vm_size = self.get_openshift_machine_type('azure', size_config['worker_size'], 'worker')
        master_vm_size = self.get_openshift_machine_type('azure', size_config['master_size'], 'master')
        
        worker_count = cluster_config.get('worker_count', size_config['worker_count'])
        
        # Get merged networking configuration (defaults + user overrides)
        networking = self.get_merged_networking_config(cluster_config, 'aro')
        
        terraform_config = f'''
# =============================================================================
# ARO CLUSTER: {cluster_name}
# =============================================================================

# Resource Group for ARO
resource "azurerm_resource_group" "{clean_name}_rg" {{
  name     = "rg-aro-{cluster_name}"
  location = "{location}"
  
  tags = {{
    Environment = var.environment
    ManagedBy   = "yamlforge"
    Cloud       = "azure"
    Platform    = "aro"
  }}
}}

# Virtual Network for ARO
resource "azurerm_virtual_network" "{clean_name}_vnet" {{
  name                = "vnet-aro-{cluster_name}"
  address_space       = ["{networking.get('vnet_cidr', '10.1.0.0/16')}"]
  location            = azurerm_resource_group.{clean_name}_rg.location
  resource_group_name = azurerm_resource_group.{clean_name}_rg.name
  
  tags = {{
    Environment = var.environment
    ManagedBy   = "yamlforge"
  }}
}}

# Master Subnet
resource "azurerm_subnet" "{clean_name}_master_subnet" {{
  name                 = "master-subnet"
  resource_group_name  = azurerm_resource_group.{clean_name}_rg.name
  virtual_network_name = azurerm_virtual_network.{clean_name}_vnet.name
  address_prefixes     = ["{networking.get('master_subnet_cidr', '10.1.0.0/24')}"]
  
  # Required for ARO
  private_link_service_network_policies_enabled = false
  
  service_endpoints = [
    "Microsoft.ContainerRegistry"
  ]
}}

# Worker Subnet  
resource "azurerm_subnet" "{clean_name}_worker_subnet" {{
  name                 = "worker-subnet"
  resource_group_name  = azurerm_resource_group.{clean_name}_rg.name
  virtual_network_name = azurerm_virtual_network.{clean_name}_vnet.name
  address_prefixes     = ["{networking.get('worker_subnet_cidr', '10.1.1.0/24')}"]
  
  service_endpoints = [
    "Microsoft.ContainerRegistry"
  ]
}}

# ARO Cluster
resource "azapi_resource" "{clean_name}" {{
  type      = "Microsoft.RedHatOpenShift/openShiftClusters@2023-09-04"
  name      = "aro-{cluster_name}"
  location  = azurerm_resource_group.{clean_name}_rg.location
  parent_id = azurerm_resource_group.{clean_name}_rg.id

  body = jsonencode({{
    properties = {{
      clusterProfile = {{
        domain               = "{cluster_name}"
        fipsValidatedModules = "{cluster_config.get('fips_enabled', False) and 'Enabled' or 'Disabled'}"
        resourceGroupId      = "/subscriptions/${{var.azure_subscription_id}}/resourceGroups/aro-{cluster_name}-cluster"
        version              = "{version}"
      }}
      
      networkProfile = {{
        podCidr     = "{networking.get('pod_cidr', '10.128.0.0/14')}"
        serviceCidr = "{networking.get('service_cidr', '172.30.0.0/16')}"
      }}
      
      servicePrincipalProfile = {{
        clientId     = var.azure_aro_client_id
        clientSecret = var.azure_aro_client_secret
      }}
      
      masterProfile = {{
        vmSize               = "{master_vm_size}"
        subnetId            = azurerm_subnet.{clean_name}_master_subnet.id
        encryptionAtHost    = "Disabled"
        diskEncryptionSetId = null
      }}
      
      workerProfiles = [
        {{
          name                = "workers"
          vmSize              = "{worker_vm_size}"
          diskSizeGB          = {cluster_config.get('worker_disk_size', 128)}
          subnetId           = azurerm_subnet.{clean_name}_worker_subnet.id
          count              = {worker_count}
          encryptionAtHost   = "Disabled"
          diskEncryptionSetId = null
        }}
      ]
      
      apiserverProfile = {{
        visibility = "{cluster_config.get('private', False) and 'Private' or 'Public'}"
      }}
      
      ingressProfiles = [
        {{
          name       = "default"
          visibility = "{cluster_config.get('private', False) and 'Private' or 'Public'}"
        }}
      ]
    }}
  }})

  tags = {{
    Environment = var.environment
    ManagedBy   = "yamlforge"
    Cloud       = "azure"
    Platform    = "aro"
  }}
  
  timeouts {{
    create = "60m"
    delete = "60m"
    update = "60m"
  }}
}}

'''

        return terraform_config 
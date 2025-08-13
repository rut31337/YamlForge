"""
ARO (Azure Red Hat OpenShift) Provider for yamlforge
Supports Azure Red Hat OpenShift managed service with comprehensive Terraform automation
"""

import os
import json
import time
import requests
from typing import Dict, List
from .base import BaseOpenShiftProvider
from ...utils import find_yamlforge_file


class AROProvider(BaseOpenShiftProvider):
    """ARO Provider for Azure Red Hat OpenShift using dedicated Azure provider resource"""

    def __init__(self, converter):
        super().__init__(converter)
        self.provider_name = 'aro'
        self._aro_versions_cache = None
        self._cache_timestamp = None
        self._cache_ttl = 3600  # Cache for 1 hour

    def _get_azure_access_token(self) -> str:
        """Get Azure access token using service principal credentials"""
        tenant_id = os.getenv('ARM_TENANT_ID')
        client_id = os.getenv('ARM_CLIENT_ID') 
        client_secret = os.getenv('ARM_CLIENT_SECRET')
        
        if not all([tenant_id, client_id, client_secret]):
            raise ValueError(
                "Azure credentials not found. Please set ARM_TENANT_ID, ARM_CLIENT_ID, and ARM_CLIENT_SECRET environment variables."
            )
        
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        token_data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'https://management.azure.com/.default'
        }
        
        try:
            response = requests.post(token_url, data=token_data, timeout=30)
            response.raise_for_status()
            return response.json()['access_token']
        except requests.RequestException as e:
            raise ValueError(f"Failed to get Azure access token: {e}")

    def _query_aro_versions(self, location: str = "eastus") -> List[str]:
        """Query supported ARO versions from Azure Management API with caching"""
        # Check cache first
        if (self._aro_versions_cache and self._cache_timestamp and 
            time.time() - self._cache_timestamp < self._cache_ttl):
            print(f"Using cached ARO versions (age: {int(time.time() - self._cache_timestamp)}s)")
            return self._aro_versions_cache
        
        subscription_id = os.getenv('ARM_SUBSCRIPTION_ID') or os.getenv('AZURE_SUBSCRIPTION_ID')
        if not subscription_id:
            raise ValueError("Azure subscription ID not found. Please set ARM_SUBSCRIPTION_ID environment variable.")
        
        access_token = self._get_azure_access_token()
        api_url = (f"https://management.azure.com/subscriptions/{subscription_id}/"
                  f"providers/Microsoft.RedHatOpenShift/locations/{location}/"
                  f"openshiftversions?api-version=2023-11-22")
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Retry with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Retrying Azure API call in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                
                print(f"Querying Azure API for supported ARO versions in {location}...")
                response = requests.get(api_url, headers=headers, timeout=30)
                response.raise_for_status()
                
                api_data = response.json()
                versions = []
                
                if 'value' in api_data:
                    for version_obj in api_data['value']:
                        if 'properties' in version_obj and 'version' in version_obj['properties']:
                            versions.append(version_obj['properties']['version'])
                
                # Cache the results, sorted newest first
                self._aro_versions_cache = sorted(versions, reverse=True)
                self._cache_timestamp = time.time()
                
                print(f"Retrieved {len(versions)} supported ARO versions from Azure API")
                return self._aro_versions_cache
                
            except requests.RequestException as e:
                if attempt == max_retries - 1:  # Last attempt
                    raise ValueError(f"Failed to query Azure API for ARO versions after {max_retries} attempts: {e}")
                print(f"Azure API call failed (attempt {attempt + 1}/{max_retries}): {e}")

    def _validate_aro_version(self, version: str, region: str = "eastus") -> str:
        """Validate requested ARO version against Azure API"""
        supported_versions = self._query_aro_versions(region)
        
        # Handle "latest" keyword
        if version.lower() == "latest":
            latest_version = supported_versions[0]  # First in sorted list
            print(f"ARO version 'latest' resolved to {latest_version}")
            return latest_version
        
        # Exact match
        if version in supported_versions:
            print(f"ARO version {version} is supported")
            return version
        
        # Partial match (e.g., "4.15" -> "4.15.49")
        if not version.count('.') >= 2:  # If not a full semantic version
            matches = [v for v in supported_versions if v.startswith(version + '.')]
            if matches:
                selected = matches[0]  # Take the highest (first in sorted list)
                print(f"ARO version {version} mapped to supported version {selected}")
                return selected
        
        # No match found - error out
        raise ValueError(
            f"ARO version '{version}' is not supported in Azure region '{region}'. "
            f"Supported versions: {', '.join(supported_versions[:5])}{'...' if len(supported_versions) > 5 else ''}"
        )
    
    def generate_aro_cluster(self, cluster_config: Dict) -> str:
        """Generate ARO cluster using dedicated azurerm_redhat_openshift_cluster resource"""
        
        cluster_name = cluster_config.get('name')
        if not cluster_name:
            raise ValueError("ARO cluster 'name' must be specified")
        
        clean_name = self.clean_name(cluster_name)
        
        # Required configuration
        region = cluster_config.get('region')
        if not region:
            raise ValueError(f"ARO cluster '{cluster_name}' must specify 'region'")
            
        version = cluster_config.get('version')
        if not version:
            raise ValueError(f"ARO cluster '{cluster_name}' must specify 'version'")
        
        # Validate ARO version against Azure API in real-time
        print(f"ARO cluster '{cluster_name}': Validating OpenShift version {version} against Azure API...")
        try:
            validated_version = self._validate_aro_version(version, region)
            version = validated_version  # Use the validated/mapped version
        except ValueError as e:
            # Re-raise with cluster context
            raise ValueError(f"ARO cluster '{cluster_name}': {str(e)}")
        
        size = cluster_config.get('size')
        if not size:
            raise ValueError(f"ARO cluster '{cluster_name}' must specify 'size'")
        size_config = self.get_cluster_size_config(size, 'aro')
        
        # Worker configuration with size fallback
        worker_count = cluster_config.get('worker_count')
        if worker_count is None:
            worker_count = size_config['worker_count']
            
        # ARO requires minimum 3 worker nodes
        if worker_count < 3:
            print(f"ARO cluster '{cluster_name}': Worker count {worker_count} is below minimum. Adjusting to 3 worker nodes.")
            worker_count = 3
        
        worker_disk_size = cluster_config.get('worker_disk_size', 128)
        controlplane_vm_size = size_config['controlplane_size']
        worker_vm_size = size_config['worker_size']
        
        # Load ARO flavor mappings from YAML file
        try:
            import yaml
            from pathlib import Path
            
            aro_flavors_path = find_yamlforge_file("mappings/flavors/aro.yaml")
            if aro_flavors_path.exists():
                with open(aro_flavors_path, 'r') as f:
                    aro_flavors = yaml.safe_load(f)
                    flavor_mappings = aro_flavors.get('flavor_mappings', {})
                    
                    # Find the appropriate size configuration
                    size_found = False
                    for size_name, size_configs in flavor_mappings.items():
                        if size_name in [controlplane_vm_size, worker_vm_size]:
                            # Get the first (and usually only) config for this size
                            if size_configs:
                                flavor_name = next(iter(size_configs.keys()))
                                flavor_config = size_configs[flavor_name]
                                
                                if size_name == controlplane_vm_size:
                                    controlplane_azure_size = flavor_config.get('controlplane_size', 'Standard_D8s_v3')
                                if size_name == worker_vm_size:
                                    worker_azure_size = flavor_config.get('worker_size', 'Standard_D4s_v3')
                                size_found = True
                    
                    if not size_found:
                        # Fallback to default sizes if not found in mappings
                        controlplane_azure_size = 'Standard_D8s_v3'
                        worker_azure_size = 'Standard_D4s_v3'
                        print(f"Warning: ARO size configuration not found in mappings, using defaults")
            else:
                raise ValueError("ARO flavors file not found: mappings/flavors/aro.yaml")
        except Exception as e:
            # Fallback to default sizes if YAML loading fails
            controlplane_azure_size = 'Standard_D8s_v3'
            worker_azure_size = 'Standard_D4s_v3'
            print(f"Warning: Could not load ARO flavors from YAML: {e}, using defaults")
        
        # Security and networking configuration
        private_cluster = cluster_config.get('private', False)
        fips_enabled = cluster_config.get('fips_enabled', False)
        
        api_visibility = "Private" if private_cluster else "Public"
        ingress_visibility = "Private" if private_cluster else "Public" 
        fips_setting = "true" if fips_enabled else "false"
        
        # Custom networking configuration
        networking = cluster_config.get('networking', {})
        vnet_cidr = networking.get('vnet_cidr', '10.1.0.0/16')
        controlplane_subnet_cidr = networking.get('controlplane_subnet_cidr', '10.1.0.0/24')
        worker_subnet_cidr = networking.get('worker_subnet_cidr', '10.1.1.0/24')
        pod_cidr = networking.get('pod_cidr', '10.128.0.0/14')
        service_cidr = networking.get('service_cidr', '172.30.0.0/16')
        
        # Resource naming with GUID
        guid = self.converter.get_validated_guid()
        
        # Generate unique resource group name to avoid conflicts
        import time
        timestamp = str(int(time.time()))[-6:]  # Last 6 digits of timestamp
        
        terraform_config = f'''
# =============================================================================
# AZURE RED HAT OPENSHIFT (ARO) CLUSTER: {cluster_name}
# =============================================================================
# Complete Terraform automation using dedicated azurerm_redhat_openshift_cluster resource
# Automatic service principal creation, networking, and security configuration
# OpenShift version {version} validated against Azure API during YamlForge generation

# Resource Group for ARO cluster with unique naming
resource "azurerm_resource_group" "aro_{clean_name}_rg" {{
  name     = "rg-aro-{cluster_name}-{guid}-{timestamp}"
  location = "{region}"

  tags = merge(var.common_tags, {{
    Name        = "rg-aro-{cluster_name}-{guid}-{timestamp}"
    Environment = var.environment
    ManagedBy   = "yamlforge"
    Cloud       = "azure"
    Platform    = "aro"
    Cluster     = "{cluster_name}"
    GUID        = "{guid}"
  }})
}}

# Note: Azure resource providers are automatically registered by Terraform
# Microsoft.RedHatOpenShift is typically pre-registered in Azure subscriptions
# Skipping explicit registration to avoid conflicts

# Virtual Network for ARO cluster
resource "azurerm_virtual_network" "aro_{clean_name}_vnet" {{
  name                = "vnet-aro-{cluster_name}-{guid}"
  address_space       = ["{vnet_cidr}"]
  location            = azurerm_resource_group.aro_{clean_name}_rg.location
  resource_group_name = azurerm_resource_group.aro_{clean_name}_rg.name

  tags = merge(var.common_tags, {{
    Name        = "vnet-aro-{cluster_name}-{guid}"
    Environment = var.environment
    ManagedBy   = "yamlforge"
    Cloud       = "azure"
    Platform    = "aro"
    Cluster     = "{cluster_name}"
    GUID        = "{guid}"
  }})
}}

# Control plane subnet for control plane nodes
resource "azurerm_subnet" "aro_{clean_name}_controlplane_subnet" {{
  name                                          = "controlplane-subnet"
  resource_group_name                           = azurerm_resource_group.aro_{clean_name}_rg.name
  virtual_network_name                          = azurerm_virtual_network.aro_{clean_name}_vnet.name
  address_prefixes                              = ["{controlplane_subnet_cidr}"]
  private_link_service_network_policies_enabled = false
  service_endpoints                             = ["Microsoft.ContainerRegistry", "Microsoft.Storage"]
}}

# Worker subnet for compute nodes  
resource "azurerm_subnet" "aro_{clean_name}_worker_subnet" {{
  name                 = "worker-subnet"
  resource_group_name  = azurerm_resource_group.aro_{clean_name}_rg.name
  virtual_network_name = azurerm_virtual_network.aro_{clean_name}_vnet.name
  address_prefixes     = ["{worker_subnet_cidr}"]
  service_endpoints    = ["Microsoft.ContainerRegistry", "Microsoft.Storage"]
}}

# Note: ARO does NOT support Network Security Groups on subnets
# Azure Red Hat OpenShift manages security at the cluster level internally
# Any NSG attachments will cause deployment failure with:
# "The provided subnet is invalid: must not have a network security group attached"

# Get current Azure client configuration
data "azurerm_client_config" "current" {{}}

# Use existing service principal credentials from environment variables
# This avoids the need for elevated Azure AD permissions to create new applications
# Uses the same credentials that authenticated Terraform (ARM_CLIENT_ID/ARM_CLIENT_SECRET)
locals {{
  aro_service_principal_client_id = data.azurerm_client_config.current.client_id
  aro_service_principal_client_secret = var.arm_client_secret
}}

# Role assignment: Contributor role for service principal on resource group
resource "azurerm_role_assignment" "aro_{clean_name}_sp_contributor" {{
  scope                = azurerm_resource_group.aro_{clean_name}_rg.id
  role_definition_name = "Contributor"
  principal_id         = data.azurerm_client_config.current.object_id
}}

# Get ARO Resource Provider service principal
data "azuread_service_principal" "aro_rp" {{
  display_name = "Azure Red Hat OpenShift RP"
}}

# Role assignment: Network Contributor role for ARO RP on VNet
resource "azurerm_role_assignment" "aro_{clean_name}_rp_network_contributor" {{
  scope                = azurerm_virtual_network.aro_{clean_name}_vnet.id
  role_definition_name = "Network Contributor"
  principal_id         = data.azuread_service_principal.aro_rp.object_id
}}

# Azure Red Hat OpenShift Cluster using dedicated resource
resource "azurerm_redhat_openshift_cluster" "aro_{clean_name}" {{
  name                = "aro-{cluster_name}-{guid}"
  location            = azurerm_resource_group.aro_{clean_name}_rg.location
  resource_group_name = azurerm_resource_group.aro_{clean_name}_rg.name

  cluster_profile {{
    domain                 = "{cluster_name}-{guid}"
    fips_enabled = {fips_setting}
    version                = "{version}"
    pull_secret            = var.redhat_pull_secret
  }}

  network_profile {{
    pod_cidr     = "{pod_cidr}"
    service_cidr = "{service_cidr}"
  }}

  main_profile {{
    vm_size   = "{controlplane_azure_size}"
    subnet_id = azurerm_subnet.aro_{clean_name}_controlplane_subnet.id
  }}

  api_server_profile {{
    visibility = "{api_visibility}"
  }}

  ingress_profile {{

    visibility = "{ingress_visibility}"
  }}

  worker_profile {{
    vm_size      = "{worker_azure_size}"
    disk_size_gb = {worker_disk_size}
    node_count   = {worker_count}
    subnet_id    = azurerm_subnet.aro_{clean_name}_worker_subnet.id
  }}

  service_principal {{
    client_id     = local.aro_service_principal_client_id
    client_secret = local.aro_service_principal_client_secret
  }}

  depends_on = [
    azurerm_role_assignment.aro_{clean_name}_sp_contributor,
    azurerm_role_assignment.aro_{clean_name}_rp_network_contributor,
    azurerm_subnet.aro_{clean_name}_controlplane_subnet,
    azurerm_subnet.aro_{clean_name}_worker_subnet
  ]

  tags = merge(var.common_tags, {{
    Name        = "aro-{cluster_name}-{guid}"
    Environment = var.environment
    ManagedBy   = "yamlforge"
    Cloud       = "azure"
    Platform    = "aro"
    Cluster     = "{cluster_name}"
    GUID        = "{guid}"
  }})

  timeouts {{
    create = "90m"
    delete = "90m"
  }}
}}

# =============================================================================
# ARO CLUSTER OUTPUTS
# =============================================================================

# Basic cluster information
output "aro_cluster_id_{clean_name}" {{
  description = "ARO cluster resource ID"
  value       = azurerm_redhat_openshift_cluster.aro_{clean_name}.id
}}

output "aro_cluster_name_{clean_name}" {{
  description = "ARO cluster name"
  value       = azurerm_redhat_openshift_cluster.aro_{clean_name}.name
}}

output "aro_cluster_version_{clean_name}" {{
  description = "ARO cluster OpenShift version (validated against Azure API)"
  value       = "{version}"
}}

output "aro_resource_group_{clean_name}" {{
  description = "ARO cluster resource group"
  value       = azurerm_resource_group.aro_{clean_name}_rg.name
}}

# Access information
output "aro_api_server_url_{clean_name}" {{
  description = "ARO cluster API server URL"
  value       = azurerm_redhat_openshift_cluster.aro_{clean_name}.api_server_profile[0].url
}}

output "aro_console_url_{clean_name}" {{
  description = "ARO cluster console URL"
  value       = azurerm_redhat_openshift_cluster.aro_{clean_name}.console_url
}}

# Integration details
output "aro_service_principal_client_id_{clean_name}" {{
  description = "ARO cluster service principal client ID"
  value       = local.aro_service_principal_client_id
}}

output "aro_controlplane_subnet_id_{clean_name}" {{
  description = "ARO cluster control plane subnet ID"
  value       = azurerm_subnet.aro_{clean_name}_controlplane_subnet.id
}}

output "aro_worker_subnet_id_{clean_name}" {{
  description = "ARO cluster worker subnet ID"
  value       = azurerm_subnet.aro_{clean_name}_worker_subnet.id
}}

# Cluster endpoint for provider configuration
output "aro_cluster_endpoint_{clean_name}" {{
  description = "ARO cluster endpoint for provider configuration"
  value       = azurerm_redhat_openshift_cluster.aro_{clean_name}.api_server_profile[0].url
}}
'''

        return terraform_config 

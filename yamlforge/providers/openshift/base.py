"""
Base OpenShift Provider for yamlforge
Contains common functionality shared by all OpenShift deployment types
"""

import yaml
import json
import re
from typing import Dict, List, Optional, Any
from pathlib import Path


class BaseOpenShiftProvider:
    """Base class for all OpenShift deployment types"""
    
    # Mapping of OpenShift types to cloud providers
    OPENSHIFT_PROVIDER_MAP = {
        'rosa-classic': 'aws',        # ROSA Classic - customer manages infrastructure
        'rosa-hcp': 'aws',           # ROSA with Hosted Control Planes - Red Hat manages control plane
        'aro': 'azure',
        'openshift-dedicated': None,  # Can run on multiple clouds
        'self-managed': None,         # Can run on any infrastructure
        'hypershift': None,           # Control plane can be anywhere
    }
    
    # Default OpenShift versions
    SUPPORTED_VERSIONS = [
        '4.14.15', '4.14.12', '4.14.10',
        '4.13.25', '4.13.20', '4.13.15',
        '4.12.35', '4.12.30'
    ]
    
    def __init__(self, converter):
        self.converter = converter
        self.openshift_config = self.load_config()
        
    def load_config(self):
        """Load OpenShift configuration from defaults YAML file."""
        defaults_file = Path("defaults/openshift.yaml")
        if not defaults_file.exists():
            raise Exception(f"Required OpenShift defaults file not found: {defaults_file}")

        try:
            with open(defaults_file, 'r') as f:
                defaults_config = yaml.safe_load(f)
        except Exception as e:
            raise Exception(f"Failed to load defaults/openshift.yaml: {e}")

        if not defaults_config:
            raise Exception("defaults/openshift.yaml is empty or invalid")

        return defaults_config.get('openshift', {})
        
    def load_operator_config(self, operator_type: str) -> Dict:
        """Load operator-specific configuration from YAML file."""
        config_file = Path(f"defaults/openshift_operators/{operator_type}.yaml")
        if not config_file.exists():
            raise Exception(f"Required operator config file not found: {config_file}")

        try:
            with open(config_file, 'r') as f:
                operator_config = yaml.safe_load(f)
        except Exception as e:
            raise Exception(f"Failed to load {config_file}: {e}")

        if not operator_config:
            raise Exception(f"{config_file} is empty or invalid")

        return operator_config
        
    def get_openshift_provider(self, cluster_type: str) -> Optional[str]:
        """Get the cloud provider for an OpenShift cluster type"""
        return self.OPENSHIFT_PROVIDER_MAP.get(cluster_type)
        
    def validate_openshift_version(self, version: str) -> str:
        """Validate and normalize OpenShift version"""
        if not version:
            return self.SUPPORTED_VERSIONS[0]  # Latest stable
            
        if version in self.SUPPORTED_VERSIONS:
            return version
            
        # Try to find a close match
        major_minor = '.'.join(version.split('.')[:2])
        for supported in self.SUPPORTED_VERSIONS:
            if supported.startswith(major_minor):
                return supported
                
        # Default to latest if no match
        return self.SUPPORTED_VERSIONS[0]
        
    def get_cluster_size_config(self, size: str, cluster_type: str) -> Dict[str, Any]:
        """Get cluster sizing configuration based on yamlforge size"""
        
        # Try to get cloud provider for this cluster type
        cloud_provider = self.get_openshift_provider(cluster_type)
        
        # Try OpenShift-specific flavor configurations first
        if cloud_provider:
            openshift_flavor_key = f"openshift_{cloud_provider}"
            openshift_flavors = self.converter.flavors.get(openshift_flavor_key, {})
            
            if openshift_flavors:
                cluster_sizes = openshift_flavors.get('cluster_sizes', {})
                if size in cluster_sizes:
                    return cluster_sizes[size]
        
        # Try any available OpenShift flavor configuration as fallback
        for flavor_key, flavor_data in self.converter.flavors.items():
            if flavor_key.startswith('openshift_'):
                cluster_sizes = flavor_data.get('cluster_sizes', {})
                if size in cluster_sizes:
                    return cluster_sizes[size]
        
        # If no YAML configuration found, raise an error
        available_sizes = set()
        for flavor_key, flavor_data in self.converter.flavors.items():
            if flavor_key.startswith('openshift_'):
                cluster_sizes = flavor_data.get('cluster_sizes', {})
                available_sizes.update(cluster_sizes.keys())
        
        if available_sizes:
            raise ValueError(f"OpenShift cluster size '{size}' not found in YAML configurations. Available sizes: {sorted(available_sizes)}")
        else:
            raise ValueError(f"No OpenShift flavor configurations found in YAML files. Please ensure openshift_*.yaml files are present in mappings/flavors/")
        
    def get_default_base_networking(self, cluster_type: str) -> Dict[str, str]:
        """Get default base networking configuration for OpenShift from YAML config"""
        
        networking_config = self.openshift_config.get('default_base_networking', {})
        
        # Base OpenShift networking from YAML
        base_networking = {
            'service_cidr': networking_config.get('service_cidr', '172.30.0.0/16'),
            'pod_cidr': networking_config.get('pod_cidr', '10.128.0.0/14'),
            'host_prefix': str(networking_config.get('host_prefix', 23))
        }
        
        # Provider-specific networking from YAML
        provider_networking = networking_config.get(cluster_type, {})
        if cluster_type == 'self-managed':
            # Handle both 'self-managed' and 'self_managed' in YAML
            provider_networking = networking_config.get('self_managed', provider_networking)
            
        base_networking.update(provider_networking)
            
        return base_networking
        
    def get_networking_value(self, cluster_type: str, key: str, default: str = None) -> str:
        """Get a specific networking value for a cluster type with fallbacks"""
        networking_defaults = self.get_default_base_networking(cluster_type)
        return networking_defaults.get(key, default or '')
        
    def get_merged_networking_config(self, cluster_config: Dict, cluster_type: str) -> Dict[str, str]:
        """Get merged networking configuration with user overrides taking precedence"""
        # Start with base defaults from YAML
        base_networking = self.get_default_base_networking(cluster_type)
        
        # Merge with user-provided networking configuration
        user_networking = cluster_config.get('networking', {})
        merged_networking = base_networking.copy()
        merged_networking.update(user_networking)
        
        return merged_networking
        
    def generate_terraform_providers(self, cluster_configs: List[Dict]) -> str:
        """Generate Terraform provider blocks for OpenShift clusters"""
        
        providers_needed = set()
        
        # Determine which providers we need
        for cluster in cluster_configs:
            cluster_type = cluster.get('type')
            cloud_provider = self.get_openshift_provider(cluster_type)
            
            if cluster_type in ['rosa-classic', 'rosa-hcp', 'openshift-dedicated']:
                providers_needed.add('rhcs')  # Red Hat Cloud Services
            if cluster_type == 'aro':
                providers_needed.add('azapi')  # Azure API
            if cluster_type == 'self-managed':
                # Self-managed can run on any provider, check the provider field
                self_managed_provider = cluster.get('provider', 'aws')
                providers_needed.add(self_managed_provider)
            if cluster_type == 'openshift-dedicated':
                # Dedicated can run on multiple clouds, check cloud_provider
                dedicated_cloud = cluster.get('cloud_provider', 'aws')
                providers_needed.add(dedicated_cloud)
            if cluster_type == 'hypershift':
                # HyperShift worker nodes can run on any provider
                hypershift_provider = cluster.get('provider', 'aws')
                providers_needed.add(hypershift_provider)
                # Also need kubectl provider for HyperShift CRDs
                providers_needed.add('kubectl')
            if cloud_provider:
                providers_needed.add(cloud_provider)
                
        # For applications
        if any(cluster.get('applications') for cluster in cluster_configs):
            providers_needed.update(['kubernetes', 'helm', 'kubectl'])
            
        terraform_config = '''
terraform {
  required_providers {'''

        # Add required providers
        if 'rhcs' in providers_needed:
            terraform_config += '''
    rhcs = {
      source  = "terraform-redhat/rhcs"
      version = "~> 1.6"
    }'''
            
        if 'azapi' in providers_needed:
            terraform_config += '''
    azapi = {
      source  = "Azure/azapi"
      version = "~> 1.0"
    }'''
            
        if 'kubernetes' in providers_needed:
            terraform_config += '''
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.20"
    }'''
            
        if 'helm' in providers_needed:
            terraform_config += '''
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.10"
    }'''
            
        if 'kubectl' in providers_needed:
            terraform_config += '''
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = "~> 1.14"
    }'''

        terraform_config += '''
  }
}

'''

        # Add provider configurations
        if 'rhcs' in providers_needed:
            terraform_config += '''
# Red Hat Cloud Services Provider
provider "rhcs" {
  token = var.redhat_openshift_token
  url   = var.redhat_openshift_url
}

'''

        return terraform_config
        
    def generate_openshift_variables(self, cluster_configs: List[Dict]) -> str:
        """Generate Terraform variables for OpenShift clusters"""
        
        variables = '''
# =============================================================================
# OPENSHIFT CREDENTIALS
# =============================================================================

variable "redhat_openshift_token" {
  description = "Red Hat OpenShift Cluster Manager API token"
  type        = string
  sensitive   = true
}

variable "redhat_openshift_url" {
  description = "Red Hat OpenShift Cluster Manager API URL"
  type        = string
  default     = "https://api.openshift.com"
}

# =============================================================================
# OPENSHIFT CONFIGURATION
# =============================================================================

variable "openshift_version" {
  description = "Default OpenShift version to deploy"
  type        = string
  default     = "4.14.15"
}

'''

        # Add cluster-specific variables
        for cluster in cluster_configs:
            cluster_name = cluster.get('name', 'default')
            clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', cluster_name)
            
            variables += f'''
variable "openshift_{clean_name}_token" {{
  description = "Access token for {cluster_name} cluster"
  type        = string
  sensitive   = true
  default     = ""
}}

'''

        return variables
        
    def clean_name(self, name: str) -> str:
        """Clean name for Terraform resource naming"""
        return re.sub(r'[^a-zA-Z0-9_]', '_', name)
    
    def get_openshift_machine_type(self, provider: str, size: str, role: str = 'worker') -> str:
        """Get OpenShift-optimized machine type from flavor mappings"""
        # Try OpenShift-specific flavors first
        openshift_flavor_key = f"openshift_{provider}"
        openshift_flavors = self.converter.flavors.get(openshift_flavor_key, {})
        
        if openshift_flavors:
            # Check size mappings first
            size_mappings = openshift_flavors.get('size_mappings', {})
            mapped_size = size_mappings.get(size)
            
            if mapped_size:
                flavor_mappings = openshift_flavors.get('flavor_mappings', {})
                flavor_config = flavor_mappings.get(mapped_size)
                if flavor_config:
                    # Return the first (and usually only) machine type for this size
                    return list(flavor_config.keys())[0]
            
            # If no size mapping found, try direct lookup in flavor mappings
            flavor_mappings = openshift_flavors.get('flavor_mappings', {})
            if size in flavor_mappings:
                return list(flavor_mappings[size].keys())[0]
        
        # Fallback to regular provider flavors
        provider_flavors = self.converter.flavors.get(provider, {})
        machine_type = provider_flavors.get('flavor_mappings', {}).get(size)
        
        if machine_type:
            return machine_type
        
        # If no YAML configuration found, raise an error with helpful information
        available_flavors = {}
        
        # Check OpenShift-specific flavors
        openshift_flavor_key = f"openshift_{provider}"
        if openshift_flavor_key in self.converter.flavors:
            flavor_mappings = self.converter.flavors[openshift_flavor_key].get('flavor_mappings', {})
            if flavor_mappings:
                available_flavors[f"OpenShift-{provider}"] = list(flavor_mappings.keys())
        
        # Check regular provider flavors
        provider_flavors = self.converter.flavors.get(provider, {})
        if provider_flavors:
            flavor_mappings = provider_flavors.get('flavor_mappings', {})
            if flavor_mappings:
                available_flavors[provider] = list(flavor_mappings.keys())
        
        # Check all OpenShift flavor configurations
        for flavor_key, flavor_data in self.converter.flavors.items():
            if flavor_key.startswith('openshift_'):
                flavor_mappings = flavor_data.get('flavor_mappings', {})
                if flavor_mappings:
                    available_flavors[flavor_key] = list(flavor_mappings.keys())
        
        if available_flavors:
            flavor_info = []
            for flavor_source, sizes in available_flavors.items():
                flavor_info.append(f"  {flavor_source}: {sizes}")
            
            raise ValueError(f"OpenShift machine type '{size}' for provider '{provider}' (role: {role}) not found in YAML configurations.\n\nAvailable machine types:\n" + "\n".join(flavor_info) + f"\n\nPlease check mappings/flavors/openshift_{provider}.yaml or add the missing size mapping.")
        else:
            raise ValueError(f"No flavor configurations found for provider '{provider}'. Please ensure the appropriate YAML files are present in mappings/flavors/.") 
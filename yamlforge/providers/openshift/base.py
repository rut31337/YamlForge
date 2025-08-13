"""
Base OpenShift Provider for yamlforge
Contains common functionality shared by all OpenShift deployment types
"""

import yaml
import json
import re
from typing import Dict, List, Optional, Any
from pathlib import Path
from ...utils import find_yamlforge_file


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
    
    # OpenShift versions are dynamically fetched from Red Hat API
    # No static fallback versions - API connectivity required
    
    def __init__(self, converter=None):
        """Initialize the base OpenShift provider"""
        self.converter = converter
        # Load OpenShift defaults for service account permissions
        self.openshift_defaults = self._load_openshift_defaults()
        # Maintain backward compatibility
        self.openshift_config = self.load_config()
    
    def _load_openshift_defaults(self):
        """Load OpenShift defaults configuration"""
        import yaml
        from ...utils import find_yamlforge_file
        
        try:
            defaults_path = find_yamlforge_file('defaults/openshift.yaml')
            with open(defaults_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            # Return minimal defaults if file not found
            return {
                'security': {
                    'service_accounts': {
                        'cluster_admin_limited': {'permissions': []},
                        'app_deployer': {'permissions': []}
                    }
                }
            }
        
    def load_config(self):
        """Load OpenShift configuration from defaults YAML file."""
        defaults_file = find_yamlforge_file("defaults/openshift.yaml")
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
    
    def get_token_duration(self) -> str:
        """Get token duration from OpenShift defaults configuration."""
        token_config = self.openshift_defaults.get('security', {}).get('service_accounts', {}).get('token_expiration', {})
        return token_config.get('default_duration', '8760h')  # Default to 1 year if not configured
        
    def load_operator_config(self, operator_type: str) -> Dict:
        """Load operator-specific configuration from YAML file."""
        config_file = find_yamlforge_file(f"defaults/openshift_operators/{operator_type}.yaml")
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
        
    def validate_openshift_version(self, version: str, cluster_type: str = "rosa", auto_discover_version: bool = False) -> str:
        """
        Validate OpenShift version using dynamic version management
        
        Args:
            version: OpenShift version to validate
            cluster_type: Type of OpenShift cluster (rosa-classic, rosa-hcp, self-managed, etc.)
            auto_discover_version: If False (default), fail on unsupported versions; if True, auto-discover and upgrade to latest
            
        Returns:
            Validated version string
            
        Raises:
            ValueError: If version is unsupported and auto_discover_version is False
        """
        # Skip version validation in no-credentials mode
        if self.converter and self.converter.no_credentials:
            print(f"  NO-CREDENTIALS MODE: Skipping OpenShift version validation for '{version}'")
            return version
        
        # For self-managed clusters, skip ROSA API validation
        # Self-managed clusters can use any OpenShift version without ROSA-specific restrictions
        if cluster_type == "self-managed":
            print(f"  SELF-MANAGED: Skipping ROSA version validation for '{version}' (any OpenShift version allowed)")
            return version
        
        # Only validate against ROSA API for ROSA cluster types
        if cluster_type not in ["rosa-classic", "rosa-hcp"]:
            print(f"  NON-ROSA CLUSTER: Skipping ROSA version validation for '{version}' (cluster type: {cluster_type})")
            return version
            
        try:
            # Import the dynamic version manager for ROSA clusters
            from .rosa_dynamic import DynamicROSAVersionProvider
            dynamic_provider = DynamicROSAVersionProvider()
            
            # Use get_recommended_version which handles all cases including the auto_discover_version flag
            return dynamic_provider.get_recommended_version(version, cluster_type=cluster_type, auto_discover_version=auto_discover_version)
            
        except Exception as e:
            # If dynamic provider fails, this is a critical error for ROSA clusters
            raise ValueError(f"Cannot validate OpenShift version '{version}': {e}. "
                           f"Ensure REDHAT_OPENSHIFT_TOKEN is set and API connectivity is available.")
        
    def get_cluster_size_config(self, size: str, cluster_type: str, cloud_provider: str = None) -> Dict[str, Any]:
        """Get cluster sizing configuration based on yamlforge size"""
        
        # For self-managed clusters, use the explicitly provided cloud_provider
        if cluster_type == "self-managed" and cloud_provider:
            target_cloud_provider = cloud_provider
        else:
            # Try to get cloud provider for this cluster type from the mapping
            target_cloud_provider = self.get_openshift_provider(cluster_type)
        
        # Try OpenShift-specific flavor configurations first
        if target_cloud_provider:
            openshift_flavor_key = f"openshift_{target_cloud_provider}"
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
        

        
    def get_merged_networking_config(self, cluster_config: Dict, cluster_type: str) -> Dict[str, str]:
        """Get merged networking configuration with user overrides taking precedence"""
        # Start with base defaults from YAML
        base_networking = self.get_default_base_networking(cluster_type)
        
        # Merge with user-provided networking configuration
        user_networking = cluster_config.get('networking') or {}
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
                # ARO uses standard Azure provider (azurerm)
                pass
            if cluster_type == 'self-managed':
                # Self-managed can run on any provider, check the provider field
                self_managed_provider = cluster.get('provider')
                providers_needed.add(self_managed_provider)
            if cluster_type == 'openshift-dedicated':
                # Dedicated can run on multiple clouds, check provider
                dedicated_cloud = cluster.get('provider')
                providers_needed.add(dedicated_cloud)
            if cluster_type == 'hypershift':
                # HyperShift worker nodes can run on any provider
                hypershift_provider = cluster.get('provider')
                providers_needed.add(hypershift_provider)
                # Also need kubectl provider for HyperShift CRDs
                providers_needed.add('kubectl')
            if cloud_provider:
                providers_needed.add(cloud_provider)
                
        # For applications
        if any(cluster.get('applications') for cluster in cluster_configs):
            providers_needed.update(['kubernetes', 'helm', 'kubectl'])
            
        terraform_config = '''
# OpenShift Provider Configuration

'''

        # Note: Required providers are managed by the core converter
        terraform_config += '''

'''

        # Provider configurations are handled by the core converter
        # The OpenShift provider just returns its configuration blocks

        return terraform_config
        
    def generate_openshift_variables(self, cluster_configs: List[Dict]) -> str:
        """Generate Terraform variables for OpenShift clusters"""
        
        variables = '''
# =============================================================================
# OPENSHIFT CREDENTIALS
# =============================================================================

# Red Hat Pull Secret for enhanced content access
variable "redhat_pull_secret" {
  description = "Red Hat pull secret for accessing Red Hat container registries and additional content"
  type        = string
  sensitive   = true
  default     = ""
}

# =============================================================================
# OPENSHIFT CONFIGURATION
# =============================================================================

variable "openshift_version" {
  description = "Default OpenShift version to deploy"
  type        = string
  default     = "4.18.19"
}

variable "deploy_day2_operations" {
  description = "Deploy Day-2 operations (monitoring, GitOps, operators). Set to true when clusters are ready."
  type        = bool
  default     = false
}



variable "deploy_hypershift_mgmt" {
  description = "Deploy HyperShift management clusters"
  type        = bool
  default     = false
}

variable "deploy_hypershift_hosted" {
  description = "Deploy HyperShift hosted clusters (requires management clusters to be ready)"
  type        = bool
  default     = false
}

variable "rosa_oidc_config_id" {
  description = "OIDC configuration ID for ROSA clusters (shared between Classic and HCP)"
  type        = string
  default     = ""
}

'''

        # Add cluster-specific variables
        for cluster in cluster_configs:
            cluster_name = cluster.get('name')
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
        """Get OpenShift-optimized machine type from flavor mappings
        
        Args:
            provider: Cloud provider (aws, azure, etc.)
            size: Size specification (small, medium, large)
            role: Node role ('worker' or 'controlplane')
        """
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

 

    def generate_application_providers(self, cluster_configs: List[Dict], deployment_method: str = 'terraform') -> str:
        """Generate Kubernetes and Helm provider configurations for the 3-tier service account model."""
        if not cluster_configs:
            return ""
            
        provider_config = '''
# =============================================================================
# KUBERNETES & HELM PROVIDERS - 3-TIER SERVICE ACCOUNT MODEL
# =============================================================================

'''
        
        for cluster in cluster_configs:
            cluster_name = cluster.get('name')
            if not cluster_name:
                continue
                
            clean_name = self.clean_name(cluster_name)
            cluster_type = cluster.get('type')
            if not cluster_type:
                raise ValueError(f"Cluster type must be specified for cluster '{cluster_name}'. Supported types: rosa-classic, rosa-hcp, aro, openshift-dedicated, self-managed, hypershift")
            
            # Handle ROSA clusters based on deployment method
            if cluster_type in ['rosa-classic', 'rosa-hcp']:
                if deployment_method == 'cli':
                    # CLI method - skip provider configuration
                    provider_config += f'''
# =============================================================================
# ROSA CLUSTER: {cluster_name} (CLI Method)
# =============================================================================
# ROSA clusters are created via ROSA CLI after Terraform deployment
# Provider configurations will be available after running: ./rosa-setup.sh
# Use 'rosa describe cluster {cluster_name}' to get connection details

'''
                    continue
                else:
                    # Terraform method with phased deployment - skip providers for Phase 1
                    provider_config += f'''
# =============================================================================
# ROSA CLUSTER: {cluster_name} (Terraform Method - Unified Deployment)
# =============================================================================
# Providers will be generated after cluster is deployed
# Infrastructure and clusters deploy together with proper terraform dependencies
# Day-2 operations are available after cluster deployment

'''
                    continue
            
            # Determine cluster endpoint and deployment condition based on type
            cluster_condition = '1'  # Default to always deployed
            if cluster_type == 'rosa-classic':
                cluster_endpoint = f"rhcs_cluster_rosa_classic.{clean_name}.api_url"
            elif cluster_type == 'rosa-hcp':
                cluster_endpoint = f"rhcs_cluster_rosa_hcp.{clean_name}.api_url"
            elif cluster_type == 'aro':
                cluster_endpoint = f"azurerm_redhat_openshift_cluster.aro_{clean_name}.api_server_profile[0].url"
            elif cluster_type == 'openshift-dedicated':
                cluster_endpoint = f"rhcs_cluster_rosa_classic.{clean_name}.api_url"  # OSD uses similar API
            elif cluster_type == 'self-managed':
                # For self-managed clusters, determine by infrastructure provider
                provider = cluster.get('provider')
                if provider == 'aws':
                    cluster_endpoint = f"module.{clean_name}_openshift.cluster_endpoint"
                elif provider == 'gcp':
                    cluster_endpoint = f"module.{clean_name}_openshift.cluster_endpoint"
                elif provider == 'azure':
                    cluster_endpoint = f"module.{clean_name}_openshift.cluster_endpoint"
                else:
                    cluster_endpoint = f"module.{clean_name}_openshift.cluster_endpoint"
            elif cluster_type == 'hypershift':
                cluster_endpoint = f"rhcs_cluster_rosa_hcp.{clean_name}.api_url"
                cluster_condition = 'var.deploy_hypershift_hosted ? 1 : 0'
            else:
                # Generic fallback
                cluster_endpoint = f"module.{clean_name}.cluster_endpoint"
            
            # Only generate providers if cluster will be deployed
            if cluster_condition != '1':
                provider_config += f'''
# ===== CONDITIONAL PROVIDERS for {cluster_name} (only created when cluster exists) =====
# These providers are only created when {cluster_condition.replace('?', 'is')} true

'''
            
            provider_config += f'''
# ===== FULL CLUSTER ADMIN PROVIDERS for {cluster_name} =====
provider "kubernetes" {{
  alias = "{clean_name}_cluster_admin"
  
  host  = try({cluster_endpoint}, "")
  token = try({cluster_endpoint}, "") != "" ? try(base64decode(kubernetes_secret.{clean_name}_cluster_admin_token[0].data["token"]), "") : ""
  cluster_ca_certificate = try({cluster_endpoint}, "") != "" ? try(base64decode(kubernetes_secret.{clean_name}_cluster_admin_token[0].data["ca.crt"]), "") : ""
  
  insecure = false
}}

provider "helm" {{
  alias = "{clean_name}_cluster_admin"
  
  kubernetes {{
    host  = try({cluster_endpoint}, "")
    token = try({cluster_endpoint}, "") != "" ? try(base64decode(kubernetes_secret.{clean_name}_cluster_admin_token[0].data["token"]), "") : ""
    cluster_ca_certificate = try({cluster_endpoint}, "") != "" ? try(base64decode(kubernetes_secret.{clean_name}_cluster_admin_token[0].data["ca.crt"]), "") : ""
  }}
}}

# ===== LIMITED CLUSTER ADMIN PROVIDERS for {cluster_name} =====
provider "kubernetes" {{
  alias = "{clean_name}_cluster_admin_limited"
  
  host  = try({cluster_endpoint}, "")
  token = try({cluster_endpoint}, "") != "" ? try(base64decode(kubernetes_secret.{clean_name}_cluster_admin_limited_token[0].data["token"]), "") : ""
  cluster_ca_certificate = try({cluster_endpoint}, "") != "" ? try(base64decode(kubernetes_secret.{clean_name}_cluster_admin_limited_token[0].data["ca.crt"]), "") : ""
  
  insecure = false
}}

provider "helm" {{
  alias = "{clean_name}_cluster_admin_limited"
  
  kubernetes {{
    host  = try({cluster_endpoint}, "")
    token = try({cluster_endpoint}, "") != "" ? try(base64decode(kubernetes_secret.{clean_name}_cluster_admin_limited_token[0].data["token"]), "") : ""
    cluster_ca_certificate = try({cluster_endpoint}, "") != "" ? try(base64decode(kubernetes_secret.{clean_name}_cluster_admin_limited_token[0].data["ca.crt"]), "") : ""
  }}
}}

# ===== APPLICATION DEPLOYER PROVIDERS for {cluster_name} =====
provider "kubernetes" {{
  alias = "{clean_name}_app_deployer"
  
  host  = try({cluster_endpoint}, "")
  token = try({cluster_endpoint}, "") != "" ? try(base64decode(kubernetes_secret.{clean_name}_app_deployer_token[0].data["token"]), "") : ""
  cluster_ca_certificate = try({cluster_endpoint}, "") != "" ? try(base64decode(kubernetes_secret.{clean_name}_app_deployer_token[0].data["ca.crt"]), "") : ""
  
  insecure = false
}}

provider "helm" {{
  alias = "{clean_name}_app_deployer"
  
  kubernetes {{
    host  = try({cluster_endpoint}, "")
    token = try({cluster_endpoint}, "") != "" ? try(base64decode(kubernetes_secret.{clean_name}_app_deployer_token[0].data["token"]), "") : ""
    cluster_ca_certificate = try({cluster_endpoint}, "") != "" ? try(base64decode(kubernetes_secret.{clean_name}_app_deployer_token[0].data["ca.crt"]), "") : ""
  }}
}}

'''
        
        return provider_config
    


    def generate_full_admin_service_account(self, cluster_config: Dict) -> str:
        """Generate full cluster-admin service account with unlimited privileges."""
        cluster_name = cluster_config.get('name')
        clean_name = self.clean_name(cluster_name)
        cluster_endpoint = self._get_cluster_endpoint_for_type(cluster_config)
        token_duration = self.get_token_duration()
        
        return f'''
# =============================================================================
# FULL CLUSTER ADMIN SERVICE ACCOUNT: {cluster_name}
# =============================================================================

        # Full Cluster Admin Service Account (unrestricted access)
resource "kubernetes_service_account" "{clean_name}_cluster_admin" {{
  count = var.deploy_day2_operations ? 1 : 0
  
  metadata {{
    name      = "cluster-admin"
    namespace = "default"
    annotations = {{
      "yamlforge.io/cluster" = "{cluster_name}"
      "yamlforge.io/cluster-type" = "{cluster_config.get('type')}"
      "yamlforge.io/purpose" = "full-cluster-administration"
      "yamlforge.io/scope" = "full-cluster-access"
      "yamlforge.io/security-level" = "high-privilege"
    }}
  }}
}}

        # ClusterRoleBinding for full cluster-admin permissions
resource "kubernetes_cluster_role_binding" "{clean_name}_cluster_admin_binding" {{
  count = var.deploy_day2_operations ? 1 : 0
  
  metadata {{
    name = "yamlforge-cluster-admin"
    annotations = {{
      "yamlforge.io/cluster" = "{cluster_name}"
      "yamlforge.io/cluster-type" = "{cluster_config.get('type')}"
      "yamlforge.io/purpose" = "full-cluster-administration"
    }}
  }}

  role_ref {{
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = "cluster-admin"
  }}

  subject {{
    kind      = "ServiceAccount"
    name      = kubernetes_service_account.{clean_name}_cluster_admin[0].metadata[0].name
    namespace = kubernetes_service_account.{clean_name}_cluster_admin[0].metadata[0].namespace
  }}
}}

        # Full Admin Service Account Token Secret (with expiration)
resource "kubernetes_secret" "{clean_name}_cluster_admin_token" {{
  count = var.deploy_day2_operations ? 1 : 0
  
  metadata {{
    name      = "cluster-admin-token"
    namespace = "default"
    annotations = {{
      "kubernetes.io/service-account.name" = kubernetes_service_account.{clean_name}_cluster_admin[0].metadata[0].name
      "kubernetes.io/service-account.token-expiration-time" = "{token_duration}"
      "yamlforge.io/cluster" = "{cluster_name}"
      "yamlforge.io/cluster-type" = "{cluster_config.get('type')}"
      "yamlforge.io/purpose" = "full-cluster-administration-token"
      "yamlforge.io/security-level" = "high-privilege"
      "yamlforge.io/token-duration" = "{token_duration}"
    }}
  }}

  type = "kubernetes.io/service-account-token"
}}

# Output the full admin service account token
output "{clean_name}_cluster_admin_token" {{
  description = "Full cluster admin token for {cluster_name} (UNRESTRICTED ACCESS) - Type: {cluster_config.get('type')}"
  value       = length(kubernetes_secret.{clean_name}_cluster_admin_token) > 0 ? kubernetes_secret.{clean_name}_cluster_admin_token[0].data["token"] : ""
  sensitive   = true
}}'''

    def generate_limited_admin_service_account(self, cluster_config: Dict) -> str:
        """Generate limited cluster admin service account with restricted privileges."""
        cluster_name = cluster_config.get('name')
        clean_name = self.clean_name(cluster_name)
        cluster_endpoint = self._get_cluster_endpoint_for_type(cluster_config)
        token_duration = self.get_token_duration()
        
        # Get service account configuration from defaults
        sa_config = self.openshift_defaults.get('security', {}).get('service_accounts', {}).get('cluster_admin_limited', {})
        permissions = sa_config.get('permissions', [])
        
        # Generate ClusterRole rules from permissions
        cluster_role_rules = ""
        for permission in permissions:
            api_groups = permission.get('api_groups', [''])
            resources = permission.get('resources', [])
            verbs = permission.get('verbs', [])
            
            # Convert Python lists to Terraform HCL syntax
            api_groups_hcl = '[' + ', '.join(f'"{item}"' for item in api_groups) + ']'
            resources_hcl = '[' + ', '.join(f'"{item}"' for item in resources) + ']'
            verbs_hcl = '[' + ', '.join(f'"{item}"' for item in verbs) + ']'
            
            cluster_role_rules += f'''
  rule {{
    api_groups = {api_groups_hcl}
    resources  = {resources_hcl}
    verbs      = {verbs_hcl}
  }}'''
        
        return f'''
# =============================================================================
# LIMITED CLUSTER ADMIN SERVICE ACCOUNT: {cluster_name}
# =============================================================================

        # Limited Cluster Admin Service Account (operators, Day2 operations)
resource "kubernetes_service_account" "{clean_name}_cluster_admin_limited" {{
  count = var.deploy_day2_operations ? 1 : 0
  
  metadata {{
    name      = "cluster-admin-limited"
    namespace = "default"
    annotations = {{
      "yamlforge.io/cluster" = "{cluster_name}"
      "yamlforge.io/cluster-type" = "{cluster_config.get('type')}"
      "yamlforge.io/purpose" = "limited-cluster-administration"
      "yamlforge.io/scope" = "{sa_config.get('scope', 'operators,day2-operations,cluster-config')}"
      "yamlforge.io/security-level" = "{sa_config.get('security_level', 'medium-privilege')}"
    }}
  }}
}}

        # Custom ClusterRole for limited admin permissions
resource "kubernetes_cluster_role" "{clean_name}_cluster_admin_limited_role" {{
  count = var.deploy_day2_operations ? 1 : 0
  
  metadata {{
    name = "yamlforge-cluster-admin-limited"
    annotations = {{
      "yamlforge.io/cluster" = "{cluster_name}"
      "yamlforge.io/cluster-type" = "{cluster_config.get('type')}"
      "yamlforge.io/description" = "{sa_config.get('description', 'Limited cluster admin for operators and Day2 operations')}"
    }}
  }}{cluster_role_rules}
}}

        # ClusterRoleBinding for limited admin permissions
resource "kubernetes_cluster_role_binding" "{clean_name}_cluster_admin_limited_binding" {{
  count = var.deploy_day2_operations ? 1 : 0
  
  metadata {{
    name = "yamlforge-cluster-admin-limited"
    annotations = {{
      "yamlforge.io/cluster" = "{cluster_name}"
      "yamlforge.io/cluster-type" = "{cluster_config.get('type')}"
      "yamlforge.io/purpose" = "limited-cluster-administration"
    }}
  }}

  role_ref {{
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role.{clean_name}_cluster_admin_limited_role[0].metadata[0].name
  }}

  subject {{
    kind      = "ServiceAccount"
    name      = kubernetes_service_account.{clean_name}_cluster_admin_limited[0].metadata[0].name
    namespace = kubernetes_service_account.{clean_name}_cluster_admin_limited[0].metadata[0].namespace
  }}
}}

        # Limited Admin Service Account Token Secret (with expiration)
resource "kubernetes_secret" "{clean_name}_cluster_admin_limited_token" {{
  count = var.deploy_day2_operations ? 1 : 0
  
  metadata {{
    name      = "cluster-admin-limited-token"
    namespace = "default"
    annotations = {{
      "kubernetes.io/service-account.name" = kubernetes_service_account.{clean_name}_cluster_admin_limited[0].metadata[0].name
      "kubernetes.io/service-account.token-expiration-time" = "{token_duration}"
      "yamlforge.io/cluster" = "{cluster_name}"
      "yamlforge.io/cluster-type" = "{cluster_config.get('type')}"
      "yamlforge.io/purpose" = "limited-cluster-administration-token"
      "yamlforge.io/security-level" = "{sa_config.get('security_level', 'medium-privilege')}"
      "yamlforge.io/token-duration" = "{token_duration}"
    }}
  }}

  type = "kubernetes.io/service-account-token"
}}

# Output the limited admin service account token
output "{clean_name}_cluster_admin_limited_token" {{
  description = "Limited cluster admin token for {cluster_name} (operators/Day2 ops) - Type: {cluster_config.get('type')}"
  value       = length(kubernetes_secret.{clean_name}_cluster_admin_limited_token) > 0 ? kubernetes_secret.{clean_name}_cluster_admin_limited_token[0].data["token"] : ""
  sensitive   = true
}}'''

    def generate_app_deployer_service_account(self, cluster_config: Dict) -> str:
        """Generate application deployer service account with limited privileges for app deployment."""
        cluster_name = cluster_config.get('name')
        clean_name = self.clean_name(cluster_name)
        token_duration = self.get_token_duration()
        
        # Load permissions from defaults
        sa_config = self.openshift_defaults.get('security', {}).get('service_accounts', {}).get('app_deployer', {})
        permissions = sa_config.get('permissions', [])
        
        # Generate ClusterRole rules from permissions
        cluster_role_rules = ""
        for permission in permissions:
            api_groups = permission.get('api_groups', [''])
            resources = permission.get('resources', [])
            verbs = permission.get('verbs', [])
            
            # Convert Python lists to Terraform HCL syntax
            api_groups_hcl = '[' + ', '.join(f'"{item}"' for item in api_groups) + ']'
            resources_hcl = '[' + ', '.join(f'"{item}"' for item in resources) + ']'
            verbs_hcl = '[' + ', '.join(f'"{item}"' for item in verbs) + ']'
            
            cluster_role_rules += f'''
  rule {{
    api_groups = {api_groups_hcl}
    resources  = {resources_hcl}
    verbs      = {verbs_hcl}
  }}'''
        
        return f'''
# =============================================================================
# APPLICATION DEPLOYER SERVICE ACCOUNT: {cluster_name}
# =============================================================================

        # Application Deployer Service Account (limited application permissions)
resource "kubernetes_service_account" "{clean_name}_app_deployer" {{
  count = var.deploy_day2_operations ? 1 : 0
  
  metadata {{
    name      = "app-deployer"
    namespace = "default"
    annotations = {{
      "yamlforge.io/cluster" = "{cluster_name}"
      "yamlforge.io/cluster-type" = "{cluster_config.get('type')}"
      "yamlforge.io/purpose" = "application-deployment"
      "yamlforge.io/scope" = "{sa_config.get('scope', 'applications,namespaces,services,deployments')}"
      "yamlforge.io/security-level" = "{sa_config.get('security_level', 'low-privilege')}"
    }}
  }}
}}

        # Custom ClusterRole for application deployment permissions
resource "kubernetes_cluster_role" "{clean_name}_app_deployer_role" {{
  count = var.deploy_day2_operations ? 1 : 0
  
  metadata {{
    name = "yamlforge-app-deployer"
    annotations = {{
      "yamlforge.io/cluster" = "{cluster_name}"
      "yamlforge.io/cluster-type" = "{cluster_config.get('type')}"
      "yamlforge.io/description" = "{sa_config.get('description', 'Application deployment with limited permissions')}"
    }}
  }}{cluster_role_rules}
}}

        # ClusterRoleBinding for app deployer
resource "kubernetes_cluster_role_binding" "{clean_name}_app_deployer_binding" {{
  count = var.deploy_day2_operations ? 1 : 0
  
  metadata {{
    name = "yamlforge-app-deployer"
    annotations = {{
      "yamlforge.io/cluster" = "{cluster_name}"
      "yamlforge.io/cluster-type" = "{cluster_config.get('type')}"
    }}
  }}

  role_ref {{
    api_group = "rbac.authorization.k8s.io"
    kind      = "ClusterRole"
    name      = kubernetes_cluster_role.{clean_name}_app_deployer_role[0].metadata[0].name
  }}

  subject {{
    kind      = "ServiceAccount"
    name      = kubernetes_service_account.{clean_name}_app_deployer[0].metadata[0].name
    namespace = kubernetes_service_account.{clean_name}_app_deployer[0].metadata[0].namespace
  }}
}}

        # App Deployer Service Account Token Secret (with expiration)
resource "kubernetes_secret" "{clean_name}_app_deployer_token" {{
  count = var.deploy_day2_operations ? 1 : 0
  
  metadata {{
    name      = "app-deployer-token"
    namespace = "default"
    annotations = {{
      "kubernetes.io/service-account.name" = kubernetes_service_account.{clean_name}_app_deployer[0].metadata[0].name
      "kubernetes.io/service-account.token-expiration-time" = "{token_duration}"
      "yamlforge.io/cluster" = "{cluster_name}"
      "yamlforge.io/cluster-type" = "{cluster_config.get('type')}"
      "yamlforge.io/purpose" = "application-deployment-token"
      "yamlforge.io/security-level" = "{sa_config.get('security_level', 'low-privilege')}"
      "yamlforge.io/token-duration" = "{token_duration}"
    }}
  }}

  type = "kubernetes.io/service-account-token"
}}

# Output the app deployer service account token
output "{clean_name}_app_deployer_token" {{
  description = "Application deployer token for {cluster_name} (limited app permissions) - Type: {cluster_config.get('type')}"
  value       = length(kubernetes_secret.{clean_name}_app_deployer_token) > 0 ? kubernetes_secret.{clean_name}_app_deployer_token[0].data["token"] : ""
  sensitive   = true
}}'''
    

    
    def _get_cluster_endpoint_for_type(self, cluster_config: Dict) -> str:
        """Get the appropriate cluster endpoint reference based on cluster type."""
        cluster_name = cluster_config.get('name')
        cluster_type = cluster_config.get('type')
        if not cluster_type:
            cluster_name = cluster_config.get('name') or 'unknown'
            raise ValueError(f"Cluster type must be specified for cluster '{cluster_name}'. Supported types: rosa-classic, rosa-hcp, aro, openshift-dedicated, self-managed, hypershift")
        clean_name = self.clean_name(cluster_name)
        
        # Determine cluster endpoint based on type
        if cluster_type == 'rosa-classic':
            return f"rhcs_cluster_rosa_classic.{clean_name}.api_url"
        elif cluster_type == 'rosa-hcp':
            return f"rhcs_cluster_rosa_hcp.{clean_name}.api_url"
        elif cluster_type == 'aro':
            return f"azurerm_redhat_openshift_cluster.aro_{clean_name}.api_server_profile[0].url"
        elif cluster_type == 'openshift-dedicated':
            return f"rhcs_cluster_rosa_classic.{clean_name}.api_url"  # OSD uses similar API
        elif cluster_type == 'self-managed':
            # For self-managed clusters, determine by infrastructure provider
            provider = cluster_config.get('provider')
            if not provider:
                cluster_name = cluster_config.get('name') or 'unknown'
                raise ValueError(f"Self-managed cluster '{cluster_name}' must specify 'provider'")
            if provider == 'aws':
                return f"module.{clean_name}_openshift.cluster_endpoint"
            elif provider == 'gcp':
                return f"module.{clean_name}_openshift.cluster_endpoint"
            elif provider == 'azure':
                return f"module.{clean_name}_openshift.cluster_endpoint"
            else:
                return f"module.{clean_name}_openshift.cluster_endpoint" 

"""
OpenShift Dedicated Provider for yamlforge
Supports Red Hat managed OpenShift Dedicated clusters on multiple clouds
"""

from typing import Dict
from .base import BaseOpenShiftProvider


class OpenShiftDedicatedProvider(BaseOpenShiftProvider):
    """OpenShift Dedicated Provider (Multi-Cloud)"""
    
    def generate_dedicated_cluster(self, cluster_config: Dict) -> str:
        """Generate OpenShift Dedicated cluster"""
        
        cluster_name = cluster_config.get('name')
        if not cluster_name:
            raise ValueError("OpenShift Dedicated cluster 'name' must be specified")
        
        clean_name = self.clean_name(cluster_name)
        
        cloud_provider = cluster_config.get('provider')
        if not cloud_provider:
            raise ValueError(f"OpenShift Dedicated cluster '{cluster_name}' must specify 'provider'")
            
        region = cluster_config.get('region')
        if not region:
            raise ValueError(f"OpenShift Dedicated cluster '{cluster_name}' must specify 'region'")
            
        version = cluster_config.get('version')
        if not version:
            raise ValueError(f"OpenShift Dedicated cluster '{cluster_name}' must specify 'version'")
        version = self.validate_openshift_version(version, cluster_type="openshift-dedicated")
        
        size = cluster_config.get('size')
        if not size:
            raise ValueError(f"OpenShift Dedicated cluster '{cluster_name}' must specify 'size'")
        size_config = self.get_cluster_size_config(size, 'openshift-dedicated')
        
        # OpenShift Dedicated configuration
        dedicated_config = cluster_config.get('dedicated') or {}
        support_level = dedicated_config.get('support_level', 'standard')
        maintenance_window = dedicated_config.get('maintenance_window', 'sunday-2am')
        
        terraform_config = f'''
# =============================================================================
# OPENSHIFT DEDICATED: {cluster_name}
# =============================================================================

# OpenShift Dedicated Cluster (Red Hat Managed)
resource "rhcs_cluster_dedicated" "{clean_name}" {{
  name               = "{cluster_name}"
  cloud_provider     = "{cloud_provider}"
  region             = "{region}"
  openshift_version  = "{version}"
  
  # Cluster sizing
  compute_machine_type = "{self.get_dedicated_machine_type(cloud_provider, size_config['worker_size'])}"
  replicas            = {cluster_config.get('worker_count') or size_config['worker_count']}
  
  # Dedicated-specific configuration
  support_level      = "{support_level}"
  maintenance_window = "{maintenance_window}"
  
  # High availability
  multi_az = {str(cluster_config.get('multi_az') or True).lower()}
  
  # Compliance options
'''

        # Add compliance settings if specified
        compliance = dedicated_config.get('compliance', [])
        if compliance:
            compliance_str = '", "'.join(compliance)
            terraform_config += f'''
  compliance = ["{compliance_str}"]
'''

        # Get merged networking configuration (defaults + user overrides)
        networking = self.get_merged_networking_config(cluster_config, 'openshift-dedicated')
        
        terraform_config += f'''
  
  # Networking
  machine_cidr = "{networking.get('machine_cidr')}"
  service_cidr = "{networking.get('service_cidr')}"
  pod_cidr     = "{networking.get('pod_cidr')}"
  
  # Cloud provider specific settings
'''

        # Add cloud provider specific configuration
        if cloud_provider == 'aws':
            terraform_config += f'''
  aws_account_id = var.aws_account_id
  aws_region     = "{region}"
'''
        elif cloud_provider == 'azure':
            terraform_config += f'''
  azure_subscription_id = var.azure_subscription_id
  azure_tenant_id       = var.azure_tenant_id
  azure_region          = "{region}"
'''
        elif cloud_provider == 'gcp':
            terraform_config += f'''
  gcp_project_id = var.gcp_project_id
  gcp_region     = "{region}"
'''

        terraform_config += f'''
  
  # Properties
  properties = {{
    managed_by_redhat = true
    dedicated_support = "{support_level}"
  }}
  
  # Tags
  tags = {{
    Environment = var.environment
    ManagedBy   = "yamlforge"
    Cloud       = "{cloud_provider}"
    Platform    = "openshift-dedicated"
    Support     = "{support_level}"
  }}
}}

'''

        return terraform_config
    
    def get_dedicated_machine_type(self, cloud_provider: str, size: str) -> str:
        """Get machine type for OpenShift Dedicated based on cloud provider"""
        
        # Get machine types from existing flavor mappings
        flavors = self.converter.flavors.get(cloud_provider, {})
        machine_type = flavors.get('flavor_mappings', {}).get(size)
        
        if machine_type:
            return machine_type
        
        # Use OpenShift-optimized flavor lookup
        return self.get_openshift_machine_type(cloud_provider, size, 'controlplane') 

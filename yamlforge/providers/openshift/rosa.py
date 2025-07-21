"""
ROSA (Red Hat OpenShift Service on AWS) Provider for yamlforge
Supports both ROSA Classic and ROSA with Hosted Control Planes (HCP)
"""

from typing import Dict
from .base import BaseOpenShiftProvider


class ROSAProvider(BaseOpenShiftProvider):
    """Red Hat OpenShift Service on AWS (ROSA) Provider"""
    
    def generate_rosa_classic_cluster(self, cluster_config: Dict) -> str:
        """Generate ROSA Classic cluster Terraform configuration"""
        
        cluster_name = cluster_config.get('name', 'rosa-cluster')
        clean_name = self.clean_name(cluster_name)
        region = cluster_config.get('region', 'us-east-1')
        version = self.validate_openshift_version(cluster_config.get('version', ''))
        size_config = self.get_cluster_size_config(
            cluster_config.get('size', 'medium'), 'rosa-classic'
        )
        
        # Get machine pool configuration
        worker_count = cluster_config.get('worker_count', size_config['worker_count'])
        min_replicas = cluster_config.get('min_replicas', worker_count)
        max_replicas = cluster_config.get('max_replicas', worker_count * 2)
        
        # Get machine types using OpenShift-optimized flavor mappings
        machine_type = self.get_openshift_machine_type('aws', size_config['worker_size'], 'worker')
        
        terraform_config = f'''
# =============================================================================
# ROSA CLASSIC CLUSTER: {cluster_name}
# =============================================================================

# ROSA Classic Cluster
resource "rhcs_cluster_rosa_classic" "{clean_name}" {{
  name               = "{cluster_name}"
  cloud_region       = "{region}"
  aws_account_id     = var.aws_account_id
  availability_zones = data.aws_availability_zones.{clean_name}.names
  
  # Cluster Configuration
  openshift_version = "{version}"
  multi_az          = true
  
  # Machine Pool Configuration
  compute_machine_type = "{machine_type}"
  replicas            = {worker_count}
  
  # Networking
'''

        # Get merged networking configuration (defaults + user overrides)
        networking = self.get_merged_networking_config(cluster_config, 'rosa-classic')
        
        terraform_config += f'''
  machine_cidr = "{networking.get('machine_cidr')}"
  service_cidr = "{networking.get('service_cidr')}"
  pod_cidr     = "{networking.get('pod_cidr')}"
  host_prefix  = {networking.get('host_prefix')}
  
  # Access Configuration
  private = {str(cluster_config.get('private', False)).lower()}
  
  # Properties
  properties = {{
    rosa_creator_arn = var.aws_rosa_creator_arn
  }}
  
  # Tags
  tags = {{
    Environment = var.environment
    ManagedBy   = "yamlforge"
    Cloud       = "aws"
    Platform    = "rosa-classic"
  }}
}}

# Get availability zones for the region
data "aws_availability_zones" "{clean_name}" {{
  state = "available"
}}

'''

        # Add auto-scaling machine pool if different from base
        if min_replicas != max_replicas:
            terraform_config += f'''
# Auto-scaling machine pool for {cluster_name}
resource "rhcs_machine_pool" "{clean_name}_workers" {{
  cluster      = rhcs_cluster_rosa_classic.{clean_name}.id
  name         = "workers"
  machine_type = "{machine_type}"
  replicas     = {worker_count}
  
  autoscaling = {{
    enabled      = true
    min_replicas = {min_replicas}
    max_replicas = {max_replicas}
  }}
  
  labels = {{
    "node-role" = "worker"
    "environment" = var.environment
  }}
}}

'''

        # Add cluster addons if specified
        addons = cluster_config.get('addons', [])
        for addon in addons:
            terraform_config += f'''
# ROSA Classic Addon: {addon}
resource "rhcs_cluster_rosa_classic_addon" "{clean_name}_{addon.replace('-', '_')}" {{
  cluster = rhcs_cluster_rosa_classic.{clean_name}.id
  name    = "{addon}"
}}

'''

        return terraform_config

    def generate_rosa_hcp_cluster(self, cluster_config: Dict) -> str:
        """Generate ROSA with Hosted Control Planes (HCP) cluster Terraform configuration"""
        
        cluster_name = cluster_config.get('name', 'rosa-hcp-cluster')
        clean_name = self.clean_name(cluster_name)
        region = cluster_config.get('region', 'us-east-1')
        version = self.validate_openshift_version(cluster_config.get('version', ''))
        size_config = self.get_cluster_size_config(
            cluster_config.get('size', 'medium'), 'rosa-hcp'
        )
        
        # Get machine pool configuration
        worker_count = cluster_config.get('worker_count', size_config['worker_count'])
        min_replicas = cluster_config.get('min_replicas', worker_count)
        max_replicas = cluster_config.get('max_replicas', worker_count * 2)
        
        # Get machine types using OpenShift-optimized flavor mappings
        machine_type = self.get_openshift_machine_type('aws', size_config['worker_size'], 'worker')
        
        terraform_config = f'''
# =============================================================================
# ROSA HCP CLUSTER: {cluster_name}
# =============================================================================

# ROSA HCP Cluster (Hosted Control Planes)
resource "rhcs_cluster_rosa_hcp" "{clean_name}" {{
  name               = "{cluster_name}"
  cloud_region       = "{region}"
  openshift_version  = "{version}"
  
  # AWS Settings
  aws_account_id     = var.aws_account_id
  aws_billing_account_id = var.aws_billing_account_id
  
  # Availability zones
  availability_zones = ["{region}a", "{region}b", "{region}c"]
  
  # Compute configuration (workers only - control plane is hosted)
  compute_machine_type = "{machine_type}"
  replicas            = {worker_count}
  
  # Networking
'''

        # Get merged networking configuration (defaults + user overrides)  
        networking = self.get_merged_networking_config(cluster_config, 'rosa-hcp')
        
        terraform_config += f'''
  machine_cidr = "{networking.get('machine_cidr')}"
  
  # HCP-specific settings
  etcd_encryption = {str(cluster_config.get('etcd_encryption', True)).lower()}
  
  # Access Configuration
  private = {str(cluster_config.get('private', False)).lower()}
  
  # Properties
  properties = {{
    rosa_creator_arn = var.aws_rosa_creator_arn
  }}
  
  # Lifecycle management
  disable_waiting_in_destroy = false
  destroy_timeout = 60
  
  # Tags
  tags = {{
'''

        # Add tags
        tags = cluster_config.get('tags', {})
        default_tags = {
            'Environment': cluster_config.get('environment', 'development'),
            'Project': cluster_config.get('project', cluster_name),
            'OpenShift-Type': 'rosa-hcp',
            'yamlforge-managed': 'true'
        }
        all_tags = {**default_tags, **tags}
        
        for key, value in all_tags.items():
            terraform_config += f'    "{key}" = "{value}"\n'

        terraform_config += '''  }
}

'''

        # Add machine pool for auto-scaling (if enabled)
        if cluster_config.get('auto_scaling', {}).get('enabled', False):
            min_replicas = cluster_config.get('auto_scaling', {}).get('min_replicas', min_replicas)
            max_replicas = cluster_config.get('auto_scaling', {}).get('max_replicas', max_replicas)
            
            terraform_config += f'''
# ROSA HCP Machine Pool with Auto-scaling
resource "rhcs_machine_pool" "{clean_name}_workers" {{
  cluster      = rhcs_cluster_rosa_hcp.{clean_name}.id
  name         = "workers"
  machine_type = "{machine_type}"
  
  # Auto-scaling configuration
  autoscaling = {{
    enabled      = true
    min_replicas = {min_replicas}
    max_replicas = {max_replicas}
  }}
  
  # Availability zones
  availability_zones = ["{region}a", "{region}b", "{region}c"]
  
  # Node labels
  labels = {{
    "node-role.kubernetes.io/worker" = ""
    "cluster" = "{cluster_name}"
  }}
  
  # Taints (if specified)
'''

            # Add taints if specified
            taints = cluster_config.get('machine_pools', [{}])[0].get('taints', [])
            if taints:
                terraform_config += '  taints = [\n'
                for taint in taints:
                    terraform_config += f'''    {{
      key    = "{taint.get('key', '')}"
      value  = "{taint.get('value', '')}"
      effect = "{taint.get('effect', 'NoSchedule')}"
    }},
'''
                terraform_config += '  ]\n'
            
            terraform_config += '}\n\n'

        # Add OIDC configuration (required for HCP)
        terraform_config += f'''
# OIDC Configuration (required for ROSA HCP)
resource "rhcs_rosa_oidc_config" "{clean_name}_oidc" {{
  managed            = true
  secret_arn        = var.aws_rosa_oidc_secret_arn
  issuer_url        = rhcs_cluster_rosa_hcp.{clean_name}.sts.oidc_endpoint_url
  thumbprint_list   = rhcs_cluster_rosa_hcp.{clean_name}.sts.thumbprint_list
  
  tags = {{
    "Name" = "{cluster_name}-oidc"
    "Cluster" = "{cluster_name}"
  }}
}}

'''

        # Add operator roles (required for HCP)
        terraform_config += f'''
# Operator Roles (required for ROSA HCP)
resource "rhcs_rosa_operator_roles" "{clean_name}_operator_roles" {{
  cluster_id    = rhcs_cluster_rosa_hcp.{clean_name}.id
  operator_role_prefix = "{clean_name}"
  
  depends_on = [rhcs_rosa_oidc_config.{clean_name}_oidc]
}}

'''

        # Add addons (if specified)
        addons = cluster_config.get('addons', [])
        if addons:
            terraform_config += f'''
# ROSA HCP Cluster Addons
'''
            for addon in addons:
                terraform_config += f'''
resource "rhcs_hcp_cluster_addon" "{clean_name}_{addon.replace('-', '_')}" {{
  cluster = rhcs_cluster_rosa_hcp.{clean_name}.id
  name    = "{addon}"
}}

'''

        return terraform_config 
"""
ROSA (Red Hat OpenShift Service on AWS) Provider for yamlforge
Supports both ROSA Classic and ROSA with Hosted Control Planes (HCP)
Supports both ROSA CLI and RHCS Terraform provider deployment methods
"""

from typing import Dict
from .base import BaseOpenShiftProvider


class ROSAProvider(BaseOpenShiftProvider):
    """Red Hat OpenShift Service on AWS (ROSA) Provider"""
    
    def generate_rosa_classic_cluster(self, cluster_config: Dict) -> str:
        """Generate ROSA Classic cluster Terraform configuration"""
        
        cluster_name = cluster_config.get('name')
        if not cluster_name:
            raise ValueError("ROSA cluster 'name' must be specified")
        
        clean_name = self.clean_name(cluster_name)
        
        region = cluster_config.get('region')
        if not region:
            raise ValueError(f"ROSA cluster '{cluster_name}' must specify 'region'")
            
        version = cluster_config.get('version')
        # Get auto_discover_version from global defaults
        auto_discover_version = self.openshift_defaults.get('openshift', {}).get('auto_discover_version', False)
        version = self.validate_openshift_version(version, cluster_type="rosa-classic", auto_discover_version=auto_discover_version)
        
        size = cluster_config.get('size')
        if not size:
            raise ValueError(f"ROSA cluster '{cluster_name}' must specify 'size'")
        size_config = self.get_cluster_size_config(size, 'rosa-classic')
        
        # Get machine pool configuration
        worker_count = cluster_config.get('worker_count')
        if worker_count is None:
            worker_count = size_config['worker_count']  # Use size config as fallback
        
        # Enforce ROSA Classic multi-AZ requirement: minimum 3 worker nodes
        multi_az = cluster_config.get('multi_az', True)  # Default to multi-AZ
        if multi_az and worker_count < 3:
            print(f"Warning: ROSA Classic multi-AZ clusters require at least 3 worker nodes. Adjusting from {worker_count} to 3. Update your input YAML!")
            worker_count = 3
        
        min_replicas = cluster_config.get('min_replicas')
        if min_replicas is None:
            min_replicas = worker_count
            
        max_replicas = cluster_config.get('max_replicas')
        if max_replicas is None:
            max_replicas = worker_count * 2
        
        # Get machine types using OpenShift-optimized flavor mappings
        machine_type = self.get_openshift_machine_type('aws', size_config['worker_size'], 'worker')
        
        # Get GUID for consistent resource naming
        guid = self.converter.get_validated_guid()
        
        # Check deployment method from defaults
        rosa_deployment = self.openshift_defaults.get('openshift', {}).get('rosa_deployment', {})
        deployment_method = rosa_deployment.get('method', 'terraform')  # Default to terraform
        
        if deployment_method == 'terraform':
            return self._generate_rosa_classic_terraform(cluster_config, clean_name, region, version, 
                                                        machine_type, worker_count, multi_az, guid)
        else:  # CLI method
            return self._generate_rosa_classic_cli(cluster_config, clean_name, region, version, 
                                                  machine_type, worker_count, multi_az, guid)

    def generate_rosa_hcp_cluster(self, cluster_config: Dict, yaml_data: Dict) -> str:
        """Generate ROSA with Hosted Control Planes (HCP) cluster Terraform configuration"""
        
        cluster_name = cluster_config.get('name')
        if not cluster_name:
            raise ValueError("ROSA HCP cluster 'name' must be specified")
        
        clean_name = self.clean_name(cluster_name)
        
        region = cluster_config.get('region')
        if not region:
            raise ValueError(f"ROSA HCP cluster '{cluster_name}' must specify 'region'")
            
        version = cluster_config.get('version')
        # Get auto_discover_version from global defaults
        auto_discover_version = self.openshift_defaults.get('openshift', {}).get('auto_discover_version', False)
        version = self.validate_openshift_version(version, cluster_type="rosa-hcp", auto_discover_version=auto_discover_version)
        
        size = cluster_config.get('size')
        if not size:
            raise ValueError(f"ROSA HCP cluster '{cluster_name}' must specify 'size'")
        size_config = self.get_cluster_size_config(size, 'rosa-hcp')
        
        # Get machine pool configuration
        worker_count = cluster_config.get('worker_count')
        if worker_count is None:
            worker_count = size_config['worker_count']  # Use size config as fallback
        
        # Enforce ROSA HCP requirement: worker count must be multiple of availability zones
        # AWS regions typically have 3 AZs, so adjust worker count accordingly
        az_count = 3  # Standard for us-east-1, us-west-2, etc.
        if worker_count % az_count != 0:
            adjusted_count = ((worker_count // az_count) + 1) * az_count
            print(f"Warning: ROSA HCP clusters require worker count to be multiple of availability zones ({az_count}). Adjusting from {worker_count} to {adjusted_count}. Update your input YAML!")
            worker_count = adjusted_count
        
        min_replicas = cluster_config.get('min_replicas')
        if min_replicas is None:
            min_replicas = worker_count
            
        max_replicas = cluster_config.get('max_replicas')
        if max_replicas is None:
            max_replicas = worker_count * 2
        
        # Get machine types using OpenShift-optimized flavor mappings
        machine_type = self.get_openshift_machine_type('aws', size_config['worker_size'], 'worker')
        
        # Get GUID for consistent resource naming
        guid = self.converter.get_validated_guid(yaml_data)
        
        terraform_config = f'''
# =============================================================================
# ROSA HCP CLUSTER: {cluster_name}
# =============================================================================

# ROSA HCP cluster will be created using ROSA CLI commands
# See the generated rosa-setup.sh script for cluster creation

# Local values for ROSA HCP cluster reference
locals {{
  rosa_hcp_cluster_name_{clean_name} = "{cluster_name}"
  rosa_hcp_region_{clean_name} = "{region}"
  rosa_hcp_version_{clean_name} = "{version}"
  rosa_hcp_machine_type_{clean_name} = "{machine_type}"
  rosa_hcp_replicas_{clean_name} = {worker_count}
  rosa_hcp_subnet_ids_{clean_name} = local.public_subnet_ids_{region.replace('-', '_')}_{guid}
}}

# Placeholder outputs for ROSA HCP cluster (will be populated after CLI creation)
output "rosa_hcp_cluster_id_{clean_name}" {{
  description = "ROSA HCP cluster ID for {cluster_name}"
  value = "Run rosa describe cluster {cluster_name} to get cluster details"
}}

output "rosa_hcp_api_url_{clean_name}" {{
  description = "ROSA HCP API URL for {cluster_name}"
  value = "Run rosa describe cluster {cluster_name} --output json | jq -r '.api.url'"
}}

output "rosa_hcp_console_url_{clean_name}" {{
  description = "ROSA HCP console URL for {cluster_name}"
  value = "Run rosa describe cluster {cluster_name} --output json | jq -r '.console.url'"
}}

'''

        # Check deployment method from defaults
        rosa_deployment = self.openshift_defaults.get('openshift', {}).get('rosa_deployment', {})
        deployment_method = rosa_deployment.get('method', 'terraform')  # Default to terraform
        
        if deployment_method == 'terraform':
            return self._generate_rosa_hcp_terraform(cluster_config, clean_name, region, version, 
                                                    machine_type, worker_count, guid, yaml_data)
        else:  # CLI method
            return self._generate_rosa_hcp_cli(cluster_config, clean_name, region, version, 
                                              machine_type, worker_count, guid, yaml_data)
    
    def _generate_rosa_classic_terraform(self, cluster_config: Dict, clean_name: str, region: str, 
                                        version: str, machine_type: str, worker_count: int, 
                                        multi_az: bool, guid: str) -> str:
        """Generate ROSA Classic cluster using RHCS Terraform provider with automated STS roles"""
        cluster_name = cluster_config.get('name')
        
        # Get networking configuration
        networking = self.get_merged_networking_config(cluster_config, 'rosa-classic')
        
        # Get private cluster setting
        private_cluster = cluster_config.get('private', False)
        

        
        # Always use deployment separation for ROSA Classic clusters to enable phased deployment
        needs_rosa_separation = cluster_config.get('_needs_rosa_separation', False)
        needs_hypershift_separation = cluster_config.get('_needs_hypershift_separation', False)
        deployment_group = cluster_config.get('_deployment_group', 'rosa_classic')
        
        # ROSA clusters are always deployed when defined in the YAML
        
        # Generate cluster-specific operator roles only (shared resources handled elsewhere)
        aws_provider = self.converter.get_aws_provider()
        operator_roles_config = aws_provider.generate_rosa_operator_roles(cluster_name, region, guid)
        
        terraform_config = f'''
# =============================================================================
# ROSA CLASSIC CLUSTER: {cluster_name} (Fully Automated with STS)
# =============================================================================

{operator_roles_config}

# Local variables for operator role configuration (cluster-specific)
locals {{
  operator_role_prefix_{clean_name} = "{cluster_name}"
}}

# ROSA Classic cluster using RHCS Terraform provider with automated STS
resource "rhcs_cluster_rosa_classic" "{clean_name}" {{
  
  name               = "{cluster_name}"
  cloud_region       = "{region}"
  version            = "{version}"
  
  # Required availability zones - use filtered local variable from YamlForge
  availability_zones = local.selected_azs_{region.replace('-', '_')}_{guid}
  
  # Machine configuration
  aws_account_id           = data.aws_caller_identity.current.account_id
  compute_machine_type     = "{machine_type}"
  replicas                 = {worker_count}
  
  # Networking
  machine_cidr = "{networking.get('machine_cidr', '10.0.0.0/16')}"
  service_cidr = "{networking.get('service_cidr', '172.30.0.0/16')}" 
  pod_cidr     = "{networking.get('pod_cidr', '10.128.0.0/14')}"
  host_prefix  = {networking.get('host_prefix', 23)}
  
  # High availability and private cluster
  multi_az = {str(multi_az).lower()}
  private  = {str(private_cluster).lower()}
'''

        # Add networking infrastructure dependencies if not using existing VPC
        if not cluster_config.get('use_existing_vpc', False):
            terraform_config += f'''
  # Network dependencies - use all subnet IDs (YamlForge generates public + private subnets for ROSA Classic Multi-AZ)
  aws_subnet_ids = local.all_subnet_ids_{region.replace('-', '_')}_{guid}
'''

        terraform_config += f'''
  
  # STS configuration with automatically created roles
  sts = {{
    operator_role_prefix = "{cluster_name}"
    role_arn            = data.aws_iam_role.rosa_classic_installer_role.arn
    support_role_arn    = data.aws_iam_role.rosa_classic_support_role.arn
    instance_iam_roles = {{
      master_role_arn = data.aws_iam_role.rosa_classic_master_role.arn
      worker_role_arn = data.aws_iam_role.rosa_classic_worker_role.arn
    }}
  }}
  
  # Properties
  properties = {{
    rosa_creator_arn = data.aws_caller_identity.current.arn
  }}
  
  # Tags
  tags = {{
    Environment = var.environment
    ManagedBy   = "yamlforge"
    Platform    = "rosa-classic"
    GUID        = "{guid}"
    Region      = "{region}"
  }}
  
  # Wait for all prerequisites to be ready
  depends_on = [
    aws_vpc.main_vpc_{region.replace('-', '_')}_{guid},
    aws_subnet.public_subnet_{region.replace('-', '_')}_{guid},
    aws_internet_gateway.main_igw_{region.replace('-', '_')}_{guid},
    data.aws_iam_role.rosa_classic_installer_role,
    data.aws_iam_role.rosa_classic_support_role,
    data.aws_iam_role.rosa_classic_worker_role,
    data.aws_iam_role.rosa_classic_master_role,
    rhcs_rosa_oidc_config.oidc_config
  ]
}}

# Outputs for ROSA Classic cluster
output "rosa_classic_cluster_id_{clean_name}" {{
  description = "ROSA Classic cluster ID for {cluster_name}"
  value = rhcs_cluster_rosa_classic.{clean_name}.id
}}

output "rosa_classic_api_url_{clean_name}" {{
  description = "ROSA Classic API URL for {cluster_name}"
  value = rhcs_cluster_rosa_classic.{clean_name}.api_url
}}

output "rosa_classic_console_url_{clean_name}" {{
  description = "ROSA Classic console URL for {cluster_name}"
  value = rhcs_cluster_rosa_classic.{clean_name}.console_url
}}

output "rosa_classic_oidc_endpoint_{clean_name}" {{
  description = "ROSA Classic OIDC endpoint for {cluster_name}"
  value = length(rhcs_cluster_rosa_classic.{clean_name}) > 0 ? rhcs_rosa_oidc_config.oidc_config.oidc_endpoint_url : ""
}}

'''
        return terraform_config

    def _generate_rosa_classic_cli(self, cluster_config: Dict, clean_name: str, region: str, 
                                  version: str, machine_type: str, worker_count: int, 
                                  multi_az: bool, guid: str) -> str:
        """Generate ROSA Classic cluster using ROSA CLI (direct method)"""
        cluster_name = cluster_config.get('name')
        
        terraform_config = f'''
# =============================================================================
# ROSA CLASSIC CLUSTER: {cluster_name} (ROSA CLI Method)
# =============================================================================

# ROSA Classic cluster will be created using ROSA CLI commands
# See the generated rosa-setup.sh script for cluster creation

# Local values for ROSA Classic cluster reference
locals {{
  rosa_classic_cluster_name_{clean_name} = "{cluster_name}"
  rosa_classic_region_{clean_name} = "{region}"
  rosa_classic_version_{clean_name} = "{version}"
  rosa_classic_machine_type_{clean_name} = "{machine_type}"
  rosa_classic_replicas_{clean_name} = {worker_count}
}}

# Placeholder outputs for ROSA Classic cluster (will be populated after CLI creation)
output "rosa_classic_cluster_id_{clean_name}" {{
  description = "ROSA Classic cluster ID for {cluster_name}"
  value = "Run rosa describe cluster {cluster_name} to get cluster details"
}}

output "rosa_classic_api_url_{clean_name}" {{
  description = "ROSA Classic API URL for {cluster_name}"
  value = "Run rosa describe cluster {cluster_name} --output json | jq -r '.api.url'"
}}

output "rosa_classic_console_url_{clean_name}" {{
  description = "ROSA Classic console URL for {cluster_name}"
  value = "Run rosa describe cluster {cluster_name} --output json | jq -r '.console.url'"
}}

'''
        return terraform_config

    def _generate_rosa_hcp_terraform(self, cluster_config: Dict, clean_name: str, region: str, 
                                    version: str, machine_type: str, worker_count: int, 
                                    guid: str, yaml_data: Dict) -> str:
        """Generate ROSA HCP cluster using RHCS Terraform provider with automated STS roles"""
        cluster_name = cluster_config.get('name')
        
        # Get networking configuration
        networking = self.get_merged_networking_config(cluster_config, 'rosa-hcp')
        
        # Get private cluster setting
        private_cluster = cluster_config.get('private', False)
        


        
        # Always use deployment separation for ROSA HCP clusters to enable phased deployment
        needs_rosa_separation = cluster_config.get('_needs_rosa_separation', False)
        deployment_group = cluster_config.get('_deployment_group', 'rosa_hcp')
        
        # ROSA clusters are always deployed when defined in the YAML
        
        # Generate cluster-specific operator roles only (shared resources handled elsewhere)
        aws_provider = self.converter.get_aws_provider()
        operator_roles_config = aws_provider.generate_rosa_operator_roles(cluster_name, region, guid, yaml_data)
        
        terraform_config = f'''
# =============================================================================
# ROSA HCP CLUSTER: {cluster_name} (Fully Automated with STS)
# =============================================================================

{operator_roles_config}



# ROSA HCP cluster using RHCS Terraform provider with automated STS
resource "rhcs_cluster_rosa_hcp" "{clean_name}" {{
  
  name               = "{cluster_name}"
  cloud_region       = "{region}"
  version            = "{version}"
  
  # Required availability zones - use filtered local variable from YamlForge
  availability_zones = local.selected_azs_{region.replace('-', '_')}_{guid}
  
  # Machine configuration
  aws_account_id           = data.aws_caller_identity.current.account_id
  aws_billing_account_id   = var.aws_billing_account_id != "" ? var.aws_billing_account_id : data.aws_caller_identity.current.account_id
  compute_machine_type     = "{machine_type}"
  replicas                 = {worker_count}
  
  # Private cluster
  private = {str(private_cluster).lower()}
  
  # Network dependencies - use all subnet IDs (YamlForge generates public + private subnets for ROSA HCP)
  aws_subnet_ids = local.all_subnet_ids_{region.replace('-', '_')}_{guid}
  
  # STS configuration with automatically created roles
  sts = {{
    operator_role_prefix = "{cluster_name}"
    oidc_config_id     = rhcs_rosa_oidc_config.oidc_config.id
    role_arn            = data.aws_iam_role.rosa_hcp_installer_role.arn
    support_role_arn    = data.aws_iam_role.rosa_hcp_support_role.arn
    instance_iam_roles = {{
      worker_role_arn = data.aws_iam_role.rosa_hcp_worker_role.arn
    }}
  }}
  
  # Properties
  properties = {{
    rosa_creator_arn = data.aws_caller_identity.current.arn
  }}
  
  # Tags
  tags = {{
    Environment = var.environment
    ManagedBy   = "yamlforge"
    Platform    = "rosa-hcp"
    GUID        = "{guid}"
    Region      = "{region}"
  }}
  
  # Wait for all prerequisites to be ready
  depends_on = [
    aws_vpc.main_vpc_{region.replace('-', '_')}_{guid},
    aws_subnet.public_subnet_{region.replace('-', '_')}_{guid},
    aws_internet_gateway.main_igw_{region.replace('-', '_')}_{guid},
    data.aws_iam_role.rosa_hcp_installer_role,
    data.aws_iam_role.rosa_hcp_support_role,
    data.aws_iam_role.rosa_hcp_worker_role,
    rhcs_rosa_oidc_config.oidc_config
  ]
}}

# Outputs for ROSA HCP cluster
output "rosa_hcp_cluster_id_{clean_name}" {{
  description = "ROSA HCP cluster ID for {cluster_name}"
  value = rhcs_cluster_rosa_hcp.{clean_name}.id
}}

output "rosa_hcp_api_url_{clean_name}" {{
  description = "ROSA HCP API URL for {cluster_name}"
  value = rhcs_cluster_rosa_hcp.{clean_name}.api_url
}}

output "rosa_hcp_console_url_{clean_name}" {{
  description = "ROSA HCP console URL for {cluster_name}"
  value = rhcs_cluster_rosa_hcp.{clean_name}.console_url
}}

output "rosa_hcp_oidc_endpoint_{clean_name}" {{
  description = "ROSA HCP OIDC endpoint for {cluster_name}"
  value = length(rhcs_cluster_rosa_hcp.{clean_name}) > 0 ? rhcs_rosa_oidc_config.oidc_config.oidc_endpoint_url : ""
}}

'''
        return terraform_config

    def _generate_rosa_hcp_cli(self, cluster_config: Dict, clean_name: str, region: str, 
                              version: str, machine_type: str, worker_count: int, 
                              guid: str, yaml_data: Dict) -> str:
        """Generate ROSA HCP cluster using ROSA CLI (direct method)"""
        cluster_name = cluster_config.get('name')
        
        terraform_config = f'''
# =============================================================================
# ROSA HCP CLUSTER: {cluster_name} (ROSA CLI Method)
# =============================================================================

# ROSA HCP cluster will be created using ROSA CLI commands
# See the generated rosa-setup.sh script for cluster creation

# Local values for ROSA HCP cluster reference
locals {{
  rosa_hcp_cluster_name_{clean_name} = "{cluster_name}"
  rosa_hcp_region_{clean_name} = "{region}"
  rosa_hcp_version_{clean_name} = "{version}"
  rosa_hcp_machine_type_{clean_name} = "{machine_type}"
  rosa_hcp_replicas_{clean_name} = {worker_count}
  rosa_hcp_subnet_ids_{clean_name} = local.public_subnet_ids_{region.replace('-', '_')}_{guid}
}}

# Placeholder outputs for ROSA HCP cluster (will be populated after CLI creation)
output "rosa_hcp_cluster_id_{clean_name}" {{
  description = "ROSA HCP cluster ID for {cluster_name}"
  value = "Run rosa describe cluster {cluster_name} to get cluster details"
}}

output "rosa_hcp_api_url_{clean_name}" {{
  description = "ROSA HCP API URL for {cluster_name}"
  value = "Run rosa describe cluster {cluster_name} --output json | jq -r '.api.url'"
}}

output "rosa_hcp_console_url_{clean_name}" {{
  description = "ROSA HCP console URL for {cluster_name}"
  value = "Run rosa describe cluster {cluster_name} --output json | jq -r '.console.url'"
}}

'''
        return terraform_config 

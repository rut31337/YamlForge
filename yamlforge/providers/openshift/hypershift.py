"""
HyperShift Provider for yamlforge
Supports OpenShift hosted control planes with worker nodes on any cloud provider
"""

from typing import Dict, List
from .base import BaseOpenShiftProvider


class HyperShiftProvider(BaseOpenShiftProvider):
    """HyperShift Provider for hosted control planes"""
    
    def get_worker_infrastructure_dependency(self, worker_provider: str, clean_name: str) -> str:
        """Get the appropriate worker infrastructure dependency based on provider"""
        if worker_provider == 'aws':
            return f",\n    aws_autoscaling_group.{clean_name}_workers_asg"
        elif worker_provider == 'gcp':
            # For now, GCP worker infrastructure is TODO, so no dependency
            return ""
        elif worker_provider == 'azure':
            # For now, Azure worker infrastructure is TODO, so no dependency
            return ""
        else:
            # For other providers, no specific dependency yet
            return ""
    
    def get_coreos_image_for_openshift_version(self, openshift_version: str) -> str:
        """Determine appropriate CoreOS image key based on OpenShift version"""
        if not openshift_version:
            return "RHCOS-latest"
        
        # Extract major.minor version (e.g., "4.14.15" -> "4.14")
        try:
            version_parts = openshift_version.split('.')
            if len(version_parts) >= 2:
                major_minor = f"{version_parts[0]}.{version_parts[1]}"
                
                # Map OpenShift versions to CoreOS image keys
                version_map = {
                    "4.14": "RHCOS-414",
                    "4.15": "RHCOS-415",
                    "4.16": "RHCOS-latest",  # Use latest for newer versions
                }
                
                return version_map.get(major_minor, "RHCOS-latest")
        except (ValueError, IndexError):
            pass
        
        return "RHCOS-latest"
    
    def generate_coreos_ami_data_source(self, clean_name: str, coreos_image_key: str) -> str:
        """Generate fallback AMI data source for CoreOS"""
        # Get image configuration from mappings
        image_config = self.converter.images.get(coreos_image_key, {})
        aws_config = image_config.get('aws', {})
        
        # Use configured pattern or fallback to generic
        name_pattern = aws_config.get('name_pattern', 'rhcos-*')
        owner_key = aws_config.get('owner_key', 'rhcos_owner')
        
        # Get owner ID from configuration
        try:
            aws_provider = getattr(self.converter, 'providers', {}).get('aws')
            if aws_provider:
                owner_id = aws_provider.get_aws_resolver()._get_required_config_owner(owner_key)
            else:
                owner_id = "531415883065"  # RHCOS owner fallback
        except:
            owner_id = "531415883065"  # RHCOS owner fallback
        
        return f'''
# Get Red Hat CoreOS AMI for HyperShift worker nodes ({coreos_image_key})
data "aws_ami" "{clean_name}_worker_ami" {{
  most_recent = true
  owners      = ["{owner_id}"]
  
  filter {{
    name   = "name"
    values = ["{name_pattern}"]
  }}
  
  filter {{
    name   = "architecture"
    values = ["x86_64"]
  }}
  
  filter {{
    name   = "state"
    values = ["available"]
  }}
}}
'''
    
    def resolve_hypershift_worker_ami(self, clean_name: str, coreos_image_key: str, region: str, no_credentials_mode: bool) -> tuple:
        """Resolve AMI reference and data source for HyperShift worker nodes"""
        if no_credentials_mode:
            return '"ami-PLACEHOLDER-REPLACE-WITH-ACTUAL-AMI"', ""
        
        # Try dynamic resolution first
        try:
            aws_provider = getattr(self.converter, 'providers', {}).get('aws')
            if aws_provider:
                ami_reference, resolution_type = aws_provider.resolve_aws_ami(
                    coreos_image_key, clean_name, "x86_64", region, self.converter.current_yaml_data
                )
                
                if resolution_type == "dynamic" and ami_reference:
                    # Dynamic resolution succeeded - use the AMI directly
                    return ami_reference, ""
                elif ami_reference is None:
                    # Fallback to data source
                    data_source = self.generate_coreos_ami_data_source(clean_name, coreos_image_key)
                    return f'data.aws_ami.{clean_name}_worker_ami.id', data_source
                else:
                    # Data source HCL returned
                    return f'data.aws_ami.{clean_name}_worker_ami.id', resolution_type or ""
        except Exception as e:
            print(f"Warning: Failed to resolve CoreOS image {coreos_image_key}: {e}")
        
        # Fallback to data source
        data_source = self.generate_coreos_ami_data_source(clean_name, coreos_image_key)
        return f'data.aws_ami.{clean_name}_worker_ami.id', data_source
    
    def resolve_gcp_hypershift_worker_image(self, clean_name: str, coreos_image_key: str, region: str, no_credentials_mode: bool) -> tuple:
        """Resolve GCP image reference and data source for HyperShift worker nodes"""
        if no_credentials_mode:
            return '"projects/rhcos-cloud/global/images/family/rhcos"', ""
        
        # Try dynamic resolution first using GCP provider
        try:
            gcp_provider = getattr(self.converter, 'providers', {}).get('gcp')
            if gcp_provider:
                # Check if the GCP provider has image resolution methods
                image_config = self.converter.images.get(coreos_image_key, {})
                gcp_config = image_config.get('gcp', {})
                
                if gcp_config:
                    image_family = gcp_config.get('image_family', 'rhcos')
                    project = gcp_config.get('project', 'rhcos-cloud')
                    
                    # Use data source for GCP CoreOS images
                    data_source = self.generate_gcp_coreos_image_data_source(clean_name, image_family, project)
                    return f'data.google_compute_image.{clean_name}_worker_image.self_link', data_source
        except Exception as e:
            print(f"Warning: Failed to resolve GCP CoreOS image {coreos_image_key}: {e}")
        
        # Fallback to hardcoded RHCOS family
        data_source = self.generate_gcp_coreos_image_data_source(clean_name, "rhcos", "rhcos-cloud")
        return f'data.google_compute_image.{clean_name}_worker_image.self_link', data_source
    
    def generate_gcp_coreos_image_data_source(self, clean_name: str, image_family: str, project: str) -> str:
        """Generate GCP data source for CoreOS images"""
        return f'''
# Get Red Hat CoreOS image for HyperShift worker nodes (GCP)
data "google_compute_image" "{clean_name}_worker_image" {{
  family  = "{image_family}"
  project = "{project}"
}}
'''
    
    def resolve_azure_hypershift_worker_image(self, clean_name: str, coreos_image_key: str, region: str, no_credentials_mode: bool) -> tuple:
        """Resolve Azure image reference and data source for HyperShift worker nodes"""
        if no_credentials_mode:
            return '''
    publisher = "RedHat"
    offer     = "rhel-coreos"
    sku       = "rhel-coreos-gen2"
    version   = "latest"''', ""
        
        # Try dynamic resolution first using image mappings
        try:
            # Check if the converter has image mappings loaded
            image_config = self.converter.images.get(coreos_image_key, {})
            azure_config = image_config.get('azure', {})
            
            if azure_config:
                publisher = azure_config.get('publisher', 'RedHat')
                offer = azure_config.get('offer', 'rhel-coreos')
                sku = azure_config.get('sku', 'rhel-coreos-gen2')
                version = azure_config.get('version', 'latest')
                
                # Use direct marketplace image reference for Azure VM scale sets
                image_ref = f'''
    publisher = "{publisher}"
    offer     = "{offer}"
    sku       = "{sku}"
    version   = "{version}"'''
                return image_ref, ""
        except Exception as e:
            print(f"Warning: Failed to resolve Azure CoreOS image {coreos_image_key}: {e}")
        
        # Fallback to hardcoded CoreOS configuration
        image_ref = '''
    publisher = "RedHat"
    offer     = "rhel-coreos"
    sku       = "rhel-coreos-gen2"
    version   = "latest"'''
        return image_ref, ""
    
    
    def generate_hypershift_cluster(self, cluster_config: Dict, all_clusters: List[Dict]) -> str:
        """Generate HyperShift hosted cluster configuration"""
        
        cluster_name = cluster_config.get('name')
        if not cluster_name:
            raise ValueError("HyperShift cluster 'name' must be specified")
        clean_name = self.clean_name(cluster_name)
        management_cluster_name = cluster_config.get('management_cluster')
        
        if not management_cluster_name:
            raise ValueError(f"HyperShift cluster '{cluster_name}' must specify a management_cluster")
        
        # Find the management cluster configuration
        management_cluster = None
        for cluster in all_clusters:
            if cluster.get('name') == management_cluster_name:
                management_cluster = cluster
                break
                
        if not management_cluster:
            raise ValueError(f"Management cluster '{management_cluster_name}' not found for HyperShift cluster '{cluster_name}'")
        
        # Get worker infrastructure configuration
        worker_provider = cluster_config.get('provider')
        if not worker_provider:
            raise ValueError(f"HyperShift cluster '{cluster_name}' must specify 'provider' for worker nodes")
            
        worker_region = cluster_config.get('region')
        if not worker_region:
            raise ValueError(f"HyperShift cluster '{cluster_name}' must specify 'region' for worker nodes")
            
        worker_count = cluster_config.get('worker_count')
        if not worker_count:
            raise ValueError(f"HyperShift cluster '{cluster_name}' must specify 'worker_count'")
            
        worker_size = cluster_config.get('size')
        if not worker_size:
            raise ValueError(f"HyperShift cluster '{cluster_name}' must specify 'size'")
            
        version = cluster_config.get('version')
        if not version:
            raise ValueError(f"HyperShift cluster '{cluster_name}' must specify 'version'")
        version = self.validate_openshift_version(version, cluster_type="hypershift", cluster_name=cluster_name)
        
        # Determine if HyperShift deployment separation is needed
        needs_hypershift_separation = cluster_config.get('_needs_hypershift_separation', False)
        deployment_group = cluster_config.get('_deployment_group', 'hypershift_hosted')
        
        # Always deploy (no conditional variables needed)
        deployment_condition = '1'
        
        # Get management cluster resource reference for dependency
        management_clean_name = self.clean_name(management_cluster_name)
        management_cluster_type = management_cluster.get('type', 'rosa-classic')
        
        # Determine the management cluster resource reference based on its type
        if management_cluster_type == 'rosa-classic':
            management_resource_ref = f"rhcs_cluster_rosa_classic.{management_clean_name}"
        elif management_cluster_type == 'rosa-hcp':
            management_resource_ref = f"rhcs_cluster_rosa_hcp.{management_clean_name}"
        else:
            # For other types, use a generic reference
            management_resource_ref = f"module.{management_clean_name}_openshift"
        
        # Generate worker infrastructure based on provider
        worker_terraform = self.generate_hypershift_worker_infrastructure(
            cluster_config, worker_provider, worker_region, worker_count, worker_size, deployment_condition
        )
        
        # Generate HyperShift hosted cluster configuration
        hosted_cluster_terraform = self.generate_hosted_cluster_config(
            cluster_config, management_cluster, version, deployment_condition, management_resource_ref, worker_provider
        )
        
        group_note = ""
        if needs_hypershift_separation:
            group_note = f"# Deployment group: {deployment_group} - HyperShift hosted cluster\n"
        
        return f'''
# =============================================================================
# HYPERSHIFT HOSTED CLUSTER: {cluster_name}
# =============================================================================
{group_note}# Management Cluster: {management_cluster_name}
# Worker Provider: {worker_provider}
# Cost Savings: ~60-70% compared to dedicated control plane nodes
# Provisioning Time: 2-3 minutes (no control plane infrastructure needed)

{worker_terraform}

{hosted_cluster_terraform}
'''

    def generate_hypershift_worker_infrastructure(self, cluster_config: Dict, provider: str, region: str, worker_count: int, size: str, deployment_condition: str) -> str:
        """Generate worker node infrastructure for HyperShift cluster"""
        
        cluster_name = cluster_config.get('name')
        clean_name = self.clean_name(cluster_name)
        
        # Get machine type using OpenShift-optimized flavor mappings
        machine_type = self.get_openshift_machine_type(provider, size, 'worker')
        
        if provider == 'aws':
            return self.generate_aws_hypershift_workers(cluster_config, region, worker_count, machine_type, deployment_condition)
        elif provider == 'azure':
            return self.generate_azure_hypershift_workers(cluster_config, region, worker_count, machine_type, deployment_condition)
        elif provider == 'gcp':
            return self.generate_gcp_hypershift_workers(cluster_config, region, worker_count, machine_type, deployment_condition)
        elif provider in ['ibm_vpc', 'ibm_classic']:
            return self.generate_ibm_hypershift_workers(cluster_config, region, worker_count, machine_type, deployment_condition)
        elif provider == 'oci':
            return self.generate_oci_hypershift_workers(cluster_config, region, worker_count, machine_type, deployment_condition)
        elif provider == 'vmware':
            return self.generate_vmware_hypershift_workers(cluster_config, region, worker_count, machine_type, deployment_condition)
        elif provider == 'alibaba':
            return self.generate_alibaba_hypershift_workers(cluster_config, region, worker_count, machine_type, deployment_condition)
        else:
            return f"# TODO: HyperShift worker infrastructure for {provider} not yet implemented\n"
    

    
    def generate_aws_hypershift_workers(self, cluster_config: Dict, region: str, worker_count: int, machine_type: str, deployment_condition: str) -> str:
        """Generate AWS worker infrastructure for HyperShift"""
        
        cluster_name = cluster_config.get('name')
        clean_name = self.clean_name(cluster_name)
        
        # Get merged networking configuration (defaults + user overrides)
        networking = self.get_merged_networking_config(cluster_config, 'hypershift')
        
        # Check if we're in no-credentials mode
        no_credentials_mode = getattr(self.converter, 'no_credentials', False)
        
        # Determine CoreOS image based on OpenShift version
        openshift_version = cluster_config.get('version', '4.14.15')
        coreos_image_key = self.get_coreos_image_for_openshift_version(openshift_version)
        
        # Resolve CoreOS AMI for launch template
        ami_reference, ami_data_source = self.resolve_hypershift_worker_ami(
            clean_name, coreos_image_key, region, no_credentials_mode
        )
        
        terraform_config = f'''
# AWS Worker Infrastructure for HyperShift Cluster
resource "aws_vpc" "{clean_name}_workers_vpc" {{
  count = {deployment_condition}
  
  cidr_block           = "{networking.get('machine_cidr', '10.0.0.0/16')}"
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = {{
    Name = "{cluster_name}-workers-vpc"
    "kubernetes.io/cluster/{cluster_name}" = "owned"
    HyperShiftCluster = "{cluster_name}"
  }}
}}

resource "aws_subnet" "{clean_name}_workers_subnet" {{
  count = {deployment_condition}
  
  vpc_id                  = aws_vpc.{clean_name}_workers_vpc[0].id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "{region}a"
  map_public_ip_on_launch = true
  
  tags = {{
    Name = "{cluster_name}-workers-subnet"
    "kubernetes.io/cluster/{cluster_name}" = "owned"
    "kubernetes.io/role/elb" = "1"
  }}
}}

resource "aws_internet_gateway" "{clean_name}_workers_igw" {{
  count = {deployment_condition}
  
  vpc_id = aws_vpc.{clean_name}_workers_vpc[0].id
  
  tags = {{
    Name = "{cluster_name}-workers-igw"
  }}
}}

resource "aws_route_table" "{clean_name}_workers_rt" {{
  count = {deployment_condition}
  
  vpc_id = aws_vpc.{clean_name}_workers_vpc[0].id
  
  route {{
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.{clean_name}_workers_igw[0].id
  }}
  
  tags = {{
    Name = "{cluster_name}-workers-rt"
  }}
}}

resource "aws_route_table_association" "{clean_name}_workers_rta" {{
  count = {deployment_condition}
  
  subnet_id      = aws_subnet.{clean_name}_workers_subnet[0].id
  route_table_id = aws_route_table.{clean_name}_workers_rt[0].id
}}

# Security group for HyperShift workers
resource "aws_security_group" "{clean_name}_workers_sg" {{
  count = {deployment_condition}
  
  name_prefix = "{cluster_name}-workers-"
  vpc_id      = aws_vpc.{clean_name}_workers_vpc[0].id
  
  # Inbound rules for OpenShift worker nodes
  ingress {{
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["{networking.get('machine_cidr', '10.0.0.0/16')}"]
  }}
  
  ingress {{
    from_port   = 10250
    to_port     = 10250
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }}
  
  ingress {{
    from_port   = 30000
    to_port     = 32767
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }}
  
  # Outbound - allow all
  egress {{
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }}
  
  tags = {{
    Name = "{cluster_name}-workers-sg"
    "kubernetes.io/cluster/{cluster_name}" = "owned"
  }}
}}

# Launch template for HyperShift worker nodes
resource "aws_launch_template" "{clean_name}_workers_lt" {{
  count = {deployment_condition}
  
  name_prefix   = "{cluster_name}-workers-"
  image_id      = {ami_reference}
  instance_type = "{machine_type}"
  
  vpc_security_group_ids = [aws_security_group.{clean_name}_workers_sg[0].id]
  
  user_data = base64encode(<<-EOF
#!/bin/bash
# HyperShift worker node initialization script
# Cluster: {cluster_name}

# Basic system setup for HyperShift worker
yum update -y
yum install -y container-selinux

# Configure cgroup v2 for OpenShift 4.14+
echo 'GRUB_CMDLINE_LINUX="systemd.unified_cgroup_hierarchy=1"' >> /etc/default/grub
grub2-mkconfig -o /boot/grub2/grub.cfg

# Ensure proper DNS resolution
echo "nameserver 8.8.8.8" >> /etc/resolv.conf

echo "HyperShift worker node setup completed for cluster {cluster_name}"
EOF
  )
  
  tag_specifications {{
    resource_type = "instance"
    tags = {{
      Name = "{cluster_name}-worker"
      "kubernetes.io/cluster/{cluster_name}" = "owned"
      HyperShiftCluster = "{cluster_name}"
      HyperShiftRole = "worker"
    }}
  }}
}}

# Auto Scaling Group for HyperShift workers
resource "aws_autoscaling_group" "{clean_name}_workers_asg" {{
  count = {deployment_condition}
  
  name                = "{cluster_name}-workers"
  vpc_zone_identifier = [aws_subnet.{clean_name}_workers_subnet[0].id]
  target_group_arns   = []
  health_check_type   = "EC2"
  
  min_size         = {worker_count}
  max_size         = {worker_count * 2}
  desired_capacity = {worker_count}
  
  launch_template {{
    id      = aws_launch_template.{clean_name}_workers_lt[0].id
    version = "$Latest"
  }}
  
  tag {{
    key                 = "Name"
    value               = "{cluster_name}-worker"
    propagate_at_launch = true
  }}
  
  tag {{
    key                 = "kubernetes.io/cluster/{cluster_name}"
    value               = "owned"
    propagate_at_launch = true
  }}
}}

{ami_data_source}
'''
        
        return terraform_config
    
    def generate_hosted_cluster_config(self, cluster_config: Dict, management_cluster: Dict, version: str, deployment_condition: str, management_resource_ref: str, worker_provider: str) -> str:
        """Generate HyperShift hosted cluster configuration"""
        
        cluster_name = cluster_config.get('name')
        clean_name = self.clean_name(cluster_name)
        management_cluster_name = management_cluster.get('name')
        
        # Get merged networking configuration (defaults + user overrides)
        networking = self.get_merged_networking_config(cluster_config, 'hypershift')
        
        terraform_config = f'''
# HyperShift Hosted Cluster Configuration
resource "kubectl_manifest" "{clean_name}_hostedcluster" {{
  count = {deployment_condition}
  
  # Wait for management cluster and worker infrastructure before deploying hosted cluster
  
  yaml_body = yamlencode({{
    apiVersion = "hypershift.openshift.io/v1beta1"
    kind       = "HostedCluster"
    metadata = {{
      name      = "{cluster_name}"
      namespace = "clusters"
    }}
    spec = {{
      release = {{
        image = "quay.io/openshift-release-dev/ocp-release:{version}-x86_64"
      }}
      
      dns = {{
        baseDomain = "{cluster_config.get('base_domain')}"
      }}
      
      networking = {{
        clusterNetwork = [{{
          cidr = "{networking.get('pod_cidr', '10.128.0.0/14')}"
        }}]
        serviceNetwork = [{{
          cidr = "{networking.get('service_cidr', '172.30.0.0/16')}"
        }}]
        networkType = "OVNKubernetes"
      }}
      
      platform = {{
        type = "{cluster_config.get('provider').upper()}"
      }}
      
      infraID = "{cluster_name}"
      
      services = [
        {{
          service = "APIServer"
          servicePublishingStrategy = {{
            type = "LoadBalancer"
          }}
        }},
        {{
          service = "OAuthServer"
          servicePublishingStrategy = {{
            type = "Route"
          }}
        }},
        {{
          service = "OIDC"
          servicePublishingStrategy = {{
            type = "Route"
          }}
        }},
        {{
          service = "Konnectivity"
          servicePublishingStrategy = {{
            type = "Route"
          }}
        }},
        {{
          service = "Ignition"
          servicePublishingStrategy = {{
            type = "Route"
          }}
        }}
      ]
    }}
  }})

  depends_on = [
    {management_resource_ref}{self.get_worker_infrastructure_dependency(worker_provider, clean_name)}
  ]
}}

# NodePool for HyperShift workers
resource "kubectl_manifest" "{clean_name}_nodepool" {{
  count = {deployment_condition}
  
  yaml_body = yamlencode({{
    apiVersion = "hypershift.openshift.io/v1beta1"
    kind       = "NodePool"
    metadata = {{
      name      = "{cluster_name}-workers"
      namespace = "clusters"
    }}
    spec = {{
      clusterName = "{cluster_name}"
      replicas    = {cluster_config.get('worker_count')}
      
      management = {{
        upgradeType = "Replace"
      }}
      
      platform = {{
        type = "{cluster_config.get('provider').upper()}"
      }}
      
      release = {{
        image = "quay.io/openshift-release-dev/ocp-release:{version}-x86_64"
      }}
    }}
  }})

  depends_on = [
    kubectl_manifest.{clean_name}_hostedcluster
  ]
}}
'''

        return terraform_config
    
    def generate_azure_hypershift_workers(self, cluster_config: Dict, region: str, worker_count: int, machine_type: str, deployment_condition: str) -> str:
        """Generate Azure worker infrastructure for HyperShift"""
        
        cluster_name = cluster_config.get('name')
        clean_name = self.clean_name(cluster_name)
        
        # Check if we're in no-credentials mode
        no_credentials_mode = getattr(self.converter, 'no_credentials', False)
        
        # Determine CoreOS image based on OpenShift version
        openshift_version = cluster_config.get('version', '4.14.15')
        coreos_image_key = self.get_coreos_image_for_openshift_version(openshift_version)
        
        # Resolve CoreOS image for Azure
        image_reference, image_data_source = self.resolve_azure_hypershift_worker_image(
            clean_name, coreos_image_key, region, no_credentials_mode
        )
        
        terraform_config = f'''
# Azure Worker Infrastructure for HyperShift Cluster
resource "azurerm_resource_group" "{clean_name}_workers_rg" {{
  count = {deployment_condition}
  
  name     = "{cluster_name}-workers-rg"
  location = "{region}"
}}

resource "azurerm_virtual_network" "{clean_name}_workers_vnet" {{
  count = {deployment_condition}
  
  name                = "{cluster_name}-workers-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.{clean_name}_workers_rg[0].location
  resource_group_name = azurerm_resource_group.{clean_name}_workers_rg[0].name
}}

resource "azurerm_subnet" "{clean_name}_workers_subnet" {{
  count = {deployment_condition}
  
  name                 = "{cluster_name}-workers-subnet"
  resource_group_name  = azurerm_resource_group.{clean_name}_workers_rg[0].name
  virtual_network_name = azurerm_virtual_network.{clean_name}_workers_vnet[0].name
  address_prefixes     = ["10.0.1.0/24"]
}}

resource "azurerm_network_security_group" "{clean_name}_workers_nsg" {{
  count = {deployment_condition}
  
  name                = "{cluster_name}-workers-nsg"
  location            = azurerm_resource_group.{clean_name}_workers_rg[0].location
  resource_group_name = azurerm_resource_group.{clean_name}_workers_rg[0].name

  security_rule {{
    name                       = "SSH"
    priority                   = 1001
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "10.0.0.0/16"
    destination_address_prefix = "*"
  }}

  security_rule {{
    name                       = "Kubelet"
    priority                   = 1002
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "10250"
    source_address_prefix      = "10.0.0.0/8"
    destination_address_prefix = "*"
  }}

  security_rule {{
    name                       = "NodePorts"
    priority                   = 1003
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "30000-32767"
    source_address_prefix      = "10.0.0.0/8"
    destination_address_prefix = "*"
  }}
}}

resource "azurerm_linux_virtual_machine_scale_set" "{clean_name}_workers_vmss" {{
  count = {deployment_condition}
  
  name                = "{cluster_name}-workers"
  resource_group_name = azurerm_resource_group.{clean_name}_workers_rg[0].name
  location            = azurerm_resource_group.{clean_name}_workers_rg[0].location
  sku                 = "{machine_type}"
  instances           = {worker_count}

  admin_username                  = "azureuser"
  disable_password_authentication = true

  source_image_reference {{
{image_reference}
  }}

  os_disk {{
    storage_account_type = "Standard_LRS"
    caching              = "ReadWrite"
  }}

  network_interface {{
    name    = "internal"
    primary = true

    ip_configuration {{
      name      = "internal"
      primary   = true
      subnet_id = azurerm_subnet.{clean_name}_workers_subnet[0].id
    }}

    network_security_group_id = azurerm_network_security_group.{clean_name}_workers_nsg[0].id
  }}

  custom_data = base64encode(<<-EOF
#!/bin/bash
# HyperShift worker node initialization script for Azure
# Cluster: {cluster_name}

# Basic system setup for HyperShift worker
yum update -y
yum install -y container-selinux

# Configure cgroup v2 for OpenShift 4.14+
echo 'GRUB_CMDLINE_LINUX="systemd.unified_cgroup_hierarchy=1"' >> /etc/default/grub
grub2-mkconfig -o /boot/grub2/grub.cfg

# Ensure proper DNS resolution
echo "nameserver 8.8.8.8" >> /etc/resolv.conf

echo "Azure HyperShift worker node setup completed for cluster {cluster_name}"
EOF
  )

  tags = {{
    "hypershift-cluster" = "{cluster_name}"
    "hypershift-role"    = "worker"
  }}
}}

{image_data_source}
'''
        
        return terraform_config
        
    def generate_gcp_hypershift_workers(self, cluster_config: Dict, region: str, worker_count: int, machine_type: str, deployment_condition: str) -> str:
        """Generate GCP worker infrastructure for HyperShift"""
        
        cluster_name = cluster_config.get('name')
        clean_name = self.clean_name(cluster_name)
        
        # Get merged networking configuration (defaults + user overrides)
        networking = self.get_merged_networking_config(cluster_config, 'hypershift')
        
        # Check if we're in no-credentials mode
        no_credentials_mode = getattr(self.converter, 'no_credentials', False)
        
        # Determine CoreOS image based on OpenShift version
        openshift_version = cluster_config.get('version', '4.14.15')
        coreos_image_key = self.get_coreos_image_for_openshift_version(openshift_version)
        
        # Resolve CoreOS image for GCP
        image_reference, image_data_source = self.resolve_gcp_hypershift_worker_image(
            clean_name, coreos_image_key, region, no_credentials_mode
        )
        
        terraform_config = f'''
# GCP Worker Infrastructure for HyperShift Cluster
resource "google_compute_network" "{clean_name}_workers_network" {{
  count = {deployment_condition}
  
  name                    = "{cluster_name}-workers-network"
  auto_create_subnetworks = false
  project                 = local.project_id
}}

resource "google_compute_subnetwork" "{clean_name}_workers_subnet" {{
  count = {deployment_condition}
  
  name          = "{cluster_name}-workers-subnet"
  ip_cidr_range = "10.0.1.0/24"
  region        = "{region}"
  network       = google_compute_network.{clean_name}_workers_network[0].id
  project       = local.project_id
}}

resource "google_compute_firewall" "{clean_name}_workers_firewall" {{
  count = {deployment_condition}
  
  name    = "{cluster_name}-workers-firewall"
  network = google_compute_network.{clean_name}_workers_network[0].name
  project = local.project_id

  allow {{
    protocol = "tcp"
    ports    = ["22", "10250", "30000-32767"]
  }}

  source_ranges = ["{networking.get('machine_cidr', '10.0.0.0/16')}"]
  target_tags   = ["{cluster_name}-workers"]
}}

resource "google_compute_instance_template" "{clean_name}_workers_template" {{
  count = {deployment_condition}
  
  name_prefix  = "{cluster_name}-workers-"
  machine_type = "{machine_type}"
  project      = local.project_id

  disk {{
    source_image = {image_reference}
    auto_delete  = true
    boot         = true
    disk_size_gb = 50
    disk_type    = "pd-standard"
  }}

  network_interface {{
    subnetwork = google_compute_subnetwork.{clean_name}_workers_subnet[0].id
    access_config {{
      // Ephemeral IP
    }}
  }}

  metadata_startup_script = <<-EOF
#!/bin/bash
# HyperShift worker node initialization script for GCP
# Cluster: {cluster_name}

# Basic system setup for HyperShift worker
yum update -y
yum install -y container-selinux

# Configure cgroup v2 for OpenShift 4.14+
echo 'GRUB_CMDLINE_LINUX="systemd.unified_cgroup_hierarchy=1"' >> /etc/default/grub
grub2-mkconfig -o /boot/grub2/grub.cfg

# Ensure proper DNS resolution
echo "nameserver 8.8.8.8" >> /etc/resolv.conf

echo "GCP HyperShift worker node setup completed for cluster {cluster_name}"
EOF

  tags = ["{cluster_name}-workers"]

  labels = {{
    "hypershift-cluster" = "{cluster_name}"
    "hypershift-role"    = "worker"
  }}

  lifecycle {{
    create_before_destroy = true
  }}
}}

resource "google_compute_instance_group_manager" "{clean_name}_workers_group" {{
  count = {deployment_condition}
  
  name               = "{cluster_name}-workers"
  base_instance_name = "{cluster_name}-worker"
  zone               = "{region}-a"
  target_size        = {worker_count}
  project            = local.project_id

  version {{
    instance_template = google_compute_instance_template.{clean_name}_workers_template[0].id
  }}
}}

{image_data_source}
'''
        
        return terraform_config
        
    def generate_ibm_hypershift_workers(self, cluster_config: Dict, region: str, worker_count: int, machine_type: str, deployment_condition: str) -> str:
        """Generate IBM Cloud worker infrastructure for HyperShift"""
        # TODO: Implement IBM HyperShift worker infrastructure
        return f"# TODO: IBM HyperShift worker infrastructure for {cluster_config.get('name')}\n"
        
    def generate_oci_hypershift_workers(self, cluster_config: Dict, region: str, worker_count: int, machine_type: str, deployment_condition: str) -> str:
        """Generate Oracle Cloud worker infrastructure for HyperShift"""
        # TODO: Implement OCI HyperShift worker infrastructure
        return f"# TODO: OCI HyperShift worker infrastructure for {cluster_config.get('name')}\n"
        
    def generate_vmware_hypershift_workers(self, cluster_config: Dict, region: str, worker_count: int, machine_type: str, deployment_condition: str) -> str:
        """Generate VMware worker infrastructure for HyperShift"""
        # TODO: Implement VMware HyperShift worker infrastructure
        return f"# TODO: VMware HyperShift worker infrastructure for {cluster_config.get('name')}\n"
        
    def generate_alibaba_hypershift_workers(self, cluster_config: Dict, region: str, worker_count: int, machine_type: str, deployment_condition: str) -> str:
        """Generate Alibaba Cloud worker infrastructure for HyperShift"""
        # TODO: Implement Alibaba HyperShift worker infrastructure
        return f"# TODO: Alibaba HyperShift worker infrastructure for {cluster_config.get('name')}\n" 

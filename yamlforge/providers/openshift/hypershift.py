"""
HyperShift Provider for yamlforge
Supports OpenShift hosted control planes with worker nodes on any cloud provider
"""

from typing import Dict, List
from .base import BaseOpenShiftProvider


class HyperShiftProvider(BaseOpenShiftProvider):
    """HyperShift Provider for hosted control planes"""
    
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
        version = self.validate_openshift_version(version, cluster_type="hypershift-hosted")
        
        # Determine if HyperShift deployment separation is needed
        needs_hypershift_separation = cluster_config.get('_needs_hypershift_separation', False)
        deployment_group = cluster_config.get('_deployment_group', 'hypershift_hosted')
        
        deployment_condition = ''
        if needs_hypershift_separation and deployment_group == 'hypershift_hosted':
            deployment_condition = 'var.deploy_hypershift_hosted ? 1 : 0'
        else:
            deployment_condition = '1'
        
        # Generate worker infrastructure based on provider
        worker_terraform = self.generate_hypershift_worker_infrastructure(
            cluster_config, worker_provider, worker_region, worker_count, worker_size, deployment_condition
        )
        
        # Generate HyperShift hosted cluster configuration
        hosted_cluster_terraform = self.generate_hosted_cluster_config(
            cluster_config, management_cluster, version, deployment_condition
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
  image_id      = data.aws_ami.{clean_name}_worker_ami.id
  instance_type = "{machine_type}"
  
  vpc_security_group_ids = [aws_security_group.{clean_name}_workers_sg[0].id]
  
  user_data = base64encode(templatefile("${{path.module}}/hypershift-worker-userdata.sh", {{
    cluster_name = "{cluster_name}"
  }}))
  
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

# Get RHEL CoreOS AMI for worker nodes
data "aws_ami" "{clean_name}_worker_ami" {{
  most_recent = true
  owners      = ["309956199498"] # Red Hat
  
  filter {{
    name   = "name"
    values = ["RHCOS-*"]
  }}
  
  filter {{
    name   = "architecture"
    values = ["x86_64"]
  }}
}}
'''
        
        return terraform_config
    
    def generate_hosted_cluster_config(self, cluster_config: Dict, management_cluster: Dict, version: str, deployment_condition: str) -> str:
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
    aws_autoscaling_group.{clean_name}_workers_asg
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
        # TODO: Implement Azure HyperShift worker infrastructure
        return f"# TODO: Azure HyperShift worker infrastructure for {cluster_config.get('name')}\n"
        
    def generate_gcp_hypershift_workers(self, cluster_config: Dict, region: str, worker_count: int, machine_type: str, deployment_condition: str) -> str:
        """Generate GCP worker infrastructure for HyperShift"""
        # TODO: Implement GCP HyperShift worker infrastructure
        return f"# TODO: GCP HyperShift worker infrastructure for {cluster_config.get('name')}\n"
        
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

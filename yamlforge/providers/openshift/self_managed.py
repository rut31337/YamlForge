"""
Self-Managed OpenShift Provider for yamlforge
Supports deployment on any cloud provider infrastructure
"""

from typing import Dict
from .base import BaseOpenShiftProvider


class SelfManagedOpenShiftProvider(BaseOpenShiftProvider):
    """Self-Managed OpenShift Provider (Works with any cloud provider)"""
    
    def generate_self_managed_cluster(self, cluster_config: Dict) -> str:
        """Generate self-managed OpenShift cluster on any supported provider"""
        
        cluster_name = cluster_config.get('name')
        provider = cluster_config.get('provider')  # Default to AWS if not specified
        
        # Validate provider is supported
        supported_providers = ['aws', 'azure', 'gcp', 'ibm_vpc', 'ibm_classic', 'oci', 'vmware', 'alibaba']
        if provider not in supported_providers:
            raise ValueError(f"Provider '{provider}' not supported for self-managed OpenShift. Supported: {supported_providers}")
        
        # Get infrastructure configuration
        infrastructure = cluster_config.get('infrastructure')
        if infrastructure:
            # Use existing instances for self-managed
            return self.generate_self_managed_on_existing_infrastructure(cluster_config)
        else:
            # Generate new instances for OpenShift based on provider
            return self.generate_self_managed_with_new_infrastructure(cluster_config)
    
    def generate_self_managed_with_new_infrastructure(self, cluster_config: Dict) -> str:
        """Generate new infrastructure for self-managed OpenShift on any provider"""
        
        cluster_name = cluster_config.get('name')
        clean_name = self.clean_name(cluster_name)
        provider = cluster_config.get('provider')
        region = cluster_config.get('region')
        version = self.validate_openshift_version(cluster_config.get('version'), cluster_type="self-managed")
        
        size_config = self.get_cluster_size_config(
            cluster_config.get('size'), 'self-managed', cloud_provider=provider
        )
        
        if 'controlplane_count' not in size_config:
            raise ValueError(f"Cluster size configuration for '{cluster_config.get('size')}' is missing 'controlplane_count' field. Available fields: {list(size_config.keys())}")
        
        controlplane_count = size_config['controlplane_count']
        worker_count = cluster_config.get('worker_count')
        
        # Generate infrastructure based on provider
        if provider == 'gcp':
            return self.generate_gcp_self_managed_infrastructure(cluster_config, size_config, version)
        elif provider == 'aws':
            return self.generate_aws_self_managed_infrastructure(cluster_config, size_config, version)
        elif provider == 'azure':
            return self.generate_azure_self_managed_infrastructure(cluster_config, size_config, version)
        elif provider in ['ibm_vpc', 'ibm_classic']:
            return self.generate_ibm_self_managed_infrastructure(cluster_config, size_config, version)
        elif provider == 'oci':
            return self.generate_oci_self_managed_infrastructure(cluster_config, size_config, version)
        elif provider == 'vmware':
            return self.generate_vmware_self_managed_infrastructure(cluster_config, size_config, version)
        elif provider == 'alibaba':
            return self.generate_alibaba_self_managed_infrastructure(cluster_config, size_config, version)
        else:
            return f"# TODO: Self-managed OpenShift on {provider} not yet implemented\n"
    

    
    def generate_gcp_self_managed_infrastructure(self, cluster_config: Dict, size_config: Dict, version: str) -> str:
        """Generate GCP infrastructure for self-managed OpenShift"""
        
        cluster_name = cluster_config.get('name')
        clean_name = self.clean_name(cluster_name)
        region = cluster_config.get('region')
        zone = cluster_config.get('zone')
        
        # Get machine types using OpenShift-optimized flavor mappings  
        controlplane_machine_type = self.get_openshift_machine_type('gcp', size_config['controlplane_size'], 'controlplane')
        worker_machine_type = self.get_openshift_machine_type('gcp', size_config['worker_size'], 'worker')
        
        if 'controlplane_count' not in size_config:
            raise ValueError(f"Cluster size configuration is missing 'controlplane_count' field. Available fields: {list(size_config.keys())}")
        controlplane_count = size_config['controlplane_count']
        worker_count = cluster_config.get('worker_count')
        
        # Get merged networking configuration (defaults + user overrides)
        networking = self.get_merged_networking_config(cluster_config, 'self-managed')
        
        terraform_config = f'''
# =============================================================================
# SELF-MANAGED OPENSHIFT ON GCP: {cluster_name}
# =============================================================================

# GCP Network for OpenShift
resource "google_compute_network" "{clean_name}_vpc" {{
  name                    = "{cluster_name}-vpc"
  auto_create_subnetworks = false
  
  # Tags
  description = "VPC for self-managed OpenShift cluster {cluster_name}"
}}

# GCP Subnet for OpenShift
resource "google_compute_subnetwork" "{clean_name}_subnet" {{
  name          = "{cluster_name}-subnet"
  ip_cidr_range = "{networking.get('machine_cidr', '10.2.0.0/16')}"
  region        = "{region}"
  network       = google_compute_network.{clean_name}_vpc.id
  
  # Enable private Google access for OpenShift
  private_ip_google_access = true
}}

# Firewall rules for OpenShift
resource "google_compute_firewall" "{clean_name}_openshift_internal" {{
  name    = "{cluster_name}-openshift-internal"
  network = google_compute_network.{clean_name}_vpc.name

  allow {{
    protocol = "tcp"
    ports    = ["22623", "6443", "2379-2380", "10250-10259", "9000-9999"]
  }}
  
  allow {{
    protocol = "udp"
    ports    = ["4789", "6081", "9000-9999"]
  }}
  
  source_ranges = ["{networking.get('machine_cidr', '10.2.0.0/16')}"]
  target_tags   = ["{cluster_name}-openshift"]
}}

resource "google_compute_firewall" "{clean_name}_openshift_external" {{
  name    = "{cluster_name}-openshift-external"
  network = google_compute_network.{clean_name}_vpc.name

  allow {{
    protocol = "tcp"
    ports    = ["6443", "443", "80"]
  }}
  
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["{cluster_name}-openshift-controlplane"]
}}

'''

        # Generate control plane nodes
        for i in range(controlplane_count):
            terraform_config += f'''
# OpenShift Control Plane Node {i+1}
resource "google_compute_instance" "{clean_name}_controlplane_{i+1}" {{
  name         = "{cluster_name}-controlplane-{i+1}"
  machine_type = "{controlplane_machine_type}"
  zone         = "{zone}"
  
  boot_disk {{
    initialize_params {{
      image = "rhel-cloud/rhel-9"
      size  = 120
      type  = "pd-ssd"
    }}
  }}
  
  network_interface {{
    subnetwork = google_compute_subnetwork.{clean_name}_subnet.id
    access_config {{
      # Ephemeral external IP
    }}
  }}
  
  tags = ["{cluster_name}-openshift", "{cluster_name}-openshift-controlplane"]
  
  metadata = {{
    ssh-keys = "core:${{var.ssh_public_key}}"
    user-data = base64encode(templatefile("${{path.module}}/openshift-controlplane-userdata.yaml", {{
      cluster_name = "{cluster_name}"
      node_type = "controlplane"
      node_index = {i+1}
    }}))
  }}
  
  labels = {{
    cluster = "{cluster_name}"
    role = "controlplane"
    environment = "production"
    managed_by = "yamlforge"
  }}
}}

'''

        # Generate worker nodes
        for i in range(worker_count):
            terraform_config += f'''
# OpenShift Worker Node {i+1}
resource "google_compute_instance" "{clean_name}_worker_{i+1}" {{
  name         = "{cluster_name}-worker-{i+1}"
  machine_type = "{worker_machine_type}"
  zone         = "{zone}"
  
  boot_disk {{
    initialize_params {{
      image = "rhel-cloud/rhel-9"
      size  = 120
      type  = "pd-ssd"
    }}
  }}
  
  network_interface {{
    subnetwork = google_compute_subnetwork.{clean_name}_subnet.id
    access_config {{
      # Ephemeral external IP
    }}
  }}
  
  tags = ["{cluster_name}-openshift", "{cluster_name}-openshift-worker"]
  
  metadata = {{
    ssh-keys = "core:${{var.ssh_public_key}}"
    user-data = base64encode(templatefile("${{path.module}}/openshift-worker-userdata.yaml", {{
      cluster_name = "{cluster_name}"
      node_type = "worker"
      node_index = {i+1}
    }}))
  }}
  
  labels = {{
    cluster = "{cluster_name}"
    role = "worker"
    environment = "production"
    managed_by = "yamlforge"
  }}
}}

'''

        # Add OpenShift installation automation
        terraform_config += f'''
# OpenShift Installation Configuration
resource "local_file" "{clean_name}_install_config" {{
  filename = "${{path.module}}/{cluster_name}-install-config.yaml"
  
  content = yamlencode({{
    apiVersion = "v1"
    baseDomain = "{cluster_config.get('base_domain')}"
    metadata = {{
      name = "{cluster_name}"
    }}
    compute = [{{
      hyperthreading = "Enabled"
      name = "worker"
      replicas = {worker_count}
    }}]
    controlPlane = {{
      hyperthreading = "Enabled"  
      name = "controlplane"
      replicas = {controlplane_count}
    }}
    networking = {{
      clusterNetwork = [{{
        cidr = "{networking.get('pod_cidr', '10.128.0.0/14')}"
        hostPrefix = 23
      }}]
      serviceNetwork = ["{networking.get('service_cidr', '172.30.0.0/16')}"]
      networkType = "OVNKubernetes"
    }}
    platform = {{
      gcp = {{
        projectID = var.gcp_project_id
        region = "{region}"
      }}
    }}
    pullSecret = var.openshift_pull_secret
    sshKey = var.ssh_public_key
  }})
}}

# OpenShift Installer Automation
resource "null_resource" "{clean_name}_installer" {{
  depends_on = [
    google_compute_instance.{clean_name}_controlplane_1,
    google_compute_instance.{clean_name}_worker_1,
    local_file.{clean_name}_install_config
  ]
  
  provisioner "local-exec" {{
    command = <<-EOT
      # Download OpenShift installer
      curl -L https://mirror.openshift.com/pub/openshift-v4/clients/ocp/{version}/openshift-install-linux.tar.gz | tar -xz
      chmod +x openshift-install
      
      # Create cluster directory
      mkdir -p {cluster_name}-cluster
      cp {cluster_name}-install-config.yaml {cluster_name}-cluster/install-config.yaml
      
      # Generate ignition configs
      ./openshift-install create ignition-configs --dir={cluster_name}-cluster
      
      # The ignition configs will be applied via user-data to the instances
      echo "OpenShift ignition configs generated for {cluster_name}"
    EOT
  }}
}}

'''

        return terraform_config
    
    def generate_aws_self_managed_infrastructure(self, cluster_config: Dict, size_config: Dict, version: str) -> str:
        """Generate AWS infrastructure for self-managed OpenShift"""
        # TODO: Implement AWS self-managed infrastructure
        # This would include VPC, subnets, security groups, EC2 instances, load balancers, etc.
        return f"# TODO: AWS self-managed OpenShift infrastructure for {cluster_config.get('name')}\n"
        
    def generate_azure_self_managed_infrastructure(self, cluster_config: Dict, size_config: Dict, version: str) -> str:
        """Generate Azure infrastructure for self-managed OpenShift"""
        # TODO: Implement Azure self-managed infrastructure  
        # This would include resource groups, vnets, VMs, load balancers, etc.
        return f"# TODO: Azure self-managed OpenShift infrastructure for {cluster_config.get('name')}\n"
        
    def generate_ibm_self_managed_infrastructure(self, cluster_config: Dict, size_config: Dict, version: str) -> str:
        """Generate IBM Cloud infrastructure for self-managed OpenShift"""
        # TODO: Implement IBM self-managed infrastructure
        # This would include VPC/Classic infrastructure, VSIs, load balancers, etc.
        return f"# TODO: IBM self-managed OpenShift infrastructure for {cluster_config.get('name')}\n"
        
    def generate_oci_self_managed_infrastructure(self, cluster_config: Dict, size_config: Dict, version: str) -> str:
        """Generate Oracle Cloud infrastructure for self-managed OpenShift"""
        # TODO: Implement OCI self-managed infrastructure
        # This would include VCN, subnets, compute instances, load balancers, etc.
        return f"# TODO: OCI self-managed OpenShift infrastructure for {cluster_config.get('name')}\n"
        
    def generate_vmware_self_managed_infrastructure(self, cluster_config: Dict, size_config: Dict, version: str) -> str:
        """Generate VMware vSphere infrastructure for self-managed OpenShift"""
        # TODO: Implement VMware self-managed infrastructure
        # This would include VMs, networks, storage, etc.
        return f"# TODO: VMware self-managed OpenShift infrastructure for {cluster_config.get('name')}\n"
        
    def generate_alibaba_self_managed_infrastructure(self, cluster_config: Dict, size_config: Dict, version: str) -> str:
        """Generate Alibaba Cloud infrastructure for self-managed OpenShift"""
        # TODO: Implement Alibaba self-managed infrastructure
        # This would include VPC, VSwitches, ECS instances, load balancers, etc.
        return f"# TODO: Alibaba self-managed OpenShift infrastructure for {cluster_config.get('name')}\n"
    
    def generate_self_managed_on_existing_infrastructure(self, cluster_config: Dict) -> str:
        """Generate OpenShift on existing infrastructure instances"""
        cluster_name = cluster_config.get('name')
        provider = cluster_config.get('provider')
        
        # TODO: Implement OpenShift installation on existing instances
        return f'''
# =============================================================================
# SELF-MANAGED OPENSHIFT ON EXISTING {provider.upper()} INFRASTRUCTURE: {cluster_name}
# =============================================================================

# TODO: Implement OpenShift installation on existing infrastructure
# Referenced instances: {cluster_config.get('infrastructure')}

''' 

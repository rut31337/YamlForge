"""
Core Converter Module

Contains the main YamlForgeConverter class that orchestrates multi-cloud
infrastructure generation using provider-specific implementations.
"""

import os
import re
import yaml
import subprocess
from pathlib import Path

from .credentials import CredentialsManager
from ..providers.aws import AWSProvider
from ..providers.azure import AzureProvider
from ..providers.gcp import GCPProvider
from ..providers.ibm_classic import IBMClassicProvider  # type: ignore
from ..providers.ibm_vpc import IBMVPCProvider  # type: ignore
from ..providers.oci import OCIProvider
from ..providers.vmware import VMwareProvider
from ..providers.alibaba import AlibabaProvider
from ..providers.openshift import OpenShiftProvider


class YamlForgeConverter:
    """Main converter class that orchestrates multi-cloud infrastructure generation."""

    def __init__(self, images_file="mappings/images.yaml"):
        """Initialize the converter with mappings and provider modules."""
        # Check Terraform version early
        self.validate_terraform_version()
        
        self.images = self.load_images(images_file)
        self.locations = self.load_locations("mappings/locations.yaml")
        self.flavors = self.load_flavors("mappings/flavors")
        # Load OpenShift-specific flavors from dedicated directory
        openshift_flavors = self.load_flavors("mappings/flavors_openshift")
        self.flavors.update(openshift_flavors)
        self.cloud_patterns = self.load_cloud_patterns("mappings/cloud_patterns.yaml")
        self.core_config = self.load_core_config("defaults/core.yaml")

        # Initialize credentials manager
        self.credentials = CredentialsManager()

        # Initialize provider modules (GUID will be set when processing YAML)
        self.aws_provider = AWSProvider(self)
        self.azure_provider = AzureProvider(self)
        self.gcp_provider = GCPProvider(self)
        self.ibm_classic_provider = IBMClassicProvider(self)
        self.ibm_vpc_provider = IBMVPCProvider(self)
        self.oci_provider = OCIProvider(self)
        self.vmware_provider = VMwareProvider(self)
        self.alibaba_provider = AlibabaProvider(self)
        
        # Initialize OpenShift provider
        self.openshift_provider = OpenShiftProvider(self)

        # Current YAML data for GUID extraction
        self.current_yaml_data = None

    def _has_rosa_clusters(self, yaml_data):
        """Check if YAML configuration contains any ROSA clusters."""
        if not yaml_data or 'openshift_clusters' not in yaml_data:
            return False
        
        for cluster in yaml_data['openshift_clusters']:
            cluster_type = cluster.get('type', '').lower()
            if cluster_type in ['rosa-classic', 'rosa-hcp', 'rosa']:
                return True
        return False

    def validate_terraform_version(self):
        """Validate that Terraform is installed and meets minimum version requirements."""
        try:
            # Run terraform version command
            result = subprocess.run(['terraform', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                raise ValueError(
                    "❌ Terraform Version Error: Failed to execute 'terraform --version'\n\n"
                    "💡 Please ensure Terraform is installed and available in your PATH:\n\n"
                    "1️⃣  Download and install Terraform:\n"
                    "   https://developer.hashicorp.com/terraform/downloads\n\n"
                    "2️⃣  Or use package managers:\n"
                    "   # macOS (Homebrew)\n"
                    "   brew install terraform\n\n"
                    "   # Linux (Ubuntu/Debian)\n"
                    "   wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg\n"
                    "   echo \"deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main\" | sudo tee /etc/apt/sources.list.d/hashicorp.list\n"
                    "   sudo apt update && sudo apt install terraform\n\n"
                    "3️⃣  Verify installation:\n"
                    "   terraform --version"
                )
            
            # Parse version from output (e.g., "Terraform v1.12.2")
            version_output = result.stdout.strip()
            version_match = re.search(r'Terraform v(\d+)\.(\d+)\.(\d+)', version_output)
            
            if not version_match:
                raise ValueError(
                    f"❌ Terraform Version Error: Could not parse version from output:\n{version_output}\n\n"
                    "💡 Please ensure you have a standard Terraform installation."
                )
            
            major, minor, patch = map(int, version_match.groups())
            current_version = (major, minor, patch)
            
            # Minimum required version: 1.12.0 (based on our testing)
            min_version = (1, 12, 0)
            
            if current_version < min_version:
                current_version_str = f"{major}.{minor}.{patch}"
                min_version_str = f"{min_version[0]}.{min_version[1]}.{min_version[2]}"
                
                raise ValueError(
                    f"❌ Terraform Version Error: Version {current_version_str} is too old\n\n"
                    f"🔄 Required: Terraform v{min_version_str} or newer\n"
                    f"📦 Current: Terraform v{current_version_str}\n\n"
                    "💡 YamlForge requires a modern Terraform version to resolve provider dependencies correctly.\n\n"
                    "🚀 Upgrade Terraform:\n\n"
                    "1️⃣  Download latest version:\n"
                    "   https://developer.hashicorp.com/terraform/downloads\n\n"
                    "2️⃣  Or use tfswitch for easy version management:\n"
                    "   curl -L https://raw.githubusercontent.com/warrensbox/terraform-switcher/release/install.sh | bash\n"
                    "   tfswitch\n\n"
                    "3️⃣  Update via package managers:\n"
                    "   # macOS (Homebrew)\n"
                    "   brew upgrade terraform\n\n"
                    "   # Linux (Ubuntu/Debian)\n"
                    "   sudo apt update && sudo apt upgrade terraform\n\n"
                    "4️⃣  Verify upgrade:\n"
                    "   terraform --version\n\n"
                    "📋 Why this matters: Older Terraform versions have known issues with\n"
                    "   ROSA/OpenShift provider dependency resolution that cause deployment failures."
                )
            
            # Success - version is acceptable
            current_version_str = f"{major}.{minor}.{patch}"
            print(f"Detected Terraform version {current_version_str} (meets minimum requirement)")
            
        except subprocess.TimeoutExpired:
            raise ValueError(
                "❌ Terraform Version Error: Command 'terraform --version' timed out\n\n"
                "💡 This might indicate a problem with your Terraform installation.\n"
                "   Please verify Terraform is properly installed and functional."
            )
        except FileNotFoundError:
            raise ValueError(
                "❌ Terraform Version Error: 'terraform' command not found\n\n"
                "💡 Terraform is required to deploy the generated configurations.\n\n"
                "🚀 Install Terraform:\n\n"
                "1️⃣  Download from official site:\n"
                "   https://developer.hashicorp.com/terraform/downloads\n\n"
                "2️⃣  Or use package managers:\n"
                "   # macOS (Homebrew)\n"
                "   brew install terraform\n\n"
                "   # Linux (Ubuntu/Debian)\n"
                "   wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg\n"
                "   echo \"deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main\" | sudo tee /etc/apt/sources.list.d/hashicorp.list\n"
                "   sudo apt update && sudo apt install terraform\n\n"
                "   # Windows (Chocolatey)\n"
                "   choco install terraform\n\n"
                "3️⃣  Verify installation:\n"
                "   terraform --version\n\n"
                "📋 Note: YamlForge generates Terraform configurations, so Terraform\n"
                "   is essential for deploying your infrastructure."
            )
        except Exception as e:
            raise ValueError(
                f"❌ Terraform Version Error: Unexpected error checking Terraform version:\n{str(e)}\n\n"
                "💡 Please ensure Terraform is properly installed and accessible."
            )

    def get_validated_guid(self, yaml_data=None):
        """Get GUID from environment variable or root-level YAML config with validation."""
        # Try environment variable first (highest priority)
        guid = os.environ.get('GUID', '').strip()
        
        # If not in environment, try to get from YAML root level
        if not guid and yaml_data:
            guid = yaml_data.get('guid', '')
        
        # Validate GUID format if provided
        if guid:
            # Normalize to lowercase first
            guid = guid.lower()
            if not self.validate_guid_format(guid):
                raise ValueError(
                    f"Invalid GUID format: '{guid}'. "
                    f"GUID must be exactly 5 characters, alphanumeric only (a-z, 0-9) "
                    f"to comply with DNS RFC and Kubernetes standards. "
                    f"Examples: 'abc12', 'web01', 'k8s99', '12345'"
                )
            return guid
        else:
            raise ValueError(
                "GUID is required but not provided.\n\n"
                "💡 Please choose one of these options:\n\n"
                "1️⃣  Set environment variable (recommended):\n"
                "   export GUID=web01\n\n"
                "2️⃣  Add to YAML root level:\n"
                "   guid: \"web01\"\n"
                "   yamlforge:\n"
                "     ...\n\n"
                "📋 GUID Requirements:\n"
                "   • Exactly 5 characters\n"
                "   • Lowercase alphanumeric only (a-z, 0-9)\n"
                "   • Examples: web01, app42, test1, dev99\n\n"
                "🎯 Quick Start:\n"
                "   export GUID=test1 && ./yamlforge.py your-config.yaml -d output/"
            )

    def validate_guid_format(self, guid):
        """Validate that GUID meets DNS RFC and Kubernetes standards."""
        if not guid:
            return False
        
        # Must be exactly 5 characters
        if len(guid) != 5:
            return False
        
        # Must be lowercase alphanumeric only (a-z, 0-9)
        if not re.match(r'^[a-z0-9]{5}$', guid):
            return False
        
        return True

    def set_yaml_data(self, yaml_data):
        """Set current YAML data for GUID extraction and notify providers."""
        self.current_yaml_data = yaml_data
        
        # Update GUID in providers that need it
        if hasattr(self.gcp_provider, 'update_guid'):
            self.gcp_provider.update_guid(self.get_validated_guid(yaml_data))

    def load_images(self, file_path):
        """Load image mappings from YAML file."""
        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
                return data.get('images', {})
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Using empty image mappings.")
            return {}



    def load_locations(self, file_path):
        """Load location mappings from YAML file."""
        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
                return data.get('locations', {})
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Using empty location mappings.")
            return {}

    def load_flavors(self, directory_path):
        """Load flavor mappings from directory."""
        flavors = {}
        flavor_dir = Path(directory_path)
        if flavor_dir.exists():
            for file_path in flavor_dir.glob("*.yaml"):
                try:
                    with open(file_path, 'r') as f:
                        data = yaml.safe_load(f)
                        if data:
                            cloud_name = file_path.stem
                            if cloud_name == 'generic':
                                flavors.update(data)
                            else:
                                flavors[cloud_name] = data
                except Exception as e:
                    print(f"Warning: Could not load {file_path}: {e}")
        return flavors

    def load_cloud_patterns(self, file_path):
        """Load cloud-specific flavor patterns from YAML file."""
        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
                return data or {}
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Using empty cloud patterns.")
            return {}

    def load_core_config(self, file_path):
        """Load core yamlforge configuration from YAML file."""
        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
                return data or {}
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Using default core configuration.")
            return self.get_default_core_config()

    def get_default_core_config(self):
        """Get default core configuration when core.yaml is not found."""
        return {
            'provider_selection': {
                'exclude_from_cheapest': [],
                'priority_order': [
                    'oci', 'alibaba', 'gcp', 'aws', 'azure', 
                    'ibm_vpc', 'vmware', 'ibm_classic'
                ]
            },
            'cost_analysis': {
                'default_currency': 'USD',
                'regional_cost_factors': {},
                'provider_cost_factors': {}
            }
        }

    def get_ssh_keys(self, yaml_data):
        """Extract SSH keys from YAML configuration."""
        ssh_keys = yaml_data.get('ssh_keys', {})
        
        # Default SSH key configuration if none provided
        if not ssh_keys:
            return {
                'default': {
                    'public_key': None,
                    'username': 'ec2-user'  # Default username
                }
            }
        
        # Ensure all SSH keys have required fields
        normalized_keys = {}
        for key_name, key_config in ssh_keys.items():
            if isinstance(key_config, str):
                # Simple string format: just the public key
                normalized_keys[key_name] = {
                    'public_key': key_config,
                    'username': 'ec2-user'  # Default username
                }
            elif isinstance(key_config, dict):
                # Full configuration format
                normalized_keys[key_name] = {
                    'public_key': key_config.get('public_key'),
                    'username': key_config.get('username', 'ec2-user'),
                    'comment': key_config.get('comment', '')
                }
        
        return normalized_keys

    def get_default_ssh_key(self, yaml_data):
        """Get the default SSH key for instances."""
        ssh_keys = self.get_ssh_keys(yaml_data)
        
        # Return the first available SSH key as default
        if ssh_keys:
            first_key_name = next(iter(ssh_keys))
            return ssh_keys[first_key_name]
        
        return None

    def get_instance_ssh_key(self, instance, yaml_data):
        """Get SSH key configuration for a specific instance."""
        ssh_keys = self.get_ssh_keys(yaml_data)
        
        # Check if instance specifies a particular SSH key
        instance_ssh_key = instance.get('ssh_key')
        if instance_ssh_key and instance_ssh_key in ssh_keys:
            return ssh_keys[instance_ssh_key]
        
        # Fall back to default SSH key
        return self.get_default_ssh_key(yaml_data)

    def get_effective_providers(self, include_excluded=False):
        """Get list of providers that can be used for cheapest provider selection."""
        all_providers = ['aws', 'azure', 'gcp', 'ibm_vpc', 'ibm_classic', 'oci', 'vmware', 'alibaba']
        
        if include_excluded:
            return all_providers
            
        excluded_providers = self.core_config.get('provider_selection', {}).get('exclude_from_cheapest', [])
        available_providers = [p for p in all_providers if p not in excluded_providers]
        
        return available_providers

    def log_provider_exclusions(self, analysis_type, suppress_output=False):
        """Log information about provider exclusions for cheapest provider selection."""
        if suppress_output:
            return
            
        excluded_providers = self.core_config.get('provider_selection', {}).get('exclude_from_cheapest', [])
        if excluded_providers:
            excluded_list = ', '.join(excluded_providers)
            print(f"ℹ️  Provider exclusions for {analysis_type}: {excluded_list} (excluded from cost comparison)")
            available_providers = self.get_effective_providers()
            available_list = ', '.join(available_providers)
            print(f"✅ Available providers: {available_list}")

    def detect_required_providers(self, yaml_data):
        """Detect which cloud providers are actually being used."""
        providers_in_use = set()

        # Check deployments
        deployments = yaml_data.get('deployments', {})
        for deployment_config in deployments.values():
            provider = deployment_config.get('provider')
            if provider and provider != 'cheapest':
                providers_in_use.add(provider)

        # Check instances
        instances = yaml_data.get('instances', [])
        for instance in instances:
            provider = instance.get('provider')
            if provider:
                # Resolve cheapest provider to actual provider
                if provider == 'cheapest':
                    resolved_provider = self.find_cheapest_provider(instance, suppress_output=True)
                    providers_in_use.add(resolved_provider)
                elif provider == 'cheapest-gpu':
                    resolved_provider = self.find_cheapest_gpu_provider(instance, suppress_output=True)
                    providers_in_use.add(resolved_provider)
                else:
                    providers_in_use.add(provider)

        # Check OpenShift clusters
        openshift_clusters = yaml_data.get('openshift_clusters', [])
        for cluster in openshift_clusters:
            cluster_type = cluster.get('type')
            if cluster_type:
                # Map OpenShift types to underlying cloud providers
                if cluster_type in ['rosa-classic', 'rosa-hcp']:
                    providers_in_use.add('aws')
                elif cluster_type == 'aro':
                    providers_in_use.add('azure')
                elif cluster_type == 'self-managed':
                    # Self-managed uses the specified provider
                    self_managed_provider = cluster.get('provider', 'aws')
                    providers_in_use.add(self_managed_provider)
                elif cluster_type == 'openshift-dedicated':
                    # Dedicated can run on multiple clouds, check cloud_provider
                    cloud_provider = cluster.get('cloud_provider', 'aws')
                    providers_in_use.add(cloud_provider)
                elif cluster_type == 'self-managed':
                    # Self-managed uses existing instances, providers already detected above
                    pass
                elif cluster_type == 'hypershift':
                    # HyperShift worker nodes use the specified provider
                    hypershift_provider = cluster.get('provider', 'aws')
                    providers_in_use.add(hypershift_provider)

        # Check OpenShift clusters and add required providers
        openshift_clusters = yaml_data.get('openshift_clusters', [])
        if openshift_clusters:
            # Always need these for OpenShift
            providers_in_use.update(['kubernetes', 'helm'])
            
            # Check ROSA deployment method to determine if RHCS provider is needed
            rosa_deployment = yaml_data.get('rosa_deployment', {})
            deployment_method = rosa_deployment.get('method', 'terraform')  # default to terraform
            
            for cluster in openshift_clusters:
                cluster_type = cluster.get('type', '')
                
                # ROSA clusters with Terraform method need RHCS provider
                if cluster_type in ['rosa-classic', 'rosa-hcp'] and deployment_method == 'terraform':
                    providers_in_use.add('rhcs')
                
                # Add kubectl for self-managed and HyperShift
                if cluster_type in ['self-managed', 'hypershift']:
                    providers_in_use.add('kubectl')
                
                # Add Azure-specific providers for ARO
                if cluster_type == 'aro':
                    providers_in_use.add('azapi')
                
                # Add cloud provider for the cluster
                if cluster_type in ['rosa-classic', 'rosa-hcp']:
                    providers_in_use.add('aws')
                elif cluster_type == 'aro':
                    providers_in_use.add('azure')
                elif cluster_type == 'openshift-dedicated':
                    cloud_provider = cluster.get('cloud_provider')
                    if cloud_provider:
                        providers_in_use.add(cloud_provider)
                elif cluster_type in ['self-managed', 'hypershift']:
                    cloud_provider = cluster.get('provider')
                    if cloud_provider:
                        providers_in_use.add(cloud_provider)

        return sorted(list(providers_in_use))

    def validate_provider_setup(self, yaml_data):
        """Validate cloud provider setup early to catch issues before processing."""
        required_providers = self.detect_required_providers(yaml_data)
        
        # Check each required provider
        for provider in required_providers:
            if provider == 'aws':
                # Check if user wants to skip validation
                yamlforge_config = yaml_data.get('yamlforge', {})
                aws_config = yamlforge_config.get('aws', {})
                use_data_sources = aws_config.get('use_data_sources', False)
                
                if not use_data_sources:
                    # Only validate if not using data source fallback
                    try:
                        self.aws_provider.validate_aws_setup()
                    except ValueError as e:
                        # Re-raise with context about which instances need AWS
                        aws_instances = []
                        for instance in yaml_data.get('instances', []):
                            instance_provider = instance.get('provider')
                            if instance_provider == 'aws':
                                aws_instances.append(instance.get('name', 'unnamed'))
                            elif instance_provider in ['cheapest', 'cheapest-gpu']:
                                # These might resolve to AWS
                                aws_instances.append(f"{instance.get('name', 'unnamed')} (via {instance_provider})")
                        
                        instance_list = ', '.join(aws_instances) if aws_instances else 'OpenShift clusters'
                        
                        error_msg = str(e).replace("❌ AWS Provider Error:", f"❌ AWS Provider Error (needed for: {instance_list}):")
                        raise ValueError(error_msg) from e
            
            # Add validation for other providers as needed
            # elif provider == 'azure':
            #     self.azure_provider.validate_azure_setup()
            # elif provider == 'gcp':
            #     self.gcp_provider.validate_gcp_setup()

    def validate_instance_names(self, instances):
        """Validate that no two instances have the same name within the same cloud provider."""
        # Track instances by provider
        provider_instances = {}
        
        for instance in instances:
            instance_name = instance.get('name')
            if not instance_name:
                continue
                
            provider = instance.get('provider')
            if not provider:
                continue
                
            # Resolve meta providers to actual providers
            if provider == 'cheapest':
                resolved_provider = self.find_cheapest_provider(instance, suppress_output=True)
            elif provider == 'cheapest-gpu':
                resolved_provider = self.find_cheapest_gpu_provider(instance, suppress_output=True)
            else:
                resolved_provider = provider
            
            # Initialize provider list if not exists
            if resolved_provider not in provider_instances:
                provider_instances[resolved_provider] = []
            
            # Check for duplicate names in this provider
            for existing_instance_name in provider_instances[resolved_provider]:
                if instance_name == existing_instance_name:
                    raise ValueError(
                        f"Error: Duplicate instance name '{instance_name}' found for provider '{resolved_provider}'. "
                        f"Instance names must be unique within each cloud provider to avoid Terraform resource conflicts."
                    )
            
            # Add this instance name to the provider list
            provider_instances[resolved_provider].append(instance_name)

    def generate_terraform_project(self, yaml_data):
        """Generate organized Terraform project files with full regional infrastructure."""
        # Set YAML data for GUID extraction
        self.set_yaml_data(yaml_data)
        
        files = {}
        required_providers = self.detect_required_providers(yaml_data)

        # Generate complete main.tf with regional infrastructure
        main_content = self.generate_complete_terraform(yaml_data, required_providers)

        # Generate variables file
        variables_content = self.generate_variables_tf(required_providers, yaml_data)

        # Generate terraform.tfvars example  
        tfvars_content = self.generate_tfvars_example(required_providers, yaml_data)

        files['main.tf'] = main_content
        files['variables.tf'] = variables_content
        files['terraform.tfvars'] = tfvars_content

        return files

    def generate_complete_terraform(self, yaml_data, required_providers):
        """Generate complete Terraform configuration with regional infrastructure."""
        # Ensure YAML data is set for GUID extraction
        if self.current_yaml_data != yaml_data:
            self.set_yaml_data(yaml_data)
            
        terraform_content = f'''# Generated by YamlForge v2.0 - Regional Multi-Cloud Infrastructure
# Required providers: {', '.join(required_providers)}
# Regional security groups and networking included

terraform {{
  required_version = ">= 1.12.0"
  required_providers {{'''

        # Add provider configurations
        for provider in required_providers:
            if provider == 'aws':
                terraform_content += '''
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }'''
            elif provider == 'azure':
                terraform_content += '''
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }'''
            elif provider == 'gcp':
                terraform_content += '''
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }'''
            elif provider == 'ibm_vpc':
                terraform_content += '''
    ibm = {
      source  = "IBM-Cloud/ibm"
      version = "~> 1.0"
    }'''
            elif provider == 'oci':
                terraform_content += '''
    oci = {
      source  = "oracle/oci"
      version = "~> 5.0"
    }'''
            elif provider == 'vmware':
                terraform_content += '''
    vsphere = {
      source  = "hashicorp/vsphere"
      version = "~> 2.4"
    }'''
            elif provider == 'alibaba':
                terraform_content += '''
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.0"
    }'''
            elif provider == 'rhcs':
                terraform_content += '''
    rhcs = {
      source  = "terraform-redhat/rhcs"
      version = ">= 1.0.1"
    }'''
            elif provider == 'kubernetes':
                terraform_content += '''
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }'''
            elif provider == 'helm':
                terraform_content += '''
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }'''
            elif provider == 'kubectl':
                terraform_content += '''
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = "~> 1.14"
    }'''

        terraform_content += '''
  }
}

'''

        # Add provider configurations for each required provider
        for provider in required_providers:
            if provider == 'aws':
                # Check if we have ROSA Classic clusters that need AWS credentials
                has_rosa_classic = False
                if yaml_data and 'openshift_clusters' in yaml_data:
                    for cluster in yaml_data['openshift_clusters']:
                        if cluster.get('type') == 'rosa-classic':
                            has_rosa_classic = True
                            break
                
                terraform_content += '''# AWS Provider Configuration
provider "aws" {
  region = var.aws_region
}

# AWS Caller Identity for account information
data "aws_caller_identity" "current" {}

'''
            elif provider == 'azure':
                terraform_content += '''# Azure Provider Configuration
provider "azurerm" {
  features {}
  subscription_id = var.azure_subscription_id
}

'''
            elif provider == 'gcp':
                terraform_content += '''# GCP Provider Configuration
provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

'''
            elif provider == 'ibm_vpc':
                terraform_content += '''# IBM Cloud Provider Configuration
provider "ibm" {
  region = var.ibm_region
}

'''
            elif provider == 'oci':
                terraform_content += '''# Oracle Cloud Infrastructure Provider Configuration
provider "oci" {
  tenancy_ocid     = var.oci_tenancy_ocid
  user_ocid        = var.oci_user_ocid
  fingerprint      = var.oci_fingerprint
  private_key_path = var.oci_private_key_path
  region           = var.oci_region
}

'''
            elif provider == 'vmware':
                terraform_content += '''# VMware vSphere Provider Configuration
provider "vsphere" {
  user           = var.vmware_user
  password       = var.vmware_password
  vsphere_server = var.vmware_server

  allow_unverified_ssl = var.vmware_allow_unverified_ssl
}

'''
            elif provider == 'alibaba':
                terraform_content += '''# Alibaba Cloud Provider Configuration
provider "alicloud" {
  access_key = var.alibaba_access_key
  secret_key = var.alibaba_secret_key
  region     = var.alibaba_region
}

'''
            elif provider == 'rhcs':
                terraform_content += '''# Red Hat Cloud Services Provider Configuration
provider "rhcs" {
  token = var.rhcs_token
  url   = var.rhcs_url
}

'''

        # Generate GCP project management if GCP is used
        if 'gcp' in required_providers:
            # Check if we have user management configuration
            users = yaml_data.get('users', [])
            cloud_workspace = yaml_data.get('yamlforge', {}).get('cloud_workspace', {})
            
            if users or cloud_workspace:
                terraform_content += self.gcp_provider.generate_project_management(yaml_data)

        # Generate regional networking infrastructure
        terraform_content += '''# ========================================
# Regional Networking Infrastructure
# ========================================

'''
        terraform_content += self.generate_regional_networking(yaml_data)

        # Generate regional security groups
        terraform_content += '''
# ========================================
# Regional Security Groups
# ========================================

'''
        terraform_content += self.generate_regional_security_groups(yaml_data)

        # Generate VM instances
        terraform_content += '''
# ========================================
# Virtual Machine Instances
# ========================================

'''
        instances = yaml_data.get('instances', [])
        
        # Validate for duplicate instance names within same provider
        self.validate_instance_names(instances)
        
        for i, instance in enumerate(instances):
            terraform_content += self.generate_virtual_machine(instance, i+1, yaml_data)

        # ROSA clusters use ROSA CLI instead of Terraform providers

        # Generate OpenShift clusters
        terraform_content += '''
# ========================================
# OpenShift Clusters
# ========================================

'''
        terraform_content += self.openshift_provider.generate_openshift_clusters(yaml_data)

        return terraform_content

    def generate_variables_tf(self, required_providers, yaml_data=None):
        """Generate variables.tf file with variables for required providers."""
        variables_content = '''# Variables for multi-cloud deployment
# Generated by YamlForge v2.0
# SSH keys are configured in YAML and embedded directly in resources

'''

        if 'aws' in required_providers:
            variables_content += '''# AWS Variables
variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

# ROSA clusters use ROSA CLI - no AWS account ID variable needed

# Official Red Hat Terraform modules handle AWS billing account ID automatically

# ROSA clusters use ROSA CLI for authentication and cluster creation
# AWS credentials are configured via environment variables or AWS profiles

'''

        if 'azure' in required_providers:
            variables_content += '''# Azure Variables
variable "azure_subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "azure_location" {
  description = "Azure location for deployment"
  type        = string
  default     = "East US"
}

'''

        if 'gcp' in required_providers:
            variables_content += '''# GCP Variables
variable "gcp_project_id" {
  description = "GCP project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP region for deployment"
  type        = string
  default     = "us-east1"
}

'''

        if 'ibm_vpc' in required_providers:
            variables_content += '''# IBM Cloud Variables
variable "ibm_region" {
  description = "IBM Cloud region for deployment"
  type        = string
  default     = "us-south"
}

'''

        if 'oci' in required_providers:
            variables_content += '''# Oracle Cloud Infrastructure Variables
variable "oci_tenancy_ocid" {
  description = "OCI tenancy OCID"
  type        = string
}

variable "oci_user_ocid" {
  description = "OCI user OCID"
  type        = string
}

variable "oci_fingerprint" {
  description = "OCI API key fingerprint"
  type        = string
}

variable "oci_private_key_path" {
  description = "Path to OCI private key file"
  type        = string
}

variable "oci_region" {
  description = "OCI region for deployment"
  type        = string
  default     = "us-ashburn-1"
}

variable "oci_compartment_id" {
  description = "OCI compartment OCID"
  type        = string
}

'''

        if 'vmware' in required_providers:
            variables_content += '''# VMware vSphere Variables
variable "vmware_user" {
  description = "VMware vSphere username"
  type        = string
}

variable "vmware_password" {
  description = "VMware vSphere password"
  type        = string
  sensitive   = true
}

variable "vmware_server" {
  description = "VMware vSphere server hostname or IP"
  type        = string
}

variable "vmware_datacenter" {
  description = "VMware vSphere datacenter name"
  type        = string
  default     = "Datacenter"
}

variable "vmware_cluster" {
  description = "VMware vSphere cluster name"
  type        = string
  default     = "Cluster"
}

variable "vmware_datastore" {
  description = "VMware vSphere datastore name"
  type        = string
  default     = "datastore1"
}

variable "vmware_network" {
  description = "VMware vSphere network name"
  type        = string
  default     = "VM Network"
}

variable "vmware_allow_unverified_ssl" {
  description = "Allow unverified SSL certificates for vSphere"
  type        = bool
  default     = true
}

'''

        if 'alibaba' in required_providers:
            variables_content += '''# Alibaba Cloud Variables
variable "alibaba_access_key" {
  description = "Alibaba Cloud access key"
  type        = string
  sensitive   = true
}

variable "alibaba_secret_key" {
  description = "Alibaba Cloud secret key"
  type        = string
  sensitive   = true
}

variable "alibaba_region" {
  description = "Alibaba Cloud region for deployment"
  type        = string
  default     = "cn-hangzhou"
}

'''

        if 'rhcs' in required_providers:
            variables_content += '''# Red Hat Cloud Services Variables
variable "rhcs_token" {
  description = "Red Hat OpenShift Cluster Manager offline token"
  type        = string
  sensitive   = true
}

variable "rhcs_url" {
  description = "Red Hat OpenShift Cluster Manager URL"
  type        = string
  default     = "https://api.openshift.com"
}

'''

                # Add OpenShift variables if clusters are present
        if yaml_data:
            openshift_clusters = yaml_data.get('openshift_clusters', [])
            if openshift_clusters:
                variables_content += self.openshift_provider.generate_openshift_variables(openshift_clusters)

        # Add common infrastructure variables
        variables_content += '''# =============================================================================
# COMMON INFRASTRUCTURE VARIABLES
# =============================================================================

variable "ssh_public_key" {
  description = "SSH public key for instance access"
  type        = string
}

variable "key_name" {
  description = "Name of the SSH key pair"
  type        = string
  default     = "default-key"
}

variable "environment" {
  description = "Environment tag for resources"
  type        = string
  default     = "development"
}

'''

        return variables_content

    def generate_tfvars_example(self, required_providers, yaml_data=None):
        """Generate terraform.tfvars example file."""
        # Get default SSH key
        ssh_key_info = self.credentials.get_default_ssh_key()
        
        tfvars_content = '''# Terraform Variables Configuration
# Copy this file to terraform.tfvars and customize with your values
# Generated by YamlForge v2.0

'''
        
        # Add SSH key section
        if ssh_key_info.get('available'):
            # Mask the SSH key for security (show first 20 and last 10 characters)
            ssh_key = ssh_key_info.get('public_key', '')
            if len(ssh_key) > 40:
                masked_key = ssh_key[:20] + "..." + ssh_key[-10:]
            else:
                masked_key = ssh_key[:10] + "..." if len(ssh_key) > 10 else ssh_key
                
            tfvars_content += f'''# SSH public key for instance access
# Automatically detected from: {ssh_key_info.get('source')}
ssh_public_key = "{ssh_key}"

'''
        else:
            tfvars_content += '''# SSH public key for instance access (required)
# Set SSH_PUBLIC_KEY environment variable or add to defaults/core.yaml
# Examples:
#   export SSH_PUBLIC_KEY="$(cat ~/.ssh/id_rsa.pub)"
#   export SSH_PUBLIC_KEY="ssh-rsa AAAAB3NzaC1yc2EAAAA... user@host"
ssh_public_key = "ssh-rsa AAAAB3NzaC1yc2EAAAA... your-public-key-here"

'''

        if 'aws' in required_providers:
            # Get AWS credentials with auto-discovery
            aws_creds = self.credentials.get_aws_credentials()
            
            tfvars_content += '''# =============================================================================
# AWS CONFIGURATION
# =============================================================================

'''
            
            # Try to auto-detect AWS credentials from environment variables
            access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
            secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
            aws_region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
            aws_billing_account_id = os.getenv('AWS_BILLING_ACCOUNT_ID')
            

            
            # ROSA CLI uses AWS credentials from environment variables or AWS CLI profiles
            tfvars_content += f'''# AWS Region Configuration
aws_region = "{aws_region}"

# ROSA CLI uses AWS credentials from environment variables or AWS CLI profiles
# No need to set aws_access_key_id or aws_secret_access_key in Terraform

'''
            
            # AWS account information - try environment variables first, then AWS SDK
            account_id_from_env = None
            user_arn_from_env = None
            billing_account_id = aws_billing_account_id
            
            if aws_creds.get('available'):
                # Use auto-discovered values from AWS SDK
                account_id_from_env = aws_creds.get('account_id')
                user_arn_from_env = aws_creds.get('user_arn', '')
                # Use environment variable for billing account ID if set, otherwise use account ID
                billing_account_id = billing_account_id or account_id_from_env
                
                tfvars_content += f'''# AWS Account Information (auto-detected from AWS credentials)
# ROSA clusters use ROSA CLI for authentication and cluster creation
# aws_account_id        = "{account_id_from_env}"
# aws_billing_account_id = "{billing_account_id}"

'''
            else:
                # Fall back to environment variables if AWS SDK not available
                if billing_account_id:
                    tfvars_content += f'''# AWS Account Information (partially from environment variables)
# aws_account_id        = "your-account-id"  # AWS SDK not available
# Official Red Hat modules automatically handle AWS account information
# aws_rosa_creator_arn  = "arn:aws:iam::account:user/your-username"

# ROSA clusters use ROSA CLI for authentication (no manual role configuration needed)
# aws_rosa_installer_role_arn = "arn:aws:iam::your-account-id:role/ManagedOpenShift-Installer-Role"
# aws_rosa_support_role_arn   = "arn:aws:iam::your-account-id:role/ManagedOpenShift-Support-Role"
# aws_rosa_worker_role_arn    = "arn:aws:iam::your-account-id:role/ManagedOpenShift-Worker-Role"
# aws_rosa_master_role_arn    = "arn:aws:iam::your-account-id:role/ManagedOpenShift-ControlPlane-Role"

'''
                else:
                    tfvars_content += '''# AWS Account Information for ROSA Clusters
# ROSA clusters use ROSA CLI for authentication and cluster creation
# AWS credentials configured via environment variables or AWS CLI profiles

'''

        if 'azure' in required_providers:
            tfvars_content += '''# Azure Configuration
azure_subscription_id = "your-subscription-id-here"
azure_location        = "East US"

'''

        if 'gcp' in required_providers:
            tfvars_content += '''# GCP Configuration
gcp_project_id = "your-project-id-here"
gcp_region     = "us-east1"

'''

        if 'ibm_vpc' in required_providers:
            tfvars_content += '''# IBM Cloud Configuration
ibm_region = "us-south"

'''

        if 'oci' in required_providers:
            tfvars_content += '''# Oracle Cloud Infrastructure Configuration
oci_tenancy_ocid     = "ocid1.tenancy.oc1..aaaaaaaaa..."
oci_user_ocid        = "ocid1.user.oc1..aaaaaaaaa..."
oci_fingerprint      = "aa:bb:cc:dd:ee:ff:gg:hh:ii:jj:kk:ll:mm:nn:oo:pp"
oci_private_key_path = "~/.oci/oci_api_key.pem"
oci_region           = "us-ashburn-1"
oci_compartment_id   = "ocid1.compartment.oc1..aaaaaaaaa..."

'''

        if 'vmware' in required_providers:
            tfvars_content += '''# VMware vSphere Configuration
vmware_user                   = "administrator@vsphere.local"
vmware_password              = "your-password-here"
vmware_server                = "vcenter.example.com"
vmware_datacenter            = "Datacenter"
vmware_cluster               = "Cluster"
vmware_datastore             = "datastore1"
vmware_network               = "VM Network"
vmware_allow_unverified_ssl  = true

'''

        if 'alibaba' in required_providers:
            tfvars_content += '''# Alibaba Cloud Configuration
alibaba_access_key = "LTAI4G..."
alibaba_secret_key = "your-secret-key-here"
alibaba_region     = "cn-hangzhou"

'''

        if 'rhcs' in required_providers:
            # Try to get RHCS token from environment variable
            rhcs_token = os.getenv('REDHAT_OPENSHIFT_TOKEN') or os.getenv('ROSA_TOKEN') or os.getenv('OCM_TOKEN')
            
            tfvars_content += '''# =============================================================================
# RED HAT CLOUD SERVICES CONFIGURATION
# =============================================================================

'''
            
            if rhcs_token:
                # Mask the token for security (show first 10 and last 10 characters)
                if len(rhcs_token) > 30:
                    masked_token = rhcs_token[:10] + "..." + rhcs_token[-10:]
                else:
                    masked_token = rhcs_token[:5] + "..." if len(rhcs_token) > 10 else rhcs_token
                
                tfvars_content += f'''# Red Hat OpenShift Cluster Manager Token
# Automatically detected from environment variable
rhcs_token = "{rhcs_token}"
rhcs_url   = "https://api.openshift.com"

'''
            else:
                tfvars_content += '''# Red Hat OpenShift Cluster Manager Token (required for ROSA)
# Get your token from: https://console.redhat.com/openshift/token/rosa
# Set REDHAT_OPENSHIFT_TOKEN environment variable or configure here
rhcs_token = "your-offline-token-here"
rhcs_url   = "https://api.openshift.com"

'''

        # Add OpenShift credentials if OpenShift clusters are present  
        # Note: yaml_data is not available in this method, check if rhcs provider is in required_providers
        has_openshift = 'rhcs' in required_providers
        if has_openshift:
            tfvars_content += '''# =============================================================================
# RED HAT OPENSHIFT CLUSTER MANAGER CREDENTIALS
# =============================================================================

'''
            
            # Try to auto-detect Red Hat OpenShift token from multiple sources
            redhat_token = (
                os.getenv('REDHAT_OPENSHIFT_TOKEN') or 
                os.getenv('OCM_TOKEN') or 
                os.getenv('ROSA_TOKEN')
            )
            redhat_url = os.getenv('REDHAT_OPENSHIFT_URL', 'https://api.openshift.com')
            
            if redhat_token:
                tfvars_content += f'''# Red Hat OpenShift credentials (auto-detected from environment)
redhat_openshift_token = "{redhat_token}"
redhat_openshift_url   = "{redhat_url}"

'''
            else:
                tfvars_content += '''# Red Hat OpenShift credentials (required for ROSA clusters)
# Get your token from: https://console.redhat.com/openshift/token
# Set environment variable: REDHAT_OPENSHIFT_TOKEN, OCM_TOKEN, or ROSA_TOKEN
# Or uncomment and fill in:
# redhat_openshift_token = "your_offline_token_from_console.redhat.com"
# redhat_openshift_url   = "https://api.openshift.com"

'''

        return tfvars_content

    def convert(self, config, output_dir, verbose=False):
        """Convert YAML configuration to Terraform and write files to output directory."""
        self.verbose = verbose
        # Set YAML data for GUID extraction
        self.set_yaml_data(config)
        
        # Validate cloud provider setup early
        self.validate_provider_setup(config)
        
        required_providers = self.detect_required_providers(config)


        # Generate the complete terraform configuration
        terraform_config = self.generate_complete_terraform(config, required_providers)
        
        # Write the main.tf file
        main_tf_path = os.path.join(output_dir, 'main.tf')
        with open(main_tf_path, 'w') as f:
            f.write(terraform_config)
        
        # Generate and write variables.tf
        variables_config = self.generate_variables_tf(required_providers, config)
        variables_path = os.path.join(output_dir, 'variables.tf')
        with open(variables_path, 'w') as f:
            f.write(variables_config)
        
        # Generate and write terraform.tfvars
        tfvars_config = self.generate_tfvars_example(required_providers, config)
        tfvars_path = os.path.join(output_dir, 'terraform.tfvars')
        with open(tfvars_path, 'w') as f:
            f.write(tfvars_config)
            
        # Generate ROSA CLI setup script if ROSA clusters are present
        if self.openshift_provider._has_rosa_clusters(config):
            rosa_script = self.openshift_provider.generate_rosa_cli_script(config)
            script_path = os.path.join(output_dir, 'rosa-setup.sh')
            with open(script_path, 'w') as f:
                f.write(rosa_script)
            # Make script executable
            os.chmod(script_path, 0o755)
            
            # Generate ROSA cleanup script
            cleanup_script = self.openshift_provider.generate_rosa_cleanup_script(config)
            if cleanup_script:
                cleanup_path = os.path.join(output_dir, 'rosa-cleanup.sh')
                with open(cleanup_path, 'w') as f:
                    f.write(cleanup_script)
                # Make script executable
                os.chmod(cleanup_path, 0o755)
            
            if self.verbose:
                print(f"Generated files:")
                print(f"  - {main_tf_path}")
                print(f"  - {variables_path}")
                print(f"  - {tfvars_path}")
                print(f"  - {script_path}")
                if cleanup_script:
                    print(f"  - {cleanup_path}")
        else:
            if self.verbose:
                print(f"Generated files:")
                print(f"  - {main_tf_path}")
                print(f"  - {variables_path}")
                print(f"  - {tfvars_path}")

    def convert_yaml_to_terraform(self, config):
        """Convert YAML configuration to Terraform (compatibility method)."""
        # Set YAML data for GUID extraction
        self.set_yaml_data(config)
        
        required_providers = self.detect_required_providers(config)

        # Use the complete terraform generation for full functionality
        return self.generate_complete_terraform(config, required_providers)

    def clean_name(self, name):
        """Clean a name for use as a Terraform resource identifier."""
        if not name:
            return "unnamed"
        return name.replace("-", "_").replace(".", "_").replace(" ", "_")

    def resolve_instance_region(self, instance, provider):
        """Resolve instance region with support for both direct regions and mapped locations."""
        has_region = 'region' in instance
        has_location = 'location' in instance
        instance_name = instance.get('name', 'unnamed')

        if has_region and has_location:
            raise ValueError(f"Instance '{instance_name}' cannot specify both 'region' and 'location'.")

        if not has_region and not has_location:
            raise ValueError(f"Instance '{instance_name}' must specify either 'region' or 'location'.")

        if has_region:
            return instance['region']

        if has_location:
            location_key = instance['location']
            if location_key in self.locations:
                provider_location = self.locations[location_key].get(provider)
                if provider_location:
                    return provider_location
            return location_key

    def find_closest_flavor(self, cores, memory_mb, gpus=None, gpu_type=None):
        """Find the closest matching generic flavor for given hardware requirements."""
        memory_gb = memory_mb / 1024
        
        best_matches = []
        
        # Check all generic flavors
        for flavor_name, flavor_config in self.flavors.items():
            # Skip provider-specific flavors (they're nested dictionaries)
            if isinstance(flavor_config, dict) and 'description' in flavor_config:
                # This is a generic flavor
                
                # Check if it has the required providers (we need at least one provider mapping)
                available_providers = [p for p in ['aws', 'azure', 'gcp', 'ibm_vpc', 'ibm_classic'] if p in flavor_config]
                if not available_providers:
                    continue
                
                # Analyze this flavor across providers to get average specs
                total_vcpus = 0
                total_memory = 0
                total_gpus = 0
                gpu_types_found = set()
                valid_providers = 0
                
                for provider in available_providers:
                    instance_type = flavor_config[provider]
                    provider_flavors = self.flavors.get(provider, {})
                    
                    # Try to get specs from provider flavor mappings
                    specs = self.get_instance_specs_from_provider(provider, instance_type, flavor_name, provider_flavors)
                    if specs:
                        total_vcpus += specs.get('vcpus', 0)
                        total_memory += specs.get('memory_gb', 0) 
                        total_gpus += specs.get('gpu_count', 0)
                        if specs.get('gpu_type'):
                            gpu_types_found.add(specs['gpu_type'])
                        valid_providers += 1
                
                if valid_providers == 0:
                    continue
                
                # Calculate average specs
                avg_vcpus = total_vcpus / valid_providers
                avg_memory = total_memory / valid_providers
                avg_gpus = total_gpus / valid_providers
                
                # Check if this flavor meets requirements
                meets_cpu = avg_vcpus >= cores
                meets_memory = avg_memory >= memory_gb
                meets_gpu_count = gpus is None or avg_gpus >= gpus
                meets_gpu_type = gpu_type is None or any(self.gpu_type_matches(found_type, gpu_type) for found_type in gpu_types_found)
                
                if meets_cpu and meets_memory and meets_gpu_count and meets_gpu_type:
                    # Calculate efficiency score (lower is better - means less over-provisioning)
                    cpu_overhead = avg_vcpus - cores
                    memory_overhead = avg_memory - memory_gb
                    gpu_overhead = avg_gpus - (gpus or 0)
                    
                    # Weighted efficiency score
                    efficiency_score = (cpu_overhead * 1.0) + (memory_overhead * 0.5) + (gpu_overhead * 2.0)
                    
                    # If no GPU was requested, heavily penalize GPU flavors to prefer non-GPU options
                    if gpus is None and avg_gpus > 0:
                        efficiency_score += 1000  # Heavy penalty for unwanted GPU
                    
                    # Prefer generic flavors over GPU-specific flavors when appropriate
                    is_gpu_flavor = any(gpu_prefix in flavor_name for gpu_prefix in ['gpu_', 'gpu_t4_', 'gpu_v100_', 'gpu_a100_', 'gpu_amd_'])
                    if gpus is None and is_gpu_flavor:
                        efficiency_score += 500  # Medium penalty for GPU-specific flavors when no GPU requested
                    
                    best_matches.append({
                        'flavor': flavor_name,
                        'avg_vcpus': avg_vcpus,
                        'avg_memory_gb': avg_memory,
                        'avg_gpus': avg_gpus,
                        'gpu_types': list(gpu_types_found),
                        'efficiency_score': efficiency_score,
                        'cpu_overhead': cpu_overhead,
                        'memory_overhead': memory_overhead,
                        'gpu_overhead': gpu_overhead,
                        'available_providers': available_providers,
                        'is_gpu_flavor': is_gpu_flavor
                    })
        
        if not best_matches:
            return None
        
        # Sort by efficiency score (best match first)
        best_matches.sort(key=lambda x: x['efficiency_score'])
        return best_matches[0]

    def get_instance_specs_from_provider(self, provider, instance_type, flavor_name, provider_flavors):
        """Get instance specifications from provider flavor mappings."""
        # Check flavor mappings first
        flavor_mappings = provider_flavors.get('flavor_mappings', {})
        for size_category, size_options in flavor_mappings.items():
            if instance_type in size_options:
                return size_options[instance_type]
        
        # Check direct machine type mappings (for GCP)
        machine_types = provider_flavors.get('machine_types', {})
        if instance_type in machine_types:
            return machine_types[instance_type]
        
        return None

    def find_cheapest_provider(self, instance, suppress_output=False):
        """Find the cheapest cloud provider for given instance requirements."""
        size = instance.get("size")
        cores = instance.get("cores")
        memory = instance.get("memory")  # in MB
        gpu_count = instance.get("gpu_count")  # Number of GPUs required
        gpu_type = instance.get("gpu_type")  # Specific GPU type requirement
        find_flavor = instance.get("find_flavor", False)  # NEW: Auto-find closest flavor
        
        # Validate GPU type if specified
        if gpu_type:
            self.validate_gpu_type(gpu_type)
        
        # NEW: Auto-find closest flavor if requested
        if find_flavor and cores and memory:
            closest_flavor = self.find_closest_flavor(cores, memory, gpu_count, gpu_type)
            if closest_flavor:
                memory_gb = memory / 1024
                req_desc = f"{cores} cores, {memory_gb:.1f}GB RAM"
                if gpu_count and gpu_type:
                    req_desc += f", {gpu_count} {gpu_type} GPU(s)"
                elif gpu_count:
                    req_desc += f", {gpu_count} GPU(s)"
                
                print(f"📋 Auto-matched flavor for {req_desc}:")
                print(f"  🎯 Recommended flavor: {closest_flavor['flavor']}")
                print(f"  📊 Avg specs: {closest_flavor['avg_vcpus']:.1f} vCPUs, {closest_flavor['avg_memory_gb']:.1f}GB RAM", end="")
                if closest_flavor['avg_gpus'] > 0:
                    gpu_info = f", {closest_flavor['avg_gpus']:.1f} GPUs"
                    if closest_flavor['gpu_types']:
                        gpu_info += f" ({', '.join(closest_flavor['gpu_types'])})"
                    print(gpu_info)
                else:
                    print()
                print(f"  ✅ Available on: {', '.join(closest_flavor['available_providers'])}")
                
                # Use the found flavor instead of specs
                size = closest_flavor['flavor']
                # Clear the hardware specs since we're now using flavor
                cores = None
                memory = None
        
        # Get cost information for all providers
        provider_costs = {}
        
        if size:
            # Size-based selection (existing functionality)
            provider_costs = self.find_cheapest_by_size(size, gpu_type)
            analysis_type = f"size '{size}'"
            if gpu_type:
                analysis_type += f" with {gpu_type} GPU"
        elif cores and memory:
            # Hardware specification-based selection (with optional GPU)
            provider_costs = self.find_cheapest_by_specs(cores, memory, gpu_count, gpu_type)
            memory_gb = memory / 1024
            
            if gpu_count and gpu_type:
                analysis_type = f"{cores} cores, {memory_gb:.1f}GB RAM, {gpu_count} {gpu_type} GPU(s)"
            elif gpu_count:
                analysis_type = f"{cores} cores, {memory_gb:.1f}GB RAM, {gpu_count} GPU(s)"
            else:
                analysis_type = f"{cores} cores, {memory_gb:.1f}GB RAM"
        else:
            # Fallback to medium size
            print("Warning: Instance must specify either 'size' or 'cores' and 'memory', defaulting to medium size")
            provider_costs = self.find_cheapest_by_size("medium")
            analysis_type = "size 'medium' (default)"
        
        if not provider_costs:
            # Fallback to AWS if no cost information available
            if not suppress_output:
                print(f"Warning: No cost information found for {analysis_type}, defaulting to AWS")
            return 'aws'
        
        # Find the cheapest provider
        cheapest_provider = min(provider_costs.keys(), key=lambda p: provider_costs[p]['cost'])
        
        # Only print cost analysis if not suppressed
        if not suppress_output:
            instance_name = instance.get('name', 'unnamed')
            # Log provider exclusions if any
            self.log_provider_exclusions("cheapest provider selection", suppress_output)
            print(f"Cost analysis for instance '{instance_name}' ({analysis_type}):")
            for provider, info in sorted(provider_costs.items(), key=lambda x: x[1]['cost']):
                marker = " ← SELECTED" if provider == cheapest_provider else ""
                vcpus = info.get('vcpus', 'N/A')
                memory_gb = info.get('memory_gb', 'N/A')
                gpu_count = info.get('gpu_count', 0)
                detected_gpu_type = info.get('gpu_type', '')
                
                if gpu_count > 0:
                    gpu_info = f", {gpu_count}x {detected_gpu_type}" if detected_gpu_type else f", {gpu_count} GPU(s)"
                    print(f"  {provider}: ${info['cost']:.4f}/hour ({info['instance_type']}, {vcpus} vCPU, {memory_gb}GB{gpu_info}){marker}")
                else:
                    print(f"  {provider}: ${info['cost']:.4f}/hour ({info['instance_type']}, {vcpus} vCPU, {memory_gb}GB){marker}")
        
        return cheapest_provider
    
    def find_cheapest_gpu_provider(self, instance, suppress_output=False):
        """Find the cheapest cloud provider for GPU instances, ignoring cores/memory requirements."""
        gpu_type = instance.get("gpu_type")  # Specific GPU type requirement
        
        # Validate GPU type if specified
        if gpu_type:
            self.validate_gpu_type(gpu_type)
        
        # Get cost information for all providers (GPU instances only)
        provider_costs = self.find_cheapest_gpu_by_specs(gpu_type)
        
        if gpu_type:
            analysis_type = f"cheapest {gpu_type} GPU"
        else:
            analysis_type = "cheapest GPU (any type)"
        
        if not provider_costs:
            # Fallback to AWS if no cost information available
            if not suppress_output:
                print(f"Warning: No GPU cost information found for {analysis_type}, defaulting to AWS")
            return 'aws'
        
        # Find the cheapest provider
        cheapest_provider = min(provider_costs.keys(), key=lambda p: provider_costs[p]['cost'])
        
        # Only print cost analysis if not suppressed
        if not suppress_output:
            instance_name = instance.get('name', 'unnamed')
            # Log provider exclusions if any
            self.log_provider_exclusions("cheapest GPU provider selection", suppress_output)
            print(f"GPU-optimized cost analysis for instance '{instance_name}' ({analysis_type}):")
            for provider, info in sorted(provider_costs.items(), key=lambda x: x[1]['cost']):
                marker = " ← SELECTED" if provider == cheapest_provider else ""
                vcpus = info.get('vcpus', 'N/A')
                memory_gb = info.get('memory_gb', 'N/A')
                gpu_count = info.get('gpu_count', 0)
                detected_gpu_type = info.get('gpu_type', '')
                
                gpu_info = f", {gpu_count}x {detected_gpu_type}" if detected_gpu_type else f", {gpu_count} GPU(s)"
                print(f"  {provider}: ${info['cost']:.4f}/hour ({info['instance_type']}, {vcpus} vCPU, {memory_gb}GB{gpu_info}){marker}")
        
        return cheapest_provider
    
    def find_cheapest_gpu_by_specs(self, gpu_type=None):
        """Find cheapest GPU instances across all providers, ignoring CPU/memory constraints."""
        provider_costs = {}
        
        # Get available providers (excluding those configured to be excluded from cheapest)
        available_providers = self.get_effective_providers()
        
        # Check each provider's flavor mappings for GPU instances
        for provider in available_providers:
            provider_flavors = self.flavors.get(provider, {})
            best_option = None
            
            # Check flavor mappings for GPU options
            flavor_mappings = provider_flavors.get('flavor_mappings', {})
            for size_category, size_options in flavor_mappings.items():
                for instance_type, specs in size_options.items():
                    vcpus = specs.get('vcpus', 0)
                    memory_gb = specs.get('memory_gb', 0)
                    gpus = specs.get('gpu_count', 0)
                    cost = specs.get('hourly_cost')
                    instance_gpu_type = specs.get('gpu_type', '')
                    
                    # Only consider instances with GPUs
                    if gpus <= 0 or cost is None:
                        continue
                    
                    # If specific GPU type is required, check GPU type match
                    if gpu_type and not self.gpu_type_matches(instance_gpu_type, gpu_type):
                        continue
                    
                    # If this is cheaper than current best option, use it
                    if best_option is None or cost < best_option['cost']:
                        best_option = {
                            'cost': cost,
                            'instance_type': instance_type,
                            'vcpus': vcpus,
                            'memory_gb': memory_gb,
                            'gpu_count': gpus,
                            'gpu_type': instance_gpu_type,
                            'gpu_memory_gb': specs.get('gpu_memory_gb')
                        }
            
            # Also check direct machine type mappings (for GCP)
            machine_types = provider_flavors.get('machine_types', {})
            for instance_type, specs in machine_types.items():
                vcpus = specs.get('vcpus', 0)
                memory_gb = specs.get('memory_gb', 0)
                gpus = specs.get('gpu_count', 0)
                cost = specs.get('hourly_cost')
                instance_gpu_type = specs.get('gpu_type', '')
                
                # Only consider instances with GPUs
                if gpus <= 0 or cost is None:
                    continue
                
                # If specific GPU type is required, check GPU type match
                if gpu_type and not self.gpu_type_matches(instance_gpu_type, gpu_type):
                    continue
                
                # If this is cheaper than current best option, use it
                if best_option is None or cost < best_option['cost']:
                    best_option = {
                        'cost': cost,
                        'instance_type': instance_type,
                        'vcpus': vcpus,
                        'memory_gb': memory_gb,
                        'gpu_count': gpus,
                        'gpu_type': instance_gpu_type,
                        'gpu_memory_gb': specs.get('gpu_memory_gb')
                    }
            
            if best_option:
                provider_costs[provider] = best_option
        
        return provider_costs

    def get_cheapest_gpu_instance_type(self, instance, provider):
        """Get the cheapest GPU instance type for the selected provider."""
        gpu_type = instance.get("gpu_type")
        
        # Find the cheapest GPU option for this provider
        provider_costs = self.find_cheapest_gpu_by_specs(gpu_type)
        
        if provider in provider_costs:
            return provider_costs[provider]['instance_type']
        
        # Fallback to default GPU instance type
        provider_flavors = self.flavors.get(provider, {})
        
        # Try to find a default GPU instance
        flavor_mappings = provider_flavors.get('flavor_mappings', {})
        for size_category, size_options in flavor_mappings.items():
            for instance_type, specs in size_options.items():
                if specs.get('gpu_count', 0) > 0:
                    return instance_type
        
        # Final fallback
        return "gpu_small"  # This should be mapped in flavor files
    
    def find_cheapest_by_size(self, size, gpu_type=None):
        """Find cheapest provider for a generic size, optionally filtered by GPU type."""
        provider_costs = {}
        
        # Get available providers (excluding those configured to be excluded from cheapest)
        available_providers = self.get_effective_providers()
        
        # Check generic flavors for cost comparison
        if size in self.flavors:
            generic_flavor = self.flavors[size]
            
            # Calculate costs for each provider
            for provider in available_providers:
                if provider in generic_flavor:
                    instance_type = generic_flavor[provider]
                    
                    # Look up cost in provider-specific flavor mappings
                    provider_flavors = self.flavors.get(provider, {})
                    cost_info = self.get_instance_cost_info(provider, instance_type, size, provider_flavors)
                    
                    if cost_info:
                        # Filter by GPU type if specified
                        if gpu_type:
                            instance_gpu_type = cost_info.get('gpu_type', '')
                            # Normalize GPU type comparison (case-insensitive, partial match)
                            if not self.gpu_type_matches(instance_gpu_type, gpu_type):
                                continue
                        
                        provider_costs[provider] = cost_info
        
        return provider_costs
    
    def find_cheapest_by_specs(self, required_cores, required_memory_mb, required_gpus=None, gpu_type=None):
        """Find cheapest provider for specific CPU/memory/GPU requirements."""
        provider_costs = {}
        required_memory_gb = required_memory_mb / 1024
        
        # Get available providers (excluding those configured to be excluded from cheapest)
        available_providers = self.get_effective_providers()
        
        # Check each provider's flavor mappings for instances that meet requirements
        for provider in available_providers:
            provider_flavors = self.flavors.get(provider, {})
            best_option = None
            
            # Check flavor mappings for options that meet requirements
            flavor_mappings = provider_flavors.get('flavor_mappings', {})
            for size_category, size_options in flavor_mappings.items():
                for instance_type, specs in size_options.items():
                    vcpus = specs.get('vcpus', 0)
                    memory_gb = specs.get('memory_gb', 0)
                    gpus = specs.get('gpu_count', 0)
                    cost = specs.get('hourly_cost')
                    instance_gpu_type = specs.get('gpu_type', '')
                    
                    # Check if this instance meets requirements
                    meets_requirements = (
                        vcpus >= required_cores and 
                        memory_gb >= required_memory_gb and 
                        cost is not None
                    )
                    
                    # If GPU is required, check GPU requirements
                    if required_gpus is not None:
                        meets_requirements = meets_requirements and gpus >= required_gpus
                    
                    # If specific GPU type is required, check GPU type match
                    if gpu_type and gpus > 0:
                        meets_requirements = meets_requirements and self.gpu_type_matches(instance_gpu_type, gpu_type)
                    
                    if meets_requirements:
                        # If this is cheaper than current best option, use it
                        if best_option is None or cost < best_option['cost']:
                            best_option = {
                                'cost': cost,
                                'instance_type': instance_type,
                                'vcpus': vcpus,
                                'memory_gb': memory_gb,
                                'gpus': gpus,
                                'gpu_type': instance_gpu_type,
                                'gpu_memory_gb': specs.get('gpu_memory_gb')
                            }
            
            # Also check direct machine type mappings (for GCP)
            machine_types = provider_flavors.get('machine_types', {})
            for instance_type, specs in machine_types.items():
                vcpus = specs.get('vcpus', 0)
                memory_gb = specs.get('memory_gb', 0)
                gpus = specs.get('gpu_count', 0)
                cost = specs.get('hourly_cost')
                instance_gpu_type = specs.get('gpu_type', '')
                
                # Check if this instance meets requirements
                meets_requirements = (
                    vcpus >= required_cores and 
                    memory_gb >= required_memory_gb and 
                    cost is not None
                )
                
                # If GPU is required, check GPU requirements
                if required_gpus is not None:
                    meets_requirements = meets_requirements and gpus >= required_gpus
                
                # If specific GPU type is required, check GPU type match
                if gpu_type and gpus > 0:
                    meets_requirements = meets_requirements and self.gpu_type_matches(instance_gpu_type, gpu_type)
                
                if meets_requirements:
                    # If this is cheaper than current best option, use it
                    if best_option is None or cost < best_option['cost']:
                        best_option = {
                            'cost': cost,
                            'instance_type': instance_type,
                            'vcpus': vcpus,
                            'memory_gb': memory_gb,
                            'gpus': gpus,
                            'gpu_type': instance_gpu_type,
                            'gpu_memory_gb': specs.get('gpu_memory_gb')
                        }
            
            if best_option:
                provider_costs[provider] = best_option
        
        return provider_costs
    
    def gpu_type_matches(self, instance_gpu_type, required_gpu_type):
        """Check if instance GPU type matches the required GPU type."""
        if not instance_gpu_type or not required_gpu_type:
            return False
        
        # Normalize for comparison (case-insensitive)
        instance_type = instance_gpu_type.upper().strip()
        required_type = required_gpu_type.upper().strip()
        
        # Handle common GPU type patterns
        gpu_patterns = {
            'NVIDIA T4': ['T4', 'NVIDIA T4'],
            'NVIDIA V100': ['V100', 'NVIDIA V100'],
            'NVIDIA A100': ['A100', 'NVIDIA A100'],
            'NVIDIA L4': ['L4', 'NVIDIA L4'],
            'NVIDIA L40S': ['L40S', 'NVIDIA L40S'],
            'AMD RADEON PRO V520': ['AMD', 'RADEON', 'V520', 'AMD RADEON PRO V520'],
            'NVIDIA K80': ['K80', 'NVIDIA K80']
        }
        
        # Check for direct match
        if required_type in instance_type or instance_type in required_type:
            return True
        
        # Check pattern matches
        for full_name, patterns in gpu_patterns.items():
            if required_type in patterns or required_type == full_name:
                return any(pattern in instance_type for pattern in patterns)
        
        return False
    
    def validate_gpu_type(self, requested_gpu_type):
        """Validate that the requested GPU type exists in our flavor mappings."""
        available_gpu_types = set()
        
        # Collect all GPU types from all providers (don't exclude any for validation)
        all_providers = ['aws', 'azure', 'gcp', 'ibm_vpc', 'ibm_classic', 'oci', 'vmware', 'alibaba']
        for provider in all_providers:
            provider_flavors = self.flavors.get(provider, {})
            
            # Check flavor mappings
            flavor_mappings = provider_flavors.get('flavor_mappings', {})
            for size_category, size_options in flavor_mappings.items():
                for instance_type, specs in size_options.items():
                    gpu_type = specs.get('gpu_type')
                    if gpu_type:
                        available_gpu_types.add(gpu_type)
            
            # Check direct machine type mappings (for GCP)
            machine_types = provider_flavors.get('machine_types', {})
            for instance_type, specs in machine_types.items():
                gpu_type = specs.get('gpu_type')
                if gpu_type:
                    available_gpu_types.add(gpu_type)
        
        # Check if requested GPU type matches any available GPU type
        normalized_requested = requested_gpu_type.upper().strip()
        
        for available_gpu in available_gpu_types:
            if self.gpu_type_matches(available_gpu, requested_gpu_type):
                return  # GPU type is valid
        
        # GPU type not found - provide helpful error message
        sorted_gpu_types = sorted(list(available_gpu_types))
        
        # Group GPU types by vendor for better readability
        nvidia_gpus = [gpu for gpu in sorted_gpu_types if 'NVIDIA' in gpu.upper()]
        amd_gpus = [gpu for gpu in sorted_gpu_types if 'AMD' in gpu.upper() or 'RADEON' in gpu.upper()]
        other_gpus = [gpu for gpu in sorted_gpu_types if gpu not in nvidia_gpus and gpu not in amd_gpus]
        
        error_message = f"GPU type '{requested_gpu_type}' is not available in any cloud provider. "
        error_message += f"Available GPU types:\n\n"
        
        if nvidia_gpus:
            error_message += f"NVIDIA GPUs:\n"
            for gpu in nvidia_gpus:
                error_message += f"  - {gpu}\n"
            error_message += f"\n"
        
        if amd_gpus:
            error_message += f"AMD GPUs:\n"
            for gpu in amd_gpus:
                error_message += f"  - {gpu}\n"
            error_message += f"\n"
        
        if other_gpus:
            error_message += f"Other GPUs:\n"
            for gpu in other_gpus:
                error_message += f"  - {gpu}\n"
            error_message += f"\n"
        
        error_message += f"Consider using:\n"
        error_message += f"  - Exact GPU name from the list above\n"
        error_message += f"  - Short GPU name (e.g., 'T4', 'V100', 'A100')\n"
        error_message += f"  - Generic GPU size: gpu_small, gpu_medium, gpu_large\n"
        error_message += f"  - Remove gpu_type to find cheapest GPU regardless of type"
        
        raise ValueError(error_message)
    
    def get_cheapest_instance_type(self, instance, provider):
        """Get the specific instance type selected by cheapest provider analysis."""
        size = instance.get("size")
        cores = instance.get("cores")
        memory = instance.get("memory")
        gpu_count = instance.get("gpu_count")
        
        if size:
            # Size-based selection
            provider_costs = self.find_cheapest_by_size(size)
        elif cores and memory:
            # Hardware specification-based selection
            provider_costs = self.find_cheapest_by_specs(cores, memory, gpu_count)
        else:
            # Fallback
            provider_costs = self.find_cheapest_by_size("medium")
        
        if provider in provider_costs:
            return provider_costs[provider]['instance_type']
        
        return None
    
    def resolve_instance_type(self, provider, size, instance):
        """Resolve instance type based on provider, size, and instance specifications."""
        # Check if instance specifies instance_type directly
        direct_type = instance.get("instance_type")
        if direct_type:
            return direct_type
        
        # Map generic size to provider-specific instance type
        if size in self.flavors:
            generic_flavor = self.flavors[size]
            if provider in generic_flavor:
                return generic_flavor[provider]
            else:
                # Check if this is a GPU flavor that doesn't support this provider
                if any(gpu_prefix in size for gpu_prefix in ['gpu_', 'gpu_t4_', 'gpu_v100_', 'gpu_a100_', 'gpu_amd_']):
                    available_providers = list(generic_flavor.keys())
                    
                    # Special handling for AMD GPUs
                    if 'gpu_amd_' in size:
                        raise ValueError(
                            f"AMD GPU flavor '{size}' is only available on AWS. "
                            f"Provider '{provider}' does not support AMD GPUs. "
                            f"Consider using:\n"
                            f"  - AWS provider: provider: 'aws'\n"
                            f"  - Different GPU type: gpu_t4_small, gpu_v100_small, etc.\n"
                            f"  - Cost optimization: provider: 'cheapest' with gpu_type: 'AMD Radeon Pro V520'"
                        )
                    else:
                        # General GPU flavor not available on provider
                        raise ValueError(
                            f"GPU flavor '{size}' is not available on provider '{provider}'. "
                            f"Available providers for {size}: {', '.join(available_providers)}. "
                            f"Consider using:\n"
                            f"  - Supported provider: {', '.join(available_providers)}\n"
                            f"  - Cost optimization: provider: 'cheapest'\n"
                            f"  - Hardware specification: cores + memory + gpus"
                        )
        
        # Check provider-specific flavor mappings
        provider_flavors = self.flavors.get(provider, {})
        flavor_mappings = provider_flavors.get('flavor_mappings', {})
        
        if size in flavor_mappings:
            size_options = flavor_mappings[size]
            # Return the first (usually cheapest) option
            if size_options:
                return next(iter(size_options.keys()))
        
        # Fallback to provider defaults
        defaults = {
            'aws': 't3.medium',
            'azure': 'Standard_B2ms',
            'gcp': 'e2-medium',
            'ibm_vpc': 'bx2-2x8',
            'ibm_classic': 'B1_2X4X25'
        }
        
        return defaults.get(provider, 't3.medium')
    
    def get_instance_cost_info(self, provider, instance_type, size, provider_flavors):
        """Get detailed cost and specification information for a specific instance type."""
        # Look in provider-specific flavor mappings
        flavor_mappings = provider_flavors.get('flavor_mappings', {})
        
        if size in flavor_mappings:
            size_options = flavor_mappings[size]
            # Find the instance type in the size category
            for type_name, type_info in size_options.items():
                if type_name == instance_type:
                    cost = type_info.get('hourly_cost')
                    if cost is not None:
                        return {
                            'cost': cost,
                            'instance_type': instance_type,
                            'vcpus': type_info.get('vcpus'),
                            'memory_gb': type_info.get('memory_gb')
                        }
        
        # Check direct machine type mapping for GCP
        if 'machine_types' in provider_flavors and instance_type in provider_flavors['machine_types']:
            type_info = provider_flavors['machine_types'][instance_type]
            cost = type_info.get('hourly_cost')
            if cost is not None:
                return {
                    'cost': cost,
                    'instance_type': instance_type,
                    'vcpus': type_info.get('vcpus'),
                    'memory_gb': type_info.get('memory_gb')
                }
        
        return None
    
    def get_instance_cost(self, provider, instance_type, size, provider_flavors):
        """Get hourly cost for a specific instance type (legacy method)."""
        cost_info = self.get_instance_cost_info(provider, instance_type, size, provider_flavors)
        return cost_info['cost'] if cost_info else None

    # Placeholder methods for provider delegation
    def generate_virtual_machine(self, instance, index, yaml_data, available_subnets=None):
        """Generate virtual machine configuration using provider modules."""
        provider = instance.get("provider")
        if not provider:
            raise ValueError("Instance must specify a 'provider'")

        # Handle cheapest provider meta-provider
        selected_instance_type = None
        if provider == 'cheapest':
            original_provider = provider
            provider = self.find_cheapest_provider(instance)
            # Update the instance with the selected provider for consistency
            instance = instance.copy()
            instance['provider'] = provider
            
            # Get the selected instance type from cheapest provider analysis
            selected_instance_type = self.get_cheapest_instance_type(instance, provider)
            print(f"Selected cheapest provider: {provider}")
        elif provider == 'cheapest-gpu':
            original_provider = provider
            provider = self.find_cheapest_gpu_provider(instance)
            # Update the instance with the selected provider for consistency
            instance = instance.copy()
            instance['provider'] = provider
            
            # Get the selected instance type from cheapest GPU provider analysis
            selected_instance_type = self.get_cheapest_gpu_instance_type(instance, provider)
            print(f"Selected cheapest GPU provider: {provider}")

        clean_name = self.clean_name(instance.get("name", f"instance_{index}"))
        size = instance.get("size", "medium")
        
        # Determine instance type (priority: direct specification > cheapest selection > size mapping)
        instance_type = instance.get("instance_type") or selected_instance_type or self.resolve_instance_type(provider, size, instance)

        if provider == 'aws':
            strategy_info = {'instance_type': instance_type, 'architecture': 'x86_64'}
            return self.aws_provider.generate_aws_vm(instance, index, clean_name, strategy_info, available_subnets, yaml_data)
        elif provider == 'azure':
            return self.azure_provider.generate_azure_vm(instance, index, clean_name, instance_type or size, available_subnets, yaml_data)
        elif provider == 'gcp':
            return self.gcp_provider.generate_gcp_vm(instance, index, clean_name, instance_type or size, available_subnets, yaml_data)
        elif provider == 'oci':
            return self.oci_provider.generate_oci_vm(instance, index, clean_name, instance_type or size, available_subnets, yaml_data)
        elif provider == 'vmware':
            return self.vmware_provider.generate_vmware_vm(instance, index, clean_name, instance_type or size, available_subnets, yaml_data)
        elif provider == 'alibaba':
            return self.alibaba_provider.generate_alibaba_vm(instance, index, clean_name, instance_type or size, available_subnets, yaml_data)
        elif provider in ['ibm_vpc', 'ibm_classic']:
            if provider == 'ibm_vpc':
                return self.ibm_vpc_provider.generate_ibm_vpc_vm(instance, index, clean_name, instance_type or size, yaml_data)
            else:
                return self.ibm_classic_provider.generate_ibm_classic_vm(instance, index, clean_name, instance_type or size, yaml_data)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    # Security Group and Networking Methods
    def get_instance_security_groups(self, instance):
        """Get security group references for an instance with regional awareness."""
        provider = instance.get('provider')
        region = self.resolve_instance_region(instance, provider)
        sg_names = instance.get('security_groups', [])

        # Generate regional security group references
        regional_sg_refs = []
        for sg_name in sg_names:
            # Create region-specific security group reference
            clean_sg_name = self.get_regional_sg_name(sg_name, provider, region)
            regional_sg_refs.append(clean_sg_name)

        return regional_sg_refs

    def get_regional_sg_name(self, sg_name, provider, region):
        """Generate region-specific security group name."""
        clean_sg = sg_name.replace("-", "_").replace(".", "_")
        clean_region = region.replace("-", "_").replace(".", "_")
        return f"{clean_sg}_{clean_region}"

    def get_instance_subnet(self, instance, available_subnets):
        """Get subnet for this instance with regional awareness."""
        provider = instance.get('provider')
        if provider in ['aws', 'azure', 'gcp', 'ibm_vpc']:  # Regional providers
            region = self.resolve_instance_region(instance, provider)
            if region:
                clean_region = region.replace("-", "_").replace(".", "_")
            else:
                clean_region = "default"

            subnet_name = instance.get('subnet')
            if subnet_name and subnet_name in available_subnets:
                # Return custom subnet reference with regional suffix
                clean_subnet = subnet_name.replace("-", "_").replace(".", "_")
                return f"{clean_subnet}_{clean_region}"

            # Return regional main subnet
            return f"main_subnet_{clean_region}"
        else:
            # Non-regional providers (like ibm_classic)
            return "main_subnet"

    def generate_native_security_group_rule(self, rule, provider):
        """Generate native security group rule data for specified provider."""
        # Parse rule data
        protocol = rule.get('protocol', 'tcp').lower()
        port = rule.get('port')
        from_port = rule.get('from_port', port)
        to_port = rule.get('to_port', port)
        direction = rule.get('direction', 'ingress')

        # Handle source/destination
        source = rule.get('source', rule.get('cidr', '0.0.0.0/0'))
        if isinstance(source, str):
            cidr_blocks = [source]
        else:
            cidr_blocks = source if source else ['0.0.0.0/0']

        # Convert protocol for different providers
        if provider == 'azure':
            if protocol == 'tcp':
                protocol = 'Tcp'
            elif protocol == 'udp':
                protocol = 'Udp'
            elif protocol == 'icmp':
                protocol = 'Icmp'

        return {
            'direction': direction,
            'from_port': from_port or 80,
            'to_port': to_port or 80,
            'protocol': protocol,
            'cidr_blocks': cidr_blocks
        }

    def analyze_regional_security_groups(self, config):
        """Analyze which security groups are needed in which regions."""
        regional_sgs = {}
        
        # Convert security groups list to dictionary for easier lookup
        security_groups_raw = config.get('security_groups', [])
        security_groups = {}
        
        # Handle both list and dictionary formats
        if isinstance(security_groups_raw, list):
            for sg in security_groups_raw:
                if isinstance(sg, dict) and 'name' in sg:
                    security_groups[sg['name']] = sg
        elif isinstance(security_groups_raw, dict):
            security_groups = security_groups_raw

        # Analyze instances to determine SG regional requirements
        for instance in config.get('instances', []):
            provider = instance.get('provider')
            if provider in ['aws', 'azure', 'gcp', 'ibm_vpc']:  # Regional providers
                region = self.resolve_instance_region(instance, provider)

                # Track which SGs are needed in this region
                if region not in regional_sgs:
                    regional_sgs[region] = {'provider': provider, 'security_groups': set()}

                for sg_name in instance.get('security_groups', []):
                    if sg_name in security_groups:
                        regional_sgs[region]['security_groups'].add(sg_name)

        return regional_sgs

    def generate_regional_security_groups(self, config):
        """Generate security groups for each region where they're needed."""
        regional_analysis = self.analyze_regional_security_groups(config)
        
        # Convert security groups list to dictionary for easier lookup (same as in analyze method)
        security_groups_raw = config.get('security_groups', [])
        security_groups = {}
        
        # Handle both list and dictionary formats
        if isinstance(security_groups_raw, list):
            for sg in security_groups_raw:
                if isinstance(sg, dict) and 'name' in sg:
                    security_groups[sg['name']] = sg
        elif isinstance(security_groups_raw, dict):
            security_groups = security_groups_raw
            
        sg_terraform = ""

        for region, region_data in regional_analysis.items():
            provider = region_data['provider']

            for sg_name in region_data['security_groups']:
                sg_config = security_groups[sg_name]
                rules = sg_config.get('rules', [])

                # Generate region-specific security group
                if provider == 'aws':
                    sg_terraform += self.aws_provider.generate_aws_security_group(sg_name, rules, region, config)
                elif provider == 'azure':
                    sg_terraform += self.azure_provider.generate_azure_security_group(sg_name, rules, region, config)
                elif provider == 'gcp':
                    sg_terraform += self.gcp_provider.generate_gcp_firewall_rules(sg_name, rules, region)
                elif provider == 'ibm_vpc':
                    sg_terraform += self.ibm_vpc_provider.generate_ibm_security_group(sg_name, rules, region, config)
                elif provider == 'oci':
                    sg_terraform += self.oci_provider.generate_oci_security_group(sg_name, rules, region, config)
                elif provider == 'alibaba':
                    sg_terraform += self.alibaba_provider.generate_alibaba_security_group(sg_name, rules, region, config)

        return sg_terraform

    def analyze_regional_instances(self, config):
        """Analyze which regions have instances deployed and need networking."""
        regional_instances = {}
        
        # Analyze instances to determine regional networking requirements
        for instance in config.get('instances', []):
            provider = instance.get('provider')
            
            # Resolve meta providers to actual providers
            if provider == 'cheapest':
                provider = self.find_cheapest_provider(instance, suppress_output=True)
            elif provider == 'cheapest-gpu':
                provider = self.find_cheapest_gpu_provider(instance, suppress_output=True)
            
            if provider in ['aws', 'azure', 'gcp', 'ibm_vpc']:  # Regional providers
                region = self.resolve_instance_region(instance, provider)

                # Track regions that need networking
                if region not in regional_instances:
                    regional_instances[region] = {'provider': provider, 'instances': []}
                
                regional_instances[region]['instances'].append(instance)

        return regional_instances

    def generate_regional_networking(self, config):
        """Generate networking infrastructure for each region where instances are deployed."""
        regional_analysis = self.analyze_regional_instances(config)
        networking_terraform = ""

        for region, region_data in regional_analysis.items():
            provider = region_data['provider']
            # Get deployment name from cloud_workspace
            cloud_workspace = config.get('cloud_workspace', {})
            deployment_name = cloud_workspace.get('name', 'yamlforge-deployment')
            deployment_config = config.get('network', {})

            # Generate regional networking
            if provider == 'aws':
                networking_terraform += self.aws_provider.generate_aws_networking(deployment_name, deployment_config, region, config)
            elif provider == 'azure':
                networking_terraform += self.azure_provider.generate_azure_networking(deployment_name, deployment_config, region, config)
            elif provider == 'gcp':
                networking_terraform += self.gcp_provider.generate_gcp_networking(deployment_name, deployment_config, region)
            elif provider == 'ibm_vpc':
                networking_terraform += self.ibm_vpc_provider.generate_ibm_vpc_networking(deployment_name, deployment_config, region, config)
            elif provider == 'ibm_classic':
                networking_terraform += self.ibm_classic_provider.generate_ibm_classic_networking(deployment_name, deployment_config, region, config)
            elif provider == 'oci':
                networking_terraform += self.oci_provider.generate_oci_networking(deployment_name, deployment_config, region, config)
            elif provider == 'vmware':
                networking_terraform += self.vmware_provider.generate_vmware_networking(deployment_name, deployment_config, region, config)
            elif provider == 'alibaba':
                networking_terraform += self.alibaba_provider.generate_alibaba_networking(deployment_name, deployment_config, region, config)

        return networking_terraform

    def get_instance_gcp_firewall_refs(self, instance):
        """Get GCP firewall tag references for an instance."""
        # For GCP, security groups become firewall tags
        sg_names = instance.get('security_groups', [])
        return sg_names  # GCP uses the security group names directly as tags

    def extract_rhel_info(self, image_key):
        """Extract RHEL version and architecture from image key."""
        import re
        
        # Default values
        default_version = "9"
        default_arch = "x86_64"
        
        # Try to extract RHEL version from the image key
        # Patterns to match: RHEL-9, RHEL-10.0, RHEL-8.9, RHEL9, RHEL10, etc.
        rhel_patterns = [
            r'RHEL-?(\d+(?:\.\d+)?)',  # RHEL-10.0, RHEL-9, RHEL9, etc.
            r'rhel-?(\d+(?:\.\d+)?)',  # rhel-10.0, rhel-9, rhel9, etc.
        ]
        
        version = default_version
        for pattern in rhel_patterns:
            match = re.search(pattern, image_key, re.IGNORECASE)
            if match:
                version = match.group(1)
                break
        
        # Try to extract architecture from the image key
        # Common patterns: x86_64, amd64, arm64, aarch64
        arch_patterns = [
            r'(x86_64|amd64)',     # x86_64 or amd64
            r'(arm64|aarch64)',    # ARM 64-bit
        ]
        
        architecture = default_arch
        for pattern in arch_patterns:
            match = re.search(pattern, image_key, re.IGNORECASE)
            if match:
                architecture = match.group(1)
                # Normalize architecture names
                if architecture.lower() in ['amd64']:
                    architecture = 'x86_64'
                elif architecture.lower() in ['aarch64']:
                    architecture = 'arm64'
                break
        
        return version, architecture

    def extract_fedora_version(self, image_key):
        """Extract Fedora version from image key."""
        import re
        
        # Default version
        default_version = "39"
        
        # Try to extract Fedora version from the image key
        # Patterns to match: Fedora-39, Fedora39, FEDORA-40, etc.
        fedora_patterns = [
            r'fedora-?(\d+)',  # fedora-39, fedora39, etc.
            r'FEDORA-?(\d+)',  # FEDORA-39, FEDORA39, etc.
        ]
        
        for pattern in fedora_patterns:
            match = re.search(pattern, image_key)
            if match:
                return match.group(1)
        
        return default_version

    def generate_rhel_pattern_config(self, image_key):
        """Generate RHEL pattern configuration for dynamic discovery."""
        # Extract RHEL info to generate appropriate pattern
        rhel_version, architecture = self.extract_rhel_info(image_key)
        
        # Determine if this is a GOLD/BYOS image
        is_gold = "GOLD" in image_key.upper() or "BYOS" in image_key.upper()
        
        if is_gold:
            name_pattern = f"RHEL-{rhel_version}*_HVM*Access*"
            owner_key = "redhat_gold"
        else:
            name_pattern = f"RHEL-{rhel_version}*_HVM*"
            owner_key = "redhat_public"
        
        return {
            'name_pattern': name_pattern,
            'owner_key': owner_key,
            'architecture': architecture
        }

    def determine_default_owner_key(self, image_key):
        """Determine default owner key for image discovery."""
        return "redhat_public"

    def generate_ami_data_source(self, image_key, instance_name, architecture):
        """Generate AWS AMI data source."""
        return ""
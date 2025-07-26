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

    def __init__(self, images_file="mappings/images.yaml", analyze_mode=False):
        """Initialize the converter with mappings and provider modules."""
        # Check Terraform version early (skip if in analyze mode)
        if not analyze_mode:
            self.validate_terraform_version()
        
        self.images = self.load_images(images_file)
        self.locations = self.load_locations("mappings/locations.yaml")
        self.flavors = self.load_flavors("mappings/flavors")
        # Load OpenShift-specific flavors from dedicated directory
        openshift_flavors = self.load_flavors("mappings/flavors_openshift")
        self.flavors.update(openshift_flavors)

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
        
        # Cache for resolved regions to prevent multiple validations
        self._region_cache = {}
        
        # No-credentials mode flag (set by main.py)
        self.no_credentials = False

    def get_aws_provider(self):
        """Return the AWS provider instance for use by other components."""
        return self.aws_provider

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
                    "Terraform Version Error: Failed to execute 'terraform --version'\n\n"
                    "Please ensure Terraform is installed and available in your PATH:\n\n"
                    "1. Download and install Terraform:\n"
                    "   https://developer.hashicorp.com/terraform/downloads\n\n"
                    "2. Or use package managers:\n"
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
                    f"Terraform Version Error: Could not parse version from output:\n{version_output}\n\n"
                    "Please ensure you have a standard Terraform installation."
                )
            
            major, minor, patch = map(int, version_match.groups())
            current_version = (major, minor, patch)
            
            # Minimum required version: 1.12.0 (based on our testing)
            min_version = (1, 12, 0)
            
            if current_version < min_version:
                current_version_str = f"{major}.{minor}.{patch}"
                min_version_str = f"{min_version[0]}.{min_version[1]}.{min_version[2]}"
                
                raise ValueError(
                    f"Terraform Version Error: Version {current_version_str} is too old\n\n"
                    f"Required: Terraform v{min_version_str} or newer\n"
                    f"Current: Terraform v{current_version_str}\n\n"
                    "YamlForge requires a modern Terraform version to resolve provider dependencies correctly.\n\n"
                    "Upgrade Terraform:\n\n"
                    "1. Download latest version:\n"
                    "   https://developer.hashicorp.com/terraform/downloads\n\n"
                    "2. Or use tfswitch for easy version management:\n"
                    "   curl -L https://raw.githubusercontent.com/warrensbox/terraform-switcher/release/install.sh | bash\n"
                    "   tfswitch\n\n"
                    "3. Update via package managers:\n"
                    "   # macOS (Homebrew)\n"
                    "   brew upgrade terraform\n\n"
                    "   # Linux (Ubuntu/Debian)\n"
                    "   sudo apt update && sudo apt upgrade terraform\n\n"
                    "4. Verify upgrade:\n"
                    "   terraform --version\n\n"
                    "Why this matters: Older Terraform versions have known issues with\n"
                    "   ROSA/OpenShift provider dependency resolution that cause deployment failures."
                )
            
            # Success - version is acceptable
            current_version_str = f"{major}.{minor}.{patch}"
            print(f"Detected Terraform version {current_version_str} (meets minimum requirement)")
            
        except subprocess.TimeoutExpired:
            raise ValueError(
                "Terraform Version Error: Command 'terraform --version' timed out\n\n"
                "This might indicate a problem with your Terraform installation.\n"
                "   Please verify Terraform is properly installed and functional."
            )
        except FileNotFoundError:
            raise ValueError(
                "Terraform Version Error: 'terraform' command not found\n\n"
                "Terraform is required to deploy the generated configurations.\n\n"
                "Install Terraform:\n\n"
                "1. Download from official site:\n"
                "   https://developer.hashicorp.com/terraform/downloads\n\n"
                "2. Or use package managers:\n"
                "   # macOS (Homebrew)\n"
                "   brew install terraform\n\n"
                "   # Linux (Ubuntu/Debian)\n"
                "   wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg\n"
                "   echo \"deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main\" | sudo tee /etc/apt/sources.list.d/hashicorp.list\n"
                "   sudo apt update && sudo apt install terraform\n\n"
                "   # Windows (Chocolatey)\n"
                "   choco install terraform\n\n"
                "3. Verify installation:\n"
                "   terraform --version\n\n"
                "Note: YamlForge generates Terraform configurations, so Terraform\n"
                "   is essential for deploying your infrastructure."
            )
        except Exception as e:
            raise ValueError(
                f"Terraform Version Error: Unexpected error checking Terraform version:\n{str(e)}\n\n"
                "Please ensure Terraform is properly installed and accessible."
            )

    def get_validated_guid(self, yaml_data=None):
        """Get GUID from environment variable or root-level YAML config with validation."""
        # Return cached GUID if already validated
        if hasattr(self, '_validated_guid') and self._validated_guid:
            return self._validated_guid
        
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
            # Cache the validated GUID
            self._validated_guid = guid
            return guid
        else:
            # In analyze mode, return a placeholder instead of raising an error
            if hasattr(self, 'analyze_mode') and self.analyze_mode:
                return "analyze"
            else:
                raise ValueError(
                    "GUID is required but not provided.\n\n"
                    "Please choose one of these options:\n\n"
                    "1. Set environment variable (recommended):\n"
                    "   export GUID=web01\n\n"
                    "2. Add to YAML root level:\n"
                    "   guid: \"web01\"\n"
                    "   yamlforge:\n"
                    "     ...\n\n"
                    "GUID Requirements:\n"
                    "   • Exactly 5 characters\n"
                    "   • Lowercase alphanumeric only (a-z, 0-9)\n"
                    "   • Examples: web01, app42, test1, dev99\n\n"
                    "Quick Start:\n"
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
            try:
                guid = self.get_validated_guid(yaml_data)
                self.gcp_provider.update_guid(guid)
            except Exception as e:
                # Only raise if we don't already have a valid GUID
                if not hasattr(self, '_validated_guid') or not self._validated_guid:
                    raise

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
                return data or {}
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
            # Try to get SSH key from environment variables via credentials system
            from yamlforge.core.credentials import CredentialsManager
            creds_manager = CredentialsManager()
            default_ssh_key = creds_manager.get_default_ssh_key()
            
            if default_ssh_key and default_ssh_key.get('available'):
                return {
                    'default': {
                        'public_key': default_ssh_key['public_key'],
                        'username': 'cloud-user'  # Default username
                    }
                }
            else:
                return {
                    'default': {
                        'public_key': None,
                        'username': 'cloud-user'  # Default username
                    }
                }
        
        # Ensure all SSH keys have required fields
        normalized_keys = {}
        for key_name, key_config in ssh_keys.items():
            if isinstance(key_config, str):
                # Simple string format: just the public key
                normalized_keys[key_name] = {
                    'public_key': key_config,
                    'username': 'cloud-user'  # Default username
                }
            elif isinstance(key_config, dict):
                # Full configuration format
                normalized_keys[key_name] = {
                    'public_key': key_config.get('public_key'),
                    'username': key_config.get('username', 'cloud-user'),
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

    def get_effective_providers(self, include_excluded=False, instance_exclusions=None):
        """Get list of providers that can be used for cheapest provider selection."""
        all_providers = ['aws', 'azure', 'gcp', 'ibm_vpc', 'ibm_classic', 'oci', 'vmware', 'alibaba']
        
        if include_excluded:
            return all_providers
            
        # Start with global exclusions from core config
        excluded_providers = self.core_config.get('provider_selection', {}).get('exclude_from_cheapest', [])
        
        # Add instance-specific exclusions if provided
        if instance_exclusions:
            excluded_providers = list(set(excluded_providers + instance_exclusions))
        
        available_providers = [p for p in all_providers if p not in excluded_providers]
        
        return available_providers

    def log_provider_exclusions(self, analysis_type, suppress_output=False, instance_exclusions=None, suppress_exclusions=False):
        """Log information about provider exclusions for cheapest provider selection."""
        if suppress_output or suppress_exclusions:
            return
            
        # Get global exclusions
        global_excluded = self.core_config.get('provider_selection', {}).get('exclude_from_cheapest', [])
        
        # Combine with instance-specific exclusions
        all_excluded = list(set(global_excluded + (instance_exclusions or [])))
        
        if all_excluded:
            excluded_list = ', '.join(all_excluded)
            print(f"   Per Instance provider exclusions for {analysis_type}: {excluded_list} (excluded from cost comparison)")
            # Don't show available providers here since they're shown in the main analysis

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
        # Note: openshift_clusters was already collected above
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
                
                # ARO uses standard Azure provider (azurerm)
                if cluster_type == 'aro':
                    providers_in_use.add('azure')
                
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
                        
                        error_msg = str(e).replace("AWS Provider Error:", f"AWS Provider Error (needed for: {instance_list}):")
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

    def validate_meta_provider_configuration(self, instances):
        """Validate that meta providers are not used with 'region' field."""
        meta_providers = ['cheapest', 'cheapest-gpu']
        
        for instance in instances:
            provider = instance.get('provider')
            instance_name = instance.get('name', 'unnamed')
            
            if provider in meta_providers:
                if 'region' in instance:
                    raise ValueError(
                        f"Configuration Error: Instance '{instance_name}' uses meta provider '{provider}' "
                        f"with 'region' field. Meta providers automatically select the optimal cloud provider "
                        f"and region based on cost analysis.\n\n"
                        f"Fix: Replace 'region' with 'location' for geographic preference:\n"
                        f"   # Wrong:\n"
                        f"   region: \"{instance['region']}\"\n\n"
                        f"   # Correct:\n"
                        f"   location: \"us-east\"  # Geographic preference\n\n"
                        f"Meta provider behavior:\n"
                        f"   • '{provider}' evaluates all cloud providers\n"
                        f"   • Selects cheapest option across AWS, GCP, Azure, etc.\n"
                        f"   • Uses 'location' for geographic guidance only\n"
                        f"   • Chooses optimal region within selected cloud provider"
                    )



    def generate_complete_terraform(self, yaml_data, required_providers, full_yaml_data=None):
        """Generate complete Terraform configuration with regional infrastructure."""
        # Use full_yaml_data if provided, otherwise fall back to yaml_data
        effective_yaml_data = full_yaml_data if full_yaml_data is not None else yaml_data
        
        # Ensure YAML data is set for GUID extraction
        if self.current_yaml_data != effective_yaml_data:
            self.set_yaml_data(effective_yaml_data)
        
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
    }
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 2.0"
    }'''
            elif provider == 'gcp':
                terraform_content += '''
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.9"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
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
                # Generate providers for all AWS regions used
                aws_regions = self.get_all_aws_regions(yaml_data)
                primary_region = aws_regions[0]
                
                terraform_content += f'''# AWS Provider Configuration (Multi-Region Support)
# Primary provider for region: {primary_region}
provider "aws" {{
  region = "{primary_region}"
}}

'''
                
                # Generate aliased providers for additional regions
                for region in aws_regions[1:]:
                    clean_region = region.replace("-", "_").replace(".", "_")
                    terraform_content += f'''# AWS Provider alias for region: {region}
provider "aws" {{
  alias  = "{clean_region}"
  region = "{region}"
}}

'''
                
                terraform_content += '''# AWS Caller Identity for account information
data "aws_caller_identity" "current" {}

'''
            elif provider == 'azure':
                terraform_content += '''# Azure Provider Configuration
provider "azurerm" {
  features {}
  subscription_id = var.azure_subscription_id
  
  # Use environment variables for authentication
  # Set ARM_CLIENT_ID, ARM_CLIENT_SECRET, ARM_TENANT_ID, ARM_SUBSCRIPTION_ID
  # Or use Azure CLI with: az login
}

# Azure Active Directory Provider (required for ARO)
provider "azuread" {
  # Use environment variables for authentication
  # Set ARM_CLIENT_ID, ARM_CLIENT_SECRET, ARM_TENANT_ID
  # Or use Azure CLI with: az login
}

'''
            elif provider == 'gcp':
                # Use existing service account project for provider, then create new project
                terraform_content += '''# GCP Provider Configuration
provider "google" {
  # Uses existing project from service account credentials for provider operations
  # New project will be created using this provider context
  region  = var.gcp_region
}

'''
            elif provider == 'ibm_vpc':
                terraform_content += '''# IBM Cloud Provider Configuration
provider "ibm" {
  ibmcloud_api_key = var.ibm_api_key
  region           = var.ibm_region
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
            # Always create new project for GCP deployments (enables folder-based project creation)
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
        
        # Validate meta provider configuration
        self.validate_meta_provider_configuration(instances)
        
        for i, instance in enumerate(instances):
            terraform_content += self.generate_virtual_machine(instance, i+1, yaml_data, full_yaml_data=effective_yaml_data)

        # ROSA clusters use ROSA CLI instead of Terraform providers

        # Generate OpenShift clusters
        terraform_content += '''
# ========================================
# OpenShift Clusters
# ========================================

'''
        terraform_content += self.openshift_provider.generate_openshift_clusters(yaml_data)

        # Generate comprehensive outputs for all cloud providers
        terraform_content += '''
# ========================================
# COMPREHENSIVE OUTPUTS - ALL CLOUD PROVIDERS
# ========================================

'''
        terraform_content += self.generate_comprehensive_outputs(yaml_data, required_providers)

        return terraform_content

    def generate_comprehensive_outputs(self, yaml_data, required_providers):
        """Generate comprehensive outputs showing external IPs for all cloud providers."""
        if not yaml_data or not yaml_data.get('instances'):
            return "# No instances configured for output generation\n"
        
        outputs_content = ""
        instances = yaml_data.get('instances', [])
        guid = self.get_validated_guid(yaml_data)
        
        # Group instances by provider
        provider_instances = {}
        for instance in instances:
            provider = instance.get('provider')
            
            # Resolve meta providers to actual providers
            if provider == 'cheapest':
                provider = self.find_cheapest_provider(instance, suppress_output=True)
            elif provider == 'cheapest-gpu':
                provider = self.find_cheapest_gpu_provider(instance, suppress_output=True)
            
            if provider not in provider_instances:
                provider_instances[provider] = []
            provider_instances[provider].append(instance)
        
        # Generate outputs for each provider
        if 'aws' in provider_instances:
            outputs_content += self.generate_aws_outputs(provider_instances['aws'], yaml_data)
        
        if 'gcp' in provider_instances:
            outputs_content += self.generate_gcp_outputs(provider_instances['gcp'], yaml_data)
            
        if 'azure' in provider_instances:
            outputs_content += self.generate_azure_outputs(provider_instances['azure'], yaml_data)
            
        if 'oci' in provider_instances:
            outputs_content += self.generate_oci_outputs(provider_instances['oci'], yaml_data)
            
        if 'alibaba' in provider_instances:
            outputs_content += self.generate_alibaba_outputs(provider_instances['alibaba'], yaml_data)
            
        if 'ibm_vpc' in provider_instances:
            outputs_content += self.generate_ibm_vpc_outputs(provider_instances['ibm_vpc'], yaml_data)
            
        if 'ibm_classic' in provider_instances:
            outputs_content += self.generate_ibm_classic_outputs(provider_instances['ibm_classic'], yaml_data)
            
        if 'vmware' in provider_instances:
            outputs_content += self.generate_vmware_outputs(provider_instances['vmware'], yaml_data)
        
        # Generate summary output with all instances
        outputs_content += self.generate_summary_outputs(provider_instances, yaml_data)
        
        return outputs_content

    def generate_aws_outputs(self, instances, yaml_data):
        """Generate AWS-specific outputs."""
        if not instances:
            return ""
        
        guid = self.get_validated_guid(yaml_data)
        outputs = []
        
        outputs.append('''# AWS Instances and External IPs
output "aws_instances" {
  description = "AWS EC2 instances with their external IPs and connection information"
  value = {''')
        
        for instance in instances:
            instance_name = instance.get("name", "unknown")
            # Replace {guid} placeholder in instance name
            instance_name = self.replace_guid_placeholders(instance_name)
            clean_name = self.clean_name(instance_name)
            ssh_username = self.get_instance_ssh_username(instance, 'aws', yaml_data)
            
            outputs.append(f'''    "{instance_name}" = {{
      public_ip = aws_instance.{clean_name}_{guid}.public_ip
      private_ip = aws_instance.{clean_name}_{guid}.private_ip
      public_dns = aws_instance.{clean_name}_{guid}.public_dns
      instance_id = aws_instance.{clean_name}_{guid}.id
      instance_type = aws_instance.{clean_name}_{guid}.instance_type
      availability_zone = aws_instance.{clean_name}_{guid}.availability_zone
      ssh_username = "{ssh_username}"
      ssh_command = "ssh {ssh_username}@${{aws_instance.{clean_name}_{guid}.public_ip}}"
    }}''')
        
        outputs.append('''  }
}

''')
        return '\n'.join(outputs)

    def generate_gcp_outputs(self, instances, yaml_data):
        """Generate GCP-specific outputs."""
        if not instances:
            return ""
        
        guid = self.get_validated_guid(yaml_data)
        outputs = []
        
        outputs.append('''# GCP Instances and External IPs
output "gcp_instances" {
  description = "GCP Compute instances with their external IPs and connection information"
  value = {''')
        
        # Get DNS configuration to check if DNS records exist
        dns_config = yaml_data.get('dns_config', {})
        dns_enabled = dns_config.get('root_zone_management', False)
        root_zone_domain = self.gcp_provider.get_root_zone_domain(yaml_data) if dns_enabled else None
        
        for instance in instances:
            instance_name = instance.get("name", "unknown")
            clean_name = self.clean_name(instance_name)
            
            ssh_username = self.get_instance_ssh_username(instance, 'gcp', yaml_data)
            
            # Build the output with conditional DNS information
            output_block = f'''    "{instance_name}" = {{
      public_ip = google_compute_address.{clean_name}_ip_{guid}.address
      private_ip = google_compute_instance.{clean_name}_{guid}.network_interface[0].network_ip
      machine_type = google_compute_instance.{clean_name}_{guid}.machine_type
      zone = google_compute_instance.{clean_name}_{guid}.zone
      self_link = google_compute_instance.{clean_name}_{guid}.self_link
      ssh_username = "{ssh_username}"
      ssh_command = "ssh {ssh_username}@${{google_compute_address.{clean_name}_ip_{guid}.address}}"'''
            
            # Add DNS information if DNS is enabled
            if dns_enabled and root_zone_domain:
                output_block += f'''
      public_fqdn = "{instance_name}.{guid}.{root_zone_domain}"
      private_fqdn = "{instance_name}-internal.{guid}.{root_zone_domain}"
      ssh_command_fqdn = "ssh {ssh_username}@{instance_name}.{guid}.{root_zone_domain}"'''
            
            output_block += '''
    }'''
            
            outputs.append(output_block)
        
        outputs.append('''  }
}

''')
        return '\n'.join(outputs)

    def generate_azure_outputs(self, instances, yaml_data):
        """Generate Azure-specific outputs."""
        if not instances:
            return ""
        
        guid = self.get_validated_guid(yaml_data)
        outputs = []
        
        outputs.append('''# Azure Instances and External IPs
output "azure_instances" {
  description = "Azure Virtual Machines with their external IPs and connection information"
  value = {''')
        
        for instance in instances:
            instance_name = instance.get("name", "unknown")
            clean_name = self.clean_name(instance_name)
            ssh_username = self.get_instance_ssh_username(instance, 'azure', yaml_data)
            
            outputs.append(f'''    "{instance_name}" = {{
      public_ip = azurerm_public_ip.{clean_name}_ip_{guid}.ip_address
      private_ip = azurerm_network_interface.{clean_name}_nic_{guid}.ip_configuration[0].private_ip_address
      vm_size = azurerm_linux_virtual_machine.{clean_name}_{guid}.size
      location = azurerm_linux_virtual_machine.{clean_name}_{guid}.location
      resource_group = azurerm_linux_virtual_machine.{clean_name}_{guid}.resource_group_name
      ssh_username = "{ssh_username}"
      ssh_command = "ssh {ssh_username}@${{azurerm_public_ip.{clean_name}_ip_{guid}.ip_address}}"
    }}''')
        
        outputs.append('''  }
}

''')
        return '\n'.join(outputs)

    def generate_oci_outputs(self, instances, yaml_data):
        """Generate OCI-specific outputs."""
        if not instances:
            return ""
        
        guid = self.get_validated_guid(yaml_data)
        outputs = []
        
        outputs.append('''# OCI Instances and External IPs
output "oci_instances" {
  description = "OCI Compute instances with their external IPs and connection information"
  value = {''')
        
        for instance in instances:
            instance_name = instance.get("name", "unknown")
            clean_name = self.clean_name(instance_name)
            ssh_username = self.get_instance_ssh_username(instance, 'oci', yaml_data)
            
            outputs.append(f'''    "{instance_name}" = {{
      public_ip = oci_core_instance.{clean_name}_{guid}.public_ip
      private_ip = oci_core_instance.{clean_name}_{guid}.private_ip
      shape = oci_core_instance.{clean_name}_{guid}.shape
      availability_domain = oci_core_instance.{clean_name}_{guid}.availability_domain
      compartment_id = oci_core_instance.{clean_name}_{guid}.compartment_id
      ssh_username = "{ssh_username}"
      ssh_command = "ssh {ssh_username}@${{oci_core_instance.{clean_name}_{guid}.public_ip}}"
    }}''')
        
        outputs.append('''  }
}

''')
        return '\n'.join(outputs)

    def generate_alibaba_outputs(self, instances, yaml_data):
        """Generate Alibaba Cloud-specific outputs."""
        if not instances:
            return ""
        
        guid = self.get_validated_guid(yaml_data)
        outputs = []
        
        outputs.append('''# Alibaba Cloud Instances and External IPs
output "alibaba_instances" {
  description = "Alibaba Cloud ECS instances with their external IPs and connection information"
  value = {''')
        
        for instance in instances:
            instance_name = instance.get("name", "unknown")
            clean_name = self.clean_name(instance_name)
            ssh_username = self.get_instance_ssh_username(instance, 'alibaba', yaml_data)
            
            outputs.append(f'''    "{instance_name}" = {{
      public_ip = alicloud_eip_association.{clean_name}_eip_assoc_{guid}.ip_address
      private_ip = alicloud_instance.{clean_name}_{guid}.private_ip
      instance_type = alicloud_instance.{clean_name}_{guid}.instance_type
      zone_id = alicloud_instance.{clean_name}_{guid}.availability_zone
      ssh_username = "{ssh_username}"
      ssh_command = "ssh {ssh_username}@${{alicloud_eip_association.{clean_name}_eip_assoc_{guid}.ip_address}}"
    }}''')
        
        outputs.append('''  }
}

''')
        return '\n'.join(outputs)

    def generate_ibm_vpc_outputs(self, instances, yaml_data):
        """Generate IBM VPC-specific outputs."""
        if not instances:
            return ""
        
        guid = self.get_validated_guid(yaml_data)
        outputs = []
        
        outputs.append('''# IBM Cloud VPC Instances and External IPs
output "ibm_vpc_instances" {
  description = "IBM Cloud VPC instances with their external IPs and connection information"
  value = {''')
        
        for instance in instances:
            instance_name = instance.get("name", "unknown")
            clean_name = self.clean_name(instance_name)
            ssh_username = self.get_instance_ssh_username(instance, 'ibm_vpc', yaml_data)
            
            outputs.append(f'''    "{instance_name}" = {{
      public_ip = ibm_is_floating_ip.{clean_name}_fip_{guid}.address
      private_ip = ibm_is_instance.{clean_name}_{guid}.primary_network_interface[0].primary_ipv4_address
      profile = ibm_is_instance.{clean_name}_{guid}.profile
      zone = ibm_is_instance.{clean_name}_{guid}.zone
      vpc = ibm_is_instance.{clean_name}_{guid}.vpc
      ssh_username = "{ssh_username}"
      ssh_command = "ssh {ssh_username}@${{ibm_is_floating_ip.{clean_name}_fip_{guid}.address}}"
    }}''')
        
        outputs.append('''  }
}

''')
        return '\n'.join(outputs)

    def generate_ibm_classic_outputs(self, instances, yaml_data):
        """Generate IBM Classic-specific outputs."""
        if not instances:
            return ""
        
        guid = self.get_validated_guid(yaml_data)
        outputs = []
        
        outputs.append('''# IBM Cloud Classic Instances and External IPs
output "ibm_classic_instances" {
  description = "IBM Cloud Classic instances with their external IPs and connection information"
  value = {''')
        
        for instance in instances:
            instance_name = instance.get("name", "unknown")
            clean_name = self.clean_name(instance_name)
            ssh_username = self.get_instance_ssh_username(instance, 'ibm_classic', yaml_data)
            
            outputs.append(f'''    "{instance_name}" = {{
      public_ip = ibm_compute_vm_instance.{clean_name}_{guid}.ipv4_address
      private_ip = ibm_compute_vm_instance.{clean_name}_{guid}.ipv4_address_private
      flavor = ibm_compute_vm_instance.{clean_name}_{guid}.flavor_key_name
      datacenter = ibm_compute_vm_instance.{clean_name}_{guid}.datacenter
      ssh_username = "{ssh_username}"
      ssh_command = "ssh {ssh_username}@${{ibm_compute_vm_instance.{clean_name}_{guid}.ipv4_address}}"
    }}''')
        
        outputs.append('''  }
}

''')
        return '\n'.join(outputs)

    def generate_vmware_outputs(self, instances, yaml_data):
        """Generate VMware-specific outputs."""
        if not instances:
            return ""
        
        guid = self.get_validated_guid(yaml_data)
        outputs = []
        
        outputs.append('''# VMware vSphere Instances and IPs
output "vmware_instances" {
  description = "VMware vSphere VMs with their IP addresses and connection information"
  value = {''')
        
        for instance in instances:
            instance_name = instance.get("name", "unknown")
            clean_name = self.clean_name(instance_name)
            ssh_username = self.get_instance_ssh_username(instance, 'vmware', yaml_data)
            
            outputs.append(f'''    "{instance_name}" = {{
      ip_address = vsphere_virtual_machine.{clean_name}_{guid}.default_ip_address
      guest_ip_addresses = vsphere_virtual_machine.{clean_name}_{guid}.guest_ip_addresses
      num_cpus = vsphere_virtual_machine.{clean_name}_{guid}.num_cpus
      memory = vsphere_virtual_machine.{clean_name}_{guid}.memory
      power_state = vsphere_virtual_machine.{clean_name}_{guid}.power_state
      ssh_username = "{ssh_username}"
      ssh_command = "ssh {ssh_username}@${{vsphere_virtual_machine.{clean_name}_{guid}.default_ip_address}}"
    }}''')
        
        outputs.append('''  }
}

''')
        return '\n'.join(outputs)

    def generate_summary_outputs(self, provider_instances, yaml_data):
        """Generate summary output with all instances across all providers."""
        if not provider_instances:
            return ""
        
        guid = self.get_validated_guid(yaml_data)
        outputs = []
        
        outputs.append('''# MULTI-CLOUD SUMMARY - ALL INSTANCES
output "all_instances_summary" {
  description = "Summary of all instances across all cloud providers with their external IPs"
  value = {''')
        
        for provider, instances in provider_instances.items():
            for instance in instances:
                instance_name = instance.get("name", "unknown")
                # Replace {guid} placeholder in instance name
                instance_name = self.replace_guid_placeholders(instance_name)
                clean_name = self.clean_name(instance_name)
                ssh_username = self.get_instance_ssh_username(instance, provider, yaml_data)
                
                # Generate provider-specific IP reference
                if provider == 'aws':
                    ip_ref = f"aws_instance.{clean_name}_{guid}.public_ip"
                    private_ip_ref = f"aws_instance.{clean_name}_{guid}.private_ip"
                elif provider == 'gcp':
                    ip_ref = f"google_compute_address.{clean_name}_ip_{guid}.address"
                    private_ip_ref = f"google_compute_instance.{clean_name}_{guid}.network_interface[0].network_ip"
                elif provider == 'azure':
                    ip_ref = f"azurerm_public_ip.{clean_name}_ip_{guid}.ip_address"
                    private_ip_ref = f"azurerm_network_interface.{clean_name}_nic_{guid}.ip_configuration[0].private_ip_address"
                elif provider == 'oci':
                    ip_ref = f"oci_core_instance.{clean_name}_{guid}.public_ip"
                    private_ip_ref = f"oci_core_instance.{clean_name}_{guid}.private_ip"
                elif provider == 'alibaba':
                    ip_ref = f"alicloud_eip_association.{clean_name}_eip_assoc_{guid}.ip_address"
                    private_ip_ref = f"alicloud_instance.{clean_name}_{guid}.private_ip"
                elif provider == 'ibm_vpc':
                    ip_ref = f"ibm_is_floating_ip.{clean_name}_fip_{guid}.address"
                    private_ip_ref = f"ibm_is_instance.{clean_name}_{guid}.primary_network_interface[0].primary_ipv4_address"
                elif provider == 'ibm_classic':
                    ip_ref = f"ibm_compute_vm_instance.{clean_name}_{guid}.ipv4_address"
                    private_ip_ref = f"ibm_compute_vm_instance.{clean_name}_{guid}.ipv4_address_private"
                elif provider == 'vmware':
                    ip_ref = f"vsphere_virtual_machine.{clean_name}_{guid}.default_ip_address"
                    private_ip_ref = f"vsphere_virtual_machine.{clean_name}_{guid}.default_ip_address"
                else:
                    ip_ref = "\"N/A\""
                    private_ip_ref = "\"N/A\""
                
                outputs.append(f'''    "{instance_name}" = {{
      provider = "{provider.upper()}"
      public_ip = {ip_ref}
      private_ip = {private_ip_ref}
      size = "{instance.get('size', 'unknown')}"
      image = "{instance.get('image', 'unknown')}"
      region = "{instance.get('region', 'N/A')}"
      ssh_username = "{ssh_username}"
      ssh_command = "ssh {ssh_username}@${{{ip_ref}}}"
    }}''')
        
        outputs.append('''  }
}

# External IPs Only - Quick Access
output "external_ips" {
  description = "Quick access to all external IP addresses"
  value = {''')
        
        for provider, instances in provider_instances.items():
            for instance in instances:
                instance_name = instance.get("name", "unknown")
                # Replace {guid} placeholder in instance name
                instance_name = self.replace_guid_placeholders(instance_name)
                clean_name = self.clean_name(instance_name)
                
                # Generate provider-specific IP reference
                if provider == 'aws':
                    ip_ref = f"aws_instance.{clean_name}_{guid}.public_ip"
                elif provider == 'gcp':
                    ip_ref = f"google_compute_address.{clean_name}_ip_{guid}.address"
                elif provider == 'azure':
                    ip_ref = f"azurerm_public_ip.{clean_name}_ip_{guid}.ip_address"
                elif provider == 'oci':
                    ip_ref = f"oci_core_instance.{clean_name}_{guid}.public_ip"
                elif provider == 'alibaba':
                    ip_ref = f"alicloud_eip_association.{clean_name}_eip_assoc_{guid}.ip_address"
                elif provider == 'ibm_vpc':
                    ip_ref = f"ibm_is_floating_ip.{clean_name}_fip_{guid}.address"
                elif provider == 'ibm_classic':
                    ip_ref = f"ibm_compute_vm_instance.{clean_name}_{guid}.ipv4_address"
                elif provider == 'vmware':
                    ip_ref = f"vsphere_virtual_machine.{clean_name}_{guid}.default_ip_address"
                else:
                    ip_ref = "\"N/A\""
                
                outputs.append(f'''    "{instance_name}" = {ip_ref}''')
        
        outputs.append('''  }
}

''')
        return '\n'.join(outputs)

    def get_instance_ssh_username(self, instance, provider, yaml_data=None):
        """Get the SSH username for an instance based on provider and operating system."""
        # Check if SSH username is explicitly configured for this instance
        ssh_key_config = self.get_instance_ssh_key(instance, yaml_data or {})
        if ssh_key_config and ssh_key_config.get('username'):
            return ssh_key_config['username']
        
        # Determine username based on provider and image
        image = instance.get('image', 'RHEL9-latest')
        
        # Debug output to trace the issue  
        # print(f"SSH DEBUG START: provider='{provider}', image='{image}'")
        
        if provider == 'aws':
            # AWS usernames depend on the operating system
            if any(os_name in image.upper() for os_name in ['RHEL', 'REDHAT']):
                return 'ec2-user'
            elif 'UBUNTU' in image.upper():
                return 'ubuntu'
            elif any(os_name in image.upper() for os_name in ['AMAZON', 'AMZN']):
                return 'ec2-user'
            elif 'CENTOS' in image.upper():
                return 'centos'
            elif 'FEDORA' in image.upper():
                return 'fedora'
            elif 'SUSE' in image.upper():
                return 'ec2-user'
            else:
                return 'ec2-user'  # Default for AWS
                
        elif provider == 'gcp':
            # GCP allows custom usernames, but has common defaults
            if any(os_name in image.upper() for os_name in ['RHEL', 'REDHAT']):
                return 'cloud-user'
            elif 'UBUNTU' in image.upper():
                return 'ubuntu'
            elif 'CENTOS' in image.upper():
                return 'centos'
            elif 'FEDORA' in image.upper():
                return 'fedora'
            elif 'DEBIAN' in image.upper():
                return 'debian'
            else:
                return 'cloud-user'  # Default for GCP
                
        elif provider == 'azure':
            # Azure uses configured admin username, default is azureuser
            return 'azureuser'
            
        elif provider == 'oci':
            # OCI usernames depend on the operating system
            if any(os_name in image.upper() for os_name in ['ORACLE', 'OL']):
                return 'opc'
            elif 'UBUNTU' in image.upper():
                return 'ubuntu'
            elif any(os_name in image.upper() for os_name in ['RHEL', 'REDHAT']):
                return 'cloud-user'
            elif 'CENTOS' in image.upper():
                return 'centos'
            else:
                return 'opc'  # Default for OCI
                
        elif provider == 'alibaba':
            # Alibaba Cloud typically uses root
            return 'root'
            
        elif provider in ['ibm_vpc', 'ibm_classic']:
            # IBM Cloud typically uses root
            return 'root'
            
        elif provider == 'vmware':
            # VMware is highly customizable
            return 'vmware-user'
            
        else:
            # Unknown provider - return a generic default
            return 'cloud-user'

    def generate_variables_tf(self, required_providers, yaml_data=None):
        """Generate variables.tf file with variables for required providers."""
        variables_content = '''# Variables for multi-cloud deployment
# Generated by YamlForge v2.0
# SSH keys are configured in YAML and embedded directly in resources

'''

        if 'aws' in required_providers:
            # Get the primary AWS region that will be used
            primary_aws_region = self.get_primary_aws_region(yaml_data) if yaml_data else 'us-east-1'
            
            variables_content += f'''# AWS Variables
# Note: AWS region is automatically determined from your configuration: {primary_aws_region}

variable "aws_billing_account_id" {{
  description = "AWS billing account ID for ROSA clusters (overrides default account)"
  type        = string
  default     = ""
}}

# ROSA clusters use ROSA CLI for authentication and cluster creation
# AWS credentials are configured via environment variables or AWS profiles
# AWS billing account can be overridden via AWS_BILLING_ACCOUNT_ID environment variable

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

variable "arm_client_secret" {
  description = "Azure service principal client secret for ARO clusters"
  type        = string
  sensitive   = true
}

'''

        if 'gcp' in required_providers:
            # Always creating new project - only need region variable
            variables_content += '''# GCP Variables
variable "gcp_region" {
  description = "GCP region for deployment"
  type        = string
  default     = "us-east1"
}

# Note: GCP project is created automatically using cloud_workspace name and GUID

'''

        if 'ibm_vpc' in required_providers or 'ibm_classic' in required_providers:
            variables_content += '''# IBM Cloud Variables
variable "ibm_api_key" {
  description = "IBM Cloud API key for authentication"
  type        = string
  sensitive   = true
}

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

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
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
            aws_region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
            aws_billing_account_id = os.getenv('AWS_BILLING_ACCOUNT_ID')
            

            
            # Get the determined AWS region
            determined_region = self.get_primary_aws_region(yaml_data) if yaml_data else aws_region
            
            # ROSA CLI uses AWS credentials from environment variables or AWS CLI profiles
            tfvars_content += f'''# AWS Region Configuration
# Region automatically determined from your configuration: {determined_region}

# AWS Billing Account Override (if different from default account)
aws_billing_account_id = "{aws_billing_account_id or ''}"

# ROSA CLI uses AWS credentials from environment variables or AWS CLI profiles
# No need to set aws_access_key_id or aws_secret_access_key in Terraform

'''
            
            # AWS account information - try environment variables first, then AWS SDK
            account_id_from_env = None
            billing_account_id = aws_billing_account_id
            
            if aws_creds.get('available'):
                # Use auto-discovered values from AWS SDK
                account_id_from_env = aws_creds.get('account_id')
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
            # Get Azure credentials from environment variables (no defaults)
            azure_creds = self.credentials.get_azure_credentials()
            subscription_id = azure_creds.get('subscription_id')
            
            if not subscription_id:
                raise ValueError("Azure subscription ID not found. Please set ARM_SUBSCRIPTION_ID or AZURE_SUBSCRIPTION_ID environment variable.")
            
            # Get ARM_CLIENT_SECRET for ARO service principal
            arm_client_secret = azure_creds.get('client_secret')
            
            if not arm_client_secret:
                raise ValueError("Azure client secret not found. Please set ARM_CLIENT_SECRET environment variable.")
                
            tfvars_content += f'''# Azure Configuration (from environment variables)
azure_subscription_id = "{subscription_id}"
azure_location        = "East US"
arm_client_secret     = "{arm_client_secret}"

'''

        if 'gcp' in required_providers:
            # Always creating new project
            yamlforge_data = yaml_data.get('yamlforge', {}) if yaml_data else {}
            cloud_workspace = yamlforge_data.get('cloud_workspace', {})
            workspace_name = cloud_workspace.get('name', 'yamlforge-workspace')
            tfvars_content += f'''# GCP Configuration
# Project will be created automatically as: {workspace_name.lower().replace('_', '-')}-{{GUID}}
# Folder ID: {os.getenv('GCP_FOLDER_ID', 'Not set - will use organization')}
gcp_region = "us-east1"

'''

        if 'ibm_vpc' in required_providers or 'ibm_classic' in required_providers:
            # Check for IBM Cloud API key from environment variables
            ibm_api_key = os.getenv('IC_API_KEY') or os.getenv('IBMCLOUD_API_KEY')
            
            if ibm_api_key:
                tfvars_content += f'''# IBM Cloud Configuration
# API key automatically detected from environment variable
ibm_api_key = "{ibm_api_key}"
ibm_region = "us-south"

'''
            else:
                tfvars_content += '''# IBM Cloud Configuration
# Set IC_API_KEY or IBMCLOUD_API_KEY environment variable
# Or configure ibm_api_key here
ibm_api_key = "your-ibm-cloud-api-key-here"
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

        # Red Hat Pull Secret for enhanced content access
        pull_secret = os.getenv('OCP_PULL_SECRET')
        
        if pull_secret and pull_secret.strip():
            # Escape the JSON for use in tfvars (single line, escaped quotes)
            escaped_pull_secret = pull_secret.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '')
            tfvars_content += f'''# Red Hat Pull Secret for enhanced content access
# Automatically detected from OCP_PULL_SECRET environment variable
# This enables access to Red Hat container registries and additional content
redhat_pull_secret = "{escaped_pull_secret}"

'''
        else:
            tfvars_content += '''# Red Hat Pull Secret for enhanced content access (optional but recommended)
# Download from: https://console.redhat.com/openshift/install/pull-secret
# Set OCP_PULL_SECRET environment variable or configure here
redhat_pull_secret = ""

'''

        return tfvars_content

    def convert(self, config, output_dir, verbose=False, full_yaml_data=None):
        """Convert YAML configuration to Terraform and write files to output directory."""
        self.verbose = verbose
        # Set YAML data for GUID extraction - use full YAML data if provided
        yaml_data_for_guid = full_yaml_data if full_yaml_data is not None else config
        self.set_yaml_data(yaml_data_for_guid)
        
        # Validate cloud provider setup early
        self.validate_provider_setup(config)
        
        required_providers = self.detect_required_providers(config)

        # Generate the complete terraform configuration
        terraform_config = self.generate_complete_terraform(config, required_providers, full_yaml_data)
        
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
            
        # Generate ROSA CLI setup script if ROSA clusters are present AND using CLI deployment method
        if self.openshift_provider._has_rosa_clusters(config):
            # Check deployment method - only generate scripts for CLI method
            rosa_deployment = config.get('rosa_deployment', {})
            deployment_method = rosa_deployment.get('method', 'terraform')
            
            if deployment_method == 'cli':
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
                # Terraform deployment method - no scripts generated
                if self.verbose:
                    print(f"Generated files:")
                    print(f"  - {main_tf_path}")
                    print(f"  - {variables_path}")
                    print(f"  - {tfvars_path}")
        else:
            # No ROSA clusters
            if self.verbose:
                print(f"Generated files:")
                print(f"  - {main_tf_path}")
                print(f"  - {variables_path}")
                print(f"  - {tfvars_path}")



    def clean_name(self, name):
        """Clean a name for use as a Terraform resource identifier."""
        if not name:
            return "unnamed"
        
        # Replace {guid} placeholder with actual GUID if present
        if '{guid}' in name:
            guid = self.get_validated_guid()
            name = name.replace('{guid}', guid)
        
        return name.replace("-", "_").replace(".", "_").replace(" ", "_")

    def replace_guid_placeholders(self, text):
        """Replace {guid} placeholders in text with actual GUID."""
        if not text or '{guid}' not in text:
            return text
        
        guid = self.get_validated_guid()
        return text.replace('{guid}', guid)

    def resolve_instance_region(self, instance, provider):
        """Resolve instance region with support for both direct regions and mapped locations."""
        # Create cache key to prevent multiple validations for the same instance
        instance_name = instance.get('name', 'unnamed')
        cache_key = f"{instance_name}_{provider}_{instance.get('region', '')}_{instance.get('location', '')}"
        
        # Return cached result if available
        if cache_key in self._region_cache:
            return self._region_cache[cache_key]
        
        has_region = 'region' in instance
        has_location = 'location' in instance
        find_best_region_on_fail = instance.get('find_best_region_on_fail', False)

        if has_region and has_location:
            raise ValueError(f"Instance '{instance_name}' cannot specify both 'region' and 'location'.")

        if not has_region and not has_location:
            raise ValueError(f"Instance '{instance_name}' must specify either 'region' or 'location'.")

        resolved_region = None

        if has_location:
            # Location-based: Auto-select closest region with validation
            location_key = instance['location']
            mapped_region = None
            
            # First try to get mapped region from locations - ERROR if not found
            if location_key in self.locations:
                mapped_region = self.locations[location_key].get(provider)
                if not mapped_region:
                    raise ValueError(f"Instance '{instance_name}': Location '{location_key}' is not supported for provider '{provider}'. "
                                   f"Check mappings/locations.yaml for supported locations.")
            else:
                raise ValueError(f"Instance '{instance_name}': Location '{location_key}' not found in location mappings. "
                               f"Check mappings/locations.yaml for supported locations.")
            
            # Show the location mapping
            print(f"Instance '{instance_name}': Location '{location_key}' -> mapped to region '{mapped_region}' for {provider.upper()}")
            
            # For location-based, validate and auto-select best region if needed
            instance_type = self._get_instance_type_for_validation(instance, provider)
            if instance_type and provider == 'gcp':
                print(f"Checking GCP region availability for '{instance_name}' (machine type '{instance_type}') in region '{mapped_region}'...")
                # Check if the mapped region supports the instance type
                if not self.gcp_provider.check_machine_type_availability(instance_type, mapped_region):
                    # Auto-select best available region
                    print(f"Finding alternative GCP regions for machine type '{instance_type}'...")
                    available_regions = self.gcp_provider.find_available_regions_for_machine_type(instance_type)
                    best_region = self.gcp_provider.find_closest_available_region(mapped_region, available_regions)
                    
                    if best_region:
                        print(f"WARNING: Instance '{instance_name}': Location '{location_key}' maps to region '{mapped_region}' which doesn't support machine type '{instance_type}'. Auto-selecting closest available region: '{best_region}'")
                        resolved_region = best_region
                    else:
                        raise ValueError(f"Instance '{instance_name}': No available regions found for machine type '{instance_type}' near location '{location_key}'.")
                else:
                    resolved_region = mapped_region
            else:
                resolved_region = mapped_region

        if has_region:
            # Region-based: Validate and ERROR OUT if invalid (don't continue)
            requested_region = instance['region']
            
            # Get the instance type to validate
            instance_type = self._get_instance_type_for_validation(instance, provider)
            
            if instance_type and provider == 'gcp':
                print(f"Checking GCP region availability for '{instance_name}' (machine type '{instance_type}') in region '{requested_region}'...")
                # Check if the machine type is available in the requested region
                if not self.gcp_provider.check_machine_type_availability(instance_type, requested_region):
                    print(f"Finding alternative GCP regions for machine type '{instance_type}'...")
                    available_regions = self.gcp_provider.find_available_regions_for_machine_type(instance_type)
                    
                    if find_best_region_on_fail:
                        # Auto-select closest available region
                        best_region = self.gcp_provider.find_closest_available_region(requested_region, available_regions)
                        
                        if best_region:
                            print(f"WARNING: Instance '{instance_name}': Machine type '{instance_type}' not available in region '{requested_region}'. Auto-selecting closest available region: '{best_region}'")
                            resolved_region = best_region
                        else:
                            raise ValueError(f"Instance '{instance_name}': Machine type '{instance_type}' not available in any region.")
                    else:
                        # Error out and stop execution
                        if available_regions:
                            suggestion = f"Try: {', '.join(available_regions[:3])}"
                            raise ValueError(f"Instance '{instance_name}': Machine type '{instance_type}' not available in region '{requested_region}'. "
                                           f"Available regions: {', '.join(available_regions)}. "
                                           f"Suggestion: {suggestion} or set find_best_region_on_fail: true")
                        else:
                            raise ValueError(f"Instance '{instance_name}': Machine type '{instance_type}' not available in any region.")
                else:
                    resolved_region = requested_region
            else:
                resolved_region = requested_region
        
        # Cache the result
        self._region_cache[cache_key] = resolved_region
        return resolved_region

    def _get_instance_type_for_validation(self, instance, provider):
        """Get the instance type for validation purposes."""
        # Get the size/instance_type from the instance
        size = instance.get('size') or instance.get('instance_type')
        gpu_type = instance.get('gpu_type')
        
        if not size:
            return None
        
        # For GCP, resolve the machine type considering GPU requirements
        if provider == 'gcp':
            try:
                # If this is a GPU instance, we need to find the actual machine type with GPU
                if gpu_type:
                    # Find the cheapest GPU instance type for this provider to get the actual machine type
                    provider_costs = self.find_cheapest_gpu_by_specs(gpu_type)
                    if provider in provider_costs:
                        return provider_costs[provider]['instance_type']
                    
                    # Fallback: look through flavor mappings for GPU instances
                    provider_flavors = self.flavors.get(provider, {})
                    flavor_mappings = provider_flavors.get('flavor_mappings', {})
                    
                    # Look for size/GPU combination in flavor mappings
                    for size_category, size_options in flavor_mappings.items():
                        if size_category == size or size in size_category:
                            for instance_type, specs in size_options.items():
                                if (specs.get('gpu_count', 0) > 0 and 
                                    self.gpu_type_matches(specs.get('gpu_type', ''), gpu_type)):
                                    return instance_type
                    
                    # Also check machine types
                    machine_types = provider_flavors.get('machine_types', {})
                    for instance_type, specs in machine_types.items():
                        if (specs.get('gpu_count', 0) > 0 and 
                            self.gpu_type_matches(specs.get('gpu_type', ''), gpu_type)):
                            return instance_type
                
                # For non-GPU instances, use the regular machine type resolution
                return self.gcp_provider.get_gcp_machine_type(size)
                
            except ValueError:
                # If we can't resolve the machine type, assume it's already a machine type
                return size
        
        # For other providers, return the size as-is
        return size

    def get_all_aws_regions(self, yaml_data):
        """Get all AWS regions used in the deployment configuration."""
        aws_regions = set()
        
        # Collect regions from AWS instances
        for instance in yaml_data.get('instances', []):
            provider = instance.get('provider')
            
            # Resolve meta providers to actual providers
            if provider == 'cheapest':
                provider = self.find_cheapest_provider(instance, suppress_output=True)
            elif provider == 'cheapest-gpu':
                provider = self.find_cheapest_gpu_provider(instance, suppress_output=True)
            
            if provider == 'aws':
                try:
                    region = self.resolve_instance_region(instance, 'aws')
                    aws_regions.add(region)
                except ValueError:
                    # Instance doesn't specify region, use default
                    aws_regions.add(os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
        
        # Collect regions from OpenShift clusters
        for cluster in yaml_data.get('openshift_clusters', []):
            cluster_type = cluster.get('type', '')
            if cluster_type in ['rosa-classic', 'rosa-hcp']:
                region = cluster.get('region')
                if region:
                    aws_regions.add(region)
        
        # Return sorted list of regions (primary first)
        regions_list = sorted(aws_regions) if aws_regions else [os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')]
        return regions_list
    
    def get_primary_aws_region(self, yaml_data):
        """Get the primary AWS region (first in sorted order)."""
        return self.get_all_aws_regions(yaml_data)[0]
    
    def get_aws_provider_reference(self, region, all_regions):
        """Get the Terraform provider reference for a specific AWS region."""
        if not all_regions:
            return ""
        
        primary_region = all_regions[0]
        
        # Primary region uses default provider
        if region == primary_region:
            return ""
        
        # Other regions use aliased providers
        clean_region = region.replace("-", "_").replace(".", "_")
        return f"provider = aws.{clean_region}"

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
                
                print(f"Auto-matched flavor for {req_desc}:")
                print(f"  Recommended flavor: {closest_flavor['flavor']}")
            print(f"  Avg specs: {closest_flavor['avg_vcpus']:.1f} vCPUs, {closest_flavor['avg_memory_gb']:.1f}GB RAM", end="")
            if closest_flavor['avg_gpus'] > 0:
                gpu_info = f", {closest_flavor['avg_gpus']:.1f} GPUs"
                if closest_flavor['gpu_types']:
                    gpu_info += f" ({', '.join(closest_flavor['gpu_types'])})"
                print(gpu_info)
            else:
                print()
            print(f"  Available on: {', '.join(closest_flavor['available_providers'])}")
            
            # Use the found flavor instead of specs
            size = closest_flavor['flavor']
            # Clear the hardware specs since we're now using flavor
            cores = None
            memory = None
        
        # Get cost information for all providers
        provider_costs = {}
        
        # Get instance-specific exclusions
        instance_exclusions = instance.get('exclude_providers', [])
        
        if size:
            # Size-based selection (existing functionality)
            provider_costs = self.find_cheapest_by_size(size, gpu_type, instance_exclusions)
            analysis_type = f"size '{size}'"
            if gpu_type:
                analysis_type += f" with {gpu_type} GPU"
        elif cores and memory:
            # Hardware specification-based selection (with optional GPU)
            provider_costs = self.find_cheapest_by_specs(cores, memory, gpu_count, gpu_type, instance_exclusions)
            memory_gb = memory / 1024
            
            if gpu_count and gpu_type:
                analysis_type = f"{cores} cores, {memory_gb:.1f}GB RAM, {gpu_count} {gpu_type} GPU(s)"
            elif gpu_count:
                analysis_type = f"{cores} cores, {memory_gb:.1f}GB RAM, {gpu_count} GPU(s)"
            else:
                analysis_type = f"{cores} cores, {memory_gb:.1f}GB RAM"
        else:
            # No fallback - must specify requirements
            instance_name = instance.get('name', 'unnamed')
            raise ValueError(
                f"Instance '{instance_name}': When using provider 'cheapest', you must specify either:\n"
                f"  - 'size': nano, micro, small, medium, large, xlarge, etc.\n"
                f"  - 'cores' and 'memory': e.g., cores: 2, memory: 4096 (MB)\n"
                f"  - GPU requirements: gpu_count, gpu_type, etc."
            )
        
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
            # Get instance-specific exclusions
            instance_exclusions = instance.get('exclude_providers', [])
            # Log provider exclusions if any (always suppress since they're shown under instance name)
            self.log_provider_exclusions("cheapest provider selection", suppress_output, instance_exclusions, True)
            print(f"   Cost analysis for instance '{instance_name}':")
            for provider, info in sorted(provider_costs.items(), key=lambda x: x[1]['cost']):
                marker = " ← SELECTED" if provider == cheapest_provider else ""
                vcpus = info.get('vcpus', 'N/A')
                memory_gb = info.get('memory_gb', 'N/A')
                gpu_count = info.get('gpu_count', 0)
                detected_gpu_type = info.get('gpu_type', '')
                
                if gpu_count > 0:
                    gpu_info = f", {gpu_count}x {detected_gpu_type}" if detected_gpu_type else f", {gpu_count} GPU(s)"
                    print(f"     {provider}: ${info['cost']:.4f}/hour ({info['instance_type']}, {vcpus} vCPU, {memory_gb}GB{gpu_info}){marker}")
                else:
                    print(f"     {provider}: ${info['cost']:.4f}/hour ({info['instance_type']}, {vcpus} vCPU, {memory_gb}GB){marker}")
        
        return cheapest_provider
    
    def find_cheapest_gpu_provider(self, instance, suppress_output=False):
        """Find the cheapest cloud provider for GPU instances, ignoring cores/memory requirements."""
        gpu_type = instance.get("gpu_type")  # Specific GPU type requirement
        
        # Validate GPU type if specified
        if gpu_type:
            self.validate_gpu_type(gpu_type)
        
        # Get instance-specific exclusions
        instance_exclusions = instance.get('exclude_providers', [])
        
        # Get cost information for all providers (GPU instances only)
        provider_costs = self.find_cheapest_gpu_by_specs(gpu_type, instance_exclusions)
        
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
            # Log provider exclusions if any (always suppress since they're shown under instance name)
            self.log_provider_exclusions("cheapest GPU provider selection", suppress_output, instance_exclusions, True)
            print(f"   GPU-optimized cost analysis for instance '{instance_name}':")
            for provider, info in sorted(provider_costs.items(), key=lambda x: x[1]['cost']):
                marker = " ← SELECTED" if provider == cheapest_provider else ""
                vcpus = info.get('vcpus', 'N/A')
                memory_gb = info.get('memory_gb', 'N/A')
                gpu_count = info.get('gpu_count', 0)
                detected_gpu_type = info.get('gpu_type', '')
                
                gpu_info = f", {gpu_count}x {detected_gpu_type}" if detected_gpu_type else f", {gpu_count} GPU(s)"
                print(f"     {provider}: ${info['cost']:.4f}/hour ({info['instance_type']}, {vcpus} vCPU, {memory_gb}GB{gpu_info}){marker}")
        
        return cheapest_provider
    
    def find_cheapest_gpu_by_specs(self, gpu_type=None, instance_exclusions=None):
        """Find cheapest GPU instances across all providers, ignoring CPU/memory constraints."""
        provider_costs = {}
        
        # Get available providers (excluding those configured to be excluded from cheapest)
        available_providers = self.get_effective_providers(instance_exclusions=instance_exclusions)
        
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
    
    def find_cheapest_by_size(self, size, gpu_type=None, instance_exclusions=None):
        """Find cheapest provider for a generic size, optionally filtered by GPU type."""
        provider_costs = {}
        
        # Get available providers (excluding those configured to be excluded from cheapest)
        available_providers = self.get_effective_providers(instance_exclusions=instance_exclusions)
        
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
    
    def find_cheapest_by_specs(self, required_cores, required_memory_mb, required_gpus=None, gpu_type=None, instance_exclusions=None):
        """Find cheapest provider for specific CPU/memory/GPU requirements."""
        provider_costs = {}
        required_memory_gb = required_memory_mb / 1024
        
        # Get available providers (excluding those configured to be excluded from cheapest)
        available_providers = self.get_effective_providers(instance_exclusions=instance_exclusions)
        
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
        instance_name = instance.get("name", "unnamed")
        
        # Check if instance specifies instance_type directly
        direct_type = instance.get("instance_type")
        if direct_type:
            return direct_type
        
        # Map generic size to provider-specific instance type
        if size in self.flavors:
            generic_flavor = self.flavors[size]
            if provider in generic_flavor:
                instance_type = generic_flavor[provider]
                print(f"{provider.upper()} size mapping for '{instance_name}': '{size}' -> '{instance_type}'")
                return instance_type
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
        
        # No mapping found - fail with clear error message
        # Get available sizes from both generic and provider-specific mappings
        generic_sizes = list(self.flavors.keys()) if hasattr(self, 'flavors') else []
        provider_sizes = list(flavor_mappings.keys()) if flavor_mappings else []
        all_available_sizes = sorted(set(generic_sizes + provider_sizes))
        
        raise ValueError(
            f"Instance '{instance_name}': No mapping found for size '{size}' on provider '{provider}'. "
            f"Available sizes: {', '.join(all_available_sizes)}. "
            f"Check mappings/flavors/generic.yaml and mappings/flavors/{provider}.yaml for supported sizes."
        )
    
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
    


    # Placeholder methods for provider delegation
    def generate_virtual_machine(self, instance, index, yaml_data, available_subnets=None, full_yaml_data=None):
        """Generate virtual machine configuration using provider modules."""
        provider = instance.get("provider")
        if not provider:
            instance_name = instance.get("name", "unknown")
            raise ValueError(f"Instance '{instance_name}' must specify a 'provider'")

        # Handle cheapest provider meta-provider
        selected_instance_type = None
        if provider == 'cheapest':
            provider = self.find_cheapest_provider(instance)
            # Update the instance with the selected provider for consistency
            instance = instance.copy()
            instance['provider'] = provider
            
            # Get the selected instance type from cheapest provider analysis
            selected_instance_type = self.get_cheapest_instance_type(instance, provider)
            print(f"Selected cheapest provider: {provider}")
        elif provider == 'cheapest-gpu':
            provider = self.find_cheapest_gpu_provider(instance)
            # Update the instance with the selected provider for consistency
            instance = instance.copy()
            instance['provider'] = provider
            
            # Get the selected instance type from cheapest GPU provider analysis
            selected_instance_type = self.get_cheapest_gpu_instance_type(instance, provider)
            print(f"Selected cheapest GPU provider: {provider}")

        clean_name = self.clean_name(instance.get("name", f"instance_{index}"))
        size = instance.get("size")
        instance_name = instance.get("name", "unnamed")
        
        # Validate that we have enough information to determine instance type
        direct_instance_type = instance.get("instance_type")
        
        if not direct_instance_type and not selected_instance_type and not size:
            raise ValueError(
                f"Instance '{instance_name}': Must specify either:\n"
                f"  - 'size': nano, micro, small, medium, large, xlarge, etc.\n"
                f"  - 'instance_type': provider-specific type (e.g., 't3.small', 'e2-micro')\n"
                f"  - Use 'provider: cheapest' with requirements (cores, memory, gpu_type)"
            )
        
        # Determine instance type (priority: direct specification > cheapest selection > size mapping)
        instance_type = direct_instance_type or selected_instance_type or self.resolve_instance_type(provider, size, instance)

        # Use full_yaml_data if provided, otherwise fall back to yaml_data
        effective_yaml_data = full_yaml_data if full_yaml_data is not None else yaml_data

        if provider == 'aws':
            strategy_info = {'instance_type': instance_type, 'architecture': 'x86_64'}
            return self.aws_provider.generate_aws_vm(instance, index, clean_name, strategy_info, available_subnets, effective_yaml_data)
        elif provider == 'azure':
            return self.azure_provider.generate_azure_vm(instance, index, clean_name, instance_type, available_subnets, effective_yaml_data)
        elif provider == 'gcp':
            return self.gcp_provider.generate_gcp_vm(instance, index, clean_name, instance_type, available_subnets, effective_yaml_data)
        elif provider == 'oci':
            return self.oci_provider.generate_oci_vm(instance, index, clean_name, instance_type, available_subnets, effective_yaml_data)
        elif provider == 'vmware':
            return self.vmware_provider.generate_vmware_vm(instance, index, clean_name, instance_type, available_subnets, effective_yaml_data)
        elif provider == 'alibaba':
            return self.alibaba_provider.generate_alibaba_vm(instance, index, clean_name, instance_type, available_subnets, effective_yaml_data)
        elif provider in ['ibm_vpc', 'ibm_classic']:
            if provider == 'ibm_vpc':
                return self.ibm_vpc_provider.generate_ibm_vpc_vm(instance, index, clean_name, instance_type, effective_yaml_data)
            else:
                return self.ibm_classic_provider.generate_ibm_classic_vm(instance, index, clean_name, instance_type, effective_yaml_data)
        else:
            raise ValueError(f"Unsupported provider: {provider}")



    def generate_native_security_group_rule(self, rule, provider):
        """Generate native security group rule data for specified provider."""
        # Parse rule data
        protocol = rule.get('protocol', '').lower()
        port_range = rule.get('port_range')
        direction = rule.get('direction', 'ingress')
        source = rule.get('source', '0.0.0.0/0')
        destination = rule.get('destination')
        
        # Validate required fields
        if not protocol:
            raise ValueError(f"Security group rule missing required 'protocol' field. Rule: {rule}")
        if not port_range:
            raise ValueError(f"Security group rule missing required 'port_range' field. Rule: {rule}")
        if not source:
            raise ValueError(f"Security group rule missing required 'source' field. Rule: {rule}")
        
        # Validate destination for egress rules
        if direction == 'egress' and not destination:
            raise ValueError(f"Security group egress rule missing required 'destination' field. Rule: {rule}")
        
        # Validate protocol
        valid_protocols = ['tcp', 'udp', 'icmp', 'icmpv6', 'all', 'ah', 'esp', 'gre', 'ipip']
        if protocol not in valid_protocols:
            raise ValueError(f"Invalid protocol '{protocol}'. Valid protocols: {', '.join(valid_protocols)}. Rule: {rule}")
        
        # Validate port_range format
        import re
        port_pattern = re.compile(r'^([0-9]+|[0-9]+-[0-9]+)$')
        if not port_pattern.match(port_range):
            raise ValueError(f"Invalid port_range '{port_range}'. Must be single port (e.g., '22') or range (e.g., '80-90'). Rule: {rule}")
        
        # Parse port_range to from_port and to_port
        if '-' in port_range:
            from_port, to_port = port_range.split('-', 1)
            from_port = int(from_port.strip())
            to_port = int(to_port.strip())
        else:
            # Single port becomes range
            from_port = int(port_range)
            to_port = from_port
        
        # Validate port numbers
        if from_port < 0 or from_port > 65535 or to_port < 0 or to_port > 65535:
            raise ValueError(f"Port numbers must be between 0 and 65535. Got: {from_port}-{to_port}. Rule: {rule}")
        if from_port > to_port:
            raise ValueError(f"Invalid port range: from_port ({from_port}) cannot be greater than to_port ({to_port}). Rule: {rule}")
        
        # Validate source format
        self._validate_security_group_source(source, provider, rule)
        
        # Validate destination format if provided
        if destination:
            self._validate_security_group_source(destination, provider, rule)
        
        # Handle source/destination
        if self._is_cidr_block(source):
            source_cidr_blocks = [source]
        else:
            # Provider-specific source (e.g., security group reference)
            source_cidr_blocks = [source]  # Will be handled differently by providers
        
        if destination and self._is_cidr_block(destination):
            destination_cidr_blocks = [destination]
        elif destination:
            # Provider-specific destination
            destination_cidr_blocks = [destination]
        else:
            destination_cidr_blocks = []

        # Convert direction for different providers
        if provider == 'azure':
            direction = "Inbound" if direction == 'ingress' else "Outbound"
        elif provider in ['gcp', 'oci']:
            direction = direction.upper()  # INGRESS/EGRESS
        # AWS, IBM VPC, Alibaba use lowercase ingress/egress (no conversion needed)

        # Convert protocol for different providers
        if provider == 'azure':
            if protocol == 'tcp':
                protocol = 'Tcp'
            elif protocol == 'udp':
                protocol = 'Udp'
            elif protocol == 'icmp':
                protocol = 'Icmp'
            elif protocol == 'icmpv6':
                protocol = 'Icmpv6'
            elif protocol == 'all':
                protocol = '*'
            # Other protocols remain as-is
        
        return {
            'direction': direction,
            'from_port': from_port,
            'to_port': to_port,
            'protocol': protocol,
            'source_cidr_blocks': source_cidr_blocks,
            'destination_cidr_blocks': destination_cidr_blocks,
            'source': source,  # Keep original source for provider-specific handling
            'destination': destination,  # Keep original destination for provider-specific handling
            'is_source_cidr': self._is_cidr_block(source),
            'is_destination_cidr': self._is_cidr_block(destination) if destination else True
        }
    
    def _is_cidr_block(self, source):
        """Check if source is a CIDR block."""
        import re
        cidr_pattern = re.compile(r'^([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2}$|^([0-9a-fA-F:]+::?)+/[0-9]{1,3}$')
        return bool(cidr_pattern.match(source))
    
    def _validate_security_group_source(self, source, provider, rule):
        """Validate security group source based on provider capabilities."""
        # CIDR blocks are always supported
        if self._is_cidr_block(source):
            return
        
        # Provider-specific source validation
        if provider == 'cheapest':
            raise ValueError(f"Provider-specific source '{source}' not supported with 'cheapest' provider. Use CIDR blocks only. Rule: {rule}")
        
        # AWS security group references
        if provider == 'aws' and source.startswith('sg-'):
            return
        
        # GCP tag-based sources
        if provider == 'gcp' and source == 'tags':
            return
        
        # Azure application security groups (future support)
        if provider == 'azure' and source.startswith('asg-'):
            return
        
        # IBM VPC security group references (future support)
        if provider == 'ibm_vpc' and source.startswith('sg-'):
            return
        
        # If we get here, it's an unsupported source type for this provider
        raise ValueError(f"Unsupported source '{source}' for provider '{provider}'. Use CIDR blocks or provider-specific references. Rule: {rule}")

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
            
            # Resolve meta providers to actual providers (same logic as networking analysis)
            if provider == 'cheapest':
                provider = self.find_cheapest_provider(instance, suppress_output=True)
            elif provider == 'cheapest-gpu':
                provider = self.find_cheapest_gpu_provider(instance, suppress_output=True)
            
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
            deployment_name = f"{cloud_workspace.get('name', 'yamlforge-deployment')}-{self.get_validated_guid(config)}"
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
        clean_name = self.clean_name(instance_name)
        
        # Handle different image types
        if "FEDORA" in image_key.upper():
            # Fedora images
            fedora_version = self.extract_fedora_version(image_key)
            owner = "125523088429"  # Fedora project account
            name_pattern = f"Fedora-Cloud-Base-{fedora_version}*"
            arch = "x86_64"  # Default architecture for Fedora
            is_gold = False
        else:
            # RHEL images (default)
            rhel_version, arch = self.extract_rhel_info(image_key)
            is_gold = "GOLD" in image_key.upper() or "BYOS" in image_key.upper()
            
            # Determine owner based on image type
            if is_gold:
                owner = "309956199498"  # Red Hat Gold account
                # Use pattern that targets latest versions (e.g., RHEL-9.6.*_HVM.*Access*)
                # This will naturally select the highest version due to lexicographic sorting
                name_pattern = f"RHEL-{rhel_version}.*_HVM.*Access*"
            else:
                owner = "309956199498"  # Red Hat public account
                # Use pattern that targets latest versions (e.g., RHEL-9.6.*_HVM*)
                # This will naturally select the highest version due to lexicographic sorting
                name_pattern = f"RHEL-{rhel_version}.*_HVM*"
        
        # Generate the data source
        data_source = f'''
# AWS AMI Data Source for {image_key}
data "aws_ami" "{clean_name}_ami" {{
  most_recent = true
  owners      = ["{owner}"]

  filter {{
    name   = "name"
    values = ["{name_pattern}"]
  }}

  filter {{
    name   = "virtualization-type"
    values = ["hvm"]
  }}

  filter {{
    name   = "architecture"
    values = ["{arch}"]
  }}

  filter {{
    name   = "root-device-type"
    values = ["ebs"]
  }}'''

        # Add is-public filter for GOLD images
        if is_gold:
            data_source += f'''

  filter {{
    name   = "is-public"
    values = ["false"]
  }}'''

        data_source += f'''
}}
'''
        return data_source

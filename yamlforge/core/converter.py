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
from ..utils import find_yamlforge_file
from ..providers.aws import AWSProvider
from ..providers.azure import AzureProvider
from ..providers.gcp import GCPProvider
from ..providers.ibm_classic import IBMClassicProvider  # type: ignore
from ..providers.ibm_vpc import IBMVPCProvider  # type: ignore
from ..providers.oci import OCIProvider
from ..providers.vmware import VMwareProvider
from ..providers.alibaba import AlibabaProvider
from ..providers.openshift import OpenShiftProvider
from ..providers.cnv import CNVProvider


class YamlForgeConverter:
    """Main converter class that orchestrates multi-cloud infrastructure generation."""

    def __init__(self, images_file="mappings/images.yaml", analyze_mode=False, ansible_mode=False):
        """Initialize the converter with mappings and provider modules."""
        self.ansible_mode = ansible_mode
        # Check Terraform version early (skip if in analyze mode)
        if not analyze_mode:
            self.validate_terraform_version()
        
        self.images = self.load_images(images_file)
        self.locations = self.load_locations("mappings/locations.yaml")
        self.flavors = self.load_flavors("mappings/flavors")
        # Load OpenShift-specific flavors from dedicated directory
        openshift_flavors = self.load_flavors("mappings/flavors_openshift")
        self.flavors.update(openshift_flavors)
        
        # Load storage cost mappings
        self.storage_costs = self.load_storage_costs("mappings/storage_costs.yaml")

        self.core_config = self.load_core_config("defaults/core.yaml")

        # Initialize credentials manager
        self.credentials = CredentialsManager()

        # Initialize provider modules (GUID will be set when processing YAML)
        # Note: AWS provider is initialized lazily to avoid credential checks when not needed
        self._aws_provider = None  # Lazy initialization
        self.azure_provider = AzureProvider(self)
        self.gcp_provider = GCPProvider(self)
        self.ibm_classic_provider = IBMClassicProvider(self)
        self.ibm_vpc_provider = IBMVPCProvider(self)
        self.oci_provider = OCIProvider(self)
        self.vmware_provider = VMwareProvider(self)
        self.alibaba_provider = AlibabaProvider(self)
        
        # Initialize OpenShift provider
        self.openshift_provider = OpenShiftProvider(self)
        
        # Initialize CNV provider
        self.cnv_provider = CNVProvider(self)

        # Current YAML data for GUID extraction
        self.current_yaml_data = None
        
        # Cache for resolved regions to prevent multiple validations
        self._region_cache = {}
        
        # No-credentials mode flag (set by main.py)
        self.no_credentials = False
        
        # Track instance costs for total calculation
        self.instance_costs = []
        # Track OpenShift cluster costs for total calculation
        self.openshift_costs = []

    def get_aws_provider(self):
        """Return the AWS provider instance for use by other components."""
        if self._aws_provider is None:
            self._aws_provider = AWSProvider(self)
        return self._aws_provider

    def get_cnv_provider(self):
        """Return the CNV provider instance for use by other components."""
        if not hasattr(self, '_cnv_provider') or self._cnv_provider is None:
            from yamlforge.providers.cnv.base import BaseCNVProvider
            self._cnv_provider = BaseCNVProvider(self)
        return self._cnv_provider

    def _has_rosa_clusters(self, yaml_data):
        """Check if YAML configuration contains any ROSA clusters."""
        if not yaml_data:
            return False
        
        # Check if openshift_clusters is at root level (legacy) or under yamlforge section
        openshift_clusters = yaml_data.get('openshift_clusters', [])
        if not openshift_clusters and 'yamlforge' in yaml_data:
            openshift_clusters = yaml_data['yamlforge'].get('openshift_clusters', [])
        
        for cluster in openshift_clusters:
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
            if not getattr(self, 'ansible_mode', False):
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
        
        # Merge YAML configuration overrides with core configuration
        if yaml_data and 'yamlforge' in yaml_data:
            yamlforge_config = yaml_data['yamlforge']
            if 'core' in yamlforge_config:
                # Deep merge the core configuration overrides
                self.merge_core_config_overrides(yamlforge_config['core'])
        
        # Clear GUID cache when new YAML data is set
        if hasattr(self, '_validated_guid'):
            delattr(self, '_validated_guid')
        
        # Update GUID in providers that need it
        if hasattr(self.gcp_provider, 'update_guid'):
            try:
                guid = self.get_validated_guid(yaml_data)
                self.gcp_provider.update_guid(guid)
            except Exception as e:
                # Only raise if we don't already have a valid GUID
                if not hasattr(self, '_validated_guid') or not self._validated_guid:
                    raise

    def merge_core_config_overrides(self, yaml_core_config):
        """Merge YAML core configuration overrides with the loaded core configuration."""
        if not hasattr(self, 'core_config'):
            return
        
        # Deep merge the configurations
        self.core_config = self.deep_merge(self.core_config, yaml_core_config)

    def deep_merge(self, base_dict, override_dict):
        """Deep merge two dictionaries, with override_dict taking precedence."""
        result = base_dict.copy()
        
        for key, value in override_dict.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self.deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result

    def load_images(self, file_path):
        """Load image mappings from YAML file."""
        try:
            actual_path = find_yamlforge_file(file_path)
            with open(actual_path, 'r') as f:
                data = yaml.safe_load(f)
                return data.get('images', {})
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Using empty image mappings.")
            return {}



    def load_locations(self, file_path):
        """Load location mappings from YAML file."""
        try:
            actual_path = find_yamlforge_file(file_path)
            with open(actual_path, 'r') as f:
                data = yaml.safe_load(f)
                return data or {}
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Using empty location mappings.")
            return {}

    def load_storage_costs(self, file_path):
        """Load storage cost mappings from YAML file."""
        try:
            actual_path = find_yamlforge_file(file_path)
            with open(actual_path, 'r') as f:
                data = yaml.safe_load(f)
                return data or {}
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Storage cost optimization disabled.")
            return {}

    def load_flavors(self, directory_path):
        """Load flavor mappings from directory."""
        flavors = {}
        
        # Try to find the directory using our path resolution
        try:
            # First try if it's an existing directory (development mode)
            flavor_dir = Path(directory_path)
            if not flavor_dir.exists():
                # Try repository mode (relative to this module)
                module_dir = Path(__file__).parent.parent
                flavor_dir = module_dir / directory_path
                
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
            else:
                # For pip installs, try to load individual files from the package
                try:
                    from importlib.resources import files
                    package_files = files('yamlforge')
                    
                    # Common flavor files to try loading
                    flavor_files = [
                        'alibaba.yaml', 'aws.yaml', 'azure.yaml', 'cheapest.yaml',
                        'cnv.yaml', 'gcp.yaml', 'generic.yaml', 'ibm_classic.yaml',
                        'ibm_vpc.yaml', 'oci.yaml', 'vmware.yaml'
                    ]
                    
                    for filename in flavor_files:
                        try:
                            file_path = f"{directory_path}/{filename}"
                            data_content = package_files.joinpath(file_path).read_text()
                            data = yaml.safe_load(data_content)
                            if data:
                                cloud_name = filename.replace('.yaml', '')
                                if cloud_name == 'generic':
                                    flavors.update(data)
                                else:
                                    flavors[cloud_name] = data
                        except (FileNotFoundError, Exception):
                            # Ignore missing flavor files
                            pass
                except (ImportError, Exception):
                    pass
                    
        except Exception as e:
            print(f"Warning: Could not load flavors from {directory_path}: {e}")
            
        return flavors



    def load_core_config(self, file_path):
        """Load core yamlforge configuration from YAML file."""
        try:
            actual_path = find_yamlforge_file(file_path)
            with open(actual_path, 'r') as f:
                data = yaml.safe_load(f)
                config = data or {}
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Using default core configuration.")
            config = self.get_default_core_config()
        
        # Override with environment variables if present
        self._apply_env_overrides(config)
        return config
    
    def _apply_env_overrides(self, config):
        """Apply environment variable overrides to core configuration."""
        import os
        
        # Check for provider exclusions via environment variable
        # Format: YAMLFORGE_EXCLUDE_PROVIDERS="aws,azure,gcp"
        excluded_providers_env = os.getenv('YAMLFORGE_EXCLUDE_PROVIDERS')
        if excluded_providers_env:
            excluded_providers = [p.strip() for p in excluded_providers_env.split(',') if p.strip()]
            if excluded_providers:
                # Ensure provider_selection exists
                if 'provider_selection' not in config:
                    config['provider_selection'] = {}
                
                # Merge with existing exclusions
                existing_excluded = config['provider_selection'].get('exclude_from_cheapest', [])
                all_excluded = list(set(existing_excluded + excluded_providers))
                config['provider_selection']['exclude_from_cheapest'] = all_excluded
                
                print(f"Environment override: Excluding providers from cheapest analysis: {excluded_providers}")

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
                'provider_cost_factors': {},
                'provider_discounts': {}
            },
            'security': {
                'default_username': 'cloud-user',
                'default_ssh_public_key': '',
                'auto_detect_ssh_keys': False
            }
        }
    
    def apply_discount(self, cost, provider):
        """Apply provider-specific discount to cost if configured."""
        if cost is None:
            return None
        
        # Check for environment variable first (highest priority)
        env_var_name = f"YAMLFORGE_DISCOUNT_{provider.upper()}"
        env_discount = os.environ.get(env_var_name)
        
        discount_percentage = 0
        if env_discount:
            try:
                discount_percentage = float(env_discount)
                # Validate range
                if discount_percentage < 0 or discount_percentage > 100:
                    print(f"Warning: Invalid discount percentage in {env_var_name}={env_discount}. Must be 0-100. Using 0.")
                    discount_percentage = 0
            except ValueError:
                print(f"Warning: Invalid discount percentage in {env_var_name}={env_discount}. Must be a number. Using 0.")
                discount_percentage = 0
        else:
            # Fall back to core config
            provider_discounts = self.core_config.get('cost_analysis', {}).get('provider_discounts', {})
            discount_percentage = provider_discounts.get(provider, 0)
        
        if discount_percentage > 0:
            # Apply discount as percentage (e.g., 15% discount means multiply by 0.85)
            discount_multiplier = (100 - discount_percentage) / 100
            return cost * discount_multiplier
        
        return cost
    
    def get_discount_info(self, provider):
        """Get discount information for a provider."""
        # Check for environment variable first (highest priority)
        env_var_name = f"YAMLFORGE_DISCOUNT_{provider.upper()}"
        env_discount = os.environ.get(env_var_name)
        
        discount_percentage = 0
        discount_source = "core_config"
        
        if env_discount:
            try:
                discount_percentage = float(env_discount)
                # Validate range
                if discount_percentage < 0 or discount_percentage > 100:
                    discount_percentage = 0
                else:
                    discount_source = "environment"
            except ValueError:
                discount_percentage = 0
        else:
            # Fall back to core config
            provider_discounts = self.core_config.get('cost_analysis', {}).get('provider_discounts', {})
            discount_percentage = provider_discounts.get(provider, 0)
        
        return {
            'has_discount': discount_percentage > 0,
            'discount_percentage': discount_percentage,
            'source': discount_source
        }
    
    def _format_cost_with_discount(self, provider, original_cost, discounted_cost):
        """Format cost display showing original and discounted prices if applicable."""
        if original_cost is None or discounted_cost is None:
            return "Cost N/A"
        
        discount_info = self.get_discount_info(provider)
        
        if discount_info['has_discount'] and original_cost != discounted_cost:
            # Show both original and discounted price
            discount_pct = discount_info['discount_percentage']
            return f"${original_cost:.4f}/hour → ${discounted_cost:.4f}/hour ({discount_pct}% discount)"
        else:
            # No discount, show regular price
            return f"${discounted_cost:.4f}/hour"

    def get_ssh_keys(self, yaml_data):
        """Extract SSH keys from YAML configuration."""
        ssh_keys = yaml_data.get('ssh_keys', {})
        
        # Get the default username from core configuration
        default_username = self.core_config.get('security', {}).get('default_username', 'cloud-user')
        
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
                        'username': default_username  # Use configurable default
                    }
                }
            else:
                return {
                    'default': {
                        'public_key': None,
                        'username': default_username  # Use configurable default
                    }
                }
        
        # Ensure all SSH keys have required fields
        normalized_keys = {}
        for key_name, key_config in ssh_keys.items():
            if isinstance(key_config, str):
                # Simple string format: just the public key
                normalized_keys[key_name] = {
                    'public_key': key_config,
                    'username': default_username  # Use configurable default
                }
            elif isinstance(key_config, dict):
                # Full configuration format
                normalized_keys[key_name] = {
                    'public_key': key_config.get('public_key'),
                    'username': key_config.get('username', default_username),  # Use configurable default as fallback
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
        instances = yaml_data.get('yamlforge', {}).get('instances', [])
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

        # Check storage
        storage = yaml_data.get('yamlforge', {}).get('storage', [])
        for bucket in storage:
            provider = bucket.get('provider')
            if provider:
                # Resolve cheapest provider to actual provider
                if provider == 'cheapest':
                    resolved_provider = self.find_cheapest_storage_provider(bucket, suppress_output=True)
                    providers_in_use.add(resolved_provider)
                else:
                    providers_in_use.add(provider)

        # Check OpenShift clusters
        openshift_clusters = yaml_data.get('yamlforge', {}).get('openshift_clusters', [])
        
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
        
        # Validate that cloud_workspace.name is required for all YamlForge configurations
        # Handle both full YAML data and yamlforge section
        if 'yamlforge' in yaml_data:
            # Full YAML data passed
            yamlforge_data = yaml_data.get('yamlforge', {})
        else:
            # Only yamlforge section passed
            yamlforge_data = yaml_data
        
        cloud_workspace = yamlforge_data.get('cloud_workspace', {})
        workspace_name = cloud_workspace.get('name')
        
        if not workspace_name:
            raise ValueError(
                "Configuration Error: 'yamlforge.cloud_workspace.name' is required for all YamlForge configurations.\n\n"
                "Add this to your YAML file:\n"
                "yamlforge:\n"
                "  cloud_workspace:\n"
                "    name: \"your-workspace-name\"\n"
                "    description: \"Optional description\"\n\n"
                "The workspace name is used for:\n"
                "  • Resource naming and organization\n"
                "  • CNV namespace creation\n"
                "  • Cost tracking and management\n"
                "  • Multi-cloud resource grouping"
            )
        
        # Validate that at least one of instances, openshift_clusters, or storage is required under yamlforge
        yamlforge_data = yaml_data.get('yamlforge', {})
        instances = yamlforge_data.get('instances', [])
        openshift_clusters = yamlforge_data.get('openshift_clusters', [])
        storage = yamlforge_data.get('storage', [])
        
        if not instances and not openshift_clusters and not storage:
            raise ValueError(
                "Configuration Error: At least one of 'instances', 'openshift_clusters', or 'storage' is required in YamlForge configurations.\n\n"
                "Add at least one of these to your YAML file:\n\n"
                "For cloud instances:\n"
                "yamlforge:\n"
                "  cloud_workspace:\n"
                "    name: \"your-workspace-name\"\n"
                "  instances:\n"
                "    - name: \"my-instance-{guid}\"\n"
                "      provider: \"aws\"\n"
                "      flavor: \"small\"\n"
                "      image: \"RHEL9-latest\"\n"
                "      region: \"us-east-1\"\n"
                "      ssh_key: \"my-key\"\n\n"
                "For OpenShift clusters:\n"
                "yamlforge:\n"
                "  cloud_workspace:\n"
                "    name: \"your-workspace-name\"\n"
                "  openshift_clusters:\n"
                "    - name: \"my-cluster-{guid}\"\n"
                "      type: \"rosa-classic\"\n"
                "      region: \"us-east-1\"\n"
                "      size: \"small\"\n\n"
                "For object storage:\n"
                "yamlforge:\n"
                "  cloud_workspace:\n"
                "    name: \"your-workspace-name\"\n"
                "  storage:\n"
                "    - name: \"my-bucket-{guid}\"\n"
                "      provider: \"aws\"\n"
                "      region: \"us-east-1\"\n\n"
                "YamlForge is designed to deploy cloud instances, OpenShift clusters, and object storage."
            )
        
        required_providers = self.detect_required_providers(yaml_data)
        
        # Validate that all instances have required fields
        instances = yamlforge_data.get('instances', [])
        for instance in instances:
            provider = instance.get('provider')
            if provider and provider != 'cnv':  # CNV doesn't need regions
                # Check if instance has region or location
                has_region = 'region' in instance
                has_location = 'location' in instance
                
                if not has_region and not has_location:
                    instance_name = instance.get('name', 'unnamed')
                    raise ValueError(
                        f"Configuration Error: Instance '{instance_name}' (provider: {provider}) must specify either 'region' or 'location'.\n\n"
                        f"Add one of these to your instance configuration:\n"
                        f"  region: \"us-east-1\"  # Direct region specification\n"
                        f"  location: \"east\"     # Location mapping (see mappings/locations.yaml)\n\n"
                        f"Available locations: {', '.join(sorted(self.locations.keys()))}\n"
                        f"Common regions: us-east-1, us-west-2, eu-west-1, ap-southeast-1"
                    )
                
                if has_region and has_location:
                    instance_name = instance.get('name', 'unnamed')
                    raise ValueError(
                        f"Configuration Error: Instance '{instance_name}' cannot specify both 'region' and 'location'.\n\n"
                        f"Choose one:\n"
                        f"  region: \"us-east-1\"  # Direct region specification\n"
                        f"  location: \"east\"     # Location mapping"
                    )
        
        # Validate that all storage buckets have required fields
        storage = yamlforge_data.get('storage', [])
        for bucket in storage:
            provider = bucket.get('provider')
            if provider:
                # Check if bucket has region or location
                has_region = 'region' in bucket
                has_location = 'location' in bucket
                
                if not has_region and not has_location:
                    bucket_name = bucket.get('name', 'unnamed')
                    raise ValueError(
                        f"Configuration Error: Storage bucket '{bucket_name}' (provider: {provider}) must specify either 'region' or 'location'.\n\n"
                        f"Add one of these to your bucket configuration:\n"
                        f"  region: \"us-east-1\"  # Direct region specification\n"
                        f"  location: \"east\"     # Location mapping (see mappings/locations.yaml)\n\n"
                        f"Available locations: {', '.join(sorted(self.locations.keys()))}\n"
                        f"Common regions: us-east-1, us-west-2, eu-west-1, ap-southeast-1"
                    )
                
                if has_region and has_location:
                    bucket_name = bucket.get('name', 'unnamed')
                    raise ValueError(
                        f"Configuration Error: Storage bucket '{bucket_name}' cannot specify both 'region' and 'location'.\n\n"
                        f"Choose one:\n"
                        f"  region: \"us-east-1\"  # Direct region specification\n"
                        f"  location: \"east\"     # Location mapping"
                    )
        
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
                        self.get_aws_provider().validate_aws_setup()
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
            elif provider == 'cnv':
                # Get CNV configuration
                yamlforge_config = yaml_data.get('yamlforge', {})
                cnv_config = yamlforge_config.get('cnv', {})
                validate_operator = cnv_config.get('validate_operator', True)
                
                # Skip CNV validation for now to avoid hanging
                print("CNV operator validation skipped (temporarily disabled)")
                
                # TODO: Re-enable validation once kubectl timeout issues are resolved
                # if validate_operator:
                #     try:
                #         # Import CNV provider and validate operator
                #         from yamlforge.providers.cnv.base import BaseCNVProvider
                #         cnv_provider = BaseCNVProvider(self)
                #         if not cnv_provider.validate_cnv_operator():
                #             raise ValueError("CNV/KubeVirt operator is not installed or not working")
                #     except ImportError:
                #         print("Warning: CNV provider not available for validation")
                #     except Exception as e:
                #         # Get CNV instances for error context
                #         cnv_instances = []
                #         for instance in yaml_data.get('instances', []):
                #             if instance.get('provider') == 'cnv':
                #                 cnv_instances.append(instance.get('name', 'unnamed'))
                #         
                #         instance_list = ', '.join(cnv_instances) if cnv_instances else 'CNV instances'
                #         error_msg = f"CNV Provider Error (needed for: {instance_list}): {str(e)}"
                #         raise ValueError(error_msg) from e
                # else:
                #     print("CNV operator validation skipped (validate_operator: false)")

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

    def validate_ibm_cloud_region_consistency(self, instances):
        """Validate that all IBM Cloud instances use the same region due to Terraform provider limitations."""
        ibm_instances = []
        
        # IBM Classic datacenter to region mapping
        ibm_classic_datacenter_regions = {
            'dal10': 'us-south', 'dal12': 'us-south', 'dal13': 'us-south',
            'wdc04': 'us-east', 'wdc06': 'us-east', 'wdc07': 'us-east',
            'sjc03': 'us-west', 'sjc04': 'us-west',
            'lon04': 'eu-gb', 'lon05': 'eu-gb', 'lon06': 'eu-gb',
            'fra02': 'eu-de', 'fra04': 'eu-de', 'fra05': 'eu-de',
            'tok02': 'jp-tok', 'tok04': 'jp-tok', 'tok05': 'jp-tok',
            'syd01': 'au-syd', 'syd04': 'au-syd', 'syd05': 'au-syd',
            'sao01': 'br-sao', 'sao04': 'br-sao', 'sao05': 'br-sao',
            'tor01': 'ca-tor', 'tor04': 'ca-tor', 'tor05': 'ca-tor'
        }
        
        for instance in instances:
            provider = instance.get('provider')
            if provider in ['ibm_vpc', 'ibm_classic']:
                instance_name = instance.get('name', 'unnamed')
                resolved_region = self._resolve_instance_region_silent(instance, provider)
                
                # Normalize IBM Classic datacenter names to region names
                if provider == 'ibm_classic' and resolved_region in ibm_classic_datacenter_regions:
                    normalized_region = ibm_classic_datacenter_regions[resolved_region]
                else:
                    normalized_region = resolved_region
                
                ibm_instances.append({
                    'name': instance_name,
                    'provider': provider,
                    'region': resolved_region,
                    'normalized_region': normalized_region
                })
        
        if len(ibm_instances) <= 1:
            return  # No validation needed for single or no IBM instances
        
        # Check if all instances have the same normalized region
        first_normalized_region = ibm_instances[0]['normalized_region']
        conflicting_instances = []
        
        for instance in ibm_instances[1:]:
            if instance['normalized_region'] != first_normalized_region:
                conflicting_instances.append(instance)
        
        if conflicting_instances:
            # Build detailed error message
            error_msg = (
                f"IBM Cloud Configuration Error: Multiple instances with different regions detected.\n\n"
                f"IBM Cloud Limitation: All IBM Cloud resources in a single Terraform configuration must be in the same region.\n\n"
                f"First instance region: {ibm_instances[0]['region']} ({ibm_instances[0]['name']} - {ibm_instances[0]['provider']})\n"
                f"Normalized region: {first_normalized_region}\n\n"
                f"Conflicting instances:\n"
            )
            
            for instance in conflicting_instances:
                error_msg += f"  • {instance['name']} ({instance['provider']}): {instance['region']} (normalized: {instance['normalized_region']})\n"
            
            error_msg += (
                f"\nSolutions:\n"
                f"1. Use the same region for all IBM Cloud instances (recommended: {first_normalized_region})\n"
                f"2. Split your configuration into separate YAML files with different regions\n"
                f"3. Use different GUIDs for each region-specific deployment\n\n"
                f"Example fix - update all IBM instances to use region '{first_normalized_region}':\n"
                f"  instances:\n"
                f"    - name: \"vm1\"\n"
                f"      provider: \"ibm_vpc\"\n"
                f"      region: \"{first_normalized_region}\"  # Use consistent region\n"
                f"    - name: \"vm2\"\n"
                f"      provider: \"ibm_classic\"\n"
                f"      location: \"wdc07\"  # Maps to {first_normalized_region} region\n"
            )
            
            raise ValueError(error_msg)



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
        ibm_provider_added = False  # Track if IBM provider has been added
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
            elif provider in ['ibm_vpc', 'ibm_classic']:
                # Only add IBM provider once, even if both ibm_vpc and ibm_classic are used
                if not ibm_provider_added:
                    terraform_content += '''
    ibm = {
      source  = "IBM-Cloud/ibm"
      version = "~> 1.0"
    }'''
                    ibm_provider_added = True
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
            elif provider == 'cnv':
                terraform_content += '''
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = "~> 1.14"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }'''

        terraform_content += '''
  }
}

'''

        # Add provider configurations for each required provider
        ibm_provider_config_added = False  # Track if IBM provider config has been added
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
            elif provider in ['ibm_vpc', 'ibm_classic']:
                # Only add IBM provider configuration once, even if both ibm_vpc and ibm_classic are used
                if not ibm_provider_config_added:
                    terraform_content += '''# IBM Cloud Provider Configuration
provider "ibm" {
  ibmcloud_api_key = var.ibm_api_key
  region           = var.ibm_region
}

'''
                    ibm_provider_config_added = True
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
            elif provider == 'cnv':
                terraform_content += '''# CNV/Kubernetes Provider Configuration
# Uses OpenShift environment variables for authentication
provider "kubernetes" {
  host                   = var.openshift_cluster_url
  token                  = var.openshift_cluster_token
  insecure               = false
  cluster_ca_certificate = base64decode(var.openshift_cluster_ca_cert)
}

provider "kubectl" {
  host                   = var.openshift_cluster_url
  token                  = var.openshift_cluster_token
  insecure               = false
  cluster_ca_certificate = base64decode(var.openshift_cluster_ca_cert)
  load_config_file       = false
}

provider "helm" {
  host                   = var.openshift_cluster_url
  token                  = var.openshift_cluster_token
  insecure               = false
  cluster_ca_certificate = base64decode(var.openshift_cluster_ca_cert)
}

'''

        # Generate GCP project management if GCP is used
        if 'gcp' in required_providers:
            # Always create new project for GCP deployments (enables folder-based project creation)
            terraform_content += self.gcp_provider.generate_project_management(yaml_data)

        # Collect zone information for IBM VPC instances (do this once)
        ibm_vpc_zones = self.collect_ibm_vpc_zones(yaml_data)
        
        # Generate regional networking infrastructure
        terraform_content += '''# ========================================
# Regional Networking Infrastructure
# ========================================

'''
        terraform_content += self.generate_regional_networking(yaml_data, ibm_vpc_zones)

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
        
        # Validate IBM Cloud region consistency
        self.validate_ibm_cloud_region_consistency(instances)
        
        instance_counter = 1
        for instance in instances:
            # Get count for this instance (default to 1 if not specified)
            instance_count = instance.get('count', 1)
            
            # Generate multiple instances if count > 1
            for instance_index in range(instance_count):
                # Get zone for IBM VPC instances
                zone = None
                if instance.get('provider') == 'ibm_vpc':
                    region = self.resolve_instance_region(instance, 'ibm_vpc')
                    zone = ibm_vpc_zones.get(region)
                
                # Create a copy of the instance with modified name if count > 1
                instance_copy = instance.copy()
                if instance_count > 1:
                    original_name = instance_copy['name']
                    # Resolve GUID first before applying count naming logic
                    if '{guid}' in original_name:
                        guid = self.get_validated_guid()
                        original_name = original_name.replace('{guid}', guid)
                    
                    # Check if name ends with a number and increment from there
                    import re
                    match = re.search(r'(.+?)(\d+)$', original_name)
                    if match:
                        # Name ends with number, increment from that base
                        base_name = match.group(1)
                        base_number_str = match.group(2)
                        base_number = int(base_number_str)
                        # Preserve padding (e.g., 01, 02, 003) by using the same width
                        padding_width = len(base_number_str)
                        new_number = base_number + instance_index
                        instance_copy['name'] = f"{base_name}{new_number:0{padding_width}d}"
                    else:
                        # Name doesn't end with number, append -X
                        instance_copy['name'] = f"{original_name}-{instance_index + 1}"
                
                terraform_content += self.generate_virtual_machine(instance_copy, instance_counter, yaml_data, full_yaml_data=effective_yaml_data, zone=zone)
                instance_counter += 1

        # Generate object storage buckets
        terraform_content += '''
# ========================================
# Object Storage Buckets
# ========================================

'''
        storage = yaml_data.get('storage', [])
        for bucket in storage:
            terraform_content += self.generate_storage_bucket(bucket, yaml_data, effective_yaml_data)

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
            clean_name, has_guid_placeholder = self.clean_name(instance_name)
            ssh_username = self.get_instance_ssh_username(instance, 'aws', yaml_data)
            
            # Check if the clean_name already ends with the GUID (to avoid duplication)
            if clean_name.endswith(f"_{guid}"):
                resource_name = clean_name
            elif has_guid_placeholder:
                resource_name = clean_name
            else:
                resource_name = f"{clean_name}_{guid}"
            
            outputs.append(f'''    "{instance_name}" = {{
      public_ip = aws_instance.{resource_name}.public_ip
      private_ip = aws_instance.{resource_name}.private_ip
      public_dns = aws_instance.{resource_name}.public_dns
      instance_id = aws_instance.{resource_name}.id
      instance_type = aws_instance.{resource_name}.instance_type
      availability_zone = aws_instance.{resource_name}.availability_zone
      ssh_username = "{ssh_username}"
      ssh_command = "ssh {ssh_username}@${{aws_instance.{resource_name}.public_ip}}"
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
            clean_name, has_guid_placeholder = self.clean_name(instance_name)
            
            # Use clean_name directly if GUID is already present, otherwise add GUID
            resource_name = clean_name if has_guid_placeholder else f"{clean_name}_{guid}"
            
            ssh_username = self.get_instance_ssh_username(instance, 'gcp', yaml_data)
            
            # Build the output with conditional DNS information
            output_block = f'''    "{instance_name}" = {{
      public_ip = google_compute_address.{resource_name}_ip.address
      private_ip = google_compute_instance.{resource_name}.network_interface[0].network_ip
      machine_type = google_compute_instance.{resource_name}.machine_type
      zone = google_compute_instance.{resource_name}.zone
      self_link = google_compute_instance.{resource_name}.self_link
      ssh_username = "{ssh_username}"
      ssh_command = "ssh {ssh_username}@${{google_compute_address.{resource_name}_ip.address}}"'''
            
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
            clean_name, has_guid_placeholder = self.clean_name(instance_name)
            
            # Use clean_name directly if GUID is already present, otherwise add GUID
            resource_name = clean_name if has_guid_placeholder else f"{clean_name}_{guid}"
            
            ssh_username = self.get_instance_ssh_username(instance, 'azure', yaml_data)
            
            outputs.append(f'''    "{instance_name}" = {{
      public_ip = azurerm_public_ip.{resource_name}_ip.ip_address
      private_ip = azurerm_network_interface.{resource_name}_nic.ip_configuration[0].private_ip_address
      vm_size = azurerm_linux_virtual_machine.{resource_name}.size
      location = azurerm_linux_virtual_machine.{resource_name}.location
      resource_group = azurerm_linux_virtual_machine.{resource_name}.resource_group_name
      ssh_username = "{ssh_username}"
      ssh_command = "ssh {ssh_username}@${{azurerm_public_ip.{resource_name}_ip.ip_address}}"
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
            clean_name, has_guid_placeholder = self.clean_name(instance_name)
            ssh_username = self.get_instance_ssh_username(instance, 'ibm_vpc', yaml_data)
            
            # Use clean_name directly if GUID is already present, otherwise add GUID
            resource_name = clean_name if has_guid_placeholder else f"{clean_name}_{guid}"
            
            outputs.append(f'''    "{instance_name}" = {{
      public_ip = ibm_is_floating_ip.{resource_name}_fip.address
      private_ip = ibm_is_instance.{resource_name}.primary_network_interface[0].primary_ip
      profile = ibm_is_instance.{resource_name}.profile
      zone = ibm_is_instance.{resource_name}.zone
      vpc = ibm_is_instance.{resource_name}.vpc
      ssh_username = "{ssh_username}"
      ssh_command = "ssh {ssh_username}@${{ibm_is_floating_ip.{resource_name}_fip.address}}"
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
            clean_name, has_guid_placeholder = self.clean_name(instance_name)
            ssh_username = self.get_instance_ssh_username(instance, 'ibm_classic', yaml_data)
            
            # Use clean_name directly if GUID is already present, otherwise add GUID
            resource_name = clean_name if has_guid_placeholder else f"{clean_name}_{guid}"
            
            outputs.append(f'''    "{instance_name}" = {{
      public_ip = ibm_compute_vm_instance.{resource_name}.ipv4_address
      private_ip = ibm_compute_vm_instance.{resource_name}.ipv4_address_private
      flavor = ibm_compute_vm_instance.{resource_name}.flavor_key_name
      datacenter = ibm_compute_vm_instance.{resource_name}.datacenter
      ssh_username = "{ssh_username}"
      ssh_command = "ssh {ssh_username}@${{ibm_compute_vm_instance.{resource_name}.ipv4_address}}"
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
            clean_name, has_guid_placeholder = self.clean_name(instance_name)
            ssh_username = self.get_instance_ssh_username(instance, 'vmware', yaml_data)
            
            # Use clean_name directly if GUID is already present, otherwise add GUID
            resource_name = clean_name if has_guid_placeholder else f"{clean_name}_{guid}"
            
            outputs.append(f'''    "{instance_name}" = {{
      ip_address = vsphere_virtual_machine.{resource_name}.default_ip_address
      guest_ip_addresses = vsphere_virtual_machine.{resource_name}.guest_ip_addresses
      num_cpus = vsphere_virtual_machine.{resource_name}.num_cpus
      memory = vsphere_virtual_machine.{resource_name}.memory
      power_state = vsphere_virtual_machine.{resource_name}.power_state
      ssh_username = "{ssh_username}"
      ssh_command = "ssh {ssh_username}@${{vsphere_virtual_machine.{resource_name}.default_ip_address}}"
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
                # clean_name already handles GUID replacement
                clean_name, has_guid_placeholder = self.clean_name(instance_name)
                ssh_username = self.get_instance_ssh_username(instance, provider, yaml_data)
                
                # Use clean_name directly if GUID is already present, otherwise add GUID
                resource_name = clean_name if has_guid_placeholder else f"{clean_name}_{guid}"
                
                # Generate provider-specific IP reference
                if provider == 'aws':
                    ip_ref = f"aws_instance.{resource_name}.public_ip"
                    private_ip_ref = f"aws_instance.{resource_name}.private_ip"
                elif provider == 'gcp':
                    ip_ref = f"google_compute_address.{resource_name}_ip.address"
                    private_ip_ref = f"google_compute_instance.{resource_name}.network_interface[0].network_ip"
                elif provider == 'azure':
                    ip_ref = f"azurerm_public_ip.{resource_name}_ip.ip_address"
                    private_ip_ref = f"azurerm_network_interface.{resource_name}_nic.ip_configuration[0].private_ip_address"
                elif provider == 'oci':
                    ip_ref = f"oci_core_instance.{resource_name}.public_ip"
                    private_ip_ref = f"oci_core_instance.{resource_name}.private_ip"
                elif provider == 'alibaba':
                    ip_ref = f"alicloud_eip_association.{resource_name}_eip_assoc.ip_address"
                    private_ip_ref = f"alicloud_instance.{resource_name}.private_ip"
                elif provider == 'ibm_vpc':
                    ip_ref = f"ibm_is_floating_ip.{resource_name}_fip.address"
                    private_ip_ref = f"ibm_is_instance.{resource_name}.primary_network_interface[0].primary_ip"
                elif provider == 'ibm_classic':
                    ip_ref = f"ibm_compute_vm_instance.{resource_name}.ipv4_address"
                    private_ip_ref = f"ibm_compute_vm_instance.{resource_name}.ipv4_address_private"
                elif provider == 'vmware':
                    ip_ref = f"vsphere_virtual_machine.{resource_name}.default_ip_address"
                    private_ip_ref = f"vsphere_virtual_machine.{resource_name}.default_ip_address"
                elif provider == 'cnv':
                    ip_ref = "\"NODE_IP\""
                    private_ip_ref = "\"N/A\""
                else:
                    ip_ref = "\"N/A\""
                    private_ip_ref = "\"N/A\""
                
                # Generate SSH command based on provider
                if provider == 'cnv':
                    ssh_command = f"ssh {ssh_username}@${{{ip_ref}}} -p ${{kubernetes_service.{resource_name}_ssh_service.spec[0].port[0].node_port}}"
                else:
                    ssh_command = f"ssh {ssh_username}@${{{ip_ref}}}"
                
                outputs.append(f'''    "{instance_name}" = {{
      provider = "{self.format_provider_name_for_display(provider)}"
      public_ip = {ip_ref}
      private_ip = {private_ip_ref}
      size = "{instance.get('size', 'unknown')}"
      image = "{instance.get('image', 'unknown')}"
      region = "{instance.get('region', 'N/A')}"
      ssh_username = "{ssh_username}"
      ssh_command = "{ssh_command}"
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
                # clean_name already handles GUID replacement
                clean_name, has_guid_placeholder = self.clean_name(instance_name)
                
                # Use clean_name directly if GUID is already present, otherwise add GUID
                resource_name = clean_name if has_guid_placeholder else f"{clean_name}_{guid}"
                
                # Generate provider-specific IP reference
                if provider == 'aws':
                    ip_ref = f"aws_instance.{resource_name}.public_ip"
                elif provider == 'gcp':
                    ip_ref = f"google_compute_address.{resource_name}_ip.address"
                elif provider == 'azure':
                    ip_ref = f"azurerm_public_ip.{resource_name}_ip.ip_address"
                elif provider == 'oci':
                    ip_ref = f"oci_core_instance.{resource_name}.public_ip"
                elif provider == 'alibaba':
                    ip_ref = f"alicloud_eip_association.{resource_name}_eip_assoc.ip_address"
                elif provider == 'ibm_vpc':
                    ip_ref = f"ibm_is_floating_ip.{resource_name}_fip.address"
                elif provider == 'ibm_classic':
                    ip_ref = f"ibm_compute_vm_instance.{resource_name}.ipv4_address"
                elif provider == 'vmware':
                    ip_ref = f"vsphere_virtual_machine.{resource_name}.default_ip_address"
                elif provider == 'cnv':
                    ip_ref = "\"NODE_IP\""
                else:
                    ip_ref = "\"N/A\""
                
                outputs.append(f'''    "{instance_name}" = {ip_ref}''')
        
        outputs.append('''  }
}

''')
        return '\n'.join(outputs)

    def format_provider_name_for_display(self, provider):
        """Format provider name for display purposes."""
        provider_display_names = {
            'aws': 'AWS',
            'gcp': 'GCP', 
            'azure': 'Azure',
            'oci': 'OCI',
            'alibaba': 'Alibaba Cloud',
            'ibm_vpc': 'IBM VPC',
            'ibm_classic': 'IBM Classic',
            'vmware': 'VMware'
        }
        return provider_display_names.get(provider, provider.upper())

    def print_provider_output(self, provider, message, indent_level=1):
        """Print provider-specific output with proper formatting."""
        provider_name = self.format_provider_name_for_display(provider)
        indent = "  " * indent_level
        print(f"{indent}{provider_name}: {message}")

    def start_provider_section(self, provider):
        """Start a new provider section in output."""
        provider_name = self.format_provider_name_for_display(provider)
        print(f"{provider_name}:")

    def start_global_section(self):
        """Start the global section for setup operations."""
        if not getattr(self, 'ansible_mode', False):
            print()
            print("[GLOBAL]")

    def print_global_output(self, message, indent_level=1):
        """Print global output with proper indentation."""
        if not getattr(self, 'ansible_mode', False):
            indent = "  " * indent_level
            print(f"{indent}{message}")

    def start_instance_section(self, instance_name, provider):
        """Start a new instance section in the output."""
        print()
        # Replace {guid} with actual GUID in instance name
        resolved_instance_name = self.replace_guid_placeholders(instance_name)
        print(f"[{resolved_instance_name}]")

    def print_instance_output(self, instance_name, provider, message, indent_level=1):
        """Print instance-specific output with proper indentation."""
        indent = "  " * indent_level
        print(f"{indent}{message}")

    def _print_cost_analysis_for_instance(self, instance, selected_provider):
        """Print cost analysis for cheapest provider selection under instance section."""
        instance_name = instance.get('name', 'unnamed')
        instance_count = instance.get('count', 1)
        # Get instance-specific exclusions
        instance_exclusions = instance.get('exclude_providers', [])
        
        # Get cost information for all providers
        # Handle memory in either MB or GB format
        memory_value = instance.get('memory', 4)
        if memory_value < 100:  # Assume GB if less than 100
            memory_mb = memory_value * 1024
        else:  # Assume MB if 100 or greater
            memory_mb = memory_value
            
        provider_costs = self.find_cheapest_by_specs(
            instance.get('cores', 2), 
            memory_mb,
            instance.get('gpu_count', 0),
            instance.get('gpu_type'),
            instance_exclusions
        )
        
        if provider_costs:
            # Apply discounts to provider costs for display
            for provider in provider_costs:
                original_cost = provider_costs[provider]['cost']
                provider_costs[provider]['original_cost'] = original_cost
                provider_costs[provider]['cost'] = self.apply_discount(original_cost, provider)
            
            cost_header = f"Cost analysis (x{instance_count} instances):" if instance_count > 1 else "Cost analysis:"
            self.print_instance_output(instance_name, selected_provider, cost_header)
            for provider, info in sorted(provider_costs.items(), key=lambda x: x[1]['cost']):
                marker = " ← SELECTED" if provider == selected_provider else ""
                vcpus = info.get('vcpus', 'N/A')
                memory_gb = info.get('memory_gb', 'N/A')
                gpu_count = info.get('gpu_count', 0)
                detected_gpu_type = info.get('gpu_type', '')
                
                # Calculate total cost for all instances (using discounted cost)
                per_hour_cost = info['cost']
                total_hourly_cost = per_hour_cost * instance_count
                
                # Format cost with discount info
                cost_display = self._format_cost_with_discount(provider, info.get('original_cost'), per_hour_cost)
                
                if gpu_count > 0:
                    gpu_info = f", {gpu_count}x {detected_gpu_type}" if detected_gpu_type else f", {gpu_count} GPU(s)"
                    if instance_count > 1:
                        self.print_instance_output(instance_name, selected_provider, 
                            f"  {provider}: {cost_display} each, ${total_hourly_cost:.4f}/hour total ({info['instance_type']}, {vcpus} vCPU, {memory_gb}GB{gpu_info}){marker}", 2)
                    else:
                        self.print_instance_output(instance_name, selected_provider, 
                            f"  {provider}: {cost_display} ({info['instance_type']}, {vcpus} vCPU, {memory_gb}GB{gpu_info}){marker}", 2)
                else:
                    if instance_count > 1:
                        self.print_instance_output(instance_name, selected_provider, 
                            f"  {provider}: {cost_display} each, ${total_hourly_cost:.4f}/hour total ({info['instance_type']}, {vcpus} vCPU, {memory_gb}GB){marker}", 2)
                    else:
                        self.print_instance_output(instance_name, selected_provider, 
                            f"  {provider}: {cost_display} ({info['instance_type']}, {vcpus} vCPU, {memory_gb}GB){marker}", 2)

    def _print_gpu_cost_analysis_for_instance(self, instance, selected_provider):
        """Print GPU cost analysis for cheapest GPU provider selection under instance section."""
        instance_name = instance.get('name', 'unnamed')
        instance_count = instance.get('count', 1)
        gpu_type = instance.get("gpu_type")
        
        # Get instance-specific exclusions
        instance_exclusions = instance.get('exclude_providers', [])
        
        # Get cost information for all providers (GPU instances only)
        provider_costs = self.find_cheapest_gpu_by_specs(gpu_type, instance_exclusions)
        
        if provider_costs:
            # Apply discounts to provider costs for display
            for provider in provider_costs:
                original_cost = provider_costs[provider]['cost']
                provider_costs[provider]['original_cost'] = original_cost
                provider_costs[provider]['cost'] = self.apply_discount(original_cost, provider)
            
            analysis_type = f"cheapest {gpu_type} GPU" if gpu_type else "cheapest GPU (any type)"
            cost_header = f"GPU-optimized cost analysis ({analysis_type}, x{instance_count} instances):" if instance_count > 1 else f"GPU-optimized cost analysis ({analysis_type}):"
            self.print_instance_output(instance_name, selected_provider, cost_header)
            for provider, info in sorted(provider_costs.items(), key=lambda x: x[1]['cost']):
                marker = " ← SELECTED" if provider == selected_provider else ""
                vcpus = info.get('vcpus', 'N/A')
                memory_gb = info.get('memory_gb', 'N/A')
                gpu_count = info.get('gpu_count', 0)
                detected_gpu_type = info.get('gpu_type', '')
                
                # Calculate total cost for all instances (using discounted cost)
                per_hour_cost = info['cost']
                total_hourly_cost = per_hour_cost * instance_count
                
                # Format cost with discount info
                cost_display = self._format_cost_with_discount(provider, info.get('original_cost'), per_hour_cost)
                
                gpu_info = f", {gpu_count}x {detected_gpu_type}" if detected_gpu_type else f", {gpu_count} GPU(s)"
                if instance_count > 1:
                    self.print_instance_output(instance_name, selected_provider, 
                        f"  {provider}: {cost_display} each, ${total_hourly_cost:.4f}/hour total ({info['instance_type']}, {vcpus} vCPU, {memory_gb}GB{gpu_info}){marker}", 2)
                else:
                    self.print_instance_output(instance_name, selected_provider, 
                        f"  {provider}: {cost_display} ({info['instance_type']}, {vcpus} vCPU, {memory_gb}GB{gpu_info}){marker}", 2)

    def get_instance_ssh_username(self, instance, provider, yaml_data=None):
        """Get the SSH username for an instance based on provider and operating system."""
        # Check if username is explicitly configured for this instance
        if instance.get('username'):
            return instance['username']
        
        # Check if SSH username is explicitly configured for this instance via SSH key config
        ssh_key_config = self.get_instance_ssh_key(instance, yaml_data or {})
        if ssh_key_config and ssh_key_config.get('username'):
            return ssh_key_config['username']
        
        # Get the default username from core configuration
        default_username = self.core_config.get('security', {}).get('default_username', 'cloud-user')
        
        # Determine username based on provider and image
        image = instance.get('image', '')
        
        # Debug output to trace the issue  
        # print(f"SSH DEBUG START: provider='{provider}', image='{image}'")
        
        if provider == 'aws':
            # AWS usernames - use configurable default for all images
            if any(os_name in image.upper() for os_name in ['RHEL', 'REDHAT']):
                return default_username
            elif 'UBUNTU' in image.upper():
                return default_username
            elif any(os_name in image.upper() for os_name in ['AMAZON', 'AMZN']):
                return default_username
            elif 'CENTOS' in image.upper():
                return default_username
            elif 'FEDORA' in image.upper():
                return default_username
            elif 'SUSE' in image.upper():
                return default_username
            else:
                return default_username  # Default for AWS
                
        elif provider == 'gcp':
            # GCP usernames - use configurable default for all images
            if any(os_name in image.upper() for os_name in ['RHEL', 'REDHAT']):
                return default_username
            elif 'UBUNTU' in image.upper():
                return default_username
            elif 'CENTOS' in image.upper():
                return default_username
            elif 'FEDORA' in image.upper():
                return default_username
            elif 'DEBIAN' in image.upper():
                return default_username
            else:
                return default_username  # Default for GCP
                
        elif provider == 'azure':
            # Azure usernames - use configurable default
            return default_username
            
        elif provider == 'oci':
            # OCI usernames - use configurable default for all images
            if any(os_name in image.upper() for os_name in ['ORACLE', 'OL']):
                return default_username
            elif 'UBUNTU' in image.upper():
                return default_username
            elif any(os_name in image.upper() for os_name in ['RHEL', 'REDHAT']):
                return default_username
            elif 'CENTOS' in image.upper():
                return default_username
            else:
                return default_username  # Default for OCI
                
        elif provider == 'alibaba':
            # Alibaba Cloud - use configurable default
            return default_username
            
        elif provider in ['ibm_vpc', 'ibm_classic']:
            # IBM Cloud username depends on RHEL version and cloud-user configuration
            if any(os_name in image.upper() for os_name in ['RHEL', 'REDHAT']):
                # Check if cloud-user creation is enabled in IBM VPC config
                ibm_vpc_config = yaml_data.get('yamlforge', {}).get('ibm_vpc', {})
                create_cloud_user = ibm_vpc_config.get('create_cloud_user', True)  # Default to True
                
                if create_cloud_user:
                    # Check for RHEL version
                    import re
                    version_match = re.search(r'(\d+)', image)
                    if version_match:
                        version = version_match.group(1)
                        if version == '9':
                            return default_username  # RHEL 9 uses configurable default
                        else:
                            return default_username  # RHEL 8 and earlier also use configurable default
                    else:
                        return default_username  # Default to configurable default if version can't be determined
                else:
                    return 'root'  # Use root when cloud-user creation is disabled
            else:
                return default_username  # Default for non-RHEL images
            
        elif provider == 'vmware':
            # VMware - use configurable default
            return default_username
            
        else:
            # Unknown provider - return configurable default
            return default_username

    def generate_variables_tf(self, required_providers, yaml_data=None):
        """Generate variables.tf file with variables for required providers."""
        variables_content = '''# Variables for multi-cloud deployment
# Generated by YamlForge v2.0
# SSH keys are configured in YAML and embedded directly in resources

'''

        if 'aws' in required_providers:
            # Get the primary AWS region that will be used
            primary_aws_region = self.get_primary_aws_region(yaml_data) if yaml_data else None
            
            variables_content += f'''# AWS Variables
# Note: AWS region is determined from your YAML configuration: {primary_aws_region or 'No regions specified'}

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

variable "redhat_openshift_api_url" {
  description = "Red Hat OpenShift API URL"
  type        = string
  default     = "https://api.openshift.com"
}

'''
        if 'cnv' in required_providers:
            variables_content += '''# CNV/Kubernetes Variables
variable "openshift_cluster_url" {
  description = "OpenShift cluster API URL"
  type        = string
}

variable "openshift_cluster_token" {
  description = "OpenShift cluster authentication token"
  type        = string
  sensitive   = true
}

variable "openshift_cluster_ca_cert" {
  description = "OpenShift cluster CA certificate (base64 encoded)"
  type        = string
  sensitive   = true
}

variable "no_credentials_mode" {
  description = "Run in no-credentials mode (skip dynamic lookups)"
  type        = bool
  default     = false
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

    def generate_terraform_tfvars(self, required_providers, yaml_data=None):
        """Generate terraform.tfvars configuration file with auto-discovered values."""
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
            # Get AWS credentials with auto-discovery (skip in no-credentials mode)
            if self.no_credentials:
                aws_creds = {'available': False}
                print("  NO-CREDENTIALS MODE: Skipping AWS credential discovery")
            else:
                aws_creds = self.credentials.get_aws_credentials()
            
            tfvars_content += '''# =============================================================================
# AWS CONFIGURATION
# =============================================================================

'''
            
            # Try to auto-detect AWS credentials from environment variables
            aws_billing_account_id = os.getenv('AWS_BILLING_ACCOUNT_ID')
            
            # Get the determined AWS region from YAML only
            determined_region = self.get_primary_aws_region(yaml_data) if yaml_data else None
            
            # ROSA CLI uses AWS credentials from environment variables or AWS CLI profiles
            tfvars_content += f'''# AWS Region Configuration
# Region determined from your YAML configuration: {determined_region or 'No regions specified'}

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
            if self.no_credentials:
                # In no-credentials mode, use placeholders for Azure
                subscription_id = "placeholder-subscription-id"
                arm_client_secret = "placeholder-client-secret"
            else:
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
            
            # Determine IBM VPC region from YAML configuration
            ibm_region = "us-south"  # Default fallback
            if yaml_data and 'yamlforge' in yaml_data:
                ibm_vpc_config = yaml_data['yamlforge'].get('ibm_vpc', {})
                if 'region' in ibm_vpc_config:
                    ibm_region = ibm_vpc_config['region']
                else:
                    self.print_provider_output('ibm_vpc', f"No region specified in YAML, using default: {ibm_region}")
            
            if ibm_api_key:
                tfvars_content += f'''# IBM Cloud Configuration
# API key automatically detected from environment variable
ibm_api_key = "{ibm_api_key}"
ibm_region = "{ibm_region}"

'''
            else:
                tfvars_content += f'''# IBM Cloud Configuration
# Set IC_API_KEY or IBMCLOUD_API_KEY environment variable
# Or configure ibm_api_key here
ibm_api_key = "your-ibm-cloud-api-key-here"
ibm_region = "{ibm_region}"

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
            # Check for Red Hat OpenShift token
            rhcs_token = os.getenv('REDHAT_OPENSHIFT_TOKEN')
            
            tfvars_content += '''# =============================================================================
# RED HAT CLOUD SERVICES CONFIGURATION
# =============================================================================

'''
            
            if rhcs_token:
                # Get Red Hat API URL from environment variable
                rhcs_url = os.getenv('REDHAT_OPENSHIFT_API_URL', 'https://api.openshift.com')
                
                tfvars_content += f'''# Red Hat OpenShift Cluster Manager Token
# Automatically detected from environment variable
rhcs_token = "{rhcs_token}"
rhcs_url   = "{rhcs_url}"

'''
            else:
                # Get Red Hat API URL from environment variable
                rhcs_url = os.getenv('REDHAT_OPENSHIFT_API_URL', 'https://api.openshift.com')
                
                tfvars_content += f'''# Red Hat OpenShift Cluster Manager Token (required for ROSA)
# Get your token from: https://console.redhat.com/openshift/token/rosa
# Set REDHAT_OPENSHIFT_TOKEN environment variable or configure here
rhcs_token = "your-offline-token-here"
rhcs_url   = "{rhcs_url}"

'''

        # Red Hat Pull Secret for enhanced content access (only for OpenShift clusters)
        if self._has_rosa_clusters(yaml_data):
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

        # CNV/Kubernetes configuration
        if 'cnv' in required_providers:
            # Get OpenShift cluster credentials from environment variables
            openshift_cluster_url = os.getenv('OPENSHIFT_CLUSTER_URL')
            openshift_cluster_token = os.getenv('OPENSHIFT_CLUSTER_TOKEN')
            
            if openshift_cluster_url and openshift_cluster_token:
                tfvars_content += f'''# =============================================================================
# CNV/KUBERNETES CONFIGURATION
# =============================================================================

# OpenShift Cluster Configuration
# Automatically detected from environment variables
openshift_cluster_url = "{openshift_cluster_url}"
openshift_cluster_token = "{openshift_cluster_token}"

# Note: openshift_cluster_ca_cert is optional for most OpenShift clusters
# Set OPENSHIFT_CLUSTER_CA_CERT environment variable if needed
openshift_cluster_ca_cert = ""
no_credentials_mode = {str(self.no_credentials).lower()}

'''
            else:
                tfvars_content += '''# =============================================================================
# CNV/KUBERNETES CONFIGURATION
# =============================================================================

# OpenShift Cluster Configuration
# Set these environment variables or configure manually:
#   export OPENSHIFT_CLUSTER_URL="https://api.cluster.example.com:6443"
#   export OPENSHIFT_CLUSTER_TOKEN="your-token-here"
openshift_cluster_url = "https://api.cluster.example.com:6443"
openshift_cluster_token = "your-token-here"
openshift_cluster_ca_cert = ""
no_credentials_mode = {str(self.no_credentials).lower()}

'''

        return tfvars_content

    def convert(self, config, output_dir, verbose=False, full_yaml_data=None):
        """Convert YAML configuration to Terraform and write files to output directory."""
        self.verbose = verbose
        # Reset instance costs for this conversion
        self.instance_costs = []
        # Reset OpenShift cluster costs for this conversion
        self.openshift_costs = []
        
        # Set YAML data for GUID extraction - use full YAML data if provided
        yaml_data_for_guid = full_yaml_data if full_yaml_data is not None else config
        self.set_yaml_data(yaml_data_for_guid)
        
        # Start global section for setup operations
        self.start_global_section()
        
        # Validate cloud provider setup early
        self.validate_provider_setup(full_yaml_data or config)
        
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
        tfvars_config = self.generate_terraform_tfvars(required_providers, full_yaml_data or config)
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
                    print()
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
                    print()
                    print(f"Generated files:")
                    print(f"  - {main_tf_path}")
                    print(f"  - {variables_path}")
                    print(f"  - {tfvars_path}")
        else:
            # No ROSA clusters
            if self.verbose:
                print()
                print(f"Generated files:")
                print(f"  - {main_tf_path}")
                print(f"  - {variables_path}")
                print(f"  - {tfvars_path}")



    def clean_name(self, name):
        """Clean a name for use as a Terraform resource identifier."""
        if not name:
            return "unnamed", False
        
        # Check if {guid} placeholder is present
        has_guid_placeholder = '{guid}' in name
        
        # Replace {guid} placeholder with actual GUID if present
        if has_guid_placeholder:
            guid = self.get_validated_guid()
            name = name.replace('{guid}', guid)
        
        cleaned_name = name.replace("-", "_").replace(".", "_").replace(" ", "_")
        return cleaned_name, has_guid_placeholder

    def replace_guid_placeholders(self, text):
        """Replace {guid} placeholders in text with actual GUID."""
        if not text or '{guid}' not in text:
            return text
        
        guid = self.get_validated_guid()
        return text.replace('{guid}', guid)

    def _resolve_instance_region_silent(self, instance, provider):
        """Resolve instance region silently for validation purposes (no output)."""
        # CNV provider doesn't use regions - return None
        if provider == 'cnv':
            return None
            
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
            
            # For location-based, validate and auto-select best region if needed
            instance_type = self._get_instance_type_for_validation(instance, provider)
            if instance_type and provider == 'gcp':
                # Check if the mapped region supports the instance type
                if not self.gcp_provider.check_machine_type_availability(instance_type, mapped_region, silent=True):
                    # Auto-select best available region
                    available_regions = self.gcp_provider.find_available_regions_for_machine_type(instance_type)
                    best_region = self.gcp_provider.find_closest_available_region(mapped_region, available_regions)
                    
                    if best_region:
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
                # Check if the machine type is available in the requested region
                if not self.gcp_provider.check_machine_type_availability(instance_type, requested_region, silent=True):
                    available_regions = self.gcp_provider.find_available_regions_for_machine_type(instance_type)
                    
                    if find_best_region_on_fail:
                        # Auto-select closest available region
                        best_region = self.gcp_provider.find_closest_available_region(requested_region, available_regions)
                        
                        if best_region:
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

    def resolve_instance_region(self, instance, provider):
        """Resolve instance region with support for both direct regions and mapped locations."""
        # CNV provider doesn't use regions - return None
        if provider == 'cnv':
            return None
            
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
            
            # Location mapping will be shown in the Region line below
            
            # For location-based, validate and auto-select best region if needed
            instance_type = self._get_instance_type_for_validation(instance, provider)
            if instance_type and provider == 'gcp':
                if hasattr(self, 'verbose') and self.verbose:
                    self.print_instance_output(instance_name, provider, f"Checking GCP region availability for machine type '{instance_type}' in region '{mapped_region}'...")
                # Check if the mapped region supports the instance type
                if not self.gcp_provider.check_machine_type_availability(instance_type, mapped_region):
                    # Auto-select best available region
                    if hasattr(self, 'verbose') and self.verbose:
                        self.print_instance_output(instance_name, provider, f"Finding alternative GCP regions for machine type '{instance_type}'...")
                    available_regions = self.gcp_provider.find_available_regions_for_machine_type(instance_type)
                    best_region = self.gcp_provider.find_closest_available_region(mapped_region, available_regions)
                    
                    if best_region:
                        self.print_instance_output(instance_name, provider, f"WARNING: Location '{location_key}' maps to region '{mapped_region}' which doesn't support machine type '{instance_type}'. Auto-selecting closest available region: '{best_region}'")
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
                if hasattr(self, 'verbose') and self.verbose:
                    self.print_instance_output(instance_name, provider, f"Checking GCP region availability for machine type '{instance_type}' in region '{requested_region}'...")
                # Check if the machine type is available in the requested region
                if not self.gcp_provider.check_machine_type_availability(instance_type, requested_region):
                    self.print_instance_output(instance_name, provider, f"Finding alternative GCP regions for machine type '{instance_type}'...")
                    available_regions = self.gcp_provider.find_available_regions_for_machine_type(instance_type)
                    
                    if find_best_region_on_fail:
                        # Auto-select closest available region
                        best_region = self.gcp_provider.find_closest_available_region(requested_region, available_regions)
                        
                        if best_region:
                            self.print_instance_output(instance_name, provider, f"WARNING: Machine type '{instance_type}' not available in region '{requested_region}'. Auto-selecting closest available region: '{best_region}'")
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
        # Get the flavor from the instance
        flavor = instance.get('flavor')
        gpu_type = instance.get('gpu_type')
        
        if not flavor:
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
                    
                    # Look for flavor/GPU combination in flavor mappings
                    for flavor_category, flavor_options in flavor_mappings.items():
                        if flavor_category == flavor or flavor in flavor_category:
                            for instance_type, specs in flavor_options.items():
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
                return self.gcp_provider.get_gcp_machine_type(flavor)
                
            except ValueError:
                # If we can't resolve the machine type, assume it's already a machine type
                return flavor
        
        # For other providers, return the flavor as-is
        return flavor

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
                    region = self._resolve_instance_region_silent(instance, 'aws')
                    aws_regions.add(region)
                except ValueError:
                    # Instance doesn't specify region - this should be a validation error
                    # Don't add any fallback region
                    pass
        
        # Collect regions from OpenShift clusters
        for cluster in yaml_data.get('openshift_clusters', []):
            cluster_type = cluster.get('type', '')
            if cluster_type in ['rosa-classic', 'rosa-hcp']:
                region = cluster.get('region')
                if region:
                    aws_regions.add(region)
        
        # Return sorted list of regions (primary first)
        regions_list = sorted(aws_regions) if aws_regions else []
        return regions_list
    
    def get_primary_aws_region(self, yaml_data):
        """Get the primary AWS region (first in sorted order)."""
        regions = self.get_all_aws_regions(yaml_data)
        if not regions:
            return None  # No regions found - let caller handle this
        return regions[0]
    
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

    def find_closest_flavor_for_provider(self, provider, cores, memory_mb, gpus=None, gpu_type=None):
        """Find the closest matching flavor for a specific provider given hardware requirements."""
        memory_gb = memory_mb / 1024
        
        # Get provider-specific flavor mappings
        provider_flavors = self.flavors.get(provider, {})
        flavor_mappings = provider_flavors.get('flavor_mappings', {})
        
        best_match = None
        best_score = float('inf')
        
        # Search through all flavor categories for this provider
        for flavor_name, flavor_options in flavor_mappings.items():
            for instance_type, specs in flavor_options.items():
                instance_cores = specs.get('vcpus', 0)
                instance_memory_gb = specs.get('memory_gb', 0)
                instance_gpus = specs.get('gpu_count', 0)
                instance_gpu_type = specs.get('gpu_type')
                cost = specs.get('hourly_cost')
                
                # Check if this instance meets minimum requirements
                meets_cpu = instance_cores >= cores
                meets_memory = instance_memory_gb >= memory_gb
                meets_gpu_count = gpus is None or instance_gpus >= gpus
                meets_gpu_type = gpu_type is None or (instance_gpu_type and self.gpu_type_matches(instance_gpu_type, gpu_type))
                
                if meets_cpu and meets_memory and meets_gpu_count and meets_gpu_type:
                    # Calculate score based on resource overhead (lower is better)
                    cpu_overhead = instance_cores - cores
                    memory_overhead = instance_memory_gb - memory_gb
                    gpu_overhead = instance_gpus - (gpus or 0)
                    
                    # Weight the score to favor CPU accuracy over memory, and minimize cost
                    score = (cpu_overhead * 2) + memory_overhead + (gpu_overhead * 3)
                    if cost is not None:
                        score += cost * 0.1  # Small cost factor for tie-breaking
                    
                    if score < best_score:
                        best_score = score
                        best_match = {
                            'instance_type': instance_type,
                            'flavor': flavor_name,
                            'cost': cost,
                            'vcpus': instance_cores,
                            'memory_gb': instance_memory_gb,
                            'gpu_count': instance_gpus,
                            'gpu_type': instance_gpu_type
                        }
        
        return best_match

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
        # Apply flavor-to-cores/memory conversion for cheapest provider
        instance = self._convert_flavor_to_specs_for_cheapest(instance)
        
        size = instance.get("flavor")  # Changed from "size" to "flavor"
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
        
        # Prioritize specs over size for cheapest provider selection
        if cores and memory:
            # Hardware specification-based selection (with optional GPU) - preferred for cheapest
            provider_costs = self.find_cheapest_by_specs(cores, memory, gpu_count, gpu_type, instance_exclusions)
            memory_gb = memory / 1024
            
            if gpu_count and gpu_type:
                analysis_type = f"{cores} cores, {memory_gb:.1f}GB RAM, {gpu_count} {gpu_type} GPU(s)"
            elif gpu_count:
                analysis_type = f"{cores} cores, {memory_gb:.1f}GB RAM, {gpu_count} GPU(s)"
            else:
                analysis_type = f"{cores} cores, {memory_gb:.1f}GB RAM"
        elif size:
            # Flavor-based selection (fallback when no specs provided)
            provider_costs = self.find_cheapest_by_size(size, gpu_type, instance_exclusions)
            analysis_type = f"flavor '{size}'"
            if gpu_type:
                analysis_type += f" with {gpu_type} GPU"
        else:
            # No fallback - must specify requirements
            instance_name = instance.get('name', 'unnamed')
            raise ValueError(
                f"Instance '{instance_name}': When using provider 'cheapest', you must specify either:\n"
                f"  - 'flavor': nano, micro, small, medium, large, xlarge, etc.\n"
                f"  - 'cores' and 'memory': e.g., cores: 2, memory: 4096 (MB)\n"
                f"  - GPU requirements: gpu_count, gpu_type, etc."
            )
        
        if not provider_costs:
            # Fallback to AWS if no cost information available
            if not suppress_output:
                print(f"Warning: No cost information found for {analysis_type}, defaulting to AWS")
            return 'aws'
        
        # Apply discounts to all provider costs before finding cheapest
        for provider in provider_costs:
            original_cost = provider_costs[provider]['cost']
            provider_costs[provider]['original_cost'] = original_cost
            provider_costs[provider]['cost'] = self.apply_discount(original_cost, provider)
        
        # Find the cheapest provider
        cheapest_provider = min(provider_costs.keys(), key=lambda p: provider_costs[p]['cost'])
        
        # Only print cost analysis if not suppressed
        if not suppress_output:
            instance_name = instance.get('name', 'unnamed')
            # Get instance-specific exclusions
            instance_exclusions = instance.get('exclude_providers', [])
            # Log provider exclusions if any (always suppress since they're shown under instance name)
            self.log_provider_exclusions("cheapest provider selection", suppress_output, instance_exclusions, True)
            # Resolve GUID in instance name before showing cost analysis
            resolved_instance_name = self.replace_guid_placeholders(instance_name)
            print(f"   Cost analysis for instance '{resolved_instance_name}':")
            for provider, info in sorted(provider_costs.items(), key=lambda x: x[1]['cost']):
                marker = " ← SELECTED" if provider == cheapest_provider else ""
                vcpus = info.get('vcpus', 'N/A')
                memory_gb = info.get('memory_gb', 'N/A')
                gpu_count = info.get('gpu_count', 0)
                detected_gpu_type = info.get('gpu_type', '')
                
                # Format cost display with discount info
                cost_display = self._format_cost_with_discount(provider, info.get('original_cost'), info['cost'])
                
                if gpu_count > 0:
                    gpu_info = f", {gpu_count}x {detected_gpu_type}" if detected_gpu_type else f", {gpu_count} GPU(s)"
                    print(f"     {provider}: {cost_display} ({info['instance_type']}, {vcpus} vCPU, {memory_gb}GB{gpu_info}){marker}")
                else:
                    print(f"     {provider}: {cost_display} ({info['instance_type']}, {vcpus} vCPU, {memory_gb}GB){marker}")
        
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
        
        # Apply discounts to all provider costs before finding cheapest
        for provider in provider_costs:
            original_cost = provider_costs[provider]['cost']
            provider_costs[provider]['original_cost'] = original_cost
            provider_costs[provider]['cost'] = self.apply_discount(original_cost, provider)
        
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
                
                # Format cost display with discount info
                cost_display = self._format_cost_with_discount(provider, info.get('original_cost'), info['cost'])
                
                gpu_info = f", {gpu_count}x {detected_gpu_type}" if detected_gpu_type else f", {gpu_count} GPU(s)"
                print(f"     {provider}: {cost_display} ({info['instance_type']}, {vcpus} vCPU, {memory_gb}GB{gpu_info}){marker}")
        
        return cheapest_provider

    def find_cheapest_storage_provider(self, bucket, suppress_output=False):
        """Find the cheapest cloud provider for object storage."""
        bucket_name = bucket.get('name', 'unnamed')
        
        # Check if storage costs are available
        if not self.storage_costs or not self.storage_costs.get('storage_costs'):
            if not suppress_output:
                print(f"   Storage analysis for bucket '{bucket_name}': No cost data available, defaulting to AWS")
            return 'aws'
        
        # Get available providers (excluding those configured to be excluded from cheapest)
        available_providers = self.get_effective_providers()
        storage_costs = self.storage_costs.get('storage_costs', {})
        regional_multipliers = self.storage_costs.get('regional_multipliers', {})
        
        # Get region for cost calculation
        region = bucket.get('region')
        location = bucket.get('location')
        
        provider_costs = {}
        
        for provider in available_providers:
            if provider in storage_costs:
                # Check if provider supports the requested location/region
                if location:
                    # Check if location maps to this provider
                    mapped_region = self.locations.get(location, {}).get(provider)
                    if not mapped_region:
                        # Provider doesn't support this location, skip it
                        continue
                
                base_cost = storage_costs[provider].get('typical_monthly_cost', 999.0)
                
                # Apply regional multiplier
                multiplier = 1.0
                if region and region in regional_multipliers:
                    multiplier = regional_multipliers[region]
                elif location:
                    # Try to resolve location to region and get multiplier
                    mapped_region = self.locations.get(location, {}).get(provider)
                    if mapped_region and mapped_region in regional_multipliers:
                        multiplier = regional_multipliers[mapped_region]
                    else:
                        multiplier = regional_multipliers.get('default', 1.0)
                else:
                    multiplier = regional_multipliers.get('default', 1.0)
                
                final_cost = base_cost * multiplier
                provider_costs[provider] = final_cost
        
        if not provider_costs:
            if not suppress_output:
                print(f"   Storage analysis for bucket '{bucket_name}': No providers with cost data, defaulting to AWS")
            return 'aws'
        
        # Find the cheapest provider
        cheapest_provider = min(provider_costs.keys(), key=lambda p: provider_costs[p])
        
        if not suppress_output:
            print(f"   Storage cost analysis for bucket '{bucket_name}':")
            # Sort providers by cost for display
            sorted_providers = sorted(provider_costs.items(), key=lambda x: x[1])
            for provider, cost in sorted_providers:
                marker = " ← cheapest" if provider == cheapest_provider else ""
                print(f"     {provider}: ${cost:.2f}/month{marker}")
        
        return cheapest_provider
    
    def calculate_storage_cost(self, provider, location=None):
        """Calculate storage cost for a specific provider and location."""
        if not self.storage_costs or not self.storage_costs.get('storage_costs'):
            return None
        
        storage_costs = self.storage_costs.get('storage_costs', {})
        regional_multipliers = self.storage_costs.get('regional_multipliers', {})
        
        if provider not in storage_costs:
            return None
        
        base_cost = storage_costs[provider].get('typical_monthly_cost', 0.0)
        
        # Apply regional multiplier
        multiplier = 1.0
        if location:
            # Try to resolve location to region and get multiplier
            mapped_region = None
            for region, providers in self.locations.items():
                if provider in providers:
                    mapped_region = region
                    break
            
            if mapped_region and mapped_region in regional_multipliers:
                multiplier = regional_multipliers[mapped_region]
            else:
                multiplier = regional_multipliers.get('default', 1.0)
        else:
            multiplier = regional_multipliers.get('default', 1.0)
        
        return base_cost * multiplier
    
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
            instance_type = provider_costs[provider]['instance_type']
            if instance_type:  # Make sure it's not None
                return instance_type
        
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
    
    def _convert_flavor_to_specs_for_cheapest(self, instance):
        """Convert generic flavor names to cores/memory for cheapest provider analysis."""
        instance = instance.copy()
        flavor = instance.get('flavor')
        
        # Only convert if we have a flavor but no cores/memory specs
        if flavor and not (instance.get('cores') and instance.get('memory')):
            # Load cheapest provider flavor mappings
            cheapest_flavors = self.flavors.get('cheapest', {})
            flavor_mappings = cheapest_flavors.get('flavor_mappings', {})
            
            if flavor in flavor_mappings:
                flavor_options = flavor_mappings[flavor]
                # Get the first (and typically only) option for this flavor
                flavor_key = next(iter(flavor_options.keys()))
                flavor_config = flavor_options[flavor_key]
                
                if 'cores' in flavor_config and 'memory' in flavor_config:
                    instance['cores'] = flavor_config['cores']
                    instance['memory'] = flavor_config['memory']
                    # Keep the flavor for reference, but cores/memory take precedence
        
        return instance
    
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
        # Apply flavor-to-cores/memory conversion for cheapest provider
        instance = self._convert_flavor_to_specs_for_cheapest(instance)
        
        size = instance.get("flavor")  # Changed from "size" to "flavor"
        cores = instance.get("cores")
        memory = instance.get("memory")
        gpu_count = instance.get("gpu_count")
        
        if size:
            # Flavor-based selection
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
    
    def resolve_instance_type(self, provider, flavor, instance):
        """Resolve instance type based on provider, flavor, and instance specifications."""
        instance_name = instance.get("name", "unnamed")
        
        # If flavor is already a provider-specific type, return it directly
        if flavor:
            # Check if this looks like a provider-specific instance type
            provider_prefixes = {
                'aws': ['t3.', 't2.', 't4g.', 'm5.', 'm5a.', 'm5ad.', 'm5d.', 'm5dn.', 'm5n.', 'm5zn.', 'm6a.', 'm6g.', 'm6gd.', 'm6i.', 'm6id.', 'm6idn.', 'm6in.', 'm7a.', 'm7g.', 'm7gd.', 'm7i.', 'm7i-flex.', 'c5.', 'c5a.', 'c5ad.', 'c5d.', 'c5n.', 'c6a.', 'c6g.', 'c6gd.', 'c6gn.', 'c6i.', 'c6id.', 'c6in.', 'c7a.', 'c7g.', 'c7gd.', 'c7gn.', 'c7i.', 'r5.', 'r5a.', 'r5ad.', 'r5b.', 'r5d.', 'r5dn.', 'r5n.', 'r6a.', 'r6g.', 'r6gd.', 'r6i.', 'r6id.', 'r6idn.', 'r6in.', 'r7a.', 'r7g.', 'r7gd.', 'r7i.', 'r7iz.', 'g4ad.', 'g4dn.', 'g5.', 'g5g.', 'p3.', 'p3dn.', 'p4d.', 'p4de.', 'p5.', 'inf1.', 'inf2.', 'trn1.', 'trn1n.', 'dl1.', 'f1.', 'i3.', 'i3en.', 'i4g.', 'i4i.', 'is4gen.', 'im4gn.', 'd2.', 'd3.', 'd3en.', 'h1.', 'z1d.', 'x1.', 'x1e.', 'x2gd.', 'x2idn.', 'x2iedn.', 'x2iezn.', 'u-3tb1.', 'u-6tb1.', 'u-9tb1.', 'u-12tb1.', 'u-18tb1.', 'u-24tb1.', 'u-1.', 'u-2.', 'u-3.', 'u-6.', 'u-9.', 'u-12.', 'u-18.', 'u-24.'],
                'azure': ['Standard_', 'Basic_'],
                'gcp': ['n1-', 'n2-', 'n2d-', 'n4-', 'e2-', 'c2-', 'c2d-', 'c3-', 'c3d-', 't2d-', 't2a-', 'a2-', 'a3-', 'g2-', 'm1-', 'm2-', 'm3-'],
                'oci': ['VM.Standard', 'VM.DenseIO', 'VM.GPU', 'VM.Optimized', 'BM.Standard', 'BM.DenseIO', 'BM.GPU', 'BM.HPC'],
                'ibm_vpc': ['bx2-', 'cx2-', 'mx2-', 'gx2-', 'gx3-', 'vx2d-', 'ox2-', 'ux2d-'],
                'alibaba': ['ecs.', 'r6.', 'c6.', 'g6.', 'ebm.', 'scc.', 'scch.']
            }
            
            if provider in provider_prefixes:
                if any(flavor.startswith(prefix) for prefix in provider_prefixes[provider]):
                    return flavor
        
        # Map generic flavor to provider-specific instance type
        if flavor in self.flavors:
            generic_flavor = self.flavors[flavor]
            if provider in generic_flavor:
                instance_type = generic_flavor[provider]
                # Flavor mapping output will be handled in _display_instance_hourly_cost
                return instance_type
            else:
                # Check if this is a GPU flavor that doesn't support this provider
                if any(gpu_prefix in flavor for gpu_prefix in ['gpu_', 'gpu_t4_', 'gpu_v100_', 'gpu_a100_', 'gpu_amd_']):
                    available_providers = list(generic_flavor.keys())
                    
                    # Special handling for AMD GPUs
                    if 'gpu_amd_' in flavor:
                        raise ValueError(
                            f"AMD GPU flavor '{flavor}' is only available on AWS. "
                            f"Provider '{provider}' does not support AMD GPUs. "
                            f"Consider using:\n"
                            f"  - AWS provider: provider: 'aws'\n"
                            f"  - Different GPU type: gpu_t4_small, gpu_v100_small, etc.\n"
                            f"  - Cost optimization: provider: 'cheapest' with gpu_type: 'AMD Radeon Pro V520'"
                        )
                    else:
                        # General GPU flavor not available on provider
                        raise ValueError(
                            f"GPU flavor '{flavor}' is not available on provider '{provider}'. "
                            f"Available providers for {flavor}: {', '.join(available_providers)}. "
                            f"Consider using:\n"
                            f"  - Supported provider: {', '.join(available_providers)}\n"
                            f"  - Cost optimization: provider: 'cheapest'\n"
                            f"  - Hardware specification: cores + memory + gpus"
                        )
        
        # Check provider-specific flavor mappings
        provider_flavors = self.flavors.get(provider, {})
        flavor_mappings = provider_flavors.get('flavor_mappings', {})
        
        if flavor in flavor_mappings:
            flavor_options = flavor_mappings[flavor]
            # Return the first (usually cheapest) option
            if flavor_options:
                return next(iter(flavor_options.keys()))
        
        # No mapping found - fail with clear error message
        # Get available flavors from both generic and provider-specific mappings
        generic_flavors = list(self.flavors.keys()) if hasattr(self, 'flavors') else []
        provider_flavors_list = list(flavor_mappings.keys()) if flavor_mappings else []
        all_available_flavors = sorted(set(generic_flavors + provider_flavors_list))
        
        raise ValueError(
            f"Instance '{instance_name}': No mapping found for flavor '{flavor}' on provider '{provider}'. "
            f"Available flavors: {', '.join(all_available_flavors)}. "
            f"Check mappings/flavors/generic.yaml and mappings/flavors/{provider}.yaml for supported flavors."
        )
    
    def get_instance_cost_info(self, provider, instance_type, flavor, provider_flavors):
        """Get detailed cost and specification information for a specific instance type."""
        # Look in provider-specific flavor mappings
        flavor_mappings = provider_flavors.get('flavor_mappings', {})
        
        if flavor in flavor_mappings:
            flavor_options = flavor_mappings[flavor]
            # Find the instance type in the flavor category
            for type_name, type_info in flavor_options.items():
                if type_name == instance_type:
                    cost = type_info.get('hourly_cost')
                    if cost is not None:
                        return {
                            'cost': cost,
                            'instance_type': instance_type,
                            'vcpus': type_info.get('vcpus'),
                            'memory_gb': type_info.get('memory_gb')
                        }
        
        # If flavor is a direct instance type, search across all flavor categories
        if flavor == instance_type:
            for flavor_category, flavor_options in flavor_mappings.items():
                if instance_type in flavor_options:
                    type_info = flavor_options[instance_type]
                    cost = type_info.get('hourly_cost')
                    if cost is not None:
                        return {
                            'cost': cost,
                            'instance_type': instance_type,
                            'vcpus': type_info.get('vcpus'),
                            'memory_gb': type_info.get('memory_gb'),
                            'gpu_count': type_info.get('gpu_count'),
                            'gpu_type': type_info.get('gpu_type')
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

    def _display_instance_hourly_cost(self, instance_name, provider, instance_type, flavor, original_provider, instance):
        """Display the hourly cost for an instance."""
        # For cheapest provider instances, get the cost from the cheapest provider analysis
        if original_provider in ['cheapest', 'cheapest-gpu']:
            try:
                # Get instance-specific exclusions
                instance_exclusions = instance.get('exclude_providers', [])
                
                if original_provider == 'cheapest':
                    # Handle memory in either MB or GB format
                    memory_value = instance.get('memory', 4)
                    if memory_value < 100:  # Assume GB if less than 100
                        memory_mb = memory_value * 1024
                    else:  # Assume MB if 100 or greater
                        memory_mb = memory_value
                    
                    # Get cost information for all providers
                    provider_costs = self.find_cheapest_by_specs(
                        instance.get('cores', 2), 
                        memory_mb,
                        instance.get('gpu_count', 0),
                        instance.get('gpu_type'),
                        instance_exclusions
                    )
                else:  # cheapest-gpu
                    gpu_type = instance.get("gpu_type")
                    provider_costs = self.find_cheapest_gpu_by_specs(gpu_type, instance_exclusions)
                
                if provider_costs and provider in provider_costs:
                    selected_option = provider_costs[provider]
                    hourly_cost = selected_option['cost']
                    instance_type = selected_option['instance_type']
                    # Get and display region information for cheapest provider
                    region = instance.get('region') or instance.get('location', 'unspecified')
                    mapped_region = self.locations.get(region, {}).get(provider, region) if region != 'unspecified' else 'unspecified'
                    if region == mapped_region:
                        self.print_instance_output(instance_name, provider, f"Region: {region}")
                    else:
                        self.print_instance_output(instance_name, provider, f"Region: {region} ({mapped_region})")
                    # Show flavor mapping format: original_flavor (resolved_instance_type)
                    if flavor and flavor != instance_type:
                        self.print_instance_output(instance_name, provider, f"Flavor: {flavor} ({instance_type})")
                    else:
                        self.print_instance_output(instance_name, provider, f"Flavor: {instance_type}")
                    # Apply discount and format display
                    original_cost = hourly_cost
                    discounted_cost = self.apply_discount(hourly_cost, provider)
                    cost_display = self._format_cost_with_discount(provider, original_cost, discounted_cost)
                    self.print_instance_output(instance_name, provider, f"Hourly Cost: {cost_display}")
                    # Track the discounted cost for total calculation
                    self.instance_costs.append({
                        'instance_name': instance_name,
                        'provider': provider,
                        'cost': discounted_cost
                    })
                    return
            except Exception:
                pass  # Fall back to regular cost lookup
        

        
        # Special handling for CNV provider
        if provider == 'cnv':
            provider_flavors = self.flavors.get(provider, {})
            flavor_mappings = provider_flavors.get('flavor_mappings', {})
            
            # Get the actual flavor name (could be from flavor or cores/memory)
            actual_flavor = flavor
            if not actual_flavor:
                # If no flavor specified, determine from cores/memory
                cores = instance.get('cores')
                memory = instance.get('memory')
                if cores and memory:
                    # For cores/memory, we'll show the specs instead of a flavor name
                    self.print_instance_output(instance_name, provider, f"Provider: {provider}")
                    self.print_instance_output(instance_name, provider, f"Instance specs: {cores} vCPU, {memory}MB RAM")
                    self.print_instance_output(instance_name, provider, "Hourly Cost: $0.001 (minimal CNV cost)")
                    self.instance_costs.append({
                        'instance_name': instance_name,
                        'provider': provider,
                        'cost': 0.001
                    })
                    return
            
            # Look up cost for the flavor
            if actual_flavor in flavor_mappings:
                flavor_options = flavor_mappings[actual_flavor]
                # Get the first flavor option (e.g., 'cnv-small' for 'small')
                flavor_name = next(iter(flavor_options.keys()))
                flavor_config = flavor_options[flavor_name]
                
                hourly_cost = flavor_config.get('hourly_cost', 0.001)
                vcpus = flavor_config.get('vcpus', 1)
                memory_gb = flavor_config.get('memory_gb', 1)
                
                self.print_instance_output(instance_name, provider, f"Provider: {provider}")
                self.print_instance_output(instance_name, provider, f"Instance flavor: {flavor_name} ({vcpus} vCPU, {memory_gb}GB RAM)")
                self.print_instance_output(instance_name, provider, f"Hourly Cost: ${hourly_cost:.4f}")
                
                self.instance_costs.append({
                    'instance_name': instance_name,
                    'provider': provider,
                    'cost': hourly_cost
                })
                return
            else:
                self.print_instance_output(instance_name, provider, f"Provider: {provider}")
                self.print_instance_output(instance_name, provider, f"Instance flavor: {actual_flavor}")
                self.print_instance_output(instance_name, provider, "Hourly Cost: $0.001 (minimal CNV cost)")
                self.instance_costs.append({
                    'instance_name': instance_name,
                    'provider': provider,
                    'cost': 0.001
                })
                return
        
        # Regular cost lookup for non-cheapest providers or fallback
        # Show provider information for regular instances
        self.print_instance_output(instance_name, provider, f"Provider: {provider}")
        
        provider_flavors = self.flavors.get(provider, {})
        cost_info = self.get_instance_cost_info(provider, instance_type, flavor, provider_flavors)
        
        if cost_info and cost_info.get('cost') is not None:
            hourly_cost = cost_info['cost']
            # Get and display region information
            region = instance.get('region', 'unspecified')
            mapped_region = self.locations.get(region, {}).get(provider, region) if region != 'unspecified' else 'unspecified'
            if region == mapped_region:
                self.print_instance_output(instance_name, provider, f"Region: {region}")
            else:
                self.print_instance_output(instance_name, provider, f"Region: {region} ({mapped_region})")
            # Show flavor mapping format: original_flavor (resolved_instance_type)
            if flavor and flavor != instance_type:
                self.print_instance_output(instance_name, provider, f"Flavor: {flavor} ({instance_type})")
            else:
                self.print_instance_output(instance_name, provider, f"Flavor: {instance_type}")
            # Apply discount and format display
            original_cost = hourly_cost
            discounted_cost = self.apply_discount(hourly_cost, provider)
            cost_display = self._format_cost_with_discount(provider, original_cost, discounted_cost)
            self.print_instance_output(instance_name, provider, f"Hourly Cost: {cost_display}")
            # Track the discounted cost for total calculation
            self.instance_costs.append({
                'instance_name': instance_name,
                'provider': provider,
                'cost': discounted_cost
            })
        else:
            # Get and display region information even when cost is not available
            region = instance.get('region', 'unspecified')
            mapped_region = self.locations.get(region, {}).get(provider, region) if region != 'unspecified' else 'unspecified'
            if region == mapped_region:
                self.print_instance_output(instance_name, provider, f"Region: {region}")
            else:
                self.print_instance_output(instance_name, provider, f"Region: {region} ({mapped_region})")
            # Show flavor mapping format: original_flavor (resolved_instance_type)
            if flavor and flavor != instance_type:
                self.print_instance_output(instance_name, provider, f"Flavor: {flavor} ({instance_type})")
            else:
                self.print_instance_output(instance_name, provider, f"Flavor: {instance_type}")
            self.print_instance_output(instance_name, provider, "Hourly Cost: Cost information not available")

    def calculate_openshift_cluster_cost(self, cluster, cluster_type):
        """Calculate the hourly cost for an OpenShift cluster."""
        try:
            # Determine provider based on cluster type
            provider = None
            if cluster_type == 'rosa-classic' or cluster_type == 'rosa-hcp':
                provider = 'aws'
            elif cluster_type == 'aro':
                provider = 'azure'
            elif cluster_type == 'self-managed':
                provider = cluster.get('provider', 'aws')
            
            if not provider:
                return None
            
            # Check if cluster uses size-based configuration (modern approach)
            cluster_size = cluster.get('size')
            if cluster_size:
                # Use OpenShift provider to get cluster size configuration
                try:
                    size_config = self.openshift_provider.get_cluster_size_config(cluster_size, cluster_type, provider)
                    
                    # Get counts from size config, with user overrides
                    controlplane_count = cluster.get('controlplane_count', size_config.get('controlplane_count', 0))
                    worker_count = cluster.get('worker_count', size_config.get('worker_count', 0))
                    
                    # Resolve controlplane and worker sizes to actual machine types
                    controlplane_size = size_config.get('controlplane_size', '')
                    worker_size = size_config.get('worker_size', '')
                    
                    controlplane_machine_type = ''
                    worker_machine_type = ''
                    
                    if controlplane_size:
                        try:
                            controlplane_machine_type = self.openshift_provider.get_openshift_machine_type(provider, controlplane_size, 'controlplane')
                        except Exception:
                            pass
                            
                    if worker_size:
                        try:
                            worker_machine_type = self.openshift_provider.get_openshift_machine_type(provider, worker_size, 'worker')
                        except Exception:
                            pass
                    
                except Exception:
                    # Fall back to direct machine type approach if size config fails
                    controlplane_count = cluster.get('controlplane_count', 0)
                    worker_count = cluster.get('worker_count', 0)
                    controlplane_machine_type = cluster.get('controlplane_machine_type', '')
                    worker_machine_type = cluster.get('worker_machine_type', '')
            else:
                # Use direct machine type approach (legacy)
                controlplane_count = cluster.get('controlplane_count', 0)
                worker_count = cluster.get('worker_count', 0)
                controlplane_machine_type = cluster.get('controlplane_machine_type', '')
                worker_machine_type = cluster.get('worker_machine_type', '')
            
            # Calculate costs for different node types
            total_cost = 0.0
            
            # Try OpenShift-specific flavors first, then fall back to regular provider flavors
            openshift_flavor_key = f"openshift_{provider}"
            openshift_flavors = self.flavors.get(openshift_flavor_key, {})
            provider_flavors = self.flavors.get(provider, {})
            
            # Calculate controlplane node costs
            if controlplane_count > 0 and controlplane_machine_type:
                controlplane_cost = None
                
                # Search in OpenShift-specific flavor mappings first
                for size, instances in openshift_flavors.get('flavor_mappings', {}).items():
                    if controlplane_machine_type in instances:
                        controlplane_cost = instances[controlplane_machine_type]
                        break
                
                # Fall back to regular provider flavors if not found
                if not controlplane_cost:
                    for size, instances in provider_flavors.get('flavor_mappings', {}).items():
                        if controlplane_machine_type in instances:
                            controlplane_cost = instances[controlplane_machine_type]
                            break
                
                if controlplane_cost and controlplane_cost.get('hourly_cost'):
                    total_cost += controlplane_cost['hourly_cost'] * controlplane_count
            
            # Calculate worker node costs
            if worker_count > 0 and worker_machine_type:
                worker_cost = None
                
                # Search in OpenShift-specific flavor mappings first
                for size, instances in openshift_flavors.get('flavor_mappings', {}).items():
                    if worker_machine_type in instances:
                        worker_cost = instances[worker_machine_type]
                        break
                
                # Fall back to regular provider flavors if not found
                if not worker_cost:
                    for size, instances in provider_flavors.get('flavor_mappings', {}).items():
                        if worker_machine_type in instances:
                            worker_cost = instances[worker_machine_type]
                            break
                
                if worker_cost and worker_cost.get('hourly_cost'):
                    total_cost += worker_cost['hourly_cost'] * worker_count
            
            return total_cost
            
        except Exception:
            return None

    def display_openshift_cluster_cost(self, cluster_name, cluster_type, hourly_cost):
        """Display the hourly cost for an OpenShift cluster."""
        if hourly_cost is not None:
            print(f"  Cluster hourly cost: ${hourly_cost:.4f}")
            # Track the cost for total calculation
            self.openshift_costs.append({
                'cluster_name': cluster_name,
                'cluster_type': cluster_type,
                'cost': hourly_cost
            })
        else:
            print(f"  Cluster hourly cost: Cost information not available")

    def get_openshift_cluster_cost_string(self, cluster_name, cluster_type, hourly_cost):
        """Get the hourly cost string for an OpenShift cluster."""
        if hourly_cost is not None:
            # Track the cost for total calculation
            self.openshift_costs.append({
                'cluster_name': cluster_name,
                'cluster_type': cluster_type,
                'cost': hourly_cost
            })
            return f"     Cluster hourly cost: ${hourly_cost:.4f}"
        else:
            return f"     Cluster hourly cost: Cost information not available"

    def display_total_hourly_cost(self):
        """Display the total hourly cost for all instances and OpenShift clusters."""
        total_cost = 0.0
        
        # Add instance costs
        if self.instance_costs:
            instance_total = sum(cost_info['cost'] for cost_info in self.instance_costs)
            total_cost += instance_total
        
        # Add OpenShift cluster costs
        if self.openshift_costs:
            openshift_total = sum(cost_info['cost'] for cost_info in self.openshift_costs)
            total_cost += openshift_total
        
        if total_cost > 0:
            print(f"\nTotal hourly cost for all instances and clusters: ${total_cost:.4f}")

    def get_total_hourly_cost_string(self):
        """Get the total hourly cost string for all instances and OpenShift clusters."""
        total_cost = 0.0
        
        # Add instance costs
        if self.instance_costs:
            instance_total = sum(cost_info['cost'] for cost_info in self.instance_costs)
            total_cost += instance_total
        
        # Add OpenShift cluster costs
        if self.openshift_costs:
            openshift_total = sum(cost_info['cost'] for cost_info in self.openshift_costs)
            total_cost += openshift_total
        
        if total_cost > 0:
            return f"\nTotal hourly cost for all instances and clusters: ${total_cost:.4f}"
        return ""


    # Placeholder methods for provider delegation
    def generate_virtual_machine(self, instance, index, yaml_data, available_subnets=None, full_yaml_data=None, zone=None):
        """Generate virtual machine configuration using provider modules."""
        provider = instance.get("provider")
        if not provider:
            instance_name = instance.get("name", "unknown")
            raise ValueError(f"Instance '{instance_name}' must specify a 'provider'")

        clean_name, has_guid_placeholder = self.clean_name(instance.get("name", f"instance_{index}"))
        flavor = instance.get("flavor")
        instance_name = instance.get("name", "unnamed")
        
        # Store original provider before it gets changed
        original_provider = provider
        
        # Handle cheapest provider meta-provider first to get the actual provider
        selected_instance_type = None
        if provider == 'cheapest':
            # Convert generic flavor to cores/memory if needed
            instance = self._convert_flavor_to_specs_for_cheapest(instance)
            provider = self.find_cheapest_provider(instance, suppress_output=True)
            # Update the instance with the selected provider for consistency
            instance = instance.copy()
            instance['provider'] = provider
            
            # Get the selected instance type from cheapest provider analysis
            selected_instance_type = self.get_cheapest_instance_type(instance, provider)
        elif provider == 'cheapest-gpu':
            # Convert generic flavor to cores/memory if needed
            instance = self._convert_flavor_to_specs_for_cheapest(instance)
            provider = self.find_cheapest_gpu_provider(instance, suppress_output=True)
            # Update the instance with the selected provider for consistency
            instance = instance.copy()
            instance['provider'] = provider
            
            # Get the selected instance type from cheapest GPU provider analysis
            selected_instance_type = self.get_cheapest_gpu_instance_type(instance, provider)
        
        # Start instance section with the resolved provider
        self.start_instance_section(instance_name, provider)
        
        # Clear region cache to ensure instance-specific messages are shown
        # This allows resolve_instance_region to be called again during instance processing
        cache_key = f"{instance_name}_{provider}_{instance.get('region', '')}_{instance.get('location', '')}"
        if cache_key in self._region_cache:
            del self._region_cache[cache_key]
        
        # Call resolve_instance_region to show instance-specific messages
        self.resolve_instance_region(instance, provider)
        
        # Handle cheapest provider meta-provider output (without cost analysis yet)
        if original_provider in ['cheapest', 'cheapest-gpu']:
            if original_provider == 'cheapest':
                self.print_instance_output(instance_name, provider, f"Provider: cheapest ({provider})")
            else:
                self.print_instance_output(instance_name, provider, f"Provider: cheapest-gpu ({provider})")
        
        # Validate that we have enough information to determine instance type
        cores = instance.get("cores")
        memory = instance.get("memory")
        
        # For CNV provider, allow cores and memory as an alternative to flavor
        if provider == 'cnv':
            if not flavor and not selected_instance_type and not (cores and memory):
                raise ValueError(
                    f"Instance '{instance_name}': Must specify either:\n"
                    f"  - 'flavor': small, medium, large, xlarge, etc.\n"
                    f"  - 'cores' and 'memory': e.g., cores: 2, memory: 4096 (MB)"
                )
        else:
            if not flavor and not selected_instance_type:
                raise ValueError(
                    f"Instance '{instance_name}': Must specify either:\n"
                    f"  - 'flavor': generic (small, medium, large, xlarge) or provider-specific (t3.small, e2-micro)\n"
                    f"  - Use 'provider: cheapest' with requirements (cores, memory, gpu_type)"
                )
        
        # Determine instance type (priority: direct flavor specification > cheapest selection > flavor mapping)
        # Skip instance type resolution for CNV provider entirely
        if provider == 'cnv':
            instance_type = None  # CNV doesn't use instance types
        else:
            instance_type = selected_instance_type or self.resolve_instance_type(provider, flavor, instance)

        # Calculate and display hourly cost
        self._display_instance_hourly_cost(instance_name, provider, instance_type, flavor, original_provider, instance)

        # Now show cost analysis for cheapest providers (after all instance details)
        if original_provider in ['cheapest', 'cheapest-gpu']:
            # Create a fresh copy of the original instance for cost analysis
            original_instance = {
                'name': instance.get('name'),
                'provider': original_provider,
                'cores': instance.get('cores', 2),
                'memory': instance.get('memory', 4),
                'gpu_count': instance.get('gpu_count', 0),
                'gpu_type': instance.get('gpu_type'),
                'exclude_providers': instance.get('exclude_providers', [])
            }
            
            if original_provider == 'cheapest':
                self._print_cost_analysis_for_instance(original_instance, provider)
            else:  # cheapest-gpu
                self._print_gpu_cost_analysis_for_instance(original_instance, provider)

        # Use full_yaml_data if provided, otherwise fall back to yaml_data
        effective_yaml_data = full_yaml_data if full_yaml_data is not None else yaml_data

        if provider == 'aws':
            strategy_info = {'instance_type': instance_type, 'architecture': 'x86_64'}
            return self.get_aws_provider().generate_aws_vm(instance, index, clean_name, strategy_info, available_subnets, effective_yaml_data, has_guid_placeholder)
        elif provider == 'azure':
            # For cheapest providers, pass the selected instance type instead of flavor
            azure_flavor = selected_instance_type or flavor
            return self.azure_provider.generate_azure_vm(instance, index, clean_name, azure_flavor, available_subnets, effective_yaml_data, has_guid_placeholder)
        elif provider == 'gcp':
            # For cheapest providers, pass the selected instance type instead of flavor
            gcp_flavor = selected_instance_type or flavor
            return self.gcp_provider.generate_gcp_vm(instance, index, clean_name, gcp_flavor, available_subnets, effective_yaml_data, has_guid_placeholder)
        elif provider == 'oci':
            # For cheapest providers, pass the selected instance type instead of flavor
            oci_flavor = selected_instance_type or flavor
            return self.oci_provider.generate_oci_vm(instance, index, clean_name, oci_flavor, available_subnets, effective_yaml_data, has_guid_placeholder)
        elif provider == 'vmware':
            # For cheapest providers, pass the selected instance type instead of flavor
            vmware_flavor = selected_instance_type or flavor
            return self.vmware_provider.generate_vmware_vm(instance, index, clean_name, vmware_flavor, available_subnets, effective_yaml_data, has_guid_placeholder)
        elif provider == 'alibaba':
            # For cheapest providers, pass the selected instance type instead of flavor
            alibaba_flavor = selected_instance_type or flavor
            return self.alibaba_provider.generate_alibaba_vm(instance, index, clean_name, alibaba_flavor, available_subnets, effective_yaml_data, has_guid_placeholder)
        elif provider in ['ibm_vpc', 'ibm_classic']:
            # For cheapest providers, pass the selected instance type instead of flavor
            ibm_flavor = selected_instance_type or flavor
            if provider == 'ibm_vpc':
                return self.ibm_vpc_provider.generate_ibm_vpc_vm(instance, index, clean_name, ibm_flavor, effective_yaml_data, has_guid_placeholder, zone)
            else:
                return self.ibm_classic_provider.generate_ibm_classic_vm(instance, index, clean_name, ibm_flavor, effective_yaml_data, has_guid_placeholder)
        elif provider == 'cnv':
            # For CNV, pass flavor (which may be None if using cores/memory)
            # The CNV provider will handle cores/memory internally
            return self.cnv_provider.generate_cnv_vm(instance, index, clean_name, flavor, available_subnets, effective_yaml_data, has_guid_placeholder)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def generate_storage_bucket(self, bucket, yaml_data, full_yaml_data=None):
        """Generate object storage bucket configuration using provider modules."""
        provider = bucket.get("provider")
        if not provider:
            bucket_name = bucket.get("name", "unknown")
            raise ValueError(f"Storage bucket '{bucket_name}' must specify a 'provider'")

        bucket_name = bucket.get("name", "unnamed")
        
        # Store original provider before it gets changed
        original_provider = provider
        
        # Handle cheapest provider meta-provider
        if provider == 'cheapest':
            provider = self.find_cheapest_storage_provider(bucket, suppress_output=True)
            # Update the bucket with the selected provider for consistency
            bucket = bucket.copy()
            bucket['provider'] = provider
        
        # Start bucket section with the resolved provider
        self.start_bucket_section(bucket_name, provider)
        
        # Handle cheapest provider meta-provider output
        if original_provider == 'cheapest':
            self.print_bucket_output(bucket_name, provider, f"Provider: cheapest ({provider})")
        else:
            self.print_bucket_output(bucket_name, provider, f"Provider: {provider}")
        
        # Get and display region information
        region = self.resolve_bucket_region(bucket, provider)
        self.print_bucket_output(bucket_name, provider, f"Region: {region}")
        
        # Display bucket configuration
        public = bucket.get('public', False)
        versioning = bucket.get('versioning', False)
        encryption = bucket.get('encryption', True)
        
        access_type = "public-read" if public else "private"
        self.print_bucket_output(bucket_name, provider, f"Access: {access_type}")
        self.print_bucket_output(bucket_name, provider, f"Versioning: {'enabled' if versioning else 'disabled'}")
        self.print_bucket_output(bucket_name, provider, f"Encryption: {'enabled' if encryption else 'disabled'}")

        # Use full_yaml_data if provided, otherwise fall back to yaml_data
        effective_yaml_data = full_yaml_data if full_yaml_data is not None else yaml_data

        if provider == 'aws':
            return self.get_aws_provider().generate_s3_bucket(bucket, effective_yaml_data)
        elif provider == 'azure':
            return self.azure_provider.generate_storage_account(bucket, effective_yaml_data)
        elif provider == 'gcp':
            return self.gcp_provider.generate_storage_bucket(bucket, effective_yaml_data)
        elif provider == 'oci':
            return self.oci_provider.generate_object_storage(bucket, effective_yaml_data)
        elif provider == 'alibaba':
            return self.alibaba_provider.generate_oss_bucket(bucket, effective_yaml_data)
        elif provider in ['ibm_vpc', 'ibm_classic']:
            return self.ibm_vpc_provider.generate_cos_bucket(bucket, effective_yaml_data)
        else:
            raise ValueError(f"Unsupported storage provider: {provider}")

    def resolve_bucket_region(self, bucket, provider):
        """Resolve bucket region with support for both direct regions and mapped locations."""
        bucket_name = bucket.get('name', 'unnamed')
        has_region = 'region' in bucket
        has_location = 'location' in bucket

        if has_region and has_location:
            raise ValueError(f"Storage bucket '{bucket_name}' cannot specify both 'region' and 'location'.")

        if not has_region and not has_location:
            raise ValueError(f"Storage bucket '{bucket_name}' must specify either 'region' or 'location'.")

        if has_location:
            # Location-based: Map to provider-specific region
            location_key = bucket['location']
            
            if location_key in self.locations:
                mapped_region = self.locations[location_key].get(provider)
                if not mapped_region:
                    raise ValueError(f"Storage bucket '{bucket_name}': Location '{location_key}' is not supported for provider '{provider}'. "
                                   f"Check mappings/locations.yaml for supported locations.")
                return mapped_region
            else:
                raise ValueError(f"Storage bucket '{bucket_name}': Location '{location_key}' not found in location mappings. "
                               f"Check mappings/locations.yaml for supported locations.")

        if has_region:
            # Region-based: Use directly
            return bucket['region']

    def start_bucket_section(self, bucket_name, provider):
        """Start a new bucket section in the output."""
        print()
        # Replace {guid} with actual GUID in bucket name
        resolved_bucket_name = self.replace_guid_placeholders(bucket_name)
        print(f"[{resolved_bucket_name}]")

    def print_bucket_output(self, bucket_name, provider, message, indent_level=1):
        """Print bucket-specific output with proper indentation."""
        indent = "  " * indent_level
        print(f"{indent}{message}")

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
            
            if provider in ['aws', 'azure', 'gcp', 'ibm_vpc', 'ibm_classic']:  # Regional providers
                region = self._resolve_instance_region_silent(instance, provider)

                # Create a provider-specific region key to handle multiple providers in same region
                region_key = f"{region}_{provider}" if provider in ['ibm_vpc', 'ibm_classic'] else region

                # Track which SGs are needed in this region
                if region_key not in regional_sgs:
                    regional_sgs[region_key] = {'provider': provider, 'region': region, 'security_groups': set()}

                for sg_name in instance.get('security_groups', []):
                    if sg_name in security_groups:
                        regional_sgs[region_key]['security_groups'].add(sg_name)

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

        for region_key, region_data in regional_analysis.items():
            provider = region_data['provider']
            region = region_data.get('region', region_key)  # Use actual region, fallback to region_key

            # Check if any outbound rules exist in the configured security groups
            has_outbound_rules = False
            for sg_name in region_data['security_groups']:
                sg_config = security_groups[sg_name]
                rules = sg_config.get('rules', [])
                for rule in rules:
                    if rule.get('direction') == 'egress':
                        has_outbound_rules = True
                        break
                if has_outbound_rules:
                    break

            # Check if auto-create outbound SG is enabled for this provider
            auto_create_outbound = True  # Default to True
            if provider == 'ibm_vpc':
                ibm_vpc_config = config.get('yamlforge', {}).get('ibm_vpc', {})
                auto_create_outbound = ibm_vpc_config.get('auto_create_outbound_sg', True)
            elif provider == 'ibm_classic':
                ibm_classic_config = config.get('yamlforge', {}).get('ibm_classic', {})
                auto_create_outbound = ibm_classic_config.get('auto_create_outbound_sg', True)

            # Create automatic outbound security group if needed
            if auto_create_outbound and not has_outbound_rules and provider in ['ibm_vpc', 'ibm_classic']:
                self.print_provider_output(provider, f"No outbound security group rules found. Creating automatic outbound security group for {region}.")
                guid = self.get_validated_guid(config)
                auto_outbound_sg_name = f"auto-outbound-{region}-{guid}"
                auto_outbound_rules = [{
                    'direction': 'egress',
                    'protocol': 'all',
                    'port_range': '1-65535',
                    'destination': '0.0.0.0/0',
                    'description': 'Allow all outbound traffic (auto-created)'
                }]
                if provider == 'ibm_vpc':
                    sg_terraform += self.ibm_vpc_provider.generate_ibm_security_group(auto_outbound_sg_name, auto_outbound_rules, region, config)
                elif provider == 'ibm_classic':
                    sg_terraform += self.ibm_classic_provider.generate_ibm_classic_security_group(auto_outbound_sg_name, auto_outbound_rules, region, config)
                
                # Add the auto-created security group to all instances in this region
                for instance in config.get('instances', []):
                    instance_provider = instance.get('provider')
                    if instance_provider == 'cheapest':
                        instance_provider = self.find_cheapest_provider(instance, suppress_output=True)
                    elif instance_provider == 'cheapest-gpu':
                        instance_provider = self.find_cheapest_gpu_provider(instance, suppress_output=True)
                    
                    if instance_provider == 'ibm_vpc' and self._resolve_instance_region_silent(instance, 'ibm_vpc') == region:
                        if 'security_groups' not in instance:
                            instance['security_groups'] = []
                        instance['security_groups'].append(auto_outbound_sg_name)
                    elif instance_provider == 'ibm_classic' and self._resolve_instance_region_silent(instance, 'ibm_classic') == region:
                        if 'security_groups' not in instance:
                            instance['security_groups'] = []
                        instance['security_groups'].append(auto_outbound_sg_name)

            for sg_name in region_data['security_groups']:
                sg_config = security_groups[sg_name]
                rules = sg_config.get('rules', [])

                # Generate region-specific security group
                if provider == 'aws':
                    sg_terraform += self.get_aws_provider().generate_aws_security_group(sg_name, rules, region, config)
                elif provider == 'azure':
                    sg_terraform += self.azure_provider.generate_azure_security_group(sg_name, rules, region, config)
                elif provider == 'gcp':
                    sg_terraform += self.gcp_provider.generate_gcp_firewall_rules(sg_name, rules, region)
                elif provider == 'ibm_vpc':
                    sg_terraform += self.ibm_vpc_provider.generate_ibm_security_group(sg_name, rules, region, config)
                elif provider == 'ibm_classic':
                    sg_terraform += self.ibm_classic_provider.generate_ibm_classic_security_group(sg_name, rules, region, config)
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
            
            if provider in ['aws', 'azure', 'gcp', 'ibm_vpc', 'ibm_classic']:  # Regional providers
                region = self._resolve_instance_region_silent(instance, provider)

                # Create a provider-specific region key to handle multiple providers in same region
                region_key = f"{region}_{provider}" if provider in ['ibm_vpc', 'ibm_classic'] else region

                # Track regions that need networking
                if region_key not in regional_instances:
                    regional_instances[region_key] = {'provider': provider, 'region': region, 'instances': []}
                
                regional_instances[region_key]['instances'].append(instance)

        return regional_instances

    def collect_ibm_vpc_zones(self, config):
        """Collect zone information for IBM VPC instances to ensure consistency."""
        instances = config.get('instances', [])
        zone_map = {}  # region -> zone
        
        for instance in instances:
            if instance.get('provider') == 'ibm_vpc':
                region = self._resolve_instance_region_silent(instance, 'ibm_vpc')
                user_specified_zone = instance.get('zone')
                
                if region not in zone_map:
                    # First instance in this region - validate/select zone
                    if user_specified_zone:
                        # Validate the zone
                        self.ibm_vpc_provider.validate_and_select_zone(region, user_specified_zone, config)
                        zone_map[region] = user_specified_zone
                    else:
                        # Auto-select zone
                        selected_zone = self.ibm_vpc_provider.validate_and_select_zone(region, None, config)
                        zone_map[region] = selected_zone
                else:
                    # Subsequent instance in this region - validate consistency
                    if user_specified_zone:
                        if user_specified_zone != zone_map[region]:
                            raise ValueError(f"Instance '{instance.get('name', 'unknown')}': Zone '{user_specified_zone}' conflicts with "
                                           f"previously selected zone '{zone_map[region]}' for region '{region}'. "
                                           f"All instances in the same region must use the same zone.")
                    # If no zone specified, use the already selected one
        
        return zone_map

    def generate_regional_networking(self, config, ibm_vpc_zones=None):
        """Generate networking infrastructure for each region where instances are deployed."""
        regional_analysis = self.analyze_regional_instances(config)
        networking_terraform = ""
        
        # Use provided zone information or collect it if not provided
        if ibm_vpc_zones is None:
            ibm_vpc_zones = self.collect_ibm_vpc_zones(config)

        if hasattr(self, 'verbose') and self.verbose:
            print(f"DEBUG: regional_analysis = {regional_analysis}")
            print(f"DEBUG: ibm_vpc_zones = {ibm_vpc_zones}")

        for region_key, region_data in regional_analysis.items():
            provider = region_data['provider']
            region = region_data.get('region', region_key)  # Use actual region, fallback to region_key
            if hasattr(self, 'verbose') and self.verbose:
                print(f"DEBUG: Processing region_key={region_key}, region={region}, provider={provider}")
            # Get deployment name from cloud_workspace
            cloud_workspace = config.get('cloud_workspace', {})
            workspace_name = cloud_workspace.get('name', 'yamlforge-deployment')
            
            # Check if the workspace name already contains a GUID placeholder
            if '{guid}' in workspace_name:
                # If it already has {guid}, just replace it without appending another GUID
                deployment_name = self.replace_guid_placeholders(workspace_name)
            else:
                # If it doesn't have {guid}, append the GUID
                deployment_name = f"{workspace_name}-{self.get_validated_guid(config)}"
            deployment_config = config.get('network', {})

            # Generate regional networking
            if provider == 'aws':
                networking_terraform += self.get_aws_provider().generate_aws_networking(deployment_name, deployment_config, region, config)
            elif provider == 'azure':
                networking_terraform += self.azure_provider.generate_azure_networking(deployment_name, deployment_config, region, config)
            elif provider == 'gcp':
                networking_terraform += self.gcp_provider.generate_gcp_networking(deployment_name, deployment_config, region)
            elif provider == 'ibm_vpc':
                if hasattr(self, 'verbose') and self.verbose:
                    print(f"DEBUG: About to call IBM VPC networking for region={region}")
                # Pass the selected zone for this region
                zone = ibm_vpc_zones.get(region)
                networking_terraform += self.ibm_vpc_provider.generate_ibm_vpc_networking(deployment_name, deployment_config, region, config, zone)
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
        resolved_tags = []
        for sg_name in sg_names:
            # Replace {guid} placeholder in security group name
            resolved_name = self.replace_guid_placeholders(sg_name)
            # GCP tags must be lowercase and contain only letters, numbers, and dashes
            sanitized_name = resolved_name.lower().replace("_", "-")
            resolved_tags.append(sanitized_name)
        return resolved_tags

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

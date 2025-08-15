"""
GCP Provider Module

Contains GCP-specific implementations for image resolution, VM generation,
networking, firewall rules, project management, user access control, and other GCP cloud resources.
"""

import yaml
import os
import json
from pathlib import Path
from datetime import datetime
import re
import subprocess
from ..utils import find_yamlforge_file

# GCP imports
try:
    from google.cloud import compute_v1
    from google.cloud import dns  # pylint: disable=import-error
    from google.auth import default as google_auth_default  # pylint: disable=import-error
    from google.auth.exceptions import DefaultCredentialsError  # pylint: disable=import-error
    from google.api_core import exceptions as google_exceptions
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    print("Warning: google-cloud-compute and google-cloud-dns not installed. GCP image and DNS discovery will fail if requested.")


class GCPImageResolver:
    """Resolves Red Hat Cloud Access images from Google Cloud using the Compute API."""

    def __init__(self, credentials_manager=None):
        """Initialize the instance."""
        self.credentials = credentials_manager
        self.config = self.load_config()
        self.client = None
        self.cache = {}
        self.cache_timestamps = {}

    def load_config(self):
        """Load GCP configuration from credentials system."""
        # Check if credentials are available for dynamic discovery
        if not self.credentials:
            print("Warning: GCP credentials not found. Image discovery will fail if GCP images are requested.")
            return {'project_id': '', 'has_credentials': False}
            
        gcp_creds = self.credentials.get_gcp_credentials()
        has_credentials = gcp_creds.get('available', False)

        if not has_credentials:
            print("Warning: GCP credentials not found. Image discovery will fail if GCP images are requested.")

        return {
            'project_id': gcp_creds.get('project_id', '') if has_credentials else '',
            'has_credentials': has_credentials
        }

    def get_client(self):
        """Initialize and return GCP Compute client."""
        if not GOOGLE_CLOUD_AVAILABLE:
            return None

        try:
            # Use Application Default Credentials or service account
            credentials, project = google_auth_default()
            client = compute_v1.ImagesClient(credentials=credentials)
            return client

        except DefaultCredentialsError:
            print("Warning: GCP credentials not found. Image discovery disabled.")
            return None
        except Exception as e:
            print(f"Warning: Failed to create GCP client: {e}")
            return None



    def is_cache_valid(self, family):
        """Check if cached result is still valid."""
        return family in self.cache_timestamps


class GCPProvider:
    """GCP-specific provider implementation."""

    def __init__(self, converter):
        """Initialize the instance."""
        self.converter = converter
        self.config = self.load_config()
        self.guid = None  # Will be set later when YAML data is available

    def update_guid(self, guid):
        """Update the GUID for this provider instance."""
        self.guid = guid

    def get_validated_guid(self):
        """Get GUID from converter - no local validation needed."""
        if not self.guid:
            # Get GUID from converter which handles validation
            if hasattr(self.converter, 'current_yaml_data') and self.converter.current_yaml_data:
                self.guid = self.converter.get_validated_guid(self.converter.current_yaml_data)
            else:
                # Fallback to environment variable only
                guid = os.environ.get('GUID', '').strip()
                if guid:
                    self.guid = guid.lower()
                else:
                    raise ValueError("GUID is required but not provided. Please set the GUID environment variable.")
        return self.guid

    def load_config(self):
        """Load GCP configuration from defaults and credentials system."""
        # Load defaults file using improved path detection
        try:
            defaults_file = find_yamlforge_file("defaults/gcp.yaml")
        except FileNotFoundError as e:
            raise Exception(f"Required GCP defaults file not found: defaults/gcp.yaml")

        try:
            with open(defaults_file, 'r') as f:
                defaults_config = yaml.safe_load(f)
        except Exception as e:
            raise Exception(f"Failed to load defaults/gcp.yaml: {e}")

        if not defaults_config:
            raise Exception("defaults/gcp.yaml is empty or invalid")

        # Get configuration values from defaults
        default_apis = defaults_config.get('default_apis', [])
        project_defaults = defaults_config.get('project_defaults', {})
        dns_config = defaults_config.get('dns_config', {})
        user_management = defaults_config.get('user_management', {})

        # Check if credentials are available
        gcp_creds = self.converter.credentials.get_gcp_credentials() if self.converter.credentials else {}
        has_credentials = gcp_creds.get('available', False)

        # Get project configuration from environment variables
        project_id = gcp_creds.get('project_id', '') if has_credentials else ""
        billing_account_id = ""
        organization_id = ""
        folder_id = ""
        use_existing_project = False
        existing_project_id = ""

        # Fall back to environment variables if not in credentials
        if not billing_account_id:
            billing_account_id = os.environ.get('GCP_BILLING_ACCOUNT_ID', 
                                              project_defaults.get('billing_account_id', ''))
        if not organization_id:
            organization_id = os.environ.get('GCP_ORGANIZATION_ID', 
                                           project_defaults.get('organization_id', ''))
        if not folder_id:
            folder_id = os.environ.get('GCP_FOLDER_ID', 
                                     project_defaults.get('folder_id', ''))
        
        # Project management approach configuration
        if not use_existing_project:
            use_existing_project_str = os.environ.get('GCP_USE_EXISTING_PROJECT', '').lower()
            use_existing_project = use_existing_project_str in ['true', '1', 'yes']
        
        if not existing_project_id:
            existing_project_id = os.environ.get('GCP_EXISTING_PROJECT_ID', '')
            # Fall back to GCP_PROJECT_ID if no specific existing project ID is set
            if not existing_project_id and use_existing_project:
                existing_project_id = os.environ.get('GCP_PROJECT_ID', project_id)

        # Load additional configuration from environment variables with fallback resolution
        admin_group_default = project_defaults.get('admin_group', 'gcp-admins@example.com')
        if admin_group_default.startswith('${') and admin_group_default.endswith('}'):
            # Extract environment variable name from ${VAR_NAME}
            env_var = admin_group_default[2:-1]
            admin_group = os.environ.get(env_var, 'gcp-admins@example.com')
        else:
            admin_group = os.environ.get('GCP_PROJECT_OWNER_EMAIL', admin_group_default)

        company_domain_default = user_management.get('company_domain', 'example.com')
        if company_domain_default.startswith('${') and company_domain_default.endswith('}'):
            env_var = company_domain_default[2:-1]
            company_domain = os.environ.get(env_var, 'example.com')
        else:
            company_domain = os.environ.get('GCP_COMPANY_DOMAIN', company_domain_default)

        root_zone_domain_default = dns_config.get('root_zone', {}).get('domain', 'example.com')
        if root_zone_domain_default.startswith('${') and root_zone_domain_default.endswith('}'):
            env_var = root_zone_domain_default[2:-1]
            root_zone_domain = os.environ.get(env_var, 'example.com')
        else:
            root_zone_domain = os.environ.get('GCP_ROOT_ZONE_DOMAIN', root_zone_domain_default)

        return {
            'default_apis': default_apis,
            'project_defaults': project_defaults,
            'dns_config': dns_config,
            'user_management': user_management,
            'project_id': project_id,
            'billing_account_id': billing_account_id,
            'organization_id': organization_id,
            'folder_id': folder_id,
            'use_existing_project': use_existing_project,
            'existing_project_id': existing_project_id,
            'admin_group': admin_group,
            'company_domain': company_domain,
            'root_zone_domain': root_zone_domain,
            'has_credentials': has_credentials
        }



    def get_gcp_machine_type(self, flavor_or_instance_type):
        """Get GCP machine type from flavor or instance type."""
        # Handle None input
        if not flavor_or_instance_type:
            raise ValueError("flavor_or_instance_type cannot be None or empty")
        
        # If it's already a GCP machine type, return it directly
        if any(prefix in flavor_or_instance_type for prefix in ['n1-', 'n2-', 'e2-', 'c2-', 'a2-', 'm1-', 'm2-']):
            return flavor_or_instance_type
        
        # Load GCP flavors
        gcp_flavors = self.converter.flavors.get('gcp', {}).get('flavor_mappings', {})
        size_mapping = gcp_flavors.get(flavor_or_instance_type, {})
        
        if size_mapping:
            # Return the first (usually cheapest) option
            return next(iter(size_mapping.keys()))
        
        # Check machine types
        machine_types = self.converter.flavors.get('gcp', {}).get('machine_types', {})
        if flavor_or_instance_type in machine_types:
            return flavor_or_instance_type
        
        raise ValueError(f"No GCP machine type mapping found for flavor '{flavor_or_instance_type}'. "
                        f"Available flavors: {list(gcp_flavors.keys())}")

    def check_machine_type_availability(self, machine_type, region, zone=None, silent=False):
        """Check if a GCP machine type is available in the specified region/zone."""
        # Skip availability checking in no-credentials mode
        if self.converter.no_credentials:
            if not silent:
                print(f"  NO-CREDENTIALS MODE: Skipping machine type availability check for '{machine_type}' in region '{region}'")
            return True
        
        if not GOOGLE_CLOUD_AVAILABLE:
            return self._fallback_machine_type_check(machine_type, region)
        
        try:
            # Initialize the compute client
            client = compute_v1.MachineTypesClient()
            
            if zone:
                # Check specific zone
                request = compute_v1.GetMachineTypeRequest(
                    project=self._get_project_id(),
                    zone=zone,
                    machine_type=machine_type
                )
                try:
                    client.get(request=request)
                    return True
                except google_exceptions.NotFound:
                    return False
            else:
                # Check all zones in the region using intelligent zone discovery
                available_zones = self.get_available_zones_for_region(region)
                if not available_zones:
                    return False
                    
                # Check the first available zone in the region
                request = compute_v1.ListMachineTypesRequest(
                    project=self._get_project_id(),
                    zone=available_zones[0]  # Use first available zone
                )
                try:
                    page_result = client.list(request=request)
                    for machine_type_obj in page_result:
                        if machine_type_obj.name == machine_type:
                            return True
                    return False
                except google_exceptions.NotFound:
                    return False
                    
        except Exception:
            # Fall back to known patterns if API fails
            return self._fallback_machine_type_check(machine_type, region)

    def _get_project_id(self):
        """Get the current GCP project ID."""
        try:
            # Try to get from environment
            import os
            project_id = os.environ.get('GCP_PROJECT_ID') or os.environ.get('GOOGLE_PROJECT')
            if project_id:
                return project_id
            
            # Try to get from gcloud config
            result = subprocess.run(['gcloud', 'config', 'get-value', 'project'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            
            # Default fallback
            if self.guid:
                return f"openenv-{self.guid}"
            return "openenv-12345"
            
        except Exception:
            if self.guid:
                return f"openenv-{self.guid}"
            return "openenv-12345"

    def _fallback_machine_type_check(self, machine_type, region):
        """Fallback method to check machine type availability using known patterns."""
        # Load GPU machine type availability from YAML file
        try:
            import yaml
            from pathlib import Path
            
            availability_path = find_yamlforge_file("mappings/gcp/machine-type-availability.yaml")
            if availability_path.exists():
                with open(availability_path, 'r') as f:
                    availability_data = yaml.safe_load(f)
                    gpu_machine_types = availability_data.get('gpu_machine_types', {})
                    
                    # Check if this is a GPU machine type
                    if machine_type in gpu_machine_types:
                        available_regions = gpu_machine_types[machine_type].get('regions', [])
                        return region in available_regions
                    
                    # For non-GPU machine types, assume they're available in most regions
                    # This is a conservative approach - in practice, most standard machine types are widely available
                    return True
            else:
                # Fallback if YAML file doesn't exist
                return True
        except Exception as e:
            # Fallback if YAML loading fails
            print(f"Warning: Could not load GCP machine type availability from YAML: {e}")
            return True

    def find_available_regions_for_machine_type(self, machine_type):
        """Find all regions where a machine type is available."""
        if not GOOGLE_CLOUD_AVAILABLE:
            return self._fallback_find_regions_for_machine_type(machine_type)
        
        try:
            # Initialize the compute client
            client = compute_v1.MachineTypesClient()
            
            # Get list of all zones
            zones_client = compute_v1.ZonesClient()
            request = compute_v1.ListZonesRequest(project=self._get_project_id())
            
            available_regions = set()
            
            try:
                page_result = zones_client.list(request=request)
                for zone in page_result:
                    # Check if machine type exists in this zone
                    try:
                        mt_request = compute_v1.GetMachineTypeRequest(
                            project=self._get_project_id(),
                            zone=zone.name,
                            machine_type=machine_type
                        )
                        client.get(request=mt_request)
                        # Extract region from zone (e.g., us-central1-a -> us-central1)
                        region = zone.name.rsplit('-', 1)[0]
                        available_regions.add(region)
                    except google_exceptions.NotFound:
                        continue
                        
                return sorted(list(available_regions))
                
            except google_exceptions.NotFound:
                return self._fallback_find_regions_for_machine_type(machine_type)
                
        except Exception:
            # Fall back to known patterns if API fails
            return self._fallback_find_regions_for_machine_type(machine_type)

    def _fallback_find_regions_for_machine_type(self, machine_type):
        """Fallback method to find regions for a machine type using known patterns."""
        # Load GPU machine type availability from YAML file
        try:
            import yaml
            from pathlib import Path
            
            availability_path = find_yamlforge_file("mappings/gcp/machine-type-availability.yaml")
            if availability_path.exists():
                with open(availability_path, 'r') as f:
                    availability_data = yaml.safe_load(f)
                    gpu_machine_types = availability_data.get('gpu_machine_types', {})
                    common_regions = availability_data.get('common_regions', [])
                    
                    if machine_type in gpu_machine_types:
                        return gpu_machine_types[machine_type].get('regions', [])
                    
                    # For non-GPU types, return common regions
                    return common_regions
            else:
                # Fallback if YAML file doesn't exist
                return ['us-central1', 'us-east1', 'us-west1', 'us-east4', 'us-west2']
        except Exception as e:
            # Fallback if YAML loading fails
            print(f"Warning: Could not load GCP machine type availability from YAML: {e}")
            return ['us-central1', 'us-east1', 'us-west1', 'us-east4', 'us-west2']

    def find_closest_available_region(self, requested_region, available_regions):
        """Find the closest available region to the requested region."""
        if not available_regions:
            return None
        
        # If the requested region is available, use it
        if requested_region in available_regions:
            return requested_region
        
        # Load region proximity mapping from YAML file
        try:
            import yaml
            from pathlib import Path
            
            availability_path = find_yamlforge_file("mappings/gcp/machine-type-availability.yaml")
            if availability_path.exists():
                with open(availability_path, 'r') as f:
                    availability_data = yaml.safe_load(f)
                    region_proximity = availability_data.get('region_proximity', {})
                    
                    # Check nearby regions for the requested region
                    if requested_region in region_proximity:
                        nearby_regions = region_proximity[requested_region].get('nearby_regions', [])
                        for nearby_region in nearby_regions:
                            if nearby_region in available_regions:
                                return nearby_region
                    
                    # If no nearby region found, return the first available region
                    return available_regions[0] if available_regions else None
            else:
                # Fallback if YAML file doesn't exist
                return available_regions[0] if available_regions else None
        except Exception as e:
            # Fallback if YAML loading fails
            print(f"Warning: Could not load GCP region proximity from YAML: {e}")
            return available_regions[0] if available_regions else None

    def get_gcp_image_reference(self, image_name):
        """Get GCP image reference for a given image name."""
        # Default to RHEL 9
        default_image = "projects/rhel-cloud/global/images/family/rhel-9"

        # Try to get from image mappings
        if image_name in self.converter.images:
            gcp_config = self.converter.images[image_name].get('gcp', {})
            if gcp_config and 'image' in gcp_config:
                return gcp_config['image']

        # Check for RHEL patterns
        if "RHEL" in image_name.upper():
            if "8" in image_name:
                return "projects/rhel-cloud/global/images/family/rhel-8"
            elif "9" in image_name:
                return "projects/rhel-cloud/global/images/family/rhel-9"

        # Check for other OS patterns
        if "UBUNTU" in image_name.upper():
            return "projects/ubuntu-os-cloud/global/images/family/ubuntu-2004-lts"

        return default_image

    def generate_gcp_vm(self, instance, index, clean_name, flavor, available_subnets=None, yaml_data=None, has_guid_placeholder=False):
        """Generate native GCP Compute Engine instance."""
        instance_name = instance.get("name", f"instance_{index}")
        # Replace {guid} placeholder in instance name
        instance_name = self.converter.replace_guid_placeholders(instance_name)
        image = instance.get("image")
        if not image:
            raise ValueError(f"Instance '{instance_name}' requires an 'image' field")

        # Resolve region and zone
        gcp_region = self.converter.resolve_instance_region(instance, "gcp")
        
        # Check if user specified a zone (only valid with region-based configuration)
        user_specified_zone = instance.get('zone')
        has_region = 'region' in instance
        
        if user_specified_zone and has_region:
            # User specified both region and zone - validate the zone belongs to the region
            expected_region = user_specified_zone.rsplit('-', 1)[0]  # Extract region from zone (e.g., us-east1-b -> us-east1)
            
            if expected_region != gcp_region:
                raise ValueError(f"Instance '{instance_name}': Specified zone '{user_specified_zone}' does not belong to region '{gcp_region}'. "
                               f"Zone region: '{expected_region}', Instance region: '{gcp_region}'")
            
            print(f"Using user-specified zone '{user_specified_zone}' for instance '{instance_name}' in region '{gcp_region}'")
            gcp_zone = user_specified_zone
            
        elif user_specified_zone and not has_region:
            raise ValueError(f"Instance '{instance_name}': Zone '{user_specified_zone}' can only be specified when using 'region' (not 'location'). "
                           f"Either remove 'zone' or change 'location' to 'region'.")
        else:
            # Get machine type first for zone validation
            gcp_machine_type = self.get_gcp_machine_type(flavor)
            
            # Intelligently select best zone for the region and machine type
            gcp_zone = self.get_best_zone_for_region(gcp_region, gcp_machine_type, instance_name)
        
        # Get machine type (if not already retrieved for zone validation)
        if 'gcp_machine_type' not in locals():
            gcp_machine_type = self.get_gcp_machine_type(flavor)

        # Get image reference
        gcp_image = self.get_gcp_image_reference(image)

        # Get user data script
        user_data_script = instance.get('user_data_script')

        # Get firewall tags
        firewall_refs = self.converter.get_instance_gcp_firewall_refs(instance)
        
        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})
        
        # Get GUID for consistent naming
        guid = self.get_validated_guid()
        
        # Use clean_name directly if GUID is already present, otherwise add GUID
        resource_name = clean_name if has_guid_placeholder else f"{clean_name}_{guid}"

        vm_config = f'''
# GCP Compute Instance: {instance_name}
resource "google_compute_instance" "{resource_name}" {{
  name         = "{instance_name}"
  machine_type = "{gcp_machine_type}"
  zone         = "{gcp_zone}"

  boot_disk {{
    initialize_params {{
      image = "{gcp_image}"
      size  = 20
      type  = "pd-standard"
    }}
  }}

  network_interface {{
    subnetwork = google_compute_subnetwork.main_subnet_{gcp_region.replace("-", "_").replace(".", "_")}_{guid}.id
    access_config {{
      nat_ip = google_compute_address.{resource_name}_ip.address
    }}
  }}

  project = local.project_id'''

        # Add metadata only if SSH key is configured
        if ssh_key_config and ssh_key_config.get('public_key'):
            ssh_username = ssh_key_config.get('username', 'gcp-user')
            vm_config += f'''

  metadata = {{
    ssh-keys = "{ssh_username}:{ssh_key_config['public_key']}"
  }}'''

        # Add startup script if provided
        if user_data_script:
            vm_config += f'''

  metadata_startup_script = <<-USERDATA
{user_data_script}
USERDATA'''

        # Add firewall tags if any exist
        if firewall_refs:
            vm_config += f'''

  tags = [{', '.join([f'"{tag}"' for tag in firewall_refs])}]'''

        vm_config += f'''

  labels = {{
    environment = "agnosticd"
    managed-by = "yamlforge"
  }}
}}

# GCP External IP for {instance_name}
resource "google_compute_address" "{resource_name}_ip" {{
  name    = "{instance_name}-ip"
  region  = "{gcp_region}"
  project = local.project_id
  
  depends_on = [
    time_sleep.wait_for_compute_api_{guid}
  ]
  
  lifecycle {{
    prevent_destroy = false  # Allow destruction for easier cleanup
    ignore_changes = [name, region]
  }}
}}
'''
        
        # Check if DNS management is enabled before creating DNS records
        yaml_dns_config = yaml_data.get('dns_config', {}) if yaml_data else {}
        default_dns_config = self.config.get('dns_config', {})
        merged_dns_config = {**default_dns_config, **yaml_dns_config}
        
        dns_management_enabled = merged_dns_config.get('root_zone_management', False)
        default_root_zone = default_dns_config.get('root_zone', {})
        yaml_root_zone = yaml_dns_config.get('root_zone', {})
        merged_root_zone = {**default_root_zone, **yaml_root_zone}
        
        # Get project domain (same logic as in project management)
        root_zone_domain = self.get_root_zone_domain(yaml_data)
        yaml_domain = yaml_root_zone.get('domain')
        if yaml_domain and not yaml_domain.startswith('${{'):
            project_domain = yaml_domain
        else:
            project_domain = root_zone_domain
        
        # Only create DNS records if DNS management is enabled AND domain is specified
        if dns_management_enabled and project_domain:
            vm_config += f'''
# DNS A Record for {instance_name} (if DNS zone exists)
resource "google_dns_record_set" "{clean_name}_dns_{guid}" {{
  count = length(google_dns_managed_zone.main_{guid}.name_servers) > 0 ? 1 : 0
  
  name         = "{instance_name}.{guid}.{project_domain}."
  managed_zone = google_dns_managed_zone.main_{guid}.name
  type         = "A"
  ttl          = 300
  
  rrdatas = [google_compute_address.{resource_name}_ip.address]
  project = local.project_id
}}

# Internal DNS A Record for {instance_name} (private IP)
resource "google_dns_record_set" "{clean_name}_internal_dns_{guid}" {{
  count = length(google_dns_managed_zone.main_{guid}.name_servers) > 0 ? 1 : 0
  
  name         = "{instance_name}-internal.{guid}.{project_domain}."
  managed_zone = google_dns_managed_zone.main_{guid}.name
  type         = "A"
  ttl          = 300
  
  rrdatas = [google_compute_instance.{resource_name}.network_interface[0].network_ip]
  project = local.project_id
}}
'''
        return vm_config

    def generate_gcp_firewall_rules(self, sg_name, rules, region):
        """Generate GCP firewall rules for specific region (equivalent to security groups)."""
        # Replace {guid} placeholder in security group name
        sg_name = self.converter.replace_guid_placeholders(sg_name)
        clean_name = sg_name.replace("-", "_").replace(".", "_")
        clean_region = region.replace("-", "_").replace(".", "_")
        regional_fw_name = f"{clean_name}_{clean_region}"
        regional_network_ref = f"google_compute_network.main_network_{clean_region}_{self.get_validated_guid()}.id"

        firewall_config = ""

        # Generate individual firewall rules
        for i, rule in enumerate(rules):
            rule_data = self.converter.generate_native_security_group_rule(rule, 'gcp')
            direction = rule_data['direction'].upper()  # GCP uses INGRESS/EGRESS

            # Create unique firewall rule name
            rule_name = f"{regional_fw_name}_rule_{i+1}"

            # Handle different source types
            source_cidr_blocks = rule_data.get('source_cidr_blocks', [])
            if rule_data.get('is_source_cidr', False):
                source_ranges = [f'"{cidr}"' for cidr in source_cidr_blocks]
                source_config = f'''  source_ranges = [{', '.join(source_ranges)}]'''
            else:
                # Provider-specific source (e.g., tags)
                source_config = f'''  source_tags = ["{rule_data['source']}"]'''

            # Handle different destination types
            destination_config = ""
            destination_cidr_blocks = rule_data.get('destination_cidr_blocks', [])
            if rule_data.get('destination'):
                if rule_data.get('is_destination_cidr', False):
                    destination_ranges = [f'"{cidr}"' for cidr in destination_cidr_blocks]
                    destination_config = f'''
  destination_ranges = [{', '.join(destination_ranges)}]'''
                else:
                    # Provider-specific destination (e.g., tags)
                    destination_config = f'''
  target_tags = ["{rule_data['destination']}"]'''

            firewall_config += f'''
# GCP Firewall Rule: {sg_name} Rule {i+1} (Region: {region})
resource "google_compute_firewall" "{rule_name}_{self.get_validated_guid()}" {{
  name    = "{sg_name}-{region}-rule-{i+1}"
  network = {regional_network_ref}
  project = local.project_id

  allow {{
    protocol = "{rule_data['protocol']}"
    ports    = ["{rule_data['from_port']}-{rule_data['to_port']}"]
  }}

  direction     = "{direction}"
{source_config}{destination_config}
  target_tags   = ["{sg_name}"]
}}
'''

        return firewall_config

    def generate_gcp_networking(self, deployment_name, deployment_config, region):
        """Generate GCP networking components with proper API dependencies."""
        network_config = deployment_config.get('network', {})
        network_name = network_config.get('name', f"{deployment_name}-network")
        cidr_block = network_config.get('cidr_block', '10.0.0.0/16')

        clean_region = region.replace("-", "_").replace(".", "_")

        return f'''
# GCP Network: {network_name}
resource "google_compute_network" "main_network_{clean_region}_{self.get_validated_guid()}" {{
  name                    = "{network_name}"
  auto_create_subnetworks = false
  project                 = local.project_id
  
  depends_on = [
    time_sleep.wait_for_compute_api_{self.get_validated_guid()}
  ]
}}

# GCP Subnet: {network_name} subnet
resource "google_compute_subnetwork" "main_subnet_{clean_region}_{self.get_validated_guid()}" {{
  name          = "{network_name}-subnet"
  ip_cidr_range = "{cidr_block}"
  region        = "{region}"
  network       = google_compute_network.main_network_{clean_region}_{self.get_validated_guid()}.id
  project       = local.project_id
  
  depends_on = [
    google_compute_network.main_network_{clean_region}_{self.get_validated_guid()}
  ]
}}

# Default SSH access firewall rule
resource "google_compute_firewall" "main_ssh_{clean_region}_{self.get_validated_guid()}" {{
  name    = "{network_name}-ssh"
  network = google_compute_network.main_network_{clean_region}_{self.get_validated_guid()}.id
  project = local.project_id

  allow {{
    protocol = "tcp"
    ports    = ["22"]
  }}

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["ssh-allowed"]
  
  depends_on = [
    google_compute_network.main_network_{clean_region}_{self.get_validated_guid()}
  ]
}}
'''

    def discover_dns_zone_name(self, domain, project_id):
        """Discover DNS zone name for a domain using Google Cloud DNS API."""
        if not GOOGLE_CLOUD_AVAILABLE:
            # Fallback to naming convention
            return domain.replace('.', '-') + '-zone'
        
        try:
            # Initialize DNS client
            client = dns.Client(project=project_id)
            
            # Search for managed zones that handle this domain
            domain_with_dot = domain if domain.endswith('.') else domain + '.'
            
            # List all managed zones in the project
            zones = client.list_zones()
            
            # Find zone that matches our domain
            for zone in zones:
                if zone.dns_name == domain_with_dot:
                    return zone.name
            
            # If no exact match found, fallback to naming convention
            print(f"Warning: No DNS zone found for domain '{domain}' in project '{project_id}'. Using naming convention fallback.")
            return domain.replace('.', '-') + '-zone'
            
        except Exception as e:
            print(f"Warning: Failed to discover DNS zone for domain '{domain}': {e}. Using naming convention fallback.")
            return domain.replace('.', '-') + '-zone'
    
    def get_root_zone_domain(self, yaml_data):
        """Get the root zone domain for DNS record creation."""
        if yaml_data:
            # Check if domain is specified in YAML
            dns_config = yaml_data.get('dns_config', {})
            root_zone = dns_config.get('root_zone', {})
            yaml_domain = root_zone.get('domain')
            if yaml_domain and not yaml_domain.startswith('${{'):
                return yaml_domain
        
        # Fall back to config domain (from environment or defaults)
        return self.config.get('root_zone_domain', 'example.com')
    


    def generate_project_management(self, yaml_data):
        """Generate GCP project management, user access, and DNS infrastructure."""
        project_terraform = '''
# ========================================
# GCP Project Management and User Access
# ========================================

'''
        
        # Extract user configuration
        users = yaml_data.get('users', [])
        cloud_workspace = yaml_data.get('yamlforge', {}).get('cloud_workspace', {})
        workspace_name = cloud_workspace.get('name', f'openenv-{self.get_validated_guid()}')
        
        # Get GCP configuration from YAML (override environment/defaults)
        yaml_gcp_config = yaml_data.get('yamlforge', {}).get('gcp', {})
        
        # Get configuration from loaded environment variables and defaults, with YAML overrides
        project_defaults = self.config['project_defaults']
        admin_group = self.config['admin_group']
        billing_account_id = yaml_gcp_config.get('billing_account_id', self.config['billing_account_id'])
        organization_id = yaml_gcp_config.get('organization_id', self.config['organization_id'])
        folder_id = yaml_gcp_config.get('folder_id', self.config['folder_id'])
        use_existing_project = yaml_gcp_config.get('use_existing_project', self.config['use_existing_project'])
        existing_project_id = yaml_gcp_config.get('existing_project_id', self.config['existing_project_id'])
        company_domain = self.config['company_domain']
        root_zone_domain = self.config['root_zone_domain']
        sa_name = project_defaults.get('project_service_account', 'yamlforge-automation')
        
        # Generate project ID from workspace name and GUID if creating new project
        if not self.guid:
            self.get_validated_guid()
            
        if use_existing_project and existing_project_id:
            # Use existing project
            project_id = existing_project_id
            project_terraform += f'''
# Using existing GCP Project: {existing_project_id}
data "google_project" "main_{self.get_validated_guid()}" {{
  project_id = "{existing_project_id}"
}}

# Local value to reference project ID
locals {{
  project_id = data.google_project.main_{self.get_validated_guid()}.project_id
}}

'''
        else:
            # Create new project
            # Use workspace name as project ID base, ensure it follows GCP project naming rules
            base_name = workspace_name.lower().replace('_', '-').replace(' ', '-')
            if not base_name.startswith('openenv-'):
                base_name = f'openenv-{self.guid}'
            project_id = base_name
            project_name = base_name  # Make project name and ID the same
            
            # Determine parent: folder_id takes priority over organization_id
            parent_config = ""
            if folder_id and not folder_id.startswith('${'):
                # Ensure folder_id is in correct format
                formatted_folder_id = folder_id if folder_id.startswith('folders/') else f'folders/{folder_id}'
                parent_config = f'folder_id = "{formatted_folder_id}"'
            elif organization_id and not organization_id.startswith('${'):
                parent_config = f'org_id = "{organization_id}"'
            else:
                parent_config = '# parent configured via environment (GCP_FOLDER_ID or GCP_ORGANIZATION_ID)'
            
            project_terraform += f'''
# GCP Project (creating new project)
resource "google_project" "main_{self.get_validated_guid()}" {{
  name        = "{project_name}"
  project_id  = "{project_id}"
  {parent_config}
  {f'billing_account = "{billing_account_id}"' if billing_account_id and not billing_account_id.startswith('${') else '# billing_account configured via environment'}
  
  auto_create_network = false
  
  lifecycle {{
    prevent_destroy = false  # Allow destruction for easier cleanup
  }}
}}

# Local value to reference project ID
locals {{
  project_id = google_project.main_{self.get_validated_guid()}.project_id
}}

'''
        
        # 2. Enable default APIs with explicit dependencies and wait for propagation
        default_apis = self.config['default_apis']
        api_resources = []
        
        # Set up dependency based on whether we're using existing or new project
        if use_existing_project and existing_project_id:
            project_dependency = f"data.google_project.main_{self.get_validated_guid()}"
        else:
            project_dependency = f"google_project.main_{self.get_validated_guid()}"
        
        for api in default_apis:
            clean_api = api.replace('.', '_').replace('-', '_')
            api_resource_name = f"google_project_service.{clean_api}_{self.get_validated_guid()}"
            api_resources.append(api_resource_name)
            
            project_terraform += f'''
# Enable API: {api}
resource "google_project_service" "{clean_api}_{self.get_validated_guid()}" {{
  project = local.project_id
  service = "{api}"
  
  disable_dependent_services = true
  disable_on_destroy = false
  
  depends_on = [{project_dependency}]
}}

'''
        
        # 3. Add explicit wait for Compute Engine API propagation
        project_terraform += f'''
# Wait for Compute Engine API to propagate before creating compute resources
resource "time_sleep" "wait_for_compute_api_{self.get_validated_guid()}" {{
  depends_on = [google_project_service.compute_googleapis_com_{self.get_validated_guid()}]
  
  create_duration = "60s"  # Wait 60 seconds for API propagation
}}

'''
        
        # 4. Create service account for infrastructure management
        project_terraform += f'''
# Project Service Account
resource "google_service_account" "{sa_name.replace('-', '_')}_{self.get_validated_guid()}" {{
  account_id   = "{sa_name}"
  display_name = "{project_name} Service Account"
  description  = "Service account for {project_name} infrastructure management"
  project      = local.project_id
  
  depends_on = [google_project_service.iam_googleapis_com_{self.get_validated_guid()}]
  
  lifecycle {{
    prevent_destroy = false  # Allow destruction for easier cleanup
    ignore_changes = [account_id, display_name, description]
  }}
}}

# Grant Owner role to project service account
resource "google_project_iam_member" "project_sa_owner_{self.get_validated_guid()}" {{
  project = local.project_id
  role    = "roles/owner"
  member  = "serviceAccount:${{google_service_account.{sa_name.replace('-', '_')}_{self.get_validated_guid()}.email}}"
  
  depends_on = [
    google_service_account.{sa_name.replace('-', '_')}_{self.get_validated_guid()},
    google_project_service.iam_googleapis_com_{self.get_validated_guid()}
  ]
}}

# Create service account key for project service account
resource "google_service_account_key" "project_sa_key_{self.get_validated_guid()}" {{
  service_account_id = google_service_account.{sa_name.replace('-', '_')}_{self.get_validated_guid()}.name
  
  depends_on = [google_service_account.{sa_name.replace('-', '_')}_{self.get_validated_guid()}]
}}

# Store service account key locally
resource "local_file" "project_sa_key_file_{self.get_validated_guid()}" {{
  content  = base64decode(google_service_account_key.project_sa_key_{self.get_validated_guid()}.private_key)
  filename = "{project_defaults.get('service_account_key_path', '/tmp/yamlforge-keys')}/{project_id}-{sa_name}.json"
  
  provisioner "local-exec" {{
    command = "mkdir -p {project_defaults.get('service_account_key_path', '/tmp/yamlforge-keys')}"
  }}
  
  depends_on = [google_service_account_key.project_sa_key_{self.get_validated_guid()}]
}}

'''
        
        # 5. Admin group ownership with proper dependencies
        if admin_group and '@' in admin_group:
            if admin_group.endswith('@googlegroups.com') or admin_group.startswith('group:'):
                member_type = "group"
                member_email = admin_group.replace('group:', '')
            else:
                member_type = "user"
                member_email = admin_group
        else:
            member_type = "group"
            member_email = admin_group

        # Only create IAM member if we have a valid email (not the placeholder)
        if member_email and member_email != "gcp-admins@example.com" and "@" in member_email:
            project_terraform += f'''
# Grant Owner role to admin {member_type}
resource "google_project_iam_member" "admin_owner" {{
  project = local.project_id
  role    = "roles/owner"
  member  = "{member_type}:{member_email}"
  
  depends_on = [
    google_project.main_{self.get_validated_guid()},
    google_project_service.iam_googleapis_com_{self.get_validated_guid()}
  ]
}}

'''
        
        # 6. User management logic
        # Get user management config (separate from DNS management)
        yaml_user_mgmt = yaml_data.get('user_management', {})
        default_user_mgmt = self.config.get('user_management', {})
        merged_user_mgmt = {**default_user_mgmt, **yaml_user_mgmt}
        
        # Check if domain-based ownership is enabled
        enable_domain_ownership = merged_user_mgmt.get('enable_domain_ownership', True)
        # Use company_domain from loaded config (environment variable or defaults)
        company_domain_config = company_domain
        
        for user in users:
            email = user.get('email', '')
            roles = user.get('roles', ['roles/viewer'])
            display_name = user.get('display_name', email.split('@')[0])
            
            if not email:
                continue
                
            # Check if user email domain matches company domain for automatic ownership
            if enable_domain_ownership and company_domain_config:
                user_domain = email.split('@')[1] if '@' in email else ''
                if user_domain == company_domain_config:
                    user_roles = ['roles/owner']
                else:
                    user_roles = roles
            else:
                # No domain-based ownership, use specified roles
                user_roles = roles
            
            # Generate IAM bindings for user
            for role in user_roles:
                clean_role = role.replace('/', '_').replace('.', '_')
                clean_email = email.replace('@', '_at_').replace('.', '_')
                binding_name = f"user_{clean_email}_{clean_role}"
                
                project_terraform += f'''
# User IAM: {email} -> {role}
resource "google_project_iam_member" "{binding_name}_{self.get_validated_guid()}" {{
  project = local.project_id
  role    = "{role}"
  member  = "user:{email}"
}}

'''
        
        # 7. DNS Zone Management with Automatic Delegation (Optional)
        # Get DNS config for infrastructure management (separate from user management)
        yaml_dns_config = yaml_data.get('dns_config', {})
        default_dns_config = self.config['dns_config']
        merged_dns_config = {**default_dns_config, **yaml_dns_config}
        
        # Check if DNS management is enabled and domain is specified
        dns_management_enabled = merged_dns_config.get('root_zone_management', False)
        default_root_zone = default_dns_config.get('root_zone', {})
        yaml_root_zone = yaml_dns_config.get('root_zone', {})
        merged_root_zone = {**default_root_zone, **yaml_root_zone}
        # Use root_zone_domain from loaded config (environment variable or defaults)
        # Check if YAML overrides the domain, otherwise use resolved environment variable
        yaml_domain = yaml_root_zone.get('domain')
        if yaml_domain and not yaml_domain.startswith('${{'):
            project_domain = yaml_domain
        else:
            project_domain = root_zone_domain
        
        # Only create DNS infrastructure if root zone management is enabled AND domain is specified
        if dns_management_enabled and project_domain:
            # Ensure GUID is available for DNS subdomain generation
            if not self.guid:
                self.get_validated_guid()
                
            dns_zone = project_domain
            subdomain = f"{self.guid}.{dns_zone}"
            delegation_ttl = merged_dns_config.get('delegation_ttl', 86400)
            
            # Create subdomain managed zone
            project_terraform += f'''
# Managed DNS Zone for subdomain
resource "google_dns_managed_zone" "main_{self.get_validated_guid()}" {{
  name        = "{self.guid.replace('-', '')}-zone"
  dns_name    = "{subdomain}."
  description = "Managed zone for {workspace_name} - {subdomain}"
  project     = local.project_id
  
  depends_on = [google_project_service.dns_googleapis_com_{self.get_validated_guid()}]
}}

'''
            
            # Add automatic delegation if root zone configuration is provided
            root_zone_config = merged_root_zone
            root_domain = root_zone_config.get('domain', dns_zone)
            zone_name_specified = root_zone_config.get('zone_name', '')
            root_zone_project = root_zone_config.get('project_id', self.config['project_id'])
            auto_create_root = root_zone_config.get('auto_create', False)
            
            # Determine root zone project reference
            if root_zone_project:
                root_zone_project_ref = f'"{root_zone_project}"'
                root_zone_data_project = f'  project = "{root_zone_project}"'
            else:
                root_zone_project_ref = 'google_project.main.project_id'
                root_zone_data_project = '  project = google_project.main.project_id'
            
            # Auto-discover zone name if not specified
            if not zone_name_specified:
                # Use Python API to discover zone name at generation time
                discovered_zone_name = self.discover_dns_zone_name(root_domain, root_zone_project)
                root_zone_name_ref = f'"{discovered_zone_name}"'
                
                # Add comment about auto-discovery
                project_terraform += f'''
# DNS zone name auto-discovered: {discovered_zone_name}
# (discovered for domain: {root_domain})

'''
            else:
                # Use specified zone name
                root_zone_name_ref = f'"{zone_name_specified}"'
            
            # Auto-create root zone if requested
            if auto_create_root:
                project_terraform += f'''
# Root DNS Zone (auto-created)
resource "google_dns_managed_zone" "root" {{
  name        = {root_zone_name_ref}
  dns_name    = "{root_domain}."
  description = "Root DNS zone for {root_domain}"
  project     = {root_zone_project_ref}
  
  depends_on = [google_project_service.dns_googleapis_com]
}}

'''
                root_zone_reference = f'google_dns_managed_zone.root.name'
            else:
                # Reference existing root zone
                project_terraform += f'''
# Reference existing root DNS zone
data "google_dns_managed_zone" "root" {{
  name = {root_zone_name_ref}
{root_zone_data_project}
}}

'''
                root_zone_reference = f'data.google_dns_managed_zone.root.name'
            
            # Create NS delegation records in root zone
            project_terraform += f'''
# Automatic NS delegation in root zone
resource "google_dns_record_set" "subdomain_delegation" {{
  name         = "{subdomain}."
  managed_zone = {root_zone_reference}
  type         = "NS"
  ttl          = {delegation_ttl}
  project      = {root_zone_project_ref}
  
  rrdatas = google_dns_managed_zone.main.name_servers
  
  depends_on = [
    google_dns_managed_zone.main,
    {root_zone_reference.replace('.name', '')}
  ]
}}

'''
            
            # Output DNS information (only when DNS management is enabled)
            project_terraform += f'''
# DNS Zone Information
output "dns_info" {{
  description = "DNS configuration and delegation status"
  value = {{
    subdomain = "{subdomain}"
    subdomain_zone_name = google_dns_managed_zone.main_{self.get_validated_guid()}.name
    subdomain_nameservers = google_dns_managed_zone.main_{self.get_validated_guid()}.name_servers
    delegation_status = "Automatically configured in {dns_zone}"
    root_zone_project = local.project_id
  }}
}}

'''
        
        # Project outputs (always generated)
        project_terraform += f'''
# Project outputs
output "project_info" {{
  description = "GCP Project information"
  value = {{
    project_id = local.project_id
    project_name = google_project.main_{self.get_validated_guid()}.name
    project_number = google_project.main_{self.get_validated_guid()}.number
    service_account_email = google_service_account.{sa_name.replace('-', '_')}_{self.get_validated_guid()}.email
    service_account_key_path = local_file.project_sa_key_file_{self.get_validated_guid()}.filename
    {f'dns_zone = "{subdomain}"' if dns_management_enabled and project_domain else '# DNS management disabled'}
    dns_delegation_automated = {str(dns_management_enabled and bool(project_domain)).lower()}
  }}
}}

'''
        
        return project_terraform



    def get_available_zones_for_region(self, region):
        """Get available zones for a specific region with intelligent fallback."""
        # Skip zone discovery in no-credentials mode
        if self.converter.no_credentials:
            return [f"{region}-a"]  # Return a placeholder zone
        
        if not GOOGLE_CLOUD_AVAILABLE:
            return self._fallback_get_zones_for_region(region)
        
        try:
            # Initialize the zones client
            client = compute_v1.ZonesClient()
            request = compute_v1.ListZonesRequest(project=self._get_project_id())
            
            available_zones = []
            
            try:
                page_result = client.list(request=request)
                for zone in page_result:
                    # Check if zone belongs to this region
                    zone_region = zone.name.rsplit('-', 1)[0]
                    if zone_region == region and zone.status == 'UP':
                        available_zones.append(zone.name)
                        
                # Sort zones alphabetically for consistent selection
                available_zones.sort()
                return available_zones
                
            except Exception:
                # Fall back to known patterns if API fails
                return self._fallback_get_zones_for_region(region)
                
        except Exception:
            # Fall back to known patterns if client creation fails
            return self._fallback_get_zones_for_region(region)

    def _fallback_get_zones_for_region(self, region):
        """Fallback method using known GCP zone patterns."""
        # Known zone patterns for major GCP regions
        zone_patterns = {
            'us-central1': ['us-central1-a', 'us-central1-b', 'us-central1-c', 'us-central1-f'],
            'us-east1': ['us-east1-b', 'us-east1-c', 'us-east1-d'],  # Note: NO us-east1-a!
            'us-east4': ['us-east4-a', 'us-east4-b', 'us-east4-c'],
            'us-west1': ['us-west1-a', 'us-west1-b', 'us-west1-c'],
            'us-west2': ['us-west2-a', 'us-west2-b', 'us-west2-c'],
            'us-west3': ['us-west3-a', 'us-west3-b', 'us-west3-c'],
            'us-west4': ['us-west4-a', 'us-west4-b', 'us-west4-c'],
            'europe-west1': ['europe-west1-b', 'europe-west1-c', 'europe-west1-d'],
            'europe-west2': ['europe-west2-a', 'europe-west2-b', 'europe-west2-c'],
            'europe-west3': ['europe-west3-a', 'europe-west3-b', 'europe-west3-c'],
            'asia-east1': ['asia-east1-a', 'asia-east1-b', 'asia-east1-c'],
            'asia-southeast1': ['asia-southeast1-a', 'asia-southeast1-b', 'asia-southeast1-c'],
        }
        
        if region in zone_patterns:
            return zone_patterns[region]
        
        # Generic fallback: try common zone suffixes
        fallback_zones = []
        for suffix in ['a', 'b', 'c', 'd', 'f']:
            fallback_zones.append(f"{region}-{suffix}")
        
        return fallback_zones

    def get_best_zone_for_region(self, region, machine_type=None, instance_name=None):
        """Get the best available zone for a region, optionally checking machine type availability."""
        if instance_name:
            self.converter.print_instance_output(instance_name, 'gcp', f"Finding best zone in region '{region}'...")
        
        available_zones = self.get_available_zones_for_region(region)
        
        if not available_zones:
            raise ValueError(f"No zones found for region '{region}'. Please check region availability.")
        
        # Skip machine type availability checking in no-credentials mode
        if self.converter.no_credentials:
            best_zone = available_zones[0]
            if instance_name:
                self.converter.print_instance_output(instance_name, 'gcp', f"NO-CREDENTIALS MODE: Using zone '{best_zone}' for region '{region}'")
            return best_zone
        
        # If no machine type specified, return first available zone
        if not machine_type:
            best_zone = available_zones[0]
            if instance_name:
                self.converter.print_instance_output(instance_name, 'gcp', f"Selected zone '{best_zone}' for region '{region}'")
            return best_zone
        
        # Check machine type availability in zones
        if GOOGLE_CLOUD_AVAILABLE:
            try:
                client = compute_v1.MachineTypesClient()
                
                for zone in available_zones:
                    try:
                        mt_request = compute_v1.GetMachineTypeRequest(
                            project=self._get_project_id(),
                            zone=zone,
                            machine_type=machine_type
                        )
                        client.get(request=mt_request)
                        if instance_name:
                            self.converter.print_instance_output(instance_name, 'gcp', f"Selected zone '{zone}' for machine type '{machine_type}' in region '{region}'")
                        return zone
                    except google_exceptions.NotFound:
                        continue
                        
                # If no zone supports the machine type, return first zone with warning
                if instance_name:
                    self.converter.print_instance_output(instance_name, 'gcp', f"WARNING: Machine type '{machine_type}' may not be available in region '{region}'. Using zone '{available_zones[0]}'")
                return available_zones[0]
                
            except Exception:
                # Fall back to first zone if API calls fail
                if instance_name:
                    self.converter.print_instance_output(instance_name, 'gcp', f"WARNING: Could not verify machine type availability. Using zone '{available_zones[0]}'")
                return available_zones[0]
        else:
            # No API available, return first zone
            if instance_name:
                self.converter.print_instance_output(instance_name, 'gcp', f"Selected zone '{available_zones[0]}' for region '{region}' (API unavailable)")
            return available_zones[0]

    def generate_storage_bucket(self, bucket, yaml_data):
        """Generate GCP Cloud Storage bucket configuration."""
        bucket_name = bucket.get('name', 'my-bucket')
        region = self.converter.resolve_bucket_region(bucket, 'gcp')
        guid = self.converter.get_validated_guid(yaml_data)

        # Replace GUID placeholders
        final_bucket_name = self.converter.replace_guid_placeholders(bucket_name)
        clean_bucket_name, _ = self.converter.clean_name(final_bucket_name)
        
        # Bucket configuration
        public = bucket.get('public', False)
        versioning = bucket.get('versioning', False)
        encryption = bucket.get('encryption', True)
        tags = bucket.get('tags', {})

        terraform_config = f'''
# GCP Cloud Storage Bucket: {final_bucket_name}
resource "google_storage_bucket" "{clean_bucket_name}_{guid}" {{
  name     = "{final_bucket_name}"
  location = "{region}"

  # Public access configuration
  public_access_prevention = "{"inherited" if public else "enforced"}"
  
  # Encryption configuration
  encryption {{
    default_kms_key_name = null
  }}

  labels = {{
    name = "{final_bucket_name.replace('-', '_').replace('.', '_')}"
    managed_by = "yamlforge"
    guid = "{guid}"'''

        # Add custom labels (GCP tags are called labels)
        for key, value in tags.items():
            # GCP labels must be lowercase and use underscores
            clean_key = key.lower().replace('-', '_').replace(' ', '_')
            clean_value = value.lower().replace('-', '_').replace(' ', '_')
            terraform_config += f'''
    {clean_key} = "{clean_value}"'''

        terraform_config += '''
  }
}

'''

        # Versioning configuration
        if versioning:
            terraform_config += f'''
resource "google_storage_bucket" "{clean_bucket_name}_versioning_{guid}" {{
  name     = "{final_bucket_name}"
  location = "{region}"
  
  versioning {{
    enabled = true
  }}
  
  depends_on = [google_storage_bucket.{clean_bucket_name}_{guid}]
}}

'''

        # Public access configuration
        if public:
            terraform_config += f'''
resource "google_storage_bucket_iam_binding" "{clean_bucket_name}_public_{guid}" {{
  bucket = google_storage_bucket.{clean_bucket_name}_{guid}.name
  role   = "roles/storage.objectViewer"
  
  members = [
    "allUsers",
  ]
}}

'''

        return terraform_config

"""
GCP Provider Module

Contains GCP-specific implementations for image resolution, VM generation,
networking, firewall rules, project management, user access control, and other GCP cloud resources.
"""

import yaml
import os
import uuid
import json
from pathlib import Path
from datetime import datetime, timedelta
import re
import subprocess

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
        has_credentials = self.credentials and self.credentials.gcp_config

        if not has_credentials:
            print("Warning: GCP credentials not found. Image discovery will fail if GCP images are requested.")

        return {
            'project_id': has_credentials and self.credentials.gcp_config.get('project_id', ''),
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

    def find_latest_image_by_family(self, family, architecture="X86_64"):
        """Find the latest image by family."""
        cache_key = f"{family}_{architecture}"

        # Check cache first
        if self.is_cache_valid(family):
            return self.cache[cache_key]

        client = self.get_client()
        if client is None:
            return None

        try:
            # Get the latest image from the family
            request = compute_v1.GetFromFamilyImageRequest(
                project="rhel-cloud",  # Red Hat's project for RHEL images
                family=family
            )

            image = client.get_from_family(request=request)

            if image:
                # Cache the result
                self.cache[cache_key] = image.self_link
                import time
                self.cache_timestamps[cache_key] = time.time()
                return image.self_link

            return None

        except Exception as e:
            print(f"Warning: Failed to find GCP image for family '{family}': {e}")
            return None

    def is_cache_valid(self, family):
        """Check if cached result is still valid."""
        return family in self.cache_timestamps


class GCPProvider:
    """GCP-specific provider implementation."""

    def __init__(self, converter):
        """Initialize the instance."""
        self.converter = converter
        self._gcp_resolver = None
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
        # Load defaults file directly
        defaults_file = Path("defaults/gcp.yaml")
        if not defaults_file.exists():
            raise Exception(f"Required GCP defaults file not found: {defaults_file}")

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
        has_credentials = self.converter.credentials and self.converter.credentials.gcp_config

        # Get project configuration from credentials or environment
        project_id = ""
        billing_account_id = ""
        organization_id = ""
        folder_id = ""
        
        if has_credentials:
            gcp_creds = self.converter.credentials.gcp_config
            project_id = gcp_creds.get('project_id', '')
            billing_account_id = gcp_creds.get('billing_account_id', '')
            organization_id = gcp_creds.get('organization_id', '')
            folder_id = gcp_creds.get('folder_id', '')

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
            'admin_group': admin_group,
            'company_domain': company_domain,
            'root_zone_domain': root_zone_domain,
            'has_credentials': has_credentials
        }

    def get_gcp_resolver(self):
        """Get GCP image resolver, creating it only when needed."""
        if self._gcp_resolver is None:
            self._gcp_resolver = GCPImageResolver(self.converter.credentials)
        return self._gcp_resolver

    def get_gcp_machine_type(self, size_or_instance_type):
        """Get GCP machine type from size mapping or return direct instance type."""
        # If it looks like a direct GCP instance type, return it as-is
        if any(prefix in size_or_instance_type for prefix in ['n1-', 'n2-', 'e2-', 'c2-', 'a2-', 'm1-', 'm2-']):
            return size_or_instance_type
        
        # Check for advanced flavor mappings
        gcp_flavors = self.converter.flavors.get('gcp', {}).get('flavor_mappings', {})
        size_mapping = gcp_flavors.get(size_or_instance_type, {})

        if size_mapping:
            # Return the first (preferred) machine type for this size
            machine_type = list(size_mapping.keys())[0]
            return machine_type

        # Check direct machine types mapping
        machine_types = self.converter.flavors.get('gcp', {}).get('machine_types', {})
        if size_or_instance_type in machine_types:
            return size_or_instance_type

        # No mapping found for this size
        raise ValueError(f"No GCP machine type mapping found for size '{size_or_instance_type}'. "
                       f"Available sizes: {list(gcp_flavors.keys())}")

    def check_machine_type_availability(self, machine_type, region, zone=None):
        """Check if a GCP machine type is available in the specified region/zone."""
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
            project_id = os.environ.get('GOOGLE_PROJECT')
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
        # Known GPU machine type availability patterns
        gpu_machine_types = {
            'n1-standard-4-t4': ['us-east1', 'us-east4', 'us-west1', 'us-west2'],
            'n1-standard-8-t4': ['us-east1', 'us-east4', 'us-west1', 'us-west2'],
            'n1-standard-16-t4': ['us-east1', 'us-east4', 'us-west1', 'us-west2'],
            'n1-standard-4-p4': ['us-central1', 'us-east4'],
            'n1-standard-8-p4': ['us-central1', 'us-east4'],
            'n1-standard-16-p4': ['us-central1', 'us-east4'],
            'n1-standard-4-v100': ['us-west1'],
            'n1-standard-8-v100': ['us-west1'],
            'n1-standard-16-v100': ['us-west1'],
        }
        
        # Check if this is a GPU machine type
        if machine_type in gpu_machine_types:
            return region in gpu_machine_types[machine_type]
        
        # For non-GPU machine types, assume they're available in most regions
        # This is a conservative approach - in practice, most standard machine types are widely available
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
        gpu_machine_types = {
            'n1-standard-4-t4': ['us-east1', 'us-east4', 'us-west1', 'us-west2'],
            'n1-standard-8-t4': ['us-east1', 'us-east4', 'us-west1', 'us-west2'],
            'n1-standard-16-t4': ['us-east1', 'us-east4', 'us-west1', 'us-west2'],
            'n1-standard-4-p4': ['us-central1', 'us-east4'],
            'n1-standard-8-p4': ['us-central1', 'us-east4'],
            'n1-standard-16-p4': ['us-central1', 'us-east4'],
            'n1-standard-4-v100': ['us-west1'],
            'n1-standard-8-v100': ['us-west1'],
            'n1-standard-16-v100': ['us-west1'],
        }
        
        if machine_type in gpu_machine_types:
            return gpu_machine_types[machine_type]
        
        # For non-GPU types, return common regions
        return ['us-central1', 'us-east1', 'us-west1', 'us-east4', 'us-west2']

    def find_closest_available_region(self, requested_region, available_regions):
        """Find the closest available region to the requested region."""
        if not available_regions:
            return None
        
        # If the requested region is available, use it
        if requested_region in available_regions:
            return requested_region
        
        # Simple proximity mapping (can be enhanced with actual geographic data)
        region_proximity = {
            'us-central1': ['us-east1', 'us-west1', 'us-east4', 'us-west2'],
            'us-east1': ['us-east4', 'us-central1', 'us-west1'],
            'us-east4': ['us-east1', 'us-central1', 'us-west1'],
            'us-west1': ['us-west2', 'us-central1', 'us-east1'],
            'us-west2': ['us-west1', 'us-central1', 'us-east1'],
        }
        
        # Find the closest available region
        if requested_region in region_proximity:
            for close_region in region_proximity[requested_region]:
                if close_region in available_regions:
                    return close_region
        
        # If no close match found, return the first available region
        return available_regions[0]

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

    def generate_gcp_firewall_rules_legacy(self, sg_name, rules):
        """Generate GCP firewall rules (legacy method)."""
        clean_name = sg_name.replace("-", "_").replace(".", "_")
        firewall_config = ""

        for i, rule in enumerate(rules):
            rule_data = self.converter.generate_native_security_group_rule(rule, 'gcp')
            direction = "INGRESS" if rule_data['direction'] == 'ingress' else "EGRESS"

            rule_name = f"{clean_name}_rule_{i+1}"
            ports = [str(rule_data['from_port'])] if rule_data['from_port'] == rule_data['to_port'] else [f"{rule_data['from_port']}-{rule_data['to_port']}"]

            firewall_config += f'''
# GCP Firewall Rule: {sg_name} Rule {i+1}
resource "google_compute_firewall" "{rule_name}" {{
  name    = "{sg_name}-rule-{i+1}"
  network = google_compute_network.main_network.name

  allow {{
    protocol = "{rule_data['protocol']}"
    ports    = {ports}
  }}

  direction     = "{direction}"
  source_ranges = [{', '.join([f'"{cidr}"' for cidr in rule_data['cidr_blocks']])}]

  target_tags = ["{clean_name}"]
}}

'''

        return firewall_config

    def generate_gcp_vm(self, instance, index, clean_name, size, available_subnets=None, yaml_data=None):
        """Generate native GCP Compute Engine instance."""
        instance_name = instance.get("name", f"instance_{index}")
        image = instance.get("image", "RHEL9-latest")

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
            gcp_machine_type = self.get_gcp_machine_type(size)
            
            # Intelligently select best zone for the region and machine type
            gcp_zone = self.get_best_zone_for_region(gcp_region, gcp_machine_type, instance_name)
        
        # Get machine type (if not already retrieved for zone validation)
        if 'gcp_machine_type' not in locals():
            gcp_machine_type = self.get_gcp_machine_type(size)

        # Get image reference
        gcp_image = self.get_gcp_image_reference(image)

        # Get user data script
        user_data_script = instance.get('user_data_script') or instance.get('user_data')

        # Get firewall tags
        firewall_refs = self.converter.get_instance_gcp_firewall_refs(instance)
        
        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})

        vm_config = f'''
# GCP Compute Instance: {instance_name}
resource "google_compute_instance" "{clean_name}_{self.get_validated_guid()}" {{
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
    subnetwork = google_compute_subnetwork.main_subnet_{gcp_region.replace("-", "_").replace(".", "_")}_{self.get_validated_guid()}.id
    access_config {{
      nat_ip = google_compute_address.{clean_name}_ip_{self.get_validated_guid()}.address
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
resource "google_compute_address" "{clean_name}_ip_{self.get_validated_guid()}" {{
  name    = "{instance_name}-ip"
  region  = "{gcp_region}"
  project = local.project_id
  
  depends_on = [
    time_sleep.wait_for_compute_api_{self.get_validated_guid()}
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
resource "google_dns_record_set" "{clean_name}_dns_{self.get_validated_guid()}" {{
  count = length(google_dns_managed_zone.main_{self.get_validated_guid()}.name_servers) > 0 ? 1 : 0
  
  name         = "{instance_name}.{self.get_validated_guid()}.{project_domain}."
  managed_zone = google_dns_managed_zone.main_{self.get_validated_guid()}.name
  type         = "A"
  ttl          = 300
  
  rrdatas = [google_compute_address.{clean_name}_ip_{self.get_validated_guid()}.address]
  project = local.project_id
}}

# Internal DNS A Record for {instance_name} (private IP)
resource "google_dns_record_set" "{clean_name}_internal_dns_{self.get_validated_guid()}" {{
  count = length(google_dns_managed_zone.main_{self.get_validated_guid()}.name_servers) > 0 ? 1 : 0
  
  name         = "{instance_name}-internal.{self.get_validated_guid()}.{project_domain}."
  managed_zone = google_dns_managed_zone.main_{self.get_validated_guid()}.name
  type         = "A"
  ttl          = 300
  
  rrdatas = [google_compute_instance.{clean_name}_{self.get_validated_guid()}.network_interface[0].network_ip]
  project = local.project_id
}}
'''
        return vm_config

    def generate_gcp_firewall_rules(self, sg_name, rules, region):
        """Generate GCP firewall rules for specific region (equivalent to security groups)."""
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
  source_ranges = [{', '.join([f'"{cidr}"' for cidr in rule_data['cidr_blocks']])}]
  target_tags   = ["{sg_name}"]
}}
'''

        return firewall_config

    def generate_gcp_networking(self, deployment_name, deployment_config, region):
        """Generate GCP networking components with proper API dependencies."""
        network_config = deployment_config.get('network', {})
        network_name = network_config.get('name', f"{deployment_name}-network")
        cidr_block = network_config.get('cidr_block', '10.0.0.0/16')

        clean_network_name = self.converter.clean_name(network_name)
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
    
    def generate_vm_dns_outputs(self, yaml_data):
        """Generate output statements for all VM DNS records and FQDNs."""
        if not yaml_data:
            return "    # No VM instances configured"
        
        instances = yaml_data.get('instances', [])
        gcp_instances = []
        
        # Find all GCP instances
        for instance in instances:
            provider = instance.get('provider')
            
            # Resolve meta providers to actual providers
            if provider == 'cheapest':
                provider = self.converter.find_cheapest_provider(instance, suppress_output=True)
            elif provider == 'cheapest-gpu':
                provider = self.converter.find_cheapest_gpu_provider(instance, suppress_output=True)
            
            if provider == 'gcp':
                gcp_instances.append(instance)
        
        if not gcp_instances:
            return "    # No GCP instances configured"
        
        output_lines = []
        root_domain = self.get_root_zone_domain(yaml_data)
        guid = self.get_validated_guid()
        
        for instance in gcp_instances:
            instance_name = instance.get("name", "unknown")
            clean_name = self.converter.clean_name(instance_name)
            
            # Public FQDN (external IP)
            public_fqdn = f"{instance_name}.{guid}.{root_domain}"
            # Private FQDN (internal IP)
            private_fqdn = f"{instance_name}-internal.{guid}.{root_domain}"
            
            output_lines.append(f'''    "{instance_name}" = {{
      public_fqdn = "{public_fqdn}"
      private_fqdn = "{private_fqdn}"
      public_ip = google_compute_address.{clean_name}_ip_{guid}.address
      private_ip = google_compute_instance.{clean_name}_{guid}.network_interface[0].network_ip
      dns_records = [
        google_dns_record_set.{clean_name}_dns_{guid}[0].name,
        google_dns_record_set.{clean_name}_internal_dns_{guid}[0].name
      ]
    }}''')
        
        return '\n'.join(output_lines)

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
        
        # Generate project ID from workspace name and GUID - make them the same for consistency
        if not self.guid:
            self.get_validated_guid()
        
        # Use workspace name as project ID base, ensure it follows GCP project naming rules
        base_name = workspace_name.lower().replace('_', '-').replace(' ', '-')
        if not base_name.startswith('openenv-'):
            base_name = f'openenv-{self.guid}'
        project_id = base_name
        project_name = base_name  # Make project name and ID the same
        
        # Get configuration from loaded environment variables and defaults
        project_defaults = self.config['project_defaults']
        admin_group = self.config['admin_group']
        billing_account_id = self.config['billing_account_id']
        organization_id = self.config['organization_id']
        folder_id = self.config['folder_id']
        company_domain = self.config['company_domain']
        root_zone_domain = self.config['root_zone_domain']
        sa_name = project_defaults.get('project_service_account', 'yamlforge-automation')
        
        # 1. Project creation with billing (always create, no data source check)
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
# GCP Project (always create new project)
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
  
  depends_on = [google_project.main_{self.get_validated_guid()}]
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

    def format_gcp_labels(self, tags):
        """Format tags as GCP labels (lowercase, hyphens only)."""
        if not tags:
            return ""

        label_items = []
        for key, value in tags.items():
            # GCP label keys must be lowercase and use hyphens
            gcp_key = key.lower().replace('_', '-').replace(' ', '-')
            gcp_value = str(value).lower().replace('_', '-').replace(' ', '-')
            label_items.append(f'    {gcp_key} = "{gcp_value}"')

        return f'''
  labels = {{
{chr(10).join(label_items)}
  }}'''

    def get_available_zones_for_region(self, region):
        """Get available zones for a specific region with intelligent fallback."""
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
        instance_info = f" for '{instance_name}'" if instance_name else ""
        print(f"Finding best zone{instance_info} in region '{region}'...")
        
        available_zones = self.get_available_zones_for_region(region)
        
        if not available_zones:
            raise ValueError(f"No zones found for region '{region}'. Please check region availability.")
        
        # If no machine type specified, return first available zone
        if not machine_type:
            best_zone = available_zones[0]
            print(f"Selected zone '{best_zone}' for region '{region}'")
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
                        print(f"Selected zone '{zone}' for machine type '{machine_type}' in region '{region}'")
                        return zone
                    except google_exceptions.NotFound:
                        continue
                        
                # If no zone supports the machine type, return first zone with warning
                instance_info = f" for '{instance_name}'" if instance_name else ""
                print(f"WARNING: Machine type '{machine_type}' may not be available{instance_info} in region '{region}'. Using zone '{available_zones[0]}'")
                return available_zones[0]
                
            except Exception:
                # Fall back to first zone if API calls fail
                instance_info = f" for '{instance_name}'" if instance_name else ""
                print(f"WARNING: Could not verify machine type availability{instance_info}. Using zone '{available_zones[0]}'")
                return available_zones[0]
        else:
            # No API available, return first zone
            print(f"Selected zone '{available_zones[0]}' for region '{region}' (API unavailable)")
            return available_zones[0]
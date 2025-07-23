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

# GCP imports
try:
    from google.cloud import compute_v1  # pylint: disable=import-error
    from google.cloud import dns  # pylint: disable=import-error
    from google.auth import default as google_auth_default  # pylint: disable=import-error
    from google.auth.exceptions import DefaultCredentialsError  # pylint: disable=import-error
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

        # Check if credentials are available
        has_credentials = self.converter.credentials and self.converter.credentials.gcp_config

        # Get project configuration from credentials or environment
        project_id = ""
        billing_account_id = ""
        organization_id = ""
        
        if has_credentials:
            gcp_creds = self.converter.credentials.gcp_config
            project_id = gcp_creds.get('project_id', '')
            billing_account_id = gcp_creds.get('billing_account_id', '')
            organization_id = gcp_creds.get('organization_id', '')

        # Fall back to environment variables if not in credentials
        if not billing_account_id:
            billing_account_id = os.environ.get('GCP_BILLING_ACCOUNT_ID', 
                                              project_defaults.get('billing_account_id', ''))
        if not organization_id:
            organization_id = os.environ.get('GCP_ORGANIZATION_ID', 
                                           project_defaults.get('organization_id', ''))

        return {
            'default_apis': default_apis,
            'project_defaults': project_defaults,
            'dns_config': dns_config,
            'project_id': project_id,
            'billing_account_id': billing_account_id,
            'organization_id': organization_id,
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
            return list(size_mapping.keys())[0]

        # Check direct machine types mapping
        machine_types = self.converter.flavors.get('gcp', {}).get('machine_types', {})
        if size_or_instance_type in machine_types:
            return size_or_instance_type

        # No mapping found for this size
        raise ValueError(f"No GCP machine type mapping found for size '{size_or_instance_type}'. "
                       f"Available sizes: {list(gcp_flavors.keys())}")

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
  source_ranges = {rule_data['cidr_blocks']}

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
        gcp_zone = f"{gcp_region}-a"  # Default to first zone

        # Get machine type
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
      # Ephemeral public IP
    }}
  }}'''

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

  metadata_startup_script = <<-EOF
{user_data_script}
EOF'''

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
resource "google_compute_address" "{clean_name}_ip" {{
  name   = "{instance_name}-ip"
  region = "{gcp_region}"
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

  allow {{
    protocol = "{rule_data['protocol']}"
    ports    = ["{rule_data['from_port']}-{rule_data['to_port']}"]
  }}

  direction     = "{direction}"
  source_ranges = {rule_data['cidr_blocks']}
  target_tags   = ["{sg_name}"]
}}
'''

        return firewall_config

    def generate_gcp_networking(self, deployment_name, deployment_config, region):
        """Generate GCP networking resources for specific region."""
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
}}

# GCP Subnet: {network_name} subnet
resource "google_compute_subnetwork" "main_subnet_{clean_region}_{self.get_validated_guid()}" {{
  name          = "{network_name}-subnet"
  ip_cidr_range = "{cidr_block}"
  region        = "{region}"
  network       = google_compute_network.main_network_{clean_region}_{self.get_validated_guid()}.id
}}

# Default SSH access firewall rule
resource "google_compute_firewall" "main_ssh_{clean_region}_{self.get_validated_guid()}" {{
  name    = "{network_name}-ssh"
  network = google_compute_network.main_network_{clean_region}_{self.get_validated_guid()}.id

  allow {{
    protocol = "tcp"
    ports    = ["22"]
  }}

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["ssh-allowed"]
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
        workspace_name = cloud_workspace.get('name', 'yamlforge-workspace')
        
        # Generate project ID from workspace name and GUID
        if not self.guid:
            self.get_validated_guid()
        project_id = f"{workspace_name.lower().replace('_', '-')}-{self.guid}"
        
        # Get configuration from defaults
        project_defaults = self.config['project_defaults']
        admin_group = project_defaults.get('admin_group', 'gcp-admins@example.com')
        billing_account_id = self.config['billing_account_id']
        organization_id = self.config['organization_id']
        sa_name = project_defaults.get('project_service_account', 'yamlforge-automation')
        
        # 1. Project creation with billing
        project_terraform += f'''
# GCP Project
resource "google_project" "main_{self.get_validated_guid()}" {{
  name       = "{workspace_name}"
  project_id = "{project_id}"
  {f'org_id = "{organization_id}"' if organization_id and not organization_id.startswith('${') else '# org_id configured via environment'}
  {f'billing_account = "{billing_account_id}"' if billing_account_id and not billing_account_id.startswith('${') else '# billing_account configured via environment'}
  
  auto_create_network = false
}}

'''
        
        # 2. Enable default APIs
        default_apis = self.config['default_apis']
        for api in default_apis:
            clean_api = api.replace('.', '_').replace('-', '_')
            project_terraform += f'''
# Enable API: {api}
resource "google_project_service" "{clean_api}" {{
  project = google_project.main.project_id
  service = "{api}"
  
  disable_dependent_services = true
  disable_on_destroy = false
}}

'''
        
        # 3. Create service account for infrastructure management
        project_terraform += f'''
# Project Service Account
resource "google_service_account" "{sa_name.replace('-', '_')}_{self.get_validated_guid()}" {{
  account_id   = "{sa_name}"
  display_name = "{workspace_name} Service Account"
  description  = "Service account for {workspace_name} infrastructure management"
  project      = google_project.main_{self.get_validated_guid()}.project_id
}}

# Grant Owner role to project service account
resource "google_project_iam_member" "project_sa_owner" {{
  project = google_project.main.project_id
  role    = "roles/owner"
  member  = "serviceAccount:${{google_service_account.{sa_name.replace('-', '_')}.email}}"
}}

# Create service account key for project service account
resource "google_service_account_key" "project_sa_key" {{
  service_account_id = google_service_account.{sa_name.replace('-', '_')}.name
}}

# Store service account key locally
resource "local_file" "project_sa_key_file" {{
  content  = base64decode(google_service_account_key.project_sa_key.private_key)
  filename = "{project_defaults.get('service_account_key_path', '/tmp/yamlforge-keys')}/{project_id}-{sa_name}.json"
  
  provisioner "local-exec" {{
    command = "mkdir -p {project_defaults.get('service_account_key_path', '/tmp/yamlforge-keys')}"
  }}
}}

'''
        
        # 4. Admin group ownership
        project_terraform += f'''
# Grant Owner role to admin group
resource "google_project_iam_member" "admin_group_owner" {{
  project = google_project.main.project_id
  role    = "roles/owner"
  member  = "group:{admin_group}"
}}

'''
        
        # 5. User management logic
        # Get user management config (separate from DNS management)
        yaml_user_mgmt = yaml_data.get('user_management', {})
        default_user_mgmt = self.config.get('user_management', {})
        merged_user_mgmt = {**default_user_mgmt, **yaml_user_mgmt}
        
        # Check if domain-based ownership is enabled
        enable_domain_ownership = merged_user_mgmt.get('enable_domain_ownership', True)
        company_domain = merged_user_mgmt.get('company_domain', '')
        
        for user in users:
            email = user.get('email', '')
            roles = user.get('roles', ['roles/viewer'])
            display_name = user.get('display_name', email.split('@')[0])
            
            if not email:
                continue
                
            # Check if user email domain matches company domain for automatic ownership
            if enable_domain_ownership and company_domain:
                user_domain = email.split('@')[1] if '@' in email else ''
                if user_domain == company_domain:
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
resource "google_project_iam_member" "{binding_name}" {{
  project = google_project.main.project_id
  role    = "{role}"
  member  = "user:{email}"
}}

'''
        
        # 6. DNS Zone Management with Automatic Delegation (Optional)
        # Get DNS config for infrastructure management (separate from user management)
        yaml_dns_config = yaml_data.get('dns_config', {})
        default_dns_config = self.config['dns_config']
        merged_dns_config = {**default_dns_config, **yaml_dns_config}
        
        # Check if DNS management is enabled and domain is specified
        dns_management_enabled = merged_dns_config.get('root_zone_management', False)
        default_root_zone = default_dns_config.get('root_zone', {})
        yaml_root_zone = yaml_dns_config.get('root_zone', {})
        merged_root_zone = {**default_root_zone, **yaml_root_zone}
        project_domain = merged_root_zone.get('domain', '')
        
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
  project     = google_project.main_{self.get_validated_guid()}.project_id
  
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
    subdomain_zone_name = google_dns_managed_zone.main.name
    subdomain_nameservers = google_dns_managed_zone.main.name_servers
    delegation_status = "Automatically configured in {dns_zone}"
    root_zone_project = {root_zone_project_ref}
  }}
}}

'''
        
        # Project outputs (always generated)
        project_terraform += f'''
# Project outputs
output "project_info" {{
  description = "GCP Project information"
  value = {{
    project_id = google_project.main.project_id
    project_name = google_project.main.name
    project_number = google_project.main.number
    service_account_email = google_service_account.{sa_name.replace('-', '_')}.email
    service_account_key_path = local_file.project_sa_key_file.filename
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
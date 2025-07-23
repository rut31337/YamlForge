"""
Oracle Cloud Infrastructure (OCI) Provider Module

Contains OCI-specific implementations for image resolution, VM generation,
networking, security groups, and other OCI cloud resources.
"""

import yaml
from pathlib import Path

# OCI imports - optional, fallback if not available
try:
    import oci  # pylint: disable=import-error
    OCI_SDK_AVAILABLE = True
except ImportError:
    OCI_SDK_AVAILABLE = False
    print("Warning: oci-python-sdk not installed. OCI dynamic image discovery disabled.")


class OCIImageResolver:
    """Resolves Oracle Cloud Infrastructure images using the OCI API."""

    def __init__(self, credentials_manager=None):
        """Initialize the instance."""
        self.credentials = credentials_manager
        self.config = self.load_config()
        self.client = None
        self.cache = {}
        self.cache_timestamps = {}

    def load_config(self):
        """Load OCI configuration from credentials system."""
        # Check if credentials are available for dynamic discovery
        has_credentials = self.credentials and self.credentials.oci_config

        if not has_credentials:
            print("Warning: OCI credentials not found. Image discovery will fail if OCI images are requested.")

        return {
            'has_credentials': has_credentials
        }

    def get_client(self):
        """Initialize and return OCI Compute client."""
        if not OCI_SDK_AVAILABLE:
            return None

        try:
            if self.credentials and self.credentials.oci_config:
                oci_config = self.credentials.oci_config
                config = {
                    'user': oci_config.get('user_ocid'),
                    'key_file': oci_config.get('key_file'),
                    'fingerprint': oci_config.get('fingerprint'),
                    'tenancy': oci_config.get('tenancy_ocid'),
                    'region': oci_config.get('region')
                }
                client = oci.core.ComputeClient(config)
                return client
            return None

        except Exception as e:
            print(f"Warning: Failed to create OCI client: {e}")
            return None

    def resolve_oci_image(self, image_pattern, compartment_id, region):
        """Resolve OCI image using pattern matching."""
        client = self.get_client()
        if not client:
            return None

        try:
            # List images in the compartment
            response = client.list_images(
                compartment_id=compartment_id,
                operating_system="Oracle Linux",  # TODO: Make this configurable from image mappings
                lifecycle_state="AVAILABLE"
            )

            # Filter images by pattern
            matching_images = []
            for image in response.data:
                if image_pattern.lower() in image.display_name.lower():
                    matching_images.append(image)

            if matching_images:
                # Sort by creation time and return the latest
                latest_image = sorted(matching_images, key=lambda x: x.time_created, reverse=True)[0]
                return latest_image.id

        except Exception as e:
            print(f"Warning: Failed to resolve OCI image: {e}")

        return None


class OCIProvider:
    """Oracle Cloud Infrastructure-specific provider implementation."""

    def __init__(self, converter):
        """Initialize the instance."""
        self.converter = converter
        self._oci_resolver = None

    def get_oci_resolver(self):
        """Get OCI image resolver, creating it only when needed."""
        if self._oci_resolver is None:
            self._oci_resolver = OCIImageResolver(self.converter.credentials)
        return self._oci_resolver

    def get_oci_shape(self, size_or_instance_type):
        """Get OCI shape from size mapping or return direct instance type."""
        # If it looks like a direct OCI shape, return it as-is
        if any(prefix in size_or_instance_type for prefix in ['VM.Standard', 'VM.DenseIO', 'BM.Standard']):
            return size_or_instance_type
        
        # Check for advanced flavor mappings
        oci_flavors = self.converter.flavors.get('oci', {}).get('flavor_mappings', {})
        size_mapping = oci_flavors.get(size_or_instance_type, {})

        if size_mapping:
            # Return the first (preferred) shape for this size
            return list(size_mapping.keys())[0]

        # Check direct machine type mapping
        machine_types = self.converter.flavors.get('oci', {}).get('machine_types', {})
        if size_or_instance_type in machine_types:
            return size_or_instance_type

        # No mapping found for this size
        raise ValueError(f"No OCI shape mapping found for size '{size_or_instance_type}'. "
                       f"Available sizes: {list(oci_flavors.keys())}")

    def get_oci_image_reference(self, image_name):
        """Get OCI image reference from image mapping or direct reference."""
        
        # Use the image resolver for dynamic discovery
        if hasattr(self, 'image_resolver') and self.image_resolver:
            resolved_image = self.image_resolver.resolve_oci_image(image_name)
            if resolved_image:
                return resolved_image
        
        # Check the centralized image mappings
        images = self.converter.images.get(image_name, {})
        oci_image = images.get('oci', {})
        
        if isinstance(oci_image, dict):
            # Return the image name from mapping
            return oci_image.get('image_name', oci_image.get('image_ocid', image_name))
        elif isinstance(oci_image, str):
            # Direct image name mapping
            return oci_image
        
        # Default fallback
        return "Oracle-Linux-9.0-2023.05.31-0"

    def get_oci_operating_system(self, image_name):
        """Get OCI operating system from image mapping."""
        # Check the centralized image mappings
        images = self.converter.images.get(image_name, {})
        oci_image = images.get('oci', {})
        
        if isinstance(oci_image, dict):
            return oci_image.get('operating_system', 'Oracle Linux')
        
        # Default fallback for Oracle Linux
        return 'Oracle Linux'

    def generate_oci_vm(self, instance, index, clean_name, size, available_subnets=None, yaml_data=None):
        """Generate native OCI Compute instance."""
        instance_name = instance.get("name", f"instance_{index}")
        image = instance.get("image", "RHEL9-latest")

        # Resolve region and availability domain
        oci_region = self.converter.resolve_instance_region(instance, "oci")
        availability_domain = f"{oci_region}-AD-1"  # Default to first AD

        # Get shape
        oci_shape = self.get_oci_shape(size)

        # Get image reference
        oci_image = self.get_oci_image_reference(image)
        
        # Get operating system from mapping
        oci_operating_system = self.get_oci_operating_system(image)

        # Get user data script
        user_data_script = instance.get('user_data_script') or instance.get('user_data')

        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})

        # Get OCI NSG references with regional awareness
        oci_nsg_refs = []
        sg_names = instance.get('security_groups', [])
        for sg_name in sg_names:
            clean_sg = sg_name.replace("-", "_").replace(".", "_")
            clean_region = oci_region.replace("-", "_").replace(".", "_")
            oci_nsg_refs.append(f"oci_core_network_security_group.{clean_sg}_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id")

        oci_nsg_refs_str = "[" + ", ".join(oci_nsg_refs) + "]" if oci_nsg_refs else "[]"

        vm_config = f'''
# OCI Compute Instance: {instance_name}
resource "oci_core_instance" "{clean_name}_{self.converter.get_validated_guid(yaml_data)}" {{
  availability_domain = data.oci_identity_availability_domains.default.availability_domains[0].name
  compartment_id      = var.oci_compartment_id
  shape              = "{oci_shape}"
  
  create_vnic_details {{
    subnet_id        = oci_core_subnet.main_subnet_{oci_region.replace("-", "_").replace(".", "_")}_{self.converter.get_validated_guid(yaml_data)}.id
    display_name     = "{instance_name}-vnic"
    assign_public_ip = true
    nsg_ids          = {oci_nsg_refs_str}
  }}

  source_details {{
    source_type = "image"
    source_id   = "{oci_image}"
  }}

  display_name = "{instance_name}"

  # Shape configuration for flexible shapes
  shape_config {{
    ocpus         = 1
    memory_in_gbs = 8
  }}

  # Network interface
  create_vnic_details {{
    subnet_id        = oci_core_subnet.main_subnet.id
    display_name     = "{instance_name}-vnic"
    assign_public_ip = true
  }}

  # Boot volume
  source_details {{
    source_type = "image"
    source_id   = data.oci_core_images.{clean_name}_image.images[0].id
    boot_volume_size_in_gbs = 50
  }}'''

        # Add SSH key configuration if available
        if ssh_key_config and ssh_key_config.get('public_key'):
            vm_config += f'''

  # SSH key metadata
  metadata = {{
    ssh_authorized_keys = "{ssh_key_config['public_key']}"
  }}'''

        # Add user data if provided
        if user_data_script:
            vm_config += f'''

  # User data script
  extended_metadata = {{
    user_data = base64encode(<<-EOF
{user_data_script}
EOF
    )
  }}'''

        vm_config += '''

  # Tags
  freeform_tags = {
    "Environment" = "agnosticd"
    "ManagedBy"   = "yamlforge"
  }
}

'''

        # Add image data source
        vm_config += f'''# OCI Image Data Source for {instance_name}
data "oci_core_images" "{clean_name}_image" {{
  compartment_id           = var.oci_compartment_id
  display_name             = "{oci_image}"
  operating_system         = "{oci_operating_system}"
  operating_system_version = "9"
  shape                    = "{oci_shape}"
  state                    = "AVAILABLE"
}}

'''

        return vm_config

    def generate_oci_networking(self, deployment_name, deployment_config, region, yaml_data=None):
        """Generate OCI networking resources for specific region."""
        network_config = deployment_config.get('network', {})
        network_name = network_config.get('name', f"{deployment_name}-vcn")
        cidr_block = network_config.get('cidr_block', '10.0.0.0/16')

        clean_network_name = self.converter.clean_name(network_name)
        clean_region = region.replace("-", "_").replace(".", "_")

        return f'''
# OCI VCN: {network_name} (Region: {region})
resource "oci_core_vcn" "main_vcn_{clean_region}_{self.converter.get_validated_guid(yaml_data)}" {{
  cidr_block     = "{cidr_block}"
  compartment_id = var.oci_compartment_id
  display_name   = "{network_name}-{region}"
  
  freeform_tags = {{
    "Environment" = "agnosticd"
    "ManagedBy" = "yamlforge"
  }}
}}

# OCI Internet Gateway
resource "oci_core_internet_gateway" "main_igw_{clean_region}_{self.converter.get_validated_guid(yaml_data)}" {{
  compartment_id = var.oci_compartment_id
  vcn_id         = oci_core_vcn.main_vcn_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
  display_name   = "{network_name}-igw-{region}"
  enabled        = true
  
  freeform_tags = {{
    "Environment" = "agnosticd"
    "ManagedBy" = "yamlforge"
  }}
}}

# OCI Route Table
resource "oci_core_route_table" "main_rt_{clean_region}_{self.converter.get_validated_guid(yaml_data)}" {{
  compartment_id = var.oci_compartment_id
  vcn_id         = oci_core_vcn.main_vcn_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
  display_name   = "{network_name}-rt-{region}"
  
  route_rules {{
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.main_igw_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
  }}
  
  freeform_tags = {{
    "Environment" = "agnosticd"
    "ManagedBy" = "yamlforge"
  }}
}}

# OCI Security List
resource "oci_core_security_list" "main_sl_{clean_region}_{self.converter.get_validated_guid(yaml_data)}" {{
  compartment_id = var.oci_compartment_id
  vcn_id         = oci_core_vcn.main_vcn_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
  display_name   = "{network_name}-sl-{region}"
  
  egress_security_rules {{
    destination = "0.0.0.0/0"
    protocol    = "all"
  }}
  
  ingress_security_rules {{
    protocol = "6"  # TCP
    source   = "0.0.0.0/0"
    
    tcp_options {{
      min = 22
      max = 22
    }}
  }}
  
  ingress_security_rules {{
    protocol = "6"  # TCP
    source   = "0.0.0.0/0"
    
    tcp_options {{
      min = 80
      max = 80
    }}
  }}
  
  ingress_security_rules {{
    protocol = "6"  # TCP
    source   = "0.0.0.0/0"
    
    tcp_options {{
      min = 443
      max = 443
    }}
  }}
  
  freeform_tags = {{
    "Environment" = "agnosticd"
    "ManagedBy" = "yamlforge"
  }}
}}

# OCI Subnet
resource "oci_core_subnet" "main_subnet_{clean_region}_{self.converter.get_validated_guid(yaml_data)}" {{
  cidr_block        = "{cidr_block}"
  compartment_id    = var.oci_compartment_id
  vcn_id            = oci_core_vcn.main_vcn_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
  display_name      = "{network_name}-subnet-{region}"
  route_table_id    = oci_core_route_table.main_rt_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
  security_list_ids = [oci_core_security_list.main_sl_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id]
  
  freeform_tags = {{
    "Environment" = "agnosticd"
    "ManagedBy" = "yamlforge"
  }}
}}
'''

    def generate_oci_security_group(self, sg_name, rules, region, yaml_data=None):
        """Generate OCI network security group with rules for specific region."""
        clean_name = sg_name.replace("-", "_").replace(".", "_")
        clean_region = region.replace("-", "_").replace(".", "_")
        regional_sg_name = f"{clean_name}_{clean_region}"

        security_group_config = f'''
# OCI Network Security Group: {sg_name} (Region: {region})
resource "oci_core_network_security_group" "{regional_sg_name}_{self.converter.get_validated_guid(yaml_data)}" {{
  compartment_id = var.oci_compartment_id
  vcn_id         = oci_core_vcn.main_vcn_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
  display_name   = "{sg_name}-{region}"
  
  freeform_tags = {{
    "Environment" = "agnosticd"
    "ManagedBy" = "yamlforge"
  }}
}}

'''

        # Generate security rules
        for i, rule in enumerate(rules):
            rule_data = self.converter.generate_native_security_group_rule(rule, 'oci')
            direction = "INGRESS" if rule_data['direction'] == 'ingress' else "EGRESS"
            
            security_group_config += f'''
# OCI NSG Rule: {sg_name} - Rule {i+1}
resource "oci_core_network_security_group_security_rule" "{regional_sg_name}_rule_{i+1}" {{
  network_security_group_id = oci_core_network_security_group.{regional_sg_name}.id
  direction                 = "{direction}"
  protocol                  = "{rule_data['protocol_number']}"

  source = "{rule_data['source']}"
  
  tcp_options {{
    destination_port_range {{
      min = {rule_data['port_min']}
      max = {rule_data['port_max']}
    }}
  }}
}}
'''

        return security_group_config

    def format_oci_tags(self, tags):
        """Format tags for OCI (freeform tags)."""
        if not tags:
            return ""

        tag_items = []
        for key, value in tags.items():
            tag_items.append(f'    "{key}" = "{value}"')

        return f'''
  freeform_tags = {{
{chr(10).join(tag_items)}
  }}''' 
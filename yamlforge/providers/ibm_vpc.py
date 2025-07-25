"""
IBM VPC Provider Module

Contains IBM VPC-specific implementations for VM generation, networking,
and security groups.
"""

import os


class IBMVPCProvider:
    """IBM VPC-specific provider implementation."""

    def __init__(self, converter):
        """Initialize the instance."""
        self.converter = converter
        self.config = self.load_config()

    def load_config(self):
        """Load IBM VPC configuration from environment variables."""
        # Get IBM VPC resource group configuration from environment variables
        use_existing_resource_group = False
        existing_resource_group_name = ""
        
        use_existing_rg_str = os.environ.get('IBMCLOUD_VPC_USE_EXISTING_RESOURCE_GROUP', '').lower()
        use_existing_resource_group = use_existing_rg_str in ['true', '1', 'yes']
        
        existing_resource_group_name = os.environ.get('IBMCLOUD_VPC_RESOURCE_GROUP_NAME', '')

        return {
            'use_existing_resource_group': use_existing_resource_group,
            'existing_resource_group_name': existing_resource_group_name
        }

    def get_ibm_instance_profile(self, size_or_instance_type):
        """Get IBM instance profile from size mapping or return direct instance type."""
        # If it looks like a direct IBM instance profile, return it as-is
        if any(prefix in size_or_instance_type for prefix in ['bx2-', 'cx2-', 'mx2-', 'gx2-', 'gx3-', 'vx2d-']):
            return size_or_instance_type
        
        # Check for advanced flavor mappings
        ibm_flavors = self.converter.flavors.get('ibm_vpc', {}).get('flavor_mappings', {})
        size_mapping = ibm_flavors.get(size_or_instance_type, {})

        if size_mapping:
            # Return the first (preferred) instance profile for this size
            instance_profile = list(size_mapping.keys())[0]
            return instance_profile

        # No fallbacks - all mappings should be in mappings/flavors/ibm_vpc.yaml
        available_sizes = list(ibm_flavors.keys()) if ibm_flavors else []
        raise ValueError(f"No IBM VPC instance profile mapping found for size '{size_or_instance_type}'. "
                       f"Available sizes: {available_sizes}. "
                       f"Please add mapping to mappings/flavors/ibm_vpc.yaml under 'flavor_mappings: {size_or_instance_type}'")

    def generate_ibm_security_group(self, sg_name, rules, region, yaml_data=None):
        """Generate IBM security group with rules for specific region."""
        # Replace {guid} placeholder in security group name
        sg_name = self.converter.replace_guid_placeholders(sg_name)
        clean_name = sg_name.replace("-", "_").replace(".", "_")
        clean_region = region.replace("-", "_").replace(".", "_")
        regional_sg_name = f"{clean_name}_{clean_region}"


        security_group_config = f'''
# IBM Cloud VPC Security Group: {sg_name} (Region: {region})
resource "ibm_is_security_group" "{regional_sg_name}_{self.converter.get_validated_guid(yaml_data)}" {{
  name = "{sg_name}-{region}"
  vpc  = ibm_is_vpc.main_vpc_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
  
  tags = [
    "Environment:agnosticd",
    "ManagedBy:yamlforge"
  ]
}}

'''

        # Generate security group rules
        for i, rule in enumerate(rules):
            rule_data = self.converter.generate_native_security_group_rule(rule, 'ibm')
            direction = rule_data['direction']  # 'ingress' or 'egress'

            rule_config = f'''
# IBM Security Group Rule: {sg_name} Rule {i+1} (Region: {region})
resource "ibm_is_security_group_rule" "{regional_sg_name}_rule_{i+1}" {{
  group     = ibm_is_security_group.{regional_sg_name}.id
  direction = "{direction}"
  remote    = "{rule_data['source_cidr_blocks'][0] if rule_data['source_cidr_blocks'] else '0.0.0.0/0'}"

  tcp {{
    port_min = {rule_data['from_port']}
    port_max = {rule_data['to_port']}
  }}
}}
'''
            security_group_config += rule_config

        return security_group_config

    def generate_ibm_vpc_vm(self, instance, index, clean_name, size, yaml_data=None):
        """Generate IBM VPC virtual server instance."""
        instance_name = instance.get("name", f"instance_{index}")
        # Replace {guid} placeholder in instance name
        instance_name = self.converter.replace_guid_placeholders(instance_name)
        image = instance.get("image", "RHEL9-latest")
        
        # Resolve region first
        ibm_region = self.converter.resolve_instance_region(instance, "ibm_vpc")
        
        # Check if user specified a zone (only valid with region-based configuration)
        user_specified_zone = instance.get('zone')
        has_region = 'region' in instance
        
        if user_specified_zone and has_region:
            # User specified both region and zone - validate the zone belongs to the region
            expected_region = user_specified_zone.rsplit('-', 1)[0]  # Remove last part (e.g., us-south-1 -> us-south)
            
            if expected_region != ibm_region:
                raise ValueError(f"Instance '{instance_name}': Specified zone '{user_specified_zone}' does not belong to region '{ibm_region}'. "
                               f"Zone region: '{expected_region}', Instance region: '{ibm_region}'")
            
            print(f"Using user-specified zone '{user_specified_zone}' for instance '{instance_name}' in region '{ibm_region}'")
            ibm_zone = user_specified_zone
            
        elif user_specified_zone and not has_region:
            raise ValueError(f"Instance '{instance_name}': Zone '{user_specified_zone}' can only be specified when using 'region' (not 'location'). "
                           f"Either remove 'zone' or change 'location' to 'region'.")
        else:
            # Let Terraform automatically select the best available zone
            ibm_zone = f"{ibm_region}-1"  # IBM VPC requires explicit zone, use first available
        
        # Resolve image using centralized mappings
        ibm_image_pattern = self.get_ibm_vpc_image(image)
        
        # Show resolved image in standardized format
        print(f"Dynamic image search for {instance_name} on ibm_vpc for {image} in {ibm_region} results in {ibm_image_pattern}")

        # Get instance profile
        ibm_profile = self.get_ibm_instance_profile(size)

        # Get user data script
        user_data_script = instance.get('user_data_script') or instance.get('user_data')
        
        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})

        # Generate SSH key resource if SSH key is provided
        ssh_key_resources = ""
        key_name_ref = "null"
        
        if ssh_key_config and ssh_key_config.get('public_key'):
            ssh_key_name = f"{clean_name}_ssh_key_{self.converter.get_validated_guid(yaml_data)}"
            ssh_key_resources = f'''
# IBM Cloud SSH Key for {instance_name}
resource "ibm_is_ssh_key" "{ssh_key_name}" {{
  name       = "{instance_name}-key"
  public_key = "{ssh_key_config['public_key']}"
  type       = "rsa"
}}

'''
            key_name_ref = f"ibm_is_ssh_key.{ssh_key_name}.id"

        # Get IBM security group references with regional awareness
        ibm_sg_refs = []
        sg_names = instance.get('security_groups', [])
        for sg_name in sg_names:
            clean_sg = sg_name.replace("-", "_").replace(".", "_")
            clean_region = ibm_region.replace("-", "_").replace(".", "_")
            ibm_sg_refs.append(f"ibm_is_security_group.{clean_sg}_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id")

        ibm_sg_refs_str = "[" + ", ".join(ibm_sg_refs) + "]" if ibm_sg_refs else "[]"

        # Generate the VPC instance with image data source
        image_data_source = f'''
# IBM Cloud VPC Image Data Source for {instance_name}
data "ibm_is_image" "{clean_name}_image_{self.converter.get_validated_guid(yaml_data)}" {{
  name = "{ibm_image_pattern}"
}}

'''

        vm_config = ssh_key_resources + image_data_source + f'''
# IBM Cloud VPC Instance: {instance_name}
resource "ibm_is_instance" "{clean_name}_{self.converter.get_validated_guid(yaml_data)}" {{
  name    = "{instance_name}"
  image   = data.ibm_is_image.{clean_name}_image_{self.converter.get_validated_guid(yaml_data)}.id
  profile = "{ibm_profile}"
  
  vpc     = ibm_is_vpc.main_vpc_{ibm_region.replace("-", "_").replace(".", "_")}_{self.converter.get_validated_guid(yaml_data)}.id
  zone    = "{ibm_zone}"
  keys    = [{key_name_ref}]

  primary_network_interface {{
    subnet          = ibm_is_subnet.main_subnet_{ibm_region.replace("-", "_").replace(".", "_")}_{self.converter.get_validated_guid(yaml_data)}.id
    security_groups = {ibm_sg_refs_str}
  }}

  # Create and attach floating IP
  resource_group = local.resource_group_id_{ibm_region.replace("-", "_").replace(".", "_")}_{self.converter.get_validated_guid(yaml_data)}
}}

# IBM Cloud Floating IP for {instance_name}
resource "ibm_is_floating_ip" "{clean_name}_fip_{self.converter.get_validated_guid(yaml_data)}" {{
  name   = "{instance_name}-fip"
  target = ibm_is_instance.{clean_name}_{self.converter.get_validated_guid(yaml_data)}.primary_network_interface[0].id
  zone   = "{ibm_zone}"
  
  resource_group = data.ibm_resource_group.default.id
}}
'''
        return vm_config

    def generate_ibm_vpc_networking(self, deployment_name, deployment_config, region, yaml_data=None):
        """Generate IBM VPC networking resources for specific region."""
        network_config = deployment_config.get('network', {})
        network_name = network_config.get('name', f"{deployment_name}-vpc")
        cidr_block = network_config.get('cidr_block', '10.0.0.0/16')

        clean_region = region.replace("-", "_").replace(".", "_")

        # Get IBM VPC configuration from YAML (override environment/defaults)
        yaml_ibm_config = yaml_data.get('yamlforge', {}).get('ibm_vpc', {}) if yaml_data else {}
        
        # Get configuration with YAML overrides (exactly like Azure)
        use_existing_resource_group = yaml_ibm_config.get('use_existing_resource_group', self.config['use_existing_resource_group'])
        existing_resource_group_name = yaml_ibm_config.get('existing_resource_group_name', self.config['existing_resource_group_name'])

        guid = self.converter.get_validated_guid(yaml_data)
        
        if use_existing_resource_group and existing_resource_group_name:
            # Use existing resource group (like Azure)
            networking_config = f'''
# Using existing IBM Cloud Resource Group: {existing_resource_group_name}
data "ibm_resource_group" "main_{clean_region}_{guid}" {{
  name = "{existing_resource_group_name}"
}}

# Local value to reference resource group
locals {{
  resource_group_id_{clean_region}_{guid} = data.ibm_resource_group.main_{clean_region}_{guid}.id
  resource_group_name_{clean_region}_{guid} = data.ibm_resource_group.main_{clean_region}_{guid}.name
}}
'''
        else:
            # Create new resource group (default behavior)
            networking_config = f'''
# IBM Cloud Resource Group: {network_name} (Region: {region})
resource "ibm_resource_group" "main_{clean_region}_{guid}" {{
  name = "{network_name}-{region}"
}}

# Local value to reference resource group
locals {{
  resource_group_id_{clean_region}_{guid} = ibm_resource_group.main_{clean_region}_{guid}.id
  resource_group_name_{clean_region}_{guid} = ibm_resource_group.main_{clean_region}_{guid}.name
}}
'''

        networking_config += f'''
# IBM Cloud VPC: {network_name} (Region: {region})
resource "ibm_is_vpc" "main_vpc_{clean_region}_{guid}" {{
  name = "{network_name}-{region}"
  
  tags = [
    "Environment:agnosticd",
    "ManagedBy:yamlforge"
  ]
}}

# IBM Cloud Subnet: {network_name} subnet
resource "ibm_is_subnet" "main_subnet_{clean_region}_{guid}" {{
  name                     = "{network_name}-subnet-{region}"
  vpc                      = ibm_is_vpc.main_vpc_{clean_region}_{guid}.id
  zone                     = "{region}-1"
  total_ipv4_address_count = 256
  
  tags = [
    "Environment:agnosticd",
    "ManagedBy:yamlforge"
  ]
}}

# IBM Cloud SSH Key (Global)
resource "ibm_is_ssh_key" "main_key_{clean_region}_{guid}" {{
  name       = "{network_name}-key-{region}"
  public_key = var.ssh_public_key
  type       = "rsa"
  
  tags = [
    "Environment:agnosticd",
    "ManagedBy:yamlforge"
  ]
}}
'''
        
        return networking_config



    def get_ibm_vpc_image(self, image):
        """Get IBM VPC image name pattern from centralized mappings."""
        # Use centralized image mappings (images are loaded directly, not under 'images' key)
        image_config = self.converter.images.get(image, {})
        ibm_vpc_config = image_config.get('ibm_vpc', {})
        
        if ibm_vpc_config and 'name_pattern' in ibm_vpc_config:
            return ibm_vpc_config['name_pattern']
        
        # No fallbacks - all mappings should be in mappings/images.yaml
        raise ValueError(f"No IBM VPC image mapping found for '{image}'. "
                       f"Please add mapping to mappings/images.yaml under '{image}: ibm_vpc: name_pattern'")
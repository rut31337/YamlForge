"""
IBM VPC Provider Module

Contains IBM VPC-specific implementations for VM generation, networking,
and security groups.
"""


class IBMVPCProvider:
    """IBM VPC-specific provider implementation."""

    def __init__(self, converter):
        """Initialize the instance."""
        self.converter = converter

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
            return list(size_mapping.keys())[0]

        # Fallback defaults
        size_defaults = {
            'micro': 'bx2-2x8',
            'small': 'bx2-4x16',
            'medium': 'bx2-8x32',
            'large': 'bx2-16x64',
            'xlarge': 'bx2-32x128'
        }

        if size_or_instance_type in size_defaults:
            return size_defaults[size_or_instance_type]

        # No mapping found for this size
        raise ValueError(f"No IBM instance profile mapping found for size '{size_or_instance_type}'. "
                       f"Available sizes: {list(ibm_flavors.keys()) or list(size_defaults.keys())}")

    def generate_ibm_security_group(self, sg_name, rules, region):
        """Generate IBM security group with rules for specific region."""
        clean_name = sg_name.replace("-", "_").replace(".", "_")
        clean_region = region.replace("-", "_").replace(".", "_")
        regional_sg_name = f"{clean_name}_{clean_region}"
        regional_vpc_ref = f"ibm_is_vpc.main_vpc_{clean_region}.id"

        sg_config = f'''
# IBM Security Group: {sg_name} (Region: {region})
resource "ibm_is_security_group" "{regional_sg_name}" {{
  name = "{sg_name}-{region}"
  vpc  = {regional_vpc_ref}
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
  remote    = "{rule_data['cidr_blocks'][0] if rule_data['cidr_blocks'] else '0.0.0.0/0'}"

  tcp {{
    port_min = {rule_data['from_port']}
    port_max = {rule_data['to_port']}
  }}
}}
'''
            sg_config += rule_config

        return sg_config

    def generate_ibm_vpc_vm(self, instance, index, clean_name, size, yaml_data=None):
        """Generate IBM VPC virtual server instance."""
        instance_name = instance.get("name", f"instance_{index}")
        image = instance.get("image", "RHEL9-latest")

        # Resolve region and zone
        ibm_region = self.converter.resolve_instance_region(instance, "ibm_vpc")
        ibm_zone = f"{ibm_region}-1"  # Default to first zone

        # Get instance profile
        ibm_profile = self.get_ibm_instance_profile(size)

        # Get user data script
        user_data_script = instance.get('user_data_script') or instance.get('user_data')
        
        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})

        # Generate SSH key resource if configured
        ssh_key_resources = ""
        keys_config = ""
        
        if ssh_key_config and ssh_key_config.get('public_key'):
            ssh_key_name = f"{clean_name}_ssh_key"
            ssh_key_resources = f'''
# IBM SSH Key for {instance_name}
resource "ibm_is_ssh_key" "{ssh_key_name}" {{
  name       = "{instance_name}-ssh-key"
  public_key = "{ssh_key_config['public_key']}"
  
  tags = ["environment:agnosticd", "managed-by:yamlforge"]
}}

'''
            keys_config = f"keys = [ibm_is_ssh_key.{ssh_key_name}.id]"

        vm_config = ssh_key_resources + f'''
# IBM VPC Instance: {instance_name}
resource "ibm_is_instance" "{clean_name}" {{
  name    = "{instance_name}"
  image   = data.ibm_is_image.rhel.id
  profile = "{ibm_profile}"

  primary_network_interface {{
    subnet = ibm_is_subnet.main_subnet.id
    security_groups = [ibm_is_security_group.main_sg.id]
  }}

  vpc  = ibm_is_vpc.main_vpc.id
  zone = "{ibm_zone}"'''

        # Add keys configuration if SSH key is configured
        if keys_config:
            vm_config += f'''
  {keys_config}'''

        # Add user data if provided
        if user_data_script:
            vm_config += f'''

  user_data = base64encode(<<-EOF
{user_data_script}
EOF
  )'''

        vm_config += f'''

  tags = ["environment:agnosticd", "managed-by:yamlforge"]
}}

# IBM Floating IP for {instance_name}
resource "ibm_is_floating_ip" "{clean_name}_fip" {{
  name   = "{instance_name}-fip"
  target = ibm_is_instance.{clean_name}.primary_network_interface[0].id
}}
'''
        return vm_config

    def generate_ibm_vpc_networking(self, deployment_name, deployment_config, region):
        """Generate IBM VPC networking resources for specific region."""
        network_config = deployment_config.get('network', {})
        network_name = network_config.get('name', f"{deployment_name}-vpc")
        cidr_block = network_config.get('cidr_block', '10.0.0.0/16')

        clean_network_name = self.converter.clean_name(network_name)
        clean_region = region.replace("-", "_").replace(".", "_")

        return f'''
# IBM VPC: {network_name} (Region: {region})
resource "ibm_is_vpc" "main_vpc_{clean_region}" {{
  name = "{network_name}-{region}"
}}

# IBM VPC Subnet
resource "ibm_is_subnet" "main_subnet_{clean_region}" {{
  name            = "{network_name}-subnet-{region}"
  vpc             = ibm_is_vpc.main_vpc_{clean_region}.id
  zone            = "{region}-1"
  ipv4_cidr_block = "{cidr_block}"
}}

# IBM SSH Key
resource "ibm_is_ssh_key" "main_key_{clean_region}" {{
  name       = "main-ssh-key-{region}"
  public_key = var.ssh_public_key
}}
'''

    def format_ibm_tags(self, tags):
        """Format tags for IBM (key:value format)."""
        if not tags:
            return ""

        tag_items = []
        for key, value in tags.items():
            tag_items.append(f'"{key}:{value}"')

        return f'''
  tags = [{", ".join(tag_items)}]'''
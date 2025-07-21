"""
Alibaba Cloud Provider Module

Contains Alibaba Cloud-specific implementations for image resolution, VM generation,
networking, security groups, and other Alibaba Cloud resources.
"""

import yaml
from pathlib import Path

# Alibaba Cloud imports - optional, fallback if not available
try:
    from alibabacloud_ecs20140526.client import Client as EcsClient  # pylint: disable=import-error
    from alibabacloud_tea_openapi import models as open_api_models  # pylint: disable=import-error
    ALICLOUD_SDK_AVAILABLE = True
except ImportError:
    ALICLOUD_SDK_AVAILABLE = False
    print("Warning: alibabacloud-ecs20140526 not installed. Alibaba Cloud dynamic image discovery disabled.")


class AlibabaImageResolver:
    """Resolves Alibaba Cloud images using the ECS API."""

    def __init__(self, credentials_manager=None):
        """Initialize the instance."""
        self.credentials = credentials_manager
        self.config = self.load_config()
        self.client = None
        self.cache = {}
        self.cache_timestamps = {}

    def load_config(self):
        """Load Alibaba Cloud configuration from credentials system."""
        # Check if credentials are available for dynamic discovery
        has_credentials = self.credentials and self.credentials.alibaba_config

        if not has_credentials:
            print("Warning: Alibaba Cloud credentials not found. Image discovery will fail if Alibaba images are requested.")

        return {
            'has_credentials': has_credentials
        }

    def get_client(self, region):
        """Initialize and return Alibaba Cloud ECS client."""
        if not ALICLOUD_SDK_AVAILABLE:
            return None

        try:
            if self.credentials and self.credentials.alibaba_config:
                alibaba_config = self.credentials.alibaba_config
                config = open_api_models.Config(
                    access_key_id=alibaba_config.get('access_key_id'),
                    access_key_secret=alibaba_config.get('access_key_secret'),
                    region_id=region,
                    endpoint=f'ecs.{region}.aliyuncs.com'
                )
                client = EcsClient(config)
                return client
            return None

        except Exception as e:
            print(f"Warning: Failed to create Alibaba Cloud client: {e}")
            return None

    def resolve_alibaba_image(self, image_pattern, region):
        """Resolve Alibaba Cloud image using pattern matching."""
        client = self.get_client(region)
        if not client:
            return None

        try:
            # This would require implementing the actual API call
            # For now, return None to fall back to static mapping
            pass

        except Exception as e:
            print(f"Warning: Failed to resolve Alibaba Cloud image: {e}")

        return None


class AlibabaProvider:
    """Alibaba Cloud-specific provider implementation."""

    def __init__(self, converter):
        """Initialize the instance."""
        self.converter = converter
        self._alibaba_resolver = None

    def get_alibaba_resolver(self):
        """Get Alibaba Cloud image resolver, creating it only when needed."""
        if self._alibaba_resolver is None:
            self._alibaba_resolver = AlibabaImageResolver(self.converter.credentials)
        return self._alibaba_resolver

    def get_alibaba_instance_type(self, size_or_instance_type):
        """Get Alibaba Cloud instance type from size mapping or return direct instance type."""
        # If it looks like a direct Alibaba instance type, return it as-is
        if any(prefix in size_or_instance_type for prefix in ['ecs.', 'r6.', 'c6.', 'g6.']):
            return size_or_instance_type
        
        # Check for advanced flavor mappings
        alibaba_flavors = self.converter.flavors.get('alibaba', {}).get('flavor_mappings', {})
        size_mapping = alibaba_flavors.get(size_or_instance_type, {})

        if size_mapping:
            # Return the first (preferred) instance type for this size
            return list(size_mapping.keys())[0]

        # Check direct machine type mapping
        machine_types = self.converter.flavors.get('alibaba', {}).get('machine_types', {})
        if size_or_instance_type in machine_types:
            return size_or_instance_type

        # No mapping found for this size
        raise ValueError(f"No Alibaba Cloud instance type mapping found for size '{size_or_instance_type}'. "
                       f"Available sizes: {list(alibaba_flavors.keys())}")

    def get_alibaba_image_reference(self, image_name):
        """Get Alibaba Cloud image reference from image mapping or direct reference."""
        
        # Use the image resolver for dynamic discovery
        if hasattr(self, 'alibaba_image_resolver') and self.alibaba_image_resolver:
            resolved_image = self.alibaba_image_resolver.resolve_alibaba_image(image_name, "cn-hangzhou")
            if resolved_image:
                return resolved_image
        
        # Check the centralized image mappings
        images = self.converter.images.get(image_name, {})
        alibaba_image = images.get('alibaba', {})
        
        if isinstance(alibaba_image, dict):
            # Return the image name from mapping
            return alibaba_image.get('image_name', alibaba_image.get('image_id', image_name))
        elif isinstance(alibaba_image, str):
            # Direct image name mapping
            return alibaba_image
        
        # Default fallback
        return "aliyun_3_x64_20G_alibase_20230727.vhd"

    def generate_alibaba_vm(self, instance, index, clean_name, size, available_subnets=None, yaml_data=None):
        """Generate native Alibaba Cloud ECS instance."""
        instance_name = instance.get("name", f"instance_{index}")
        image = instance.get("image", "RHEL9-latest")

        # Resolve region and zone
        alibaba_region = self.converter.resolve_instance_region(instance, "alibaba")
        availability_zone = f"{alibaba_region}a"  # Default to first zone

        # Get instance type
        alibaba_instance_type = self.get_alibaba_instance_type(size)

        # Get image reference
        alibaba_image = self.get_alibaba_image_reference(image)

        # Get user data script
        user_data_script = instance.get('user_data_script') or instance.get('user_data')

        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})

        # Generate SSH key pair resource if SSH key is provided
        ssh_key_resources = ""
        key_pair_name_ref = "null"
        
        if ssh_key_config and ssh_key_config.get('public_key'):
            ssh_key_name = f"{clean_name}_key_pair"
            ssh_key_resources = f'''
# Alibaba Cloud SSH Key Pair for {instance_name}
resource "alicloud_ecs_key_pair" "{ssh_key_name}" {{
  key_pair_name = "{instance_name}-keypair"
  public_key    = "{ssh_key_config['public_key']}"
  
  tags = {{
    Environment = "agnosticd"
    ManagedBy   = "yamlforge"
  }}
}}

'''
            key_pair_name_ref = f"alicloud_ecs_key_pair.{ssh_key_name}.key_pair_name"

        vm_config = ssh_key_resources + f'''
# Alibaba Cloud ECS Instance: {instance_name}
resource "alicloud_instance" "{clean_name}" {{
  instance_name     = "{instance_name}"
  image_id          = "{alibaba_image}"
  instance_type     = "{alibaba_instance_type}"
  availability_zone = "{availability_zone}"
  security_groups   = [alicloud_security_group.main_sg.id]
  vswitch_id        = alicloud_vswitch.main_vswitch.id

  # Storage configuration
  system_disk_category = "cloud_essd"
  system_disk_size     = 40

  # Network configuration
  internet_max_bandwidth_out = 10
  internet_charge_type      = "PayByTraffic"

  # Instance charge type
  instance_charge_type = "PostPaid"'''

        # Add SSH key pair if configured
        if key_pair_name_ref != "null":
            vm_config += f'''
  key_name = {key_pair_name_ref}'''

        # Add user data if provided
        if user_data_script:
            vm_config += f'''

  # User data script
  user_data = base64encode(<<-EOF
{user_data_script}
EOF
  )'''

        vm_config += f'''

  # Tags
  tags = {{
    Name        = "{instance_name}"
    Environment = "agnosticd"
    ManagedBy   = "yamlforge"
  }}
}}
'''

        return vm_config

    def generate_alibaba_networking(self, deployment_name, deployment_config, region):
        """Generate Alibaba Cloud networking resources for specific region."""
        network_config = deployment_config.get('network', {})
        network_name = network_config.get('name', f"{deployment_name}-vpc")
        cidr_block = network_config.get('cidr_block', '10.0.0.0/16')

        clean_network_name = self.converter.clean_name(network_name)
        clean_region = region.replace("-", "_").replace(".", "_")

        return f'''
# Alibaba Cloud VPC: {network_name} (Region: {region})
resource "alicloud_vpc" "main_vpc_{clean_region}" {{
  vpc_name   = "{network_name}-{region}"
  cidr_block = "{cidr_block}"

  tags = {{
    Name        = "{network_name}-{region}"
    Environment = "agnosticd"
    Region      = "{region}"
  }}
}}

# Alibaba Cloud VSwitch (Subnet)
resource "alicloud_vswitch" "main_vswitch_{clean_region}" {{
  vswitch_name      = "{network_name}-vswitch-{region}"
  vpc_id            = alicloud_vpc.main_vpc_{clean_region}.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "{region}a"

  tags = {{
    Name        = "{network_name}-vswitch-{region}"
    Environment = "agnosticd"
    Region      = "{region}"
  }}
}}

# Alibaba Cloud Internet Gateway (NAT Gateway for outbound)
resource "alicloud_nat_gateway" "main_nat_{clean_region}" {{
  vpc_id           = alicloud_vpc.main_vpc_{clean_region}.id
  nat_gateway_name = "{network_name}-nat-{region}"
  payment_type     = "PayAsYouGo"
  vswitch_id       = alicloud_vswitch.main_vswitch_{clean_region}.id
  nat_type         = "Enhanced"

  tags = {{
    Name        = "{network_name}-nat-{region}"
    Environment = "agnosticd"
    Region      = "{region}"
  }}
}}

# Alibaba Cloud EIP for NAT Gateway
resource "alicloud_eip_address" "main_eip_{clean_region}" {{
  address_name         = "{network_name}-eip-{region}"
  isp                  = "BGP"
  internet_charge_type = "PayByTraffic"
  payment_type         = "PayAsYouGo"

  tags = {{
    Name        = "{network_name}-eip-{region}"
    Environment = "agnosticd"
    Region      = "{region}"
  }}
}}

# Associate EIP with NAT Gateway
resource "alicloud_eip_association" "main_eip_assoc_{clean_region}" {{
  allocation_id = alicloud_eip_address.main_eip_{clean_region}.id
  instance_id   = alicloud_nat_gateway.main_nat_{clean_region}.id
}}

# Alibaba Cloud Route Table
resource "alicloud_route_table" "main_rt_{clean_region}" {{
  vpc_id           = alicloud_vpc.main_vpc_{clean_region}.id
  route_table_name = "{network_name}-rt-{region}"

  tags = {{
    Name        = "{network_name}-rt-{region}"
    Environment = "agnosticd"
    Region      = "{region}"
  }}
}}

# Route Table Association
resource "alicloud_route_table_attachment" "main_rta_{clean_region}" {{
  vswitch_id     = alicloud_vswitch.main_vswitch_{clean_region}.id
  route_table_id = alicloud_route_table.main_rt_{clean_region}.id
}}
'''

    def generate_alibaba_security_group(self, sg_name, rules, region):
        """Generate Alibaba Cloud security group with rules for specific region."""
        clean_name = sg_name.replace("-", "_").replace(".", "_")
        clean_region = region.replace("-", "_").replace(".", "_")
        regional_sg_name = f"{clean_name}_{clean_region}"

        sg_config = f'''
# Alibaba Cloud Security Group: {sg_name} (Region: {region})
resource "alicloud_security_group" "{regional_sg_name}" {{
  name   = "{sg_name}-{region}"
  vpc_id = alicloud_vpc.main_vpc_{clean_region}.id

  tags = {{
    Name        = "{sg_name}-{region}"
    Environment = "agnosticd"
    Region      = "{region}"
  }}
}}

'''

        # Generate security group rules
        for i, rule in enumerate(rules):
            rule_data = self.converter.generate_native_security_group_rule(rule, 'alibaba')
            rule_type = "ingress" if rule_data['direction'] == 'ingress' else "egress"
            
            sg_config += f'''
# Alibaba Cloud Security Group Rule: {sg_name} - Rule {i+1}
resource "alicloud_security_group_rule" "{regional_sg_name}_rule_{i+1}" {{
  type              = "{rule_type}"
  ip_protocol       = "{rule_data['protocol'].lower()}"
  nic_type          = "intranet"
  policy            = "accept"
  port_range        = "{rule_data['port_min']}/{rule_data['port_max']}"
  priority          = 1
  security_group_id = alicloud_security_group.{regional_sg_name}.id
  cidr_ip           = "{rule_data['source']}"
}}
'''

        return sg_config

    def format_alibaba_tags(self, tags):
        """Format tags for Alibaba Cloud."""
        if not tags:
            return ""

        tag_items = []
        for key, value in tags.items():
            tag_items.append(f'    {key} = "{value}"')

        return f'''
  tags = {{
{chr(10).join(tag_items)}
  }}'''

    def generate_alibaba_resource_group(self, workspace_config):
        """Generate Alibaba Cloud resource group configuration from cloud-agnostic workspace config."""
        return f'''
# Alibaba Cloud Resource Group - {workspace_config['name']}
resource "alicloud_resource_manager_resource_group" "main" {{
  resource_group_name = "{workspace_config['name']}"
  display_name        = "{workspace_config.get('description', workspace_config['name'])}"

  tags = {{
    Environment = "agnosticd"
    ManagedBy   = "yamlforge"
    Project     = "{workspace_config['name']}"
  }}
}}
''' 
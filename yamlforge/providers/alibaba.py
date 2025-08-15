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



    def get_alibaba_instance_type(self, flavor_or_instance_type):
        """Get Alibaba Cloud instance type from flavor or instance type."""
        # If it's already an Alibaba instance type, return it directly
        if any(prefix in flavor_or_instance_type for prefix in ['ecs.', 'r6.', 'c6.', 'g6.']):
            return flavor_or_instance_type
        
        # Load Alibaba flavors
        alibaba_flavors = self.converter.flavors.get('alibaba', {}).get('flavor_mappings', {})
        size_mapping = alibaba_flavors.get(flavor_or_instance_type, {})
        
        if size_mapping:
            # Return the first (usually cheapest) option
            instance_type = list(size_mapping.keys())[0]
            return instance_type
        
        # Check machine types
        machine_types = self.converter.flavors.get('alibaba', {}).get('machine_types', {})
        if flavor_or_instance_type in machine_types:
            return flavor_or_instance_type
        
        raise ValueError(f"No Alibaba Cloud instance type mapping found for flavor '{flavor_or_instance_type}'. "
                        f"Available flavors: {list(alibaba_flavors.keys())}")

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

    def generate_alibaba_vm(self, instance, index, clean_name, flavor, available_subnets=None, yaml_data=None, has_guid_placeholder=False):  # noqa: vulture
        """Generate native Alibaba Cloud ECS instance."""
        instance_name = instance.get("name", f"instance_{index}")
        # Replace {guid} placeholder in instance name
        instance_name = self.converter.replace_guid_placeholders(instance_name)
        image = instance.get("image")
        if not image:
            raise ValueError(f"Instance '{instance_name}' requires an 'image' field")

        # Resolve region and zone
        alibaba_region = self.converter.resolve_instance_region(instance, "alibaba")
        
        # Check if user specified a zone (only valid with region-based configuration)
        user_specified_zone = instance.get('zone')
        has_region = 'region' in instance
        
        if user_specified_zone and has_region:
            # User specified both region and zone - validate the zone belongs to the region
            expected_region = user_specified_zone[:-1]  # Remove last character (e.g., cn-hangzhou-a -> cn-hangzhou)
            
            if expected_region != alibaba_region:
                raise ValueError(f"Instance '{instance_name}': Specified zone '{user_specified_zone}' does not belong to region '{alibaba_region}'. "
                               f"Zone region: '{expected_region}', Instance region: '{alibaba_region}'")
            
            print(f"Using user-specified zone '{user_specified_zone}' for instance '{instance_name}' in region '{alibaba_region}'")
            availability_zone = user_specified_zone
            
        elif user_specified_zone and not has_region:
            raise ValueError(f"Instance '{instance_name}': Zone '{user_specified_zone}' can only be specified when using 'region' (not 'location'). "
                           f"Either remove 'zone' or change 'location' to 'region'.")
        else:
            # Let Terraform automatically select the best available zone
            availability_zone = f"{alibaba_region}a"  # Alibaba requires explicit zone, use first available

        # Get instance type
        alibaba_instance_type = self.get_alibaba_instance_type(flavor)

        # Get image reference
        alibaba_image = self.get_alibaba_image_reference(image)

        # Get user data script
        user_data_script = instance.get('user_data_script')

        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})
        
        # Get GUID for consistent naming
        guid = self.converter.get_validated_guid(yaml_data)
        
        # Use clean_name directly if GUID is already present, otherwise add GUID
        resource_name = clean_name if has_guid_placeholder else f"{clean_name}_{guid}"

        # Generate SSH key pair resource if SSH key is provided
        ssh_key_resources = ""
        key_name_ref = "null"
        
        if ssh_key_config and ssh_key_config.get('public_key'):
            # Use clean_name directly if GUID is already present, otherwise add GUID
            ssh_key_name = clean_name if has_guid_placeholder else f"{clean_name}_key_pair_{guid}"
            ssh_key_resources = f'''
# Alibaba Cloud Key Pair for {instance_name}
resource "alicloud_ecs_key_pair" "{ssh_key_name}" {{
  key_pair_name   = "{instance_name}-key"
  public_key      = "{ssh_key_config['public_key']}"
}}

'''
            key_name_ref = f"alicloud_ecs_key_pair.{ssh_key_name}.key_pair_name"

        # Get Alibaba security group references with regional awareness
        alibaba_sg_refs = []
        sg_names = instance.get('security_groups', [])
        for sg_name in sg_names:
            clean_sg = sg_name.replace("-", "_").replace(".", "_")
            clean_region = alibaba_region.replace("-", "_").replace(".", "_")
            alibaba_sg_refs.append(f"alicloud_security_group.{clean_sg}_{clean_region}_{guid}.id")

        alibaba_sg_refs_str = "[" + ", ".join(alibaba_sg_refs) + "]" if alibaba_sg_refs else "[]"

        # Generate the ECS instance
        vm_config = ssh_key_resources + f'''
# Alibaba Cloud ECS Instance: {instance_name}
resource "alicloud_instance" "{resource_name}" {{
  availability_zone    = "{availability_zone}"
  security_groups      = {alibaba_sg_refs_str}
  instance_type        = "{alibaba_instance_type}"
  system_disk_category = "cloud_efficiency"
  image_id             = "{alibaba_image}"
  instance_name        = "{instance_name}"
  vswitch_id           = alicloud_vswitch.main_vswitch_{alibaba_region.replace("-", "_").replace(".", "_")}_{guid}.id

  # Storage configuration
  system_disk_category = "cloud_essd"
  system_disk_size     = 40

  # Network configuration
  internet_max_bandwidth_out = 10
  internet_charge_type      = "PayByTraffic"

  # Instance charge type
  instance_charge_type = "PostPaid"'''

        # Add SSH key pair if configured
        if key_name_ref != "null":
            vm_config += f'''
  key_name = {key_name_ref}'''

        # Add user data if provided
        if user_data_script:
            vm_config += f'''

  # User data script
  user_data = base64encode(<<-USERDATA
{user_data_script}
USERDATA
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

    def generate_alibaba_networking(self, deployment_name, deployment_config, region, yaml_data=None):  # noqa: vulture
        """Generate Alibaba Cloud networking resources for specific region."""
        network_config = deployment_config.get('network', {})
        network_name = network_config.get('name', f"{deployment_name}-vpc")
        cidr_block = network_config.get('cidr_block', '10.0.0.0/16')

        clean_region = region.replace("-", "_").replace(".", "_")

        return f'''
# Alibaba Cloud VPC: {network_name} (Region: {region})
resource "alicloud_vpc" "main_vpc_{clean_region}_{self.converter.get_validated_guid(yaml_data)}" {{
  vpc_name   = "{network_name}-{region}"
  cidr_block = "{cidr_block}"
}}

# Alibaba Cloud VSwitch: {network_name} switch
resource "alicloud_vswitch" "main_vswitch_{clean_region}_{self.converter.get_validated_guid(yaml_data)}" {{
  vpc_id       = alicloud_vpc.main_vpc_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
  cidr_block   = "{cidr_block}"
  zone_id      = data.alicloud_zones.default.zones[0].id
  vswitch_name = "{network_name}-switch-{region}"
}}

# Alibaba Cloud NAT Gateway
resource "alicloud_nat_gateway" "main_nat_{clean_region}_{self.converter.get_validated_guid(yaml_data)}" {{
  vpc_id               = alicloud_vpc.main_vpc_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
  nat_gateway_name     = "{network_name}-nat-{region}"
  payment_type         = "PayAsYouGo"
  vswitch_id           = alicloud_vswitch.main_vswitch_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
  nat_type             = "Enhanced"
}}

# Alibaba Cloud EIP
resource "alicloud_eip_address" "main_eip_{clean_region}_{self.converter.get_validated_guid(yaml_data)}" {{
  bandwidth            = "10"
  internet_charge_type = "PayByBandwidth"
  address_name         = "{network_name}-eip-{region}"
}}

# Alibaba Cloud EIP Association
resource "alicloud_eip_association" "main_eip_assoc_{clean_region}_{self.converter.get_validated_guid(yaml_data)}" {{
  allocation_id = alicloud_eip_address.main_eip_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
  instance_id   = alicloud_nat_gateway.main_nat_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
}}

# Alibaba Cloud Route Table
resource "alicloud_route_table" "main_rt_{clean_region}_{self.converter.get_validated_guid(yaml_data)}" {{
  vpc_id           = alicloud_vpc.main_vpc_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
  route_table_name = "{network_name}-rt-{region}"
}}

# Alibaba Cloud Route Table Attachment
resource "alicloud_route_table_attachment" "main_rta_{clean_region}_{self.converter.get_validated_guid(yaml_data)}" {{
  vswitch_id     = alicloud_vswitch.main_vswitch_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
  route_table_id = alicloud_route_table.main_rt_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
}}
'''

    def generate_alibaba_security_group(self, sg_name, rules, region, yaml_data=None):  # noqa: vulture
        """Generate Alibaba Cloud security group with rules for specific region."""
        # Replace {guid} placeholder in security group name
        sg_name = self.converter.replace_guid_placeholders(sg_name)
        clean_name = sg_name.replace("-", "_").replace(".", "_")
        clean_region = region.replace("-", "_").replace(".", "_")
        regional_sg_name = f"{clean_name}_{clean_region}"

        security_group_config = f'''
# Alibaba Cloud Security Group: {sg_name} (Region: {region})
resource "alicloud_security_group" "{regional_sg_name}_{self.converter.get_validated_guid(yaml_data)}" {{
  name        = "{sg_name}-{region}"
  description = "Security group for {sg_name} in {region}"
  vpc_id      = alicloud_vpc.main_vpc_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id
}}

'''

        # Generate security group rules
        for i, rule in enumerate(rules):
            rule_data = self.converter.generate_native_security_group_rule(rule, 'alibaba')
            rule_type = "ingress" if rule_data['direction'] == 'ingress' else "egress"
            
            security_group_config += f'''
# Alibaba Cloud Security Group Rule: {sg_name} - Rule {i+1}
resource "alicloud_security_group_rule" "{regional_sg_name}_rule_{i+1}_{self.converter.get_validated_guid(yaml_data)}" {{
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

        return security_group_config

    def generate_oss_bucket(self, bucket, yaml_data):
        """Generate Alibaba Cloud OSS bucket configuration."""
        bucket_name = bucket.get('name', 'my-bucket')
        region = self.converter.resolve_bucket_region(bucket, 'alibaba')
        guid = self.converter.get_validated_guid(yaml_data)

        # Replace GUID placeholders
        final_bucket_name = self.converter.replace_guid_placeholders(bucket_name)
        clean_bucket_name, _ = self.converter.clean_name(final_bucket_name)
        
        # Bucket configuration
        public = bucket.get('public', False)
        versioning = bucket.get('versioning', False)
        tags = bucket.get('tags', {})

        terraform_config = f'''
# Alibaba Cloud OSS Bucket: {final_bucket_name}
resource "alicloud_oss_bucket" "{clean_bucket_name}_{guid}" {{
  bucket = "{final_bucket_name}"
  acl    = "{"public-read" if public else "private"}"

  versioning {{
    status = "{"Enabled" if versioning else "Suspended"}"
  }}

  tags = {{
    Name = "{final_bucket_name}"
    ManagedBy = "YamlForge"
    GUID = "{guid}"'''

        # Add custom tags
        for key, value in tags.items():
            terraform_config += f'''
    {key} = "{value}"'''

        terraform_config += '''
  }
}

'''

        return terraform_config



 
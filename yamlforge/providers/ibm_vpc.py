"""
IBM VPC Provider Module

Contains IBM VPC-specific implementations for VM generation, networking,
and security groups.
"""

import os
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_vpc import VpcV1


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
        
        # Get the validated GUID for resource naming
        guid = self.converter.get_validated_guid(yaml_data)
        resource_name = f"{regional_sg_name}_{guid}"

        security_group_config = f'''
# IBM Cloud VPC Security Group: {sg_name} (Region: {region})
resource "ibm_is_security_group" "{resource_name}" {{
  name = "{sg_name}-{region}"
  vpc  = ibm_is_vpc.main_vpc_{clean_region}_{guid}.id
  
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
            protocol = rule_data['protocol']
            
            # Map direction to IBM VPC format
            ibm_direction = "inbound" if direction == "ingress" else "outbound"

            # Handle different protocols for IBM VPC
            if protocol == 'all':
                # For "all" protocol, create separate rules for TCP, UDP, and ICMP
                protocols = ['tcp', 'udp', 'icmp']
                for proto in protocols:
                    if proto == 'icmp':
                        # ICMP doesn't use port ranges
                        rule_config = f'''
# IBM Security Group Rule: {sg_name} Rule {i+1} ({proto.upper()}) (Region: {region})
resource "ibm_is_security_group_rule" "{resource_name}_rule_{i+1}_{proto}" {{
  group     = ibm_is_security_group.{resource_name}.id
  direction = "{ibm_direction}"
  remote    = "{rule_data['source_cidr_blocks'][0] if rule_data['source_cidr_blocks'] else '0.0.0.0/0'}"

  {proto} {{
  }}
}}
'''
                    else:
                        # TCP and UDP use port ranges
                        rule_config = f'''
# IBM Security Group Rule: {sg_name} Rule {i+1} ({proto.upper()}) (Region: {region})
resource "ibm_is_security_group_rule" "{resource_name}_rule_{i+1}_{proto}" {{
  group     = ibm_is_security_group.{resource_name}.id
  direction = "{ibm_direction}"
  remote    = "{rule_data['source_cidr_blocks'][0] if rule_data['source_cidr_blocks'] else '0.0.0.0/0'}"

  {proto} {{
    port_min = {rule_data['from_port']}
    port_max = {rule_data['to_port']}
  }}
}}
'''
                    security_group_config += rule_config
            else:
                # Single protocol rule
                if protocol == 'icmp':
                    # ICMP doesn't use port ranges
                    rule_config = f'''
# IBM Security Group Rule: {sg_name} Rule {i+1} (Region: {region})
resource "ibm_is_security_group_rule" "{resource_name}_rule_{i+1}" {{
  group     = ibm_is_security_group.{resource_name}.id
  direction = "{ibm_direction}"
  remote    = "{rule_data['source_cidr_blocks'][0] if rule_data['source_cidr_blocks'] else '0.0.0.0/0'}"

  {protocol} {{
  }}
}}
'''
                else:
                    # TCP and UDP use port ranges
                    rule_config = f'''
# IBM Security Group Rule: {sg_name} Rule {i+1} (Region: {region})
resource "ibm_is_security_group_rule" "{resource_name}_rule_{i+1}" {{
  group     = ibm_is_security_group.{resource_name}.id
  direction = "{ibm_direction}"
  remote    = "{rule_data['source_cidr_blocks'][0] if rule_data['source_cidr_blocks'] else '0.0.0.0/0'}"

  {protocol} {{
    port_min = {rule_data['from_port']}
    port_max = {rule_data['to_port']}
  }}
}}
'''
                security_group_config += rule_config

        return security_group_config

    def generate_ibm_vpc_vm(self, instance, index, clean_name, size, yaml_data=None, has_guid_placeholder=False):
        """Generate IBM VPC virtual server instance."""
        instance_name = instance.get("name", f"instance_{index}")
        instance_name = self.converter.replace_guid_placeholders(instance_name)
        image = instance.get("image", "RHEL9-latest")
        guid = self.converter.get_validated_guid(yaml_data)
        ibm_region = self.converter.resolve_instance_region(instance, "ibm_vpc")
        user_specified_zone = instance.get('zone')
        has_region = 'region' in instance
        if user_specified_zone and has_region:
            expected_region = user_specified_zone.rsplit('-', 1)[0]
            if expected_region != ibm_region:
                raise ValueError(f"Instance '{instance_name}': Specified zone '{user_specified_zone}' does not belong to region '{ibm_region}'. "
                               f"Zone region: '{expected_region}', Instance region: '{ibm_region}'")
            print(f"Using user-specified zone '{user_specified_zone}' for instance '{instance_name}' in region '{ibm_region}'")
            ibm_zone = user_specified_zone
        elif user_specified_zone and not has_region:
            raise ValueError(f"Instance '{instance_name}': Zone '{user_specified_zone}' can only be specified when using 'region' (not 'location'). "
                           f"Either remove 'zone' or change 'location' to 'region'.")
        else:
            ibm_zone = f"{ibm_region}-1"
        # Dynamic image lookup, but skip if no-credentials
        if getattr(self.converter, 'no_credentials', False):
            image_id = "PLACEHOLDER-IBM-VPC-IMAGE-ID"
            print(f"  NO-CREDENTIALS MODE: Skipping IBM VPC image lookup for {instance_name}, using placeholder image ID.")
        else:
            # Try to use image mapping first, then fall back to dynamic lookup
            try:
                image_config = self.converter.images.get(image, {})
                ibm_vpc_config = image_config.get('ibm_vpc', {})
                
                if ibm_vpc_config and 'name_pattern' in ibm_vpc_config:
                    # Use the name pattern from image mapping
                    name_pattern = ibm_vpc_config['name_pattern']
                    print(f"Using image mapping pattern for {instance_name}: {name_pattern}")
                    
                    # Extract OS info from the image name for filtering
                    os_name = "redhat" if "rhel" in image.lower() else image.split('-')[0]
                    version = None
                    import re
                    version_match = re.search(r'(\d+)', image)
                    if version_match:
                        version = version_match.group(1)
                    
                    # Use dynamic lookup with the name pattern
                    image_id = self.find_latest_ibm_vpc_image_by_pattern(ibm_region, name_pattern, os_name, version)
                else:
                    # Fall back to original dynamic lookup logic
                    os_name = "redhat" if "rhel" in image.lower() else image.split('-')[0]
                    version = None
                    architecture = None
                    import re
                    version_match = re.search(r'(\d+)', image)
                    if version_match:
                        version = version_match.group(1)
                    if "amd64" in image.lower():
                        architecture = "amd64"
                    image_id = self.find_latest_ibm_vpc_image(ibm_region, os_name, version, architecture)
                    
                print(f"Dynamic IBM VPC image lookup for {instance_name}: {image} in {ibm_region} -> {image_id}")
            except Exception as e:
                print(f"Warning: Image lookup failed for {instance_name}: {e}")
                # Fall back to placeholder
                image_id = "PLACEHOLDER-IBM-VPC-IMAGE-ID"
        ibm_profile = self.get_ibm_instance_profile(size)
        user_data_script = instance.get('user_data_script') or instance.get('user_data')
        
        # Generate user_data script for RHEL 9 if not provided, using RHEL image, and cloud-user creation is enabled
        if not user_data_script and "rhel" in image.lower():
            # Check if cloud-user creation is enabled in IBM VPC config
            ibm_vpc_config = yaml_data.get('yamlforge', {}).get('ibm_vpc', {})
            create_cloud_user = ibm_vpc_config.get('create_cloud_user', True)  # Default to True
            
            if create_cloud_user:
                user_data_script = self.generate_rhel_user_data_script(instance, yaml_data)
        
        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})
        ssh_key_resources = ""
        
        # Get the global SSH key reference (created in networking)
        global_ssh_key_ref = f"ibm_is_ssh_key.main_key_{ibm_region.replace('-', '_').replace('.', '_')}_{guid}.id"
        
        # Check if instance specifies a different SSH key than the global one
        instance_ssh_key = instance.get('ssh_key')
        global_ssh_key_config = self.converter.get_default_ssh_key(yaml_data or {})
        
        # Only create instance-specific key if:
        # 1. Instance specifies a different SSH key name, AND
        # 2. The SSH key content is actually different from global
        should_create_instance_key = (
            instance_ssh_key and 
            instance_ssh_key != 'default' and
            ssh_key_config and 
            ssh_key_config.get('public_key') and
            global_ssh_key_config and
            global_ssh_key_config.get('public_key') and
            ssh_key_config.get('public_key') != global_ssh_key_config.get('public_key')
        )
        
        if should_create_instance_key:
            # Instance has a different SSH key - create it
            ssh_key_name = clean_name if has_guid_placeholder else f"{clean_name}_ssh_key_{guid}"
            ssh_key_resource, key_name_ref = self.generate_ssh_key_resource(
                ssh_key_name, 
                ssh_key_config['public_key'], 
                ibm_region, 
                yaml_data
            )
            ssh_key_resources = ssh_key_resource
        else:
            # Use the global SSH key
            key_name_ref = global_ssh_key_ref
        ibm_sg_refs = []
        sg_names = instance.get('security_groups', [])
        for sg_name in sg_names:
            sg_name = self.converter.replace_guid_placeholders(sg_name)
            clean_sg = sg_name.replace("-", "_").replace(".", "_")
            clean_region = ibm_region.replace("-", "_").replace(".", "_")
            sg_resource_name = f"{clean_sg}_{clean_region}_{guid}"
            ibm_sg_refs.append(f"ibm_is_security_group.{sg_resource_name}.id")
        ibm_sg_refs_str = "[" + ", ".join(ibm_sg_refs) + "]" if ibm_sg_refs else "[]"
        
        # Use clean_name directly if GUID is already present, otherwise add GUID
        resource_name = clean_name if has_guid_placeholder else f"{clean_name}_{guid}"
        
        vm_config = ssh_key_resources + f'''
# IBM Cloud VPC Instance: {instance_name}
resource "ibm_is_instance" "{resource_name}" {{
  name    = "{instance_name}"
  image   = "{image_id}"
  profile = "{ibm_profile}"
  
  vpc     = ibm_is_vpc.main_vpc_{ibm_region.replace("-", "_").replace(".", "_")}_{guid}.id
  zone    = "{ibm_zone}"
  keys    = [{key_name_ref}]

  primary_network_interface {{
    subnet          = ibm_is_subnet.main_subnet_{ibm_region.replace("-", "_").replace(".", "_")}_{guid}.id
    security_groups = {ibm_sg_refs_str}
  }}

          {f"user_data = <<-EOF\n{user_data_script}\nEOF" if user_data_script else ""}

  # Create and attach floating IP
  resource_group = local.resource_group_id_{ibm_region.replace("-", "_").replace(".", "_")}_{guid}
}}

# IBM Cloud Floating IP for {instance_name}
resource "ibm_is_floating_ip" "{resource_name}_fip" {{
  name   = "{instance_name}-fip"
  target = ibm_is_instance.{resource_name}.primary_network_interface[0].id
  
  resource_group = local.resource_group_id_{ibm_region.replace("-", "_").replace(".", "_")}_{guid}
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
        
        # Construct resource names with GUID replacement
        resource_group_name = self.converter.replace_guid_placeholders(f"{network_name}-{region}")
        vpc_name = self.converter.replace_guid_placeholders(f"{network_name}-{region}")
        subnet_name = self.converter.replace_guid_placeholders(f"{network_name}-subnet-{region}")
        ssh_key_name = self.converter.replace_guid_placeholders(f"{network_name}-key-{region}")
        
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
# IBM Cloud Resource Group: {resource_group_name} (Region: {region})
resource "ibm_resource_group" "main_{clean_region}_{guid}" {{
  name = "{resource_group_name}"
}}

# Local value to reference resource group
locals {{
  resource_group_id_{clean_region}_{guid} = ibm_resource_group.main_{clean_region}_{guid}.id
  resource_group_name_{clean_region}_{guid} = ibm_resource_group.main_{clean_region}_{guid}.name
}}
'''

        networking_config += f'''
# IBM Cloud VPC: {vpc_name} (Region: {region})
resource "ibm_is_vpc" "main_vpc_{clean_region}_{guid}" {{
  name = "{vpc_name}"
  
  tags = [
    "Environment:agnosticd",
    "ManagedBy:yamlforge"
  ]
}}

# IBM Cloud Subnet: {subnet_name}
resource "ibm_is_subnet" "main_subnet_{clean_region}_{guid}" {{
  name                     = "{subnet_name}"
  vpc                      = ibm_is_vpc.main_vpc_{clean_region}_{guid}.id
  zone                     = "{region}-1"
  total_ipv4_address_count = 256
  
  tags = [
    "Environment:agnosticd",
    "ManagedBy:yamlforge"
  ]
}}
'''

        # Generate main SSH key using the new method
        main_key_name = f"main_key_{clean_region}_{guid}"
        # For the main key, we need to handle the variable reference differently
        if getattr(self.converter, 'no_credentials', False):
            main_key_resource = f'''
# IBM Cloud SSH Key (Global): {main_key_name}
resource "ibm_is_ssh_key" "{main_key_name}" {{
  name       = "{ssh_key_name}"
  public_key = var.ssh_public_key
  type       = "rsa"
  
  tags = [
    "Environment:agnosticd",
    "ManagedBy:yamlforge"
  ]
}}
'''
        else:
            # In credentials mode, we need to get the actual key value to check for existing keys
            # For now, we'll create the resource and let Terraform handle conflicts
            main_key_resource = f'''
# IBM Cloud SSH Key (Global): {main_key_name}
resource "ibm_is_ssh_key" "{main_key_name}" {{
  name       = "{ssh_key_name}"
  public_key = var.ssh_public_key
  type       = "rsa"
  
  tags = [
    "Environment:agnosticd",
    "ManagedBy:yamlforge"
  ]
}}

# If this key already exists in IBM VPC, import it with:
# terraform import ibm_is_ssh_key.{main_key_name} <existing_key_id>
'''
        networking_config += main_key_resource
        
        return networking_config



    def find_latest_ibm_vpc_image(self, region, os_name, version=None, architecture=None, api_key=None):
        """Find the latest IBM VPC image matching the OS, version, and architecture."""
        api_key = api_key or os.getenv('IC_API_KEY') or os.getenv('IBM_CLOUD_API_KEY')
        if not api_key:
            raise ValueError("IBM Cloud API key not found in environment variables (IC_API_KEY or IBM_CLOUD_API_KEY)")
        authenticator = IAMAuthenticator(api_key)
        vpc = VpcV1(authenticator=authenticator)
        vpc.set_service_url(f"https://{region}.iaas.cloud.ibm.com/v1")
        images = vpc.list_images().get_result()["images"]
        
        # Filter images based on OS name
        if os_name.lower() == "redhat":
            # IBM VPC uses "red-X-amd64" format for Red Hat images
            # Handle specific RHEL versions like "RHEL9-latest"
            if version and "9" in version:
                filtered = [img for img in images if img["operating_system"]["name"].startswith("red-9")]
            elif version and "8" in version:
                filtered = [img for img in images if img["operating_system"]["name"].startswith("red-8")]
            else:
                # Default to latest RHEL version available
                filtered = [img for img in images if img["operating_system"]["name"].startswith("red-")]
        else:
            filtered = [img for img in images if os_name.lower() in img["operating_system"]["name"].lower()]
        
        # Filter by version if specified
        if version:
            filtered = [img for img in filtered if version in img["name"]]
        
        # Filter by architecture if specified
        if architecture:
            filtered = [img for img in filtered if architecture in img["name"]]
        
        # Sort by creation date descending
        filtered.sort(key=lambda img: img["created_at"], reverse=True)
        
        if not filtered:
            raise ValueError(f"No IBM VPC images found for OS={os_name}, version={version}, arch={architecture} in region {region}")
        
        return filtered[0]["id"]

    def find_latest_ibm_vpc_image_by_pattern(self, region, name_pattern, os_name, version=None):
        """Find the latest IBM VPC image matching a specific name pattern."""
        api_key = os.getenv('IC_API_KEY') or os.getenv('IBM_CLOUD_API_KEY')
        if not api_key:
            raise ValueError("IBM Cloud API key not found in environment variables (IC_API_KEY or IBM_CLOUD_API_KEY)")
        authenticator = IAMAuthenticator(api_key)
        vpc = VpcV1(authenticator=authenticator)
        vpc.set_service_url(f"https://{region}.iaas.cloud.ibm.com/v1")
        images = vpc.list_images().get_result()["images"]
        
        # Convert glob pattern to regex pattern
        import re
        pattern = name_pattern.replace('*', '.*')
        
        # Filter images by name pattern
        filtered = [img for img in images if re.match(pattern, img["name"])]
        
        # Additional filtering by OS if specified
        if os_name.lower() == "redhat":
            # For RHEL images, ensure we get the right version
            if version and "9" in version:
                filtered = [img for img in filtered if img["operating_system"]["name"].startswith("red-9")]
            elif version and "8" in version:
                filtered = [img for img in filtered if img["operating_system"]["name"].startswith("red-8")]
        
        # Sort by creation date descending
        filtered.sort(key=lambda img: img["created_at"], reverse=True)
        
        if not filtered:
            raise ValueError(f"No IBM VPC images found matching pattern '{name_pattern}' in region {region}")
        
        return filtered[0]["id"]

    def find_existing_ssh_key_by_fingerprint(self, public_key, region):
        """Find existing SSH key by fingerprint to provide import commands."""
        if getattr(self.converter, 'no_credentials', False):
            return None
            
        try:
            import hashlib
            import base64
            
            # Extract the key part (remove ssh-rsa prefix and comment)
            key_parts = public_key.split()
            if len(key_parts) < 2:
                print(f"Debug: Invalid SSH key format: {public_key}")
                return None
                
            key_data = key_parts[1]
            
            # Calculate SHA256 fingerprint (IBM VPC uses base64-encoded SHA256)
            key_bytes = base64.b64decode(key_data)
            fingerprint = hashlib.sha256(key_bytes).digest()
            
            # Format as SHA256:base64digest (IBM VPC format)
            formatted_fingerprint = f"SHA256:{base64.b64encode(fingerprint).decode('utf-8').rstrip('=')}"
            
            print(f"Debug: Calculated SHA256 fingerprint: {formatted_fingerprint}")
            
            # Use IBM VPC API to find existing key
            api_key = os.getenv('IC_API_KEY') or os.getenv('IBM_CLOUD_API_KEY')
            if not api_key:
                print("Debug: No IBM Cloud API key found")
                return None
                
            from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
            from ibm_vpc import VpcV1
            
            authenticator = IAMAuthenticator(api_key)
            vpc = VpcV1(authenticator=authenticator)
            vpc.set_service_url(f"https://{region}.iaas.cloud.ibm.com/v1")
            
            keys = vpc.list_keys().get_result()["keys"]
            print(f"Debug: Found {len(keys)} existing SSH keys in region {region}")
            
            for key in keys:
                existing_fingerprint = key.get("fingerprint")
                key_name = key.get('name', 'unnamed')
                key_id = key.get('id', 'unknown')
                print(f"Debug: Key '{key_name}' (ID: {key_id}) has fingerprint: '{existing_fingerprint}'")
                
                # Compare SHA256 fingerprints
                if existing_fingerprint == formatted_fingerprint:
                    print(f"Debug: SHA256 match found!")
                    return key["id"]
                    
            print("Debug: No matching SSH key found")
            return None
            
        except Exception as e:
            print(f"Warning: Could not check for existing SSH key: {e}")
            import traceback
            traceback.print_exc()
            return None

    def generate_ssh_key_resource(self, key_name, public_key, region, yaml_data=None):
        """Generate SSH key resource, using data source if key already exists."""
        # Convert key_name to kebab-case for IBM VPC compatibility
        kebab_key_name = key_name.replace('_', '-')
        
        if getattr(self.converter, 'no_credentials', False):
            # In no-credentials mode, always create the resource
            return f'''
# IBM Cloud SSH Key: {key_name}
resource "ibm_is_ssh_key" "{key_name}" {{
  name       = "{kebab_key_name}"
  public_key = "{public_key}"
  type       = "rsa"
}}
''', f"ibm_is_ssh_key.{key_name}.id"
        
        # Check if key already exists
        existing_key_id = self.find_existing_ssh_key_by_fingerprint(public_key, region)
        
        if existing_key_id:
            # Use data source to reference existing key (read-only, won't be destroyed)
            print(f"INFO: Found existing SSH key with ID {existing_key_id}, using data source")
            return f'''
# Import existing IBM Cloud SSH Key: {key_name}
data "ibm_is_ssh_key" "{key_name}" {{
  id = "{existing_key_id}"
}}
''', f"data.ibm_is_ssh_key.{key_name}.id"
        else:
            # Create new key resource
            print(f"INFO: No existing SSH key found, will create new key: {key_name}")
            return f'''
# IBM Cloud SSH Key: {key_name}
resource "ibm_is_ssh_key" "{key_name}" {{
  name       = "{kebab_key_name}"
  public_key = "{public_key}"
  type       = "rsa"
}}

# If this key already exists in IBM VPC, import it with:
# terraform import ibm_is_ssh_key.{key_name} <existing_key_id>
# 
# To find existing keys with the same fingerprint:
# 1. Calculate fingerprint: echo "{public_key}" | ssh-keygen -lf -
# 2. List keys: ibmcloud is keys --region {region}
# 3. Import matching key: terraform import ibm_is_ssh_key.{key_name} <key_id>
''', f"ibm_is_ssh_key.{key_name}.id"

    def generate_rhel_user_data_script(self, instance, yaml_data=None):
        """Generate user_data script for RHEL instances to create cloud-user account."""
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})
        public_key = ssh_key_config.get('public_key', '') if ssh_key_config else ''
        
        # Get the SSH username that should be created
        ssh_username = self.converter.get_instance_ssh_username(instance, yaml_data or {})
        
        user_data_script = f'''#!/bin/bash
# User data script for RHEL instance
# This script creates the {ssh_username} user and configures SSH access

set -e

# Create {ssh_username} user if it doesn't exist
if ! id "{ssh_username}" &>/dev/null; then
    useradd -m -s /bin/bash {ssh_username}
    echo "Created {ssh_username} user"
fi

# Create .ssh directory and set permissions
mkdir -p /home/{ssh_username}/.ssh
chmod 700 /home/{ssh_username}/.ssh

# Add SSH public key to authorized_keys
if [ -n "{public_key}" ]; then
    echo "{public_key}" >> /home/{ssh_username}/.ssh/authorized_keys
    chmod 600 /home/{ssh_username}/.ssh/authorized_keys
    echo "Added SSH key for {ssh_username}"
fi

# Set ownership
chown -R {ssh_username}:{ssh_username} /home/{ssh_username}/.ssh

# Configure sudo access for {ssh_username}
echo "{ssh_username} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/{ssh_username}
chmod 440 /etc/sudoers.d/{ssh_username}

# Disable root SSH access for security
sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config

# Restart SSH service
systemctl restart sshd

echo "User data script completed successfully"
'''
        
        return user_data_script

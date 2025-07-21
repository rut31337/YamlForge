"""
AWS Provider Module

Contains AWS-specific implementations for image resolution, VM generation,
networking, security groups, and other AWS cloud resources.
"""

import yaml
from pathlib import Path
from datetime import datetime, timedelta

# AWS imports
try:
    import boto3  # pylint: disable=import-error
    from botocore.exceptions import (  # pylint: disable=import-error
        ClientError,
        NoCredentialsError
    )
    AWS_SDK_AVAILABLE = True
except ImportError:
    AWS_SDK_AVAILABLE = False
    print("Warning: boto3 not installed. AWS dynamic AMI discovery disabled.")


class AWSImageResolver:
    """Resolves Red Hat Cloud Access AMIs from AWS using the EC2 API."""

    def __init__(self, credentials_manager=None):
        """Initialize the instance."""
        self.credentials = credentials_manager
        self.config = self.load_config()
        self.client = None
        self.cache = {}
        self.cache_timestamps = {}

    def load_config(self):
        """Load AWS configuration from defaults and credentials system."""
        # Load defaults file directly
        defaults_file = Path("defaults/aws.yaml")
        if not defaults_file.exists():
            raise Exception(f"Required AWS defaults file not found: {defaults_file}")

        try:
            with open(defaults_file, 'r') as f:
                defaults_config = yaml.safe_load(f)
        except Exception as e:
            raise Exception(f"Failed to load defaults/aws.yaml: {e}")

        if not defaults_config:
            raise Exception("defaults/aws.yaml is empty or invalid")

        # Get configuration values from defaults
        ami_owners = defaults_config.get('ami_owners', {})
        if not ami_owners:
            raise Exception("ami_owners section missing from defaults/aws.yaml")

        # Check if credentials are available for dynamic discovery
        has_credentials = self.credentials and self.credentials.aws_config

        if not has_credentials:
            print("Warning: AWS credentials not found. "
                  "AMI discovery will fail if AWS images are requested.")

        return {
            'owners': {
                'redhat_gold': self._get_required_owner('redhat_gold', ami_owners),
                'redhat_public': self._get_required_owner('redhat_public', ami_owners),
                'fedora': self._get_required_owner('fedora', ami_owners),
                'amazon': self._get_required_owner('amazon', ami_owners),
                'canonical': self._get_required_owner('canonical', ami_owners),
                'microsoft': self._get_required_owner('microsoft', ami_owners)
            }
        }

    def _get_required_owner(self, owner_key, ami_owners):
        """Get required owner ID from configuration, raising error if missing."""
        if owner_key not in ami_owners:
            raise Exception(
                f"Required AMI owner '{owner_key}' not found in "
                f"defaults/aws.yaml ami_owners section"
            )
        value = ami_owners[owner_key]
        if not value:
            raise Exception(f"AMI owner '{owner_key}' in defaults/aws.yaml is empty")
        return value

    def _get_required_config_owner(self, owner_key):
        """Get required owner ID from loaded configuration, raising error if missing."""
        owners = self.config.get('owners', {})
        if owner_key not in owners:
            raise Exception(f"Required AMI owner '{owner_key}' not found in AWS resolver configuration")
        value = owners[owner_key]
        if not value:
            raise Exception(f"AMI owner '{owner_key}' in AWS resolver configuration is empty")
        return value

    def get_client(self, region):
        """Initialize and return AWS EC2 client for the specified region."""
        if not AWS_SDK_AVAILABLE:
            return None

        try:
            # Get AWS credentials
            aws_config = self.config

            # Create session
            session = boto3.Session(
                aws_access_key_id=aws_config.get('access_key_id'),
                aws_secret_access_key=aws_config.get('secret_access_key'),
                aws_session_token=aws_config.get('session_token'),
                region_name=region,
                profile_name=aws_config.get('profile_name')
            )

            # Create EC2 client
            client = session.client('ec2', region_name=region)
            return client

        except Exception as e:
            print(f"Warning: Failed to create AWS client for region {region}: {e}")
            return None

    def is_cache_valid(self, cache_key):
        """Check if cached result is still valid."""
        return cache_key in self.cache_timestamps

    def find_latest_ami(self, name_pattern, owner, region, architecture='x86_64', additional_filters=None):
        """Find the latest AMI matching the given pattern."""
        # Include additional filters in cache key for uniqueness
        filters_str = str(sorted(additional_filters or []))
        cache_key = f"{name_pattern}_{owner}_{region}_{architecture}_{hash(filters_str)}"

        # Check cache first
        if self.is_cache_valid(cache_key):
            return self.cache[cache_key]

        client = self.get_client(region)
        if client is None:
            return None

        try:
            # Base filters for the AMI query
            filters = [
                {'Name': 'name', 'Values': [name_pattern]},
                {'Name': 'owner-id', 'Values': [owner]},
                {'Name': 'state', 'Values': ['available']},
                {'Name': 'architecture', 'Values': [architecture]}
            ]

            # Add any additional filters
            if additional_filters:
                filters.extend(additional_filters)

            # Query for AMIs
            response = client.describe_images(
                Filters=filters,
                MaxResults=50  # Limit results for performance
            )

            if not response['Images']:
                return None

            # Sort by creation date (newest first)
            images = sorted(response['Images'], key=lambda x: x['CreationDate'], reverse=True)
            latest_image = images[0]

            # Cache the result
            self.cache[cache_key] = latest_image['ImageId']

            return latest_image['ImageId']

        except Exception as e:
            print(f"Warning: Failed to find AMI with pattern '{name_pattern}': {e}")
            return None

    def resolve_rhel_ami(self, rhel_version, architecture="x86_64", is_gold=False, region=None):
        """Resolve RHEL AMI for a given version."""
        if not region:
            raise ValueError("Region must be specified for AMI resolution")

        if is_gold:
            owner_key = 'redhat_gold'
            name_pattern = f"RHEL-{rhel_version}*_HVM_GA*Access*"
        else:
            owner_key = 'redhat_public'
            name_pattern = f"RHEL-{rhel_version}*_HVM*"

        owner = self._get_required_owner(owner_key, self.config.get('ami_owners', {}))
        return self.find_latest_ami(name_pattern, owner, region, architecture)

    def resolve_ami_by_pattern(self, name_pattern, owner_key, region, architecture='x86_64', additional_filters=None):
        """Resolve AMI by pattern and owner key."""
        owner = self._get_required_owner(owner_key, self.config.get('ami_owners', {}))
        return self.find_latest_ami(name_pattern, owner, region, architecture, additional_filters)

    def resolve_fedora_ami(self, fedora_version=None, region=None, architecture='x86_64'):
        """Resolve Fedora AMI."""
        if not region:
            raise ValueError("Region must be specified for AMI resolution")

        if fedora_version:
            name_pattern = f"Fedora-Cloud-Base-{fedora_version}*"
        else:
            name_pattern = "Fedora-Cloud-Base-*"

        owner_key = 'fedora'
        owner = self._get_required_owner(owner_key, self.config.get('ami_owners', {}))
        return self.find_latest_ami(name_pattern, owner, region, architecture)


class AWSProvider:
    """AWS-specific provider implementation."""

    def __init__(self, converter):
        """Initialize the instance."""
        self.converter = converter
        self._aws_resolver = None

    def get_aws_resolver(self):
        """Get AWS image resolver, creating it only when needed."""
        if self._aws_resolver is None:
            self._aws_resolver = AWSImageResolver(self.converter.credentials)
        return self._aws_resolver

    def get_aws_filters(self, image_key):
        """Get AWS filters for AMI discovery."""
        if image_key in self.converter.images:
            aws_config = self.converter.images[image_key].get('aws', {})
            if isinstance(aws_config, dict):
                return aws_config.get('aws_filters', [])
        return []

    def ensure_is_public_false_filter(self, aws_filters):
        """Ensure is-public=false filter is present for GOLD images."""
        filters = aws_filters.copy() if aws_filters else []

        # Check if is-public filter already exists
        has_is_public = any(f.get('name') == 'is-public' for f in filters)

        if not has_is_public:
            # Add is-public=false filter for GOLD images
            filters.append({
                'name': 'is-public',
                'values': ['false']
            })
            print("Automatically adding is-public=false filter for GOLD image")

        return filters

    def get_aws_instance_type(self, size_or_instance_type):
        """Get AWS instance type from size mapping or return direct instance type."""
        # If it looks like a direct AWS instance type, return it as-is  
        if any(prefix in size_or_instance_type for prefix in ['t3', 't4', 'm5', 'm6', 'c5', 'c6', 'r5', 'r6', 'g4', 'p3', 'p4']):
            return size_or_instance_type
        
        # Check for advanced flavor mappings
        aws_flavors = self.converter.flavors.get('aws', {}).get('flavor_mappings', {})
        size_mapping = aws_flavors.get(size_or_instance_type, {})

        if size_mapping:
            # Return the first (preferred) instance type for this size
            return list(size_mapping.keys())[0]

        # No mapping found for this size
        raise ValueError(f"No AWS instance type mapping found for size '{size_or_instance_type}'. "
                       f"Available sizes: {list(aws_flavors.keys())}")

    def resolve_aws_ami(self, image_key, instance_name, architecture="x86_64", region=None):
        """Resolve AWS AMI using dynamic discovery or fallback to data source."""
        if not region:
            raise ValueError(f"Region must be specified for AWS AMI resolution for image '{image_key}'")

        image_config = self.converter.images.get(image_key, {})
        aws_config = image_config.get('aws', {})

        # Check if this is a pattern-based RHEL image (RHEL 10+)
        if not aws_config:
            pattern_config = self.converter.generate_rhel_pattern_config(image_key)
            if pattern_config:
                aws_config = pattern_config
                print(f"Generated pattern-based config for {image_key}: {aws_config}")
            else:
                return None, None

        # Use dynamic discovery if SDK is available and credentials exist
        has_credentials = self.converter.credentials and self.converter.credentials.aws_config

        if AWS_SDK_AVAILABLE and has_credentials:
            try:
                ami_id = None

                # Handle different image types
                if "RHEL" in image_key.upper():
                    # RHEL images
                    rhel_version, arch = self.converter.extract_rhel_info(image_key)
                    is_gold_image = "GOLD" in image_key.upper() or "BYOS" in image_key.upper()

                    ami_id = self.get_aws_resolver().resolve_rhel_ami(
                        rhel_version=rhel_version,
                        architecture=architecture,
                        is_gold=is_gold_image,
                        region=region
                    )
                elif "FEDORA" in image_key.upper():
                    # Fedora images
                    fedora_version = self.converter.extract_fedora_version(image_key)

                    ami_id = self.get_aws_resolver().resolve_fedora_ami(
                        fedora_version=fedora_version,
                        region=region,
                        architecture=architecture
                    )
                elif aws_config.get('name_pattern'):
                    # Pattern-based discovery
                    name_pattern = aws_config['name_pattern']
                    owner_key = aws_config.get('owner_key', self.converter.determine_default_owner_key(image_key))

                    # Get additional filters
                    additional_filters = self.get_aws_filters(image_key)
                    if "GOLD" in image_key.upper() or "BYOS" in image_key.upper():
                        additional_filters = self.ensure_is_public_false_filter(additional_filters)

                    ami_id = self.get_aws_resolver().resolve_ami_by_pattern(
                        name_pattern=name_pattern,
                        owner_key=owner_key,
                        region=region,
                        architecture=architecture,
                        additional_filters=additional_filters
                    )

                if ami_id:
                    print(f"🎯 AWS AMI dynamically resolved: {ami_id} for {image_key} in {region}")
                    return f'"{ami_id}"', "dynamic"
                else:
                    print(f"⚠️ AWS dynamic AMI resolution failed for {image_key} in {region}, falling back to data source")

            except Exception as e:
                print(f"⚠️ AWS dynamic AMI resolution error for {image_key}: {e}, falling back to data source")

        # Fallback to data source generation
        return None, None

    def generate_aws_security_group(self, sg_name, rules, region):
        """Generate AWS security group with rules for specific region."""
        clean_name = sg_name.replace("-", "_").replace(".", "_")
        clean_region = region.replace("-", "_").replace(".", "_")
        regional_sg_name = f"{clean_name}_{clean_region}"
        regional_vpc_ref = f"aws_vpc.main_vpc_{clean_region}.id"

        sg_config = f'''
# AWS Security Group: {sg_name} (Region: {region})
resource "aws_security_group" "{regional_sg_name}" {{
  name_prefix = "{sg_name}-{region}-"
  vpc_id      = {regional_vpc_ref}
  description = "Security group for {sg_name} in {region}"

'''

        # Generate ingress and egress rules
        for rule in rules:
            rule_data = self.converter.generate_native_security_group_rule(rule, 'aws')
            direction = rule_data['direction']

            rule_block = f'''  {direction} {{
    from_port   = {rule_data['from_port']}
    to_port     = {rule_data['to_port']}
    protocol    = "{rule_data['protocol']}"
    cidr_blocks = {rule_data['cidr_blocks']}
  }}

'''
            sg_config += rule_block

        sg_config += f'''  tags = {{
    Name = "{sg_name}"
    Region = "{region}"
    Environment = "agnosticd"
  }}
}}

'''
        return sg_config

    def generate_aws_vm(self, instance, index, clean_name, strategy_info, available_subnets=None, yaml_data=None):
        """Generate native AWS EC2 instance."""
        instance_name = instance.get("name", f"instance_{index}")
        image = instance.get("image", "RHEL_9_LATEST")

        # Resolve region using region/location logic
        aws_region = self.converter.resolve_instance_region(instance, "aws")

        # Use the instance type from strategy
        aws_instance_type = strategy_info['instance_type'] or 't3.medium'

        # Resolve AMI using dynamic discovery or data source
        ami_reference, resolution_type = self.resolve_aws_ami(
            image, clean_name, strategy_info['architecture'], aws_region
        )

        if not ami_reference:
            # Fallback if resolution failed
            ami_data_source = self.converter.generate_ami_data_source(image, clean_name, strategy_info['architecture'])
            ami_reference = f"data.aws_ami.{clean_name}_ami.id"
        elif resolution_type == "dynamic":
            # Dynamic resolution - no data source needed
            ami_data_source = ""
        else:
            # Data source resolution - ami_reference is the data source HCL
            ami_data_source = resolution_type or ""  # This contains the actual data source HCL
            ami_reference = f"data.aws_ami.{clean_name}_ami.id"

        # Get security groups for this instance
        sg_refs = self.converter.get_instance_security_groups(instance)

        # Convert to AWS security group references
        aws_sg_refs = []
        for sg_ref in sg_refs:
            sg_name = sg_ref.replace('.id', '')
            aws_sg_refs.append(f"aws_security_group.{sg_name}.id")

        # Get subnet for this instance
        subnet_ref = self.converter.get_instance_subnet(instance, available_subnets or {})

        # Get user data script
        user_data_script = instance.get('user_data_script') or instance.get('user_data')

        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})
        
        # Generate AWS key pair resource if SSH key is provided
        ssh_key_resources = ""
        key_name_ref = "null"
        
        if ssh_key_config and ssh_key_config.get('public_key'):
            ssh_key_name = f"{clean_name}_key_pair"
            ssh_key_resources = f'''
# AWS Key Pair for {instance_name}
resource "aws_key_pair" "{ssh_key_name}" {{
  key_name   = "{instance_name}-key"
  public_key = "{ssh_key_config['public_key']}"
  
  tags = {{
    Name = "{instance_name}-key"
    Environment = "agnosticd"
    ManagedBy = "yamlforge"
  }}
}}

'''
            key_name_ref = f"aws_key_pair.{ssh_key_name}.key_name"

        # Generate the EC2 instance
        vm_config = ami_data_source + ssh_key_resources + f'''
# AWS EC2 Instance: {instance_name}
resource "aws_instance" "{clean_name}" {{
  ami           = {ami_reference}
  instance_type = "{aws_instance_type}"'''

        # Add key name if SSH key is configured
        if key_name_ref != "null":
            vm_config += f'''
  key_name      = {key_name_ref}'''

        vm_config += f'''

  # Subnet assignment
  subnet_id = aws_subnet.{subnet_ref}.id'''

        # Add user data if provided
        if user_data_script:
            vm_config += f'''

  # User Data Script
  user_data = base64encode(<<-EOF
{user_data_script}
EOF
  )'''

        # Add security groups if any exist
        if aws_sg_refs:
            vm_config += f'''

  # Security Groups
  vpc_security_group_ids = [
    {',\n    '.join(aws_sg_refs)}
  ]'''

        vm_config += f'''

  tags = {{
    Name = "{instance_name}"
    Environment = "agnosticd"
  }}
}}
'''
        return vm_config

    def generate_aws_networking(self, deployment_name, deployment_config, region):
        """Generate AWS networking resources for specific region."""
        network_config = deployment_config.get('network', {})
        network_name = network_config.get('name', f"{deployment_name}-vpc")
        cidr_block = network_config.get('cidr_block', '10.0.0.0/16')

        clean_network_name = self.converter.clean_name(network_name)
        clean_region = region.replace("-", "_").replace(".", "_")
        regional_network_name = f"{clean_network_name}_{clean_region}"

        return f'''
# AWS VPC Network: {network_name} (Region: {region})
resource "aws_vpc" "main_vpc_{clean_region}" {{
  cidr_block = "{cidr_block}"
  tags = {{
    Name = "{network_name}-{region}"
    Region = "{region}"
  }}
}}

# AWS Subnet
resource "aws_subnet" "main_subnet_{clean_region}" {{
  vpc_id     = aws_vpc.main_vpc_{clean_region}.id
  cidr_block = "{cidr_block}"
  availability_zone = "{region}a"  # Default to first AZ
  tags = {{
    Name = "{network_name}-subnet-{region}"
    Region = "{region}"
  }}
}}

# AWS Internet Gateway
resource "aws_internet_gateway" "main_igw_{clean_region}" {{
  vpc_id = aws_vpc.main_vpc_{clean_region}.id
  tags = {{
    Name = "{network_name}-igw-{region}"
    Region = "{region}"
  }}
}}

# AWS Route Table
resource "aws_route_table" "main_rt_{clean_region}" {{
  vpc_id = aws_vpc.main_vpc_{clean_region}.id
  route {{
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main_igw_{clean_region}.id
  }}
  tags = {{
    Name = "{network_name}-rt-{region}"
    Region = "{region}"
  }}
}}

# AWS Route Table Association
resource "aws_route_table_association" "main_rta_{clean_region}" {{
  subnet_id      = aws_subnet.main_subnet_{clean_region}.id
  route_table_id = aws_route_table.main_rt_{clean_region}.id
}}
'''

    def format_aws_tags(self, tags):
        """Format tags for AWS (key-value pairs)."""
        if not tags:
            return ""

        tag_items = []
        for key, value in tags.items():
            tag_items.append(f'    {key} = "{value}"')

        return f'''
  tags = {{
{chr(10).join(tag_items)}
  }}'''

    def generate_aws_organization_from_config(self, workspace_config):
        """Generate AWS organization configuration from cloud-agnostic workspace config."""
        # AWS doesn't have a direct equivalent to resource groups or projects
        # This is a placeholder for potential AWS organization/account management
        return f'''
# AWS Organization - {workspace_config['name']}
# Note: AWS organization management typically done outside Terraform
# Consider using AWS Organizations for account hierarchy management

'''
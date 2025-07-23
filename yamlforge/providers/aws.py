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

    def __init__(self, credentials_manager=None, converter=None):
        """Initialize the instance."""
        self.credentials = credentials_manager
        self.converter = converter
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

    def find_similar_amis(self, original_pattern, owner, region, architecture='x86_64'):
        """Find similar AMIs when exact search fails, to provide helpful suggestions."""
        client = self.get_client(region)
        if client is None:
            return []
        
        suggestions = []
        
        try:
            # Try broader patterns for RHEL images
            if "RHEL" in original_pattern:
                # Extract requested version (e.g., "10.0" from "RHEL-10.0*_HVM*Access*")
                import re
                version_match = re.search(r'RHEL-(\d+)(?:\.(\d+))?', original_pattern)
                requested_major = None
                requested_minor = None
                
                if version_match:
                    requested_major = int(version_match.group(1))
                    requested_minor = int(version_match.group(2)) if version_match.group(2) else 0
                    
                    # Search for all RHEL AMIs to find the best alternatives
                    try:
                        response = client.describe_images(
                            Filters=[
                                {'Name': 'name', 'Values': ['RHEL*']},
                                {'Name': 'owner-id', 'Values': [owner]},
                                {'Name': 'state', 'Values': ['available']},
                                {'Name': 'architecture', 'Values': [architecture]}
                            ],
                            MaxResults=50
                        )
                        
                        # Parse and score all found AMIs
                        scored_amis = []
                        
                        for img in response['Images']:
                            name = img['Name']
                            
                            # Extract version from AMI name
                            ami_version_match = re.search(r'RHEL-(\d+)(?:\.(\d+))?(?:\.(\d+))?', name)
                            if ami_version_match:
                                ami_major = int(ami_version_match.group(1))
                                ami_minor = int(ami_version_match.group(2)) if ami_version_match.group(2) else 0
                                ami_patch = int(ami_version_match.group(3)) if ami_version_match.group(3) else 0
                                
                                # Calculate proximity score (lower is better)
                                major_diff = abs(requested_major - ami_major)
                                minor_diff = abs(requested_minor - ami_minor) if requested_major == ami_major else 100
                                
                                # Prefer newer versions if they're close
                                version_bonus = 0
                                if ami_major >= requested_major:
                                    version_bonus = -5  # Bonus for newer major versions
                                if ami_major == requested_major and ami_minor >= requested_minor:
                                    version_bonus = -10  # Bigger bonus for newer minor in same major
                                
                                proximity_score = (major_diff * 10) + minor_diff + version_bonus
                                
                                # Check if it's a GOLD/Access image (matches original intent)
                                is_gold_match = ("Access" in original_pattern and "Access" in name) or \
                                              ("GOLD" in original_pattern and "Access" in name) or \
                                              ("Access" not in original_pattern and "Access" not in name)
                                
                                if is_gold_match:
                                    proximity_score -= 20  # Strong preference for matching type
                                
                                scored_amis.append({
                                    'name': name,
                                    'id': img['ImageId'],
                                    'description': img.get('Description', 'N/A'),
                                    'creation_date': img['CreationDate'],
                                    'version_tuple': (ami_major, ami_minor, ami_patch),
                                    'proximity_score': proximity_score,
                                    'is_gold_match': is_gold_match
                                })
                        
                        # Sort by proximity score (best matches first), then by creation date (newest first)
                        scored_amis.sort(key=lambda x: (x['proximity_score'], x['creation_date']), reverse=False)
                        
                        # Take the top 5 suggestions
                        suggestions = scored_amis[:5]
                        
                    except Exception as e:
                        print(f"Debug: Error in improved search: {e}")
                        # Fallback to original broader search
                        base_version = str(requested_major)
                        broader_patterns = [
                            f"RHEL-{base_version}*",
                            "RHEL*"
                        ]
                        
                        for pattern in broader_patterns:
                            try:
                                response = client.describe_images(
                                    Filters=[
                                        {'Name': 'name', 'Values': [pattern]},
                                        {'Name': 'owner-id', 'Values': [owner]},
                                        {'Name': 'state', 'Values': ['available']},
                                        {'Name': 'architecture', 'Values': [architecture]}
                                    ],
                                    MaxResults=10
                                )
                                
                                for img in response['Images']:
                                    suggestions.append({
                                        'name': img['Name'],
                                        'id': img['ImageId'],
                                        'description': img.get('Description', 'N/A'),
                                        'creation_date': img['CreationDate']
                                    })
                                
                                if suggestions:
                                    break
                                    
                            except Exception:
                                continue
            
            # If still no suggestions and it was a GOLD search, try public versions
            if not suggestions and ("GOLD" in original_pattern or "Access" in original_pattern):
                try:
                    # Try public RHEL images with redhat_public owner
                    public_owner = self._get_required_config_owner('redhat_public')
                    public_pattern = original_pattern.replace("_GA", "").replace("Access", "").replace("GOLD", "").strip("*")
                    
                    response = client.describe_images(
                        Filters=[
                            {'Name': 'name', 'Values': [f"{public_pattern}*"]},
                            {'Name': 'owner-id', 'Values': [public_owner]},
                            {'Name': 'state', 'Values': ['available']},
                            {'Name': 'architecture', 'Values': [architecture]},
                            {'Name': 'is-public', 'Values': ['true']}
                        ],
                        MaxResults=5
                    )
                    
                    for img in response['Images']:
                        suggestions.append({
                            'name': img['Name'],
                            'id': img['ImageId'],
                            'description': img.get('Description', 'N/A'),
                            'creation_date': img['CreationDate'],
                            'type': 'public_alternative'
                        })
                        
                except Exception:
                    pass
                    
        except Exception as e:
            print(f"Debug: Error finding similar AMIs: {e}")
        
        # If we still have suggestions, ensure they're sorted by creation date for final ordering
        if suggestions and not any('proximity_score' in s for s in suggestions):
            suggestions.sort(key=lambda x: x['creation_date'], reverse=True)
        
        return suggestions[:5]

    def find_latest_ami(self, name_pattern, owner, region, architecture='x86_64', additional_filters=None):
        """Find the latest AMI matching the given pattern."""
        # Include additional filters in cache key for uniqueness
        filters_str = str(sorted(additional_filters or []))
        cache_key = f"{name_pattern}_{owner}_{region}_{architecture}_{hash(filters_str)}"

        # Check cache first
        if self.is_cache_valid(cache_key):
            cached_result = self.cache[cache_key]
            # Handle both old format (string) and new format (dict)
            if isinstance(cached_result, str):
                print(f"🔄 Using cached AMI: {cached_result} for pattern '{name_pattern}' in {region}")
                return {'ami_id': cached_result, 'ami_name': 'Unknown'}
            print(f"🔄 Using cached AMI: {cached_result['ami_id']} ({cached_result['ami_name']}) for pattern '{name_pattern}' in {region}")
            return cached_result

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

            # Verbose: Show detailed AMI search info
            if self.converter and hasattr(self.converter, 'verbose') and self.converter.verbose:
                print(f"[DEBUG] Verbose AMI Search: pattern='{name_pattern}', owner='{owner}', region='{region}'")
                if additional_filters:
                    print(f"[DEBUG] Additional filters: {additional_filters}")

            # Query for AMIs (no MaxResults limit to ensure we get ALL versions)
            response = client.describe_images(
                Filters=filters
                # No MaxResults - get all available AMIs to find true latest version
            )

            images = response['Images']
            
            if self.converter and hasattr(self.converter, 'verbose') and self.converter.verbose:
                print(f"[DEBUG] AWS API found {len(images)} AMI(s) matching criteria")
            
            if not images:
                
                # Try to find similar AMIs to suggest alternatives
                similar_amis = self.find_similar_amis(name_pattern, owner, region, architecture)
                if similar_amis:
                    print(f"NOTE: Found {len(similar_amis)} similar AMI(s) you might want to try:")
                    for i, ami in enumerate(similar_amis, 1):
                        ami_type = " (public alternative)" if ami.get('type') == 'public_alternative' else ""
                        print(f"   {i}. {ami['name']}{ami_type}")
                        print(f"      ID: {ami['id']}")
                
                return None

            # Sort by semantic version number for RHEL/Fedora, then by creation date
            def get_sort_key(image):
                name = image['Name']
                import re
                
                # Try to extract semantic version (e.g., "9.5.0" from "RHEL-9.5.0_HVM...")
                version_match = re.search(r'(?:RHEL|Fedora)[_-](\d+)\.(\d+)\.(\d+)', name)
                if version_match:
                    major = int(version_match.group(1))
                    minor = int(version_match.group(2))
                    patch = int(version_match.group(3))
                    # Return tuple: (major, minor, patch, creation_date) for proper sorting
                    return (major, minor, patch, image['CreationDate'])
                
                # Fallback to creation date for non-versioned images
                return (0, 0, 0, image['CreationDate'])
            
            # Sort by version (highest first), then by creation date (newest first) 
            images = sorted(images, key=get_sort_key, reverse=True)
            latest_image = images[0]

            # Cache the result (store both ID and name)
            result = {
                'ami_id': latest_image['ImageId'],
                'ami_name': latest_image['Name']
            }
            self.cache[cache_key] = result

            return result

        except Exception as e:
            print(f"Warning: Failed to find AMI with pattern '{name_pattern}': {e}")
            return None

    def resolve_rhel_ami(self, rhel_version, architecture="x86_64", is_gold=False, region=None):
        """Resolve RHEL AMI for a given version."""
        if not region:
            raise ValueError("Region must be specified for AMI resolution")

        if is_gold:
            owner_key = 'redhat_gold'
            name_pattern = f"RHEL-{rhel_version}*_HVM*Access*"
            # Add is-public=false filter for GOLD images (private AMIs)
            additional_filters = [
                {'Name': 'is-public', 'Values': ['false']}
            ]
        else:
            owner_key = 'redhat_public'
            name_pattern = f"RHEL-{rhel_version}*_HVM*"
            additional_filters = None

        owner = self._get_required_config_owner(owner_key)
        return self.find_latest_ami(name_pattern, owner, region, architecture, additional_filters)

    def resolve_ami_by_pattern(self, name_pattern, owner_key, region, architecture='x86_64', additional_filters=None):
        """Resolve AMI by pattern and owner key."""
        owner = self._get_required_config_owner(owner_key)
        result = self.find_latest_ami(name_pattern, owner, region, architecture, additional_filters)
        # Return just the AMI ID for backward compatibility
        return result['ami_id'] if result else None

    def resolve_fedora_ami(self, fedora_version=None, region=None, architecture='x86_64'):
        """Resolve Fedora AMI."""
        if not region:
            raise ValueError("Region must be specified for AMI resolution")

        if fedora_version:
            name_pattern = f"Fedora-Cloud-Base-{fedora_version}*"
        else:
            name_pattern = "Fedora-Cloud-Base-*"

        owner_key = 'fedora'
        owner = self._get_required_config_owner(owner_key)
        result = self.find_latest_ami(name_pattern, owner, region, architecture)
        # Return just the AMI ID for backward compatibility
        return result['ami_id'] if result else None


class AWSProvider:
    """AWS-specific provider implementation."""

    def __init__(self, converter):
        """Initialize the instance."""
        self.converter = converter
        self._aws_resolver = None

    def validate_aws_setup(self):
        """Validate AWS setup early - credentials, SDK, etc."""
        if not AWS_SDK_AVAILABLE:
            raise ValueError(
                            "[ERROR] AWS Provider Error: boto3 SDK not installed.\n\n"
            "To use AWS provider, install the required SDK:\n"
                "   pip install boto3\n\n"
                "Or install with AWS support:\n"
                "   pip install -r requirements-aws.txt\n\n"
                "Alternative: Use a different provider or remove AWS instances from your configuration."
            )

        # Check if credentials are available when AWS instances are being processed
        has_credentials = self.converter.credentials and self.converter.credentials.aws_config

        if not has_credentials:
            raise ValueError(
                "[ERROR] AWS Provider Error: No AWS credentials configured.\n\n"
                "NOTE: Please configure AWS credentials using one of these methods:\n\n"
                "1️⃣  AWS CLI (recommended):\n"
                "   aws configure\n\n"
                "2️⃣  Environment variables:\n"
                "   export AWS_ACCESS_KEY_ID=your-key-id\n"
                "   export AWS_SECRET_ACCESS_KEY=your-secret-key\n"
                "   export AWS_DEFAULT_REGION=us-east-1\n\n"
                "3️⃣  AWS credentials file:\n"
                "   ~/.aws/credentials\n\n"
                "4️⃣  IAM roles (for EC2 instances)\n\n"
                "📋 Alternative: Use a different provider or use Terraform data sources by setting:\n"
                "   yamlforge:\n"
                "     aws:\n"
                "       use_data_sources: true"
            )

    def get_aws_resolver(self):
        """Get AWS image resolver, creating it only when needed."""
        if self._aws_resolver is None:
            self._aws_resolver = AWSImageResolver(self.converter.credentials, self.converter)
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
        """Resolve AWS AMI using dynamic discovery or graceful failure."""
        if not region:
            raise ValueError(f"Region must be specified for AWS AMI resolution for image '{image_key}'")

        image_config = self.converter.images.get(image_key, {})
        aws_config = image_config.get('aws', {})

        # Check if this is a pattern-based RHEL image (RHEL 10+)
        if not aws_config:
            pattern_config = self.converter.generate_rhel_pattern_config(image_key)
            if pattern_config:
                aws_config = pattern_config
                # Simple search notification - details available in verbose mode
            else:
                # No AWS config found - check if user wants graceful fallback
                yamlforge_config = self.converter.current_yaml_data.get('yamlforge', {})
                aws_yamlforge_config = yamlforge_config.get('aws', {})
                use_data_sources = aws_yamlforge_config.get('use_data_sources', False)
                
                if use_data_sources:
                    print(f"ℹ️  Using Terraform data source for {image_key} (use_data_sources enabled)")
                    return None, None
                else:
                    raise ValueError(
                        f"[ERROR] AWS AMI Configuration Error: No configuration found for image '{image_key}'.\n\n"
                        f"NOTE: Please choose one of these solutions:\n\n"
                        f"1️⃣  Add image mapping to mappings/images.yaml:\n"
                        f"   {image_key}:\n"
                        f"     aws:\n"
                        f"       name_pattern: \"RHEL-9*_HVM*\"\n"
                        f"       owner_key: \"redhat_public\"\n\n"
                        f"2️⃣  Use a predefined image name from mappings/images.yaml\n\n"
                        f"3️⃣  Enable Terraform data source fallback:\n"
                        f"   yamlforge:\n"
                        f"     aws:\n"
                        f"       use_data_sources: true\n\n"
                        f"4️⃣  Use a different cloud provider"
                    )

        # Validate AWS setup before attempting AMI resolution
        self.validate_aws_setup()

        # Use dynamic discovery
        try:
            ami_id = None

            # Handle different image types
            if "RHEL" in image_key.upper():
                # RHEL images
                rhel_version, arch = self.converter.extract_rhel_info(image_key)
                is_gold_image = "GOLD" in image_key.upper() or "BYOS" in image_key.upper()
                
                if is_gold_image:
                    name_pattern = f"RHEL-{rhel_version}*_HVM*Access*"
                    owner_key = 'redhat_gold'
                    additional_filters = [{'Name': 'is-public', 'Values': ['false']}]
                else:
                    name_pattern = f"RHEL-{rhel_version}*_HVM*"
                    owner_key = 'redhat_public'
                    additional_filters = None

                ami_result = self.get_aws_resolver().find_latest_ami(
                    name_pattern=name_pattern,
                    owner=self.get_aws_resolver()._get_required_config_owner(owner_key),
                    region=region,
                    architecture=architecture,
                    additional_filters=additional_filters
                )
            elif "FEDORA" in image_key.upper():
                # Fedora images
                fedora_version = self.converter.extract_fedora_version(image_key)
                
                if fedora_version:
                    name_pattern = f"Fedora-Cloud-Base-{fedora_version}*"
                else:
                    name_pattern = "Fedora-Cloud-Base-*"

                ami_result = self.get_aws_resolver().find_latest_ami(
                    name_pattern=name_pattern,
                    owner=self.get_aws_resolver()._get_required_config_owner('fedora'),
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

                # Get both AMI ID and name for better output
                ami_result = self.get_aws_resolver().find_latest_ami(
                    name_pattern=name_pattern,
                    owner=self.get_aws_resolver()._get_required_config_owner(owner_key),
                    region=region,
                    architecture=architecture,
                    additional_filters=additional_filters
                )
            else:
                # Fallback for other image types - try generic resolution
                ami_result = None

            if ami_result and ami_result.get('ami_id'):
                ami_id = ami_result['ami_id']
                ami_name = ami_result['ami_name']
                
                # Check if this exact result was already shown to avoid duplicate output
                result_key = f"{ami_id}_{image_key}_{region}"
                if not hasattr(self, '_recent_results'):
                    self._recent_results = set()
                
                if result_key not in self._recent_results:
                    print(f"Dynamic image search for {instance_name} on aws for {image_key} in {region} results in {ami_id}")
                    if self.converter and hasattr(self.converter, 'verbose') and self.converter.verbose:
                        print(f"  Verbose: {ami_name}")
                    self._recent_results.add(result_key)
                
                return f'"{ami_id}"', "dynamic"
            else:
                # AMI resolution failed - check if user wants graceful fallback
                yamlforge_config = self.converter.current_yaml_data.get('yamlforge', {})
                aws_yamlforge_config = yamlforge_config.get('aws', {})
                use_data_sources = aws_yamlforge_config.get('use_data_sources', False)
                
                if use_data_sources:
                    print(f"WARNING: AWS AMI resolution failed for {image_key}, falling back to Terraform data source (use_data_sources enabled)")
                    return None, None
                else:
                    raise ValueError(self._generate_smart_aws_error('ami_resolution_failed', image_key, region))

        except Exception as e:
            # Check if user wants graceful fallback for errors
            yamlforge_config = self.converter.current_yaml_data.get('yamlforge', {})
            aws_yamlforge_config = yamlforge_config.get('aws', {})
            use_data_sources = aws_yamlforge_config.get('use_data_sources', False)
            
            if use_data_sources:
                print(f"WARNING: AWS AMI resolution error for {image_key}: {e}, falling back to Terraform data source (use_data_sources enabled)")
                return None, None
            else:
                if "Unable to locate credentials" in str(e):
                    raise ValueError(self._generate_smart_aws_error('credentials_error', image_key, region, e)) from e
                else:
                    # If original error contains "find AMI", it's likely an AMI resolution issue
                    if "find AMI" in str(e) or "No AMI" in str(e) or "AMI" in str(e):
                        raise ValueError(self._generate_smart_aws_error('ami_resolution_failed', image_key, region, e)) from e
                    else:
                        raise ValueError(self._generate_smart_aws_error('general_error', image_key, region, e)) from e

    def generate_aws_security_group(self, sg_name, rules, region, yaml_data=None):
        """Generate AWS security group."""
        clean_name = sg_name.replace("-", "_").replace(".", "_")
        clean_region = region.replace("-", "_").replace(".", "_")
        guid = self.converter.get_validated_guid(yaml_data)
        regional_sg_name = f"{clean_name}_{clean_region}"

        # Generate security group resource
        security_group_config = f'''
# AWS Security Group: {sg_name} (Region: {region})
resource "aws_security_group" "{regional_sg_name}_{guid}" {{
  name_prefix = "{sg_name}-{region}-"
  description = "Security group for {sg_name} in {region}"
  vpc_id      = local.vpc_id_{clean_region}_{guid}

'''

        # Generate ingress and egress rules
        for rule in rules:
            rule_data = self.converter.generate_native_security_group_rule(rule, 'aws')
            direction = rule_data['direction']

            rule_block = f'''  {direction} {{
    from_port   = {rule_data['from_port']}
    to_port     = {rule_data['to_port']}
    protocol    = "{rule_data['protocol']}"
    cidr_blocks = {self.format_cidr_blocks_hcl(rule_data['cidr_blocks'])}
  }}

'''
            security_group_config += rule_block

        security_group_config += f'''  tags = {{
    Name = "{sg_name}"
    Region = "{region}"
    Environment = "{yaml_data.get('environment', 'unknown') if yaml_data else 'unknown'}"
    ManagedBy = "yamlforge"
  }}
}}

'''
        return security_group_config

    def generate_aws_vm(self, instance, index, clean_name, strategy_info, available_subnets=None, yaml_data=None):
        """Generate AWS EC2 instance."""
        instance_name = instance.get("name", f"instance_{index}")
        image = instance.get("image", "RHEL_9_LATEST")

        # Resolve region using region/location logic
        aws_region = self.converter.resolve_instance_region(instance, "aws")

        # Use the instance type from strategy
        aws_instance_type = strategy_info['instance_type'] or 't3.medium'
        
        # Get GUID for consistent naming
        guid = self.converter.get_validated_guid(yaml_data)

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

        # Get security group references with regional awareness
        aws_sg_refs = []
        sg_names = instance.get('security_groups', [])
        for sg_name in sg_names:
            # Generate regional security group reference with GUID
            clean_sg = sg_name.replace("-", "_").replace(".", "_")
            clean_region = aws_region.replace("-", "_").replace(".", "_")
            aws_sg_refs.append(f"aws_security_group.{clean_sg}_{clean_region}_{guid}.id")

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
            ssh_key_name = f"{clean_name}_key_pair_{guid}"
            ssh_key_resources = f'''
# AWS Key Pair for {instance_name}
resource "aws_key_pair" "{ssh_key_name}" {{
  key_name   = "{instance_name}-key"
  public_key = "{ssh_key_config['public_key']}"
  
  tags = {{
    Name = "{instance_name}-key"
    Environment = "{yaml_data.get('environment', 'unknown') if yaml_data else 'unknown'}"
    ManagedBy = "yamlforge"
  }}
}}

'''
            key_name_ref = f"aws_key_pair.{ssh_key_name}.key_name"

        # Generate the instance configuration
        instance_config = ami_data_source + ssh_key_resources + f'''
# AWS EC2 Instance: {instance_name}
resource "aws_instance" "{clean_name}_{guid}" {{
  ami           = {ami_reference}
  instance_type = "{aws_instance_type}"'''

        # Add key name if SSH key is configured
        if key_name_ref != "null":
            instance_config += f'''
  key_name      = {key_name_ref}'''

        instance_config += f'''

  # Subnet assignment (uses first public subnet for backwards compatibility)
  subnet_id = local.vpc_subnet_id_{aws_region.replace("-", "_").replace(".", "_")}_{guid}'''

        # Add user data if provided
        if user_data_script:
            instance_config += f'''

  # User Data Script
  user_data = base64encode(<<-EOF
{user_data_script}
EOF
  )'''

        # Add security groups if any exist
        if aws_sg_refs:
            instance_config += f'''

  # Security Groups
  vpc_security_group_ids = [
    {',\n    '.join(aws_sg_refs)}
  ]'''

        instance_config += f'''

  tags = {{
    Name = "{instance_name}"
    Environment = "{yaml_data.get('environment', 'unknown') if yaml_data else 'unknown'}"
    ManagedBy = "yamlforge"
  }}
}}
'''
        return instance_config

    def generate_aws_networking(self, deployment_name, deployment_config, region, yaml_data=None):
        """Generate AWS networking resources for specific region."""
        network_config = deployment_config.get('network', {})
        network_name = network_config.get('name', f"{deployment_name}-vpc")
        cidr_block = network_config.get('cidr_block', '10.0.0.0/16')
        
        clean_network_name = self.converter.clean_name(network_name)
        clean_region = region.replace("-", "_").replace(".", "_")
        guid = self.converter.get_validated_guid(yaml_data)

        # Generate VPC resource
        networking_config = f'''
# AWS VPC: {network_name} (Region: {region})
resource "aws_vpc" "main_vpc_{clean_region}_{guid}" {{
  cidr_block           = "{cidr_block}"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {{
    Name = "{network_name}-{region}"
    Environment = "{yaml_data.get('environment', 'unknown') if yaml_data else 'unknown'}"
    ManagedBy = "yamlforge"
  }}
}}

# Local to reference VPC consistently  
locals {{
  vpc_id_{clean_region}_{guid} = aws_vpc.main_vpc_{clean_region}_{guid}.id
  vpc_cidr_{clean_region}_{guid} = aws_vpc.main_vpc_{clean_region}_{guid}.cidr_block
}}

'''
        
        # Generate ROSA-compatible multi-AZ subnets
        networking_config += self.generate_rosa_compatible_subnets(network_name, cidr_block, region, guid, yaml_data)
        
        # Generate Internet Gateway and Route Table
        networking_config += f'''
# AWS Internet Gateway
resource "aws_internet_gateway" "main_igw_{clean_region}_{guid}" {{
  vpc_id = local.vpc_id_{clean_region}_{guid}

  tags = {{
    Name = "{network_name}-igw-{region}"
    Environment = "{yaml_data.get('environment', 'unknown') if yaml_data else 'unknown'}"
    ManagedBy = "yamlforge"
  }}
}}

# AWS Route Table
resource "aws_route_table" "main_rt_{clean_region}_{guid}" {{
  vpc_id = local.vpc_id_{clean_region}_{guid}

  route {{
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main_igw_{clean_region}_{guid}.id
  }}

  tags = {{
    Name = "{network_name}-rt-{region}"
    Environment = "{yaml_data.get('environment', 'unknown') if yaml_data else 'unknown'}"
    ManagedBy = "yamlforge"
  }}
}}

# AWS Route Table Association
resource "aws_route_table_association" "main_rta_{clean_region}_{guid}" {{
  subnet_id      = local.vpc_subnet_id_{clean_region}_{guid}
  route_table_id = aws_route_table.main_rt_{clean_region}_{guid}.id
}}
'''
        
        return networking_config

    def generate_rosa_compatible_subnets(self, network_name, cidr_block, region, guid, yaml_data=None):
        """Generate ROSA-compatible multi-AZ subnets (minimum 2 for public clusters)."""
        clean_region = region.replace("-", "_").replace(".", "_")
        
        # Use Terraform data source to get actual available AZs for the region
        subnet_config = f'''
# Get available availability zones for {region}
data "aws_availability_zones" "available_{clean_region}_{guid}" {{
  filter {{
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }}
  state = "available"
}}

# ROSA-compatible multi-AZ public subnets (minimum 2 required for hosted clusters)
# Dynamic subnet creation based on available AZs
'''
        
        # Split CIDR block into smaller subnets
        import ipaddress
        try:
            vpc_network = ipaddress.IPv4Network(cidr_block, strict=False)
            # Create /24 subnets from the VPC CIDR (e.g., 10.0.0.0/16 -> 10.0.0.0/24, 10.0.1.0/24, etc.)
            subnets = list(vpc_network.subnets(new_prefix=24))
        except:
            # Fallback to manual calculation if ipaddress fails
            base_octets = cidr_block.split('/')[0].split('.')
            subnets = [f"{base_octets[0]}.{base_octets[1]}.{i}.0/24" for i in range(6)]  # Generate up to 6 subnets
        
        # Generate optimal number of subnets (3 for good HA, minimum 2 for ROSA)
        # Choose intelligently from available AZs
        subnet_config += f'''
# Local values to select optimal AZs  
locals {{
  # Select up to 3 AZs for good HA (use what's available, maximum 3)
  # ROSA clusters need minimum 2 AZs, but that's validated at cluster level
  selected_az_count_{clean_region}_{guid} = min(length(data.aws_availability_zones.available_{clean_region}_{guid}.names), 3)
  selected_azs_{clean_region}_{guid} = slice(data.aws_availability_zones.available_{clean_region}_{guid}.names, 0, local.selected_az_count_{clean_region}_{guid})
}}

# Public subnets - create 2-3 subnets across selected AZs (optimal for HA without over-provisioning)
resource "aws_subnet" "public_subnet_{clean_region}_{guid}" {{
  count = local.selected_az_count_{clean_region}_{guid}
  
  vpc_id                  = local.vpc_id_{clean_region}_{guid}
  cidr_block              = cidrsubnet(local.vpc_cidr_{clean_region}_{guid}, 8, count.index)
  availability_zone       = local.selected_azs_{clean_region}_{guid}[count.index]
  map_public_ip_on_launch = true

  tags = {{
    Name = "{network_name}-public-${{count.index + 1}}-${{local.selected_azs_{clean_region}_{guid}[count.index]}}"
    Environment = "{yaml_data.get('environment', 'unknown') if yaml_data else 'unknown'}"
    ManagedBy = "yamlforge"
    "kubernetes.io/role/elb" = "1"  # Required for AWS Load Balancer Controller
  }}
}}
'''
        
        # Create local values for subnet IDs (ROSA provider needs these)
        subnet_config += f'''
# Local values for ROSA subnet references
locals {{
  public_subnet_ids_{clean_region}_{guid} = aws_subnet.public_subnet_{clean_region}_{guid}[*].id
  
  # Availability zones for ROSA clusters (selected optimal AZs)
  region_azs_{clean_region}_{guid} = local.selected_azs_{clean_region}_{guid}
  
  # Primary subnet for non-ROSA resources (backwards compatibility)
  vpc_subnet_id_{clean_region}_{guid} = aws_subnet.public_subnet_{clean_region}_{guid}[0].id
}}

# Outputs for ROSA script access
output "public_subnet_ids_{clean_region}_{guid}" {{
  description = "Public subnet IDs for ROSA clusters in {region}"
  value       = local.public_subnet_ids_{clean_region}_{guid}
}}

output "region_azs_{clean_region}_{guid}" {{
  description = "Availability zones for ROSA clusters in {region}"
  value       = local.region_azs_{clean_region}_{guid}
}}
'''
        
        return subnet_config

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

    def _check_aws_credentials_status(self):
        """Check AWS credentials availability and return specific status info."""
        try:
            import boto3
            from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
            
            # Try to create a session and make a simple call to test credentials
            try:
                session = boto3.Session()
                # Use STS to verify credentials - lightweight call
                sts = session.client('sts')
                response = sts.get_caller_identity()
                return {
                    'available': True,
                    'account_id': response.get('Account'),
                    'user_arn': response.get('Arn'),
                    'issue': None
                }
            except NoCredentialsError:
                return {
                    'available': False,
                    'issue': 'no_credentials',
                    'message': 'No AWS credentials found'
                }
            except PartialCredentialsError as e:
                return {
                    'available': False,
                    'issue': 'partial_credentials',
                    'message': f'Incomplete AWS credentials: {e}'
                }
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                if error_code in ['InvalidUserID.NotFound', 'AccessDenied']:
                    return {
                        'available': False,
                        'issue': 'invalid_credentials',
                        'message': f'Invalid or expired AWS credentials: {error_code}'
                    }
                else:
                    return {
                        'available': False,
                        'issue': 'permission_error',
                        'message': f'AWS permission error: {e}'
                    }
            except Exception as e:
                return {
                    'available': False,
                    'issue': 'connection_error',
                    'message': f'AWS connection error: {e}'
                }
        except ImportError:
            return {
                'available': False,
                'issue': 'no_sdk',
                'message': 'boto3 SDK not installed'
            }

    def _generate_smart_aws_error(self, context, image_key=None, region=None, original_error=None):
        """Generate intelligent, consolidated AWS error message based on actual conditions."""
        # Check actual credential status
        cred_status = self._check_aws_credentials_status()
        
        # Check if fallback mode is enabled
        yamlforge_config = self.converter.current_yaml_data.get('yamlforge', {})
        aws_yamlforge_config = yamlforge_config.get('aws', {})
        use_data_sources = aws_yamlforge_config.get('use_data_sources', False)
        
        # Build error message based on context and actual conditions
        if context == 'ami_resolution_failed':
            error_title = f"[ERROR] AWS AMI Resolution Failed: No AMI found for '{image_key}' in region '{region}'"
        elif context == 'credentials_error':
            error_title = f"[ERROR] AWS Credentials Error"
        else:
            error_title = f"[ERROR] AWS Error"
        
        error_msg = f"{error_title}\n\n"
        
        # Add specific guidance based on credential status
        if not cred_status['available']:
            if cred_status['issue'] == 'no_sdk':
                error_msg += "🔧 SDK Issue: boto3 not installed\n"
                error_msg += "NOTE: To fix: pip install boto3\n\n"
            elif cred_status['issue'] == 'no_credentials':
                error_msg += "[CREDS] Credential Status: No AWS credentials found\n"
                error_msg += "NOTE: To fix, choose one method:\n"
                error_msg += "   • Run: aws configure\n"
                error_msg += "   • Set: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY env vars\n"
                error_msg += "   • Use: IAM roles or AWS profiles\n\n"
            elif cred_status['issue'] == 'partial_credentials':
                error_msg += f"[CREDS] Credential Status: {cred_status['message']}\n"
                error_msg += "NOTE: To fix: Ensure both access key and secret key are set\n\n"
            elif cred_status['issue'] == 'invalid_credentials':
                error_msg += f"[CREDS] Credential Status: {cred_status['message']}\n"
                error_msg += "NOTE: To fix: Check credentials are valid and not expired\n\n"
            elif cred_status['issue'] == 'permission_error':
                error_msg += f"[CREDS] Credential Status: {cred_status['message']}\n"
                error_msg += "NOTE: To fix: Check IAM permissions for EC2 and required services\n\n"
            elif cred_status['issue'] == 'connection_error':
                error_msg += f"🌐 Connection Status: {cred_status['message']}\n"
                error_msg += "NOTE: To fix: Check internet connectivity and AWS service status\n\n"
        else:
            # Credentials are working, so the issue is likely image-specific
            error_msg += f"[CREDS] Credential Status: [OK] Valid (Account: {cred_status['account_id']})\n"
            if context == 'ami_resolution_failed':
                error_msg += f"[DEBUG] Issue: No AMI found matching pattern for '{image_key}' in region '{region}'\n"
                
                # Try to provide more specific guidance based on the image type
                if "GOLD" in image_key.upper() or "BYOS" in image_key.upper():
                    error_msg += "NOTE: RHEL GOLD/BYOS images require:\n"
                    error_msg += "   • Red Hat Cloud Access subscription\n"
                    error_msg += "   • Proper entitlement in the target region\n"
                    error_msg += "   • May not be available in all regions\n"
                    error_msg += "   • Try: RHEL9-latest (public AMI) or different region\n\n"
                elif "RHEL" in image_key.upper():
                    error_msg += "NOTE: RHEL image not found - try:\n"
                    error_msg += "   • Different RHEL version (RHEL9-latest, RHEL8-latest)\n"
                    error_msg += "   • Check if region supports this RHEL version\n"
                    error_msg += "   • Verify image name in mappings/images.yaml\n\n"
                else:
                    error_msg += "NOTE: Image not found - check:\n"
                    error_msg += "   • Image name spelling and availability\n"
                    error_msg += "   • Region support for this image\n"
                    error_msg += "   • Available images in mappings/images.yaml\n\n"
            else:
                error_msg += "NOTE: Check: AWS service availability and regional access\n\n"
        
        # Always offer fallback mode as an alternative
        if not use_data_sources:
            error_msg += "🔄 Alternative: Enable Terraform data source fallback\n"
            error_msg += "   Add to your YAML:\n"
            error_msg += "   yamlforge:\n"
            error_msg += "     aws:\n"
            error_msg += "       use_data_sources: true\n\n"
        
        error_msg += "🌐 Or: Use a different cloud provider"
        
        return error_msg
    
    def format_cidr_blocks_hcl(self, cidr_blocks):
        """Convert Python list of CIDR blocks to proper Terraform HCL syntax."""
        if isinstance(cidr_blocks, list):
            # Convert each item to quoted string and join with commas
            formatted_blocks = ', '.join(f'"{block}"' for block in cidr_blocks)
            return f'[{formatted_blocks}]'
        elif isinstance(cidr_blocks, str):
            return f'["{cidr_blocks}"]'
        else:
            return '["0.0.0.0/0"]'

    def generate_rosa_sts_roles(self, yaml_data=None):
        """Generate IAM roles required for ROSA STS clusters."""
        guid = self.converter.get_validated_guid(yaml_data)
        
        terraform_config = f'''
# =============================================================================
# ROSA STS IAM ROLES - Automatically generated by YamlForge
# =============================================================================
# These roles allow Red Hat OpenShift Service on AWS (ROSA) to manage clusters
# in your AWS account using AWS Security Token Service (STS).

# ROSA Installer Role - Used by Red Hat OCM to create and manage clusters
resource "aws_iam_role" "rosa_installer_role" {{
  name = "ManagedOpenShift-Installer-Role"
  
  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Effect = "Allow"
        Principal = {{
          AWS = "arn:aws:iam::710019948333:root"
        }}
        Action = "sts:AssumeRole"
        Condition = {{
          StringEquals = {{
            "sts:ExternalId" = [
              data.aws_caller_identity.current.account_id
            ]
          }}
        }}
      }}
    ]
  }})

  tags = {{
    Name = "ROSA Installer Role"
    ManagedBy = "yamlforge"
    Environment = var.environment
    "red.hat.managed" = "true"
  }}
}}

# Attach AWS managed policy for ROSA Installer
resource "aws_iam_role_policy_attachment" "rosa_installer_policy" {{
  role       = aws_iam_role.rosa_installer_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/ROSAInstallerPolicy"
}}

# ROSA Support Role - Used by Red Hat support for troubleshooting
resource "aws_iam_role" "rosa_support_role" {{
  name = "ManagedOpenShift-Support-Role"
  
  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Effect = "Allow"
        Principal = {{
          AWS = "arn:aws:iam::710019948333:root"
        }}
        Action = "sts:AssumeRole"
        Condition = {{
          StringEquals = {{
            "sts:ExternalId" = [
              data.aws_caller_identity.current.account_id
            ]
          }}
        }}
      }}
    ]
  }})

  tags = {{
    Name = "ROSA Support Role"
    ManagedBy = "yamlforge"
    Environment = var.environment
    "red.hat.managed" = "true"
  }}
}}

# Attach AWS managed policy for ROSA Support
resource "aws_iam_role_policy_attachment" "rosa_support_policy" {{
  role       = aws_iam_role.rosa_support_role.name
  policy_arn = "arn:aws:iam::aws:policy/job-function/ViewOnlyAccess"
}}

# Additional support policy for cluster access
resource "aws_iam_role_policy_attachment" "rosa_support_policy_additional" {{
  role       = aws_iam_role.rosa_support_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/ROSASRESupportPolicy"
}}

# ROSA Worker Role - Used by worker nodes in the cluster
resource "aws_iam_role" "rosa_worker_role" {{
  name = "ManagedOpenShift-Worker-Role"
  
  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Effect = "Allow"
        Principal = {{
          Service = "ec2.amazonaws.com"
        }}
        Action = "sts:AssumeRole"
      }}
    ]
  }})

  tags = {{
    Name = "ROSA Worker Role"
    ManagedBy = "yamlforge"
    Environment = var.environment
    "red.hat.managed" = "true"
  }}
}}

# Attach AWS managed policies for ROSA Worker nodes
resource "aws_iam_role_policy_attachment" "rosa_worker_policy_1" {{
  role       = aws_iam_role.rosa_worker_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}}

resource "aws_iam_role_policy_attachment" "rosa_worker_policy_2" {{
  role       = aws_iam_role.rosa_worker_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/ROSAWorkerInstancePolicy"
}}

# Instance profile for worker nodes
resource "aws_iam_instance_profile" "rosa_worker_profile" {{
  name = "ManagedOpenShift-Worker-Role"
  role = aws_iam_role.rosa_worker_role.name

  tags = {{
    Name = "ROSA Worker Instance Profile"
    ManagedBy = "yamlforge"
    Environment = var.environment
    "red.hat.managed" = "true"
  }}
}}

# ROSA Control Plane Role - Used by control plane nodes (Classic clusters only)
resource "aws_iam_role" "rosa_master_role" {{
  name = "ManagedOpenShift-ControlPlane-Role"
  
  assume_role_policy = jsonencode({{
    Version = "2012-10-17"
    Statement = [
      {{
        Effect = "Allow"
        Principal = {{
          Service = "ec2.amazonaws.com"
        }}
        Action = "sts:AssumeRole"
      }}
    ]
  }})

  tags = {{
    Name = "ROSA Control Plane Role"
    ManagedBy = "yamlforge"
    Environment = var.environment
    "red.hat.managed" = "true"
  }}
}}

# Note: ROSA Classic control plane nodes use EC2 service principal
# and do not require a specific AWS managed policy attachment

# Instance profile for control plane nodes
resource "aws_iam_instance_profile" "rosa_master_profile" {{
  name = "ManagedOpenShift-ControlPlane-Role"
  role = aws_iam_role.rosa_master_role.name

  tags = {{
    Name = "ROSA Control Plane Instance Profile"
    ManagedBy = "yamlforge"
    Environment = var.environment
    "red.hat.managed" = "true"
  }}
}}

# =============================================================================
# ROSA STS ROLE OUTPUTS
# =============================================================================

output "rosa_installer_role_arn" {{
  description = "ARN of the ROSA Installer Role"
  value       = aws_iam_role.rosa_installer_role.arn
}}

output "rosa_support_role_arn" {{
  description = "ARN of the ROSA Support Role"
  value       = aws_iam_role.rosa_support_role.arn
}}

output "rosa_worker_role_arn" {{
  description = "ARN of the ROSA Worker Role"
  value       = aws_iam_role.rosa_worker_role.arn
}}

output "rosa_master_role_arn" {{
  description = "ARN of the ROSA Control Plane Role"
  value       = aws_iam_role.rosa_master_role.arn
}}

'''
        return terraform_config

    def generate_rosa_operator_roles(self, cluster_name, region, guid, yaml_data=None):
        """Generate cluster-specific operator roles for ROSA clusters."""
        
        terraform_config = f'''
# =============================================================================
# ROSA OPERATOR ROLES - Cluster Specific (Automated Terraform Generation)
# =============================================================================
# These roles are used by OpenShift operators within the ROSA cluster

# Local variables for operator role configuration
locals {{
  operator_role_prefix = "{cluster_name}"
  oidc_config_id      = rhcs_rosa_oidc_config.oidc_config.id
}}

# Cluster-specific operator roles (automatically created)
resource "rhcs_rosa_operator_roles" "operator_roles" {{
  operator_role_prefix = local.operator_role_prefix
  oidc_config_id      = local.oidc_config_id
  account_role_prefix = "ManagedOpenShift"
  
  depends_on = [
    rhcs_rosa_oidc_config.oidc_config,
    aws_iam_role.rosa_installer_role,
    aws_iam_role.rosa_support_role,
    aws_iam_role.rosa_worker_role,
    aws_iam_role.rosa_master_role
  ]
  
  tags = {{
    Environment = var.environment
    ManagedBy = "yamlforge"
    "red.hat.managed" = "true"
    Cluster = "{cluster_name}"
  }}
}}

'''
        return terraform_config

    def generate_rosa_oidc_config(self, cluster_name, region, guid, yaml_data=None):
        """Generate OIDC configuration for ROSA cluster authentication."""
        
        terraform_config = f'''
# =============================================================================
# ROSA OIDC CONFIGURATION (Automated Terraform Generation)
# =============================================================================
# OpenID Connect configuration required for ROSA cluster authentication

# OIDC Configuration for cluster authentication
resource "rhcs_rosa_oidc_config" "oidc_config" {{
  managed = true
  
  tags = {{
    Environment = var.environment
    ManagedBy = "yamlforge"
    "red.hat.managed" = "true"
    Cluster = "{cluster_name}"
  }}
}}

# Output OIDC configuration details
output "oidc_config_id" {{
  description = "ID of the ROSA OIDC configuration"
  value       = rhcs_rosa_oidc_config.oidc_config.id
}}

output "oidc_endpoint_url" {{
  description = "OIDC endpoint URL for the cluster"
  value       = rhcs_rosa_oidc_config.oidc_config.oidc_endpoint_url
}}

'''
        return terraform_config

    def generate_rosa_cluster_resource(self, cluster_config, region, guid, yaml_data=None):
        """Generate the ROSA cluster resource with all required dependencies."""
        
        cluster_name = cluster_config.get('name', 'rosa-cluster')
        instance_type = cluster_config.get('instance_type', 'm5.xlarge')
        replicas = cluster_config.get('replicas', 2)
        version = cluster_config.get('openshift_version', '4.14')
        multi_az = cluster_config.get('multi_az', False)
        
        # Determine availability zones
        if multi_az:
            availability_zones = f'slice(local.selected_azs_{region}_{guid}, 0, 3)'
        else:
            availability_zones = f'[local.selected_azs_{region}_{guid}[0]]'
        
        terraform_config = f'''
# =============================================================================
# ROSA CLUSTER RESOURCE (Automated Terraform Generation)
# =============================================================================
# Red Hat OpenShift Service on AWS cluster with full STS integration

# ROSA Classic Cluster
resource "rhcs_cluster_rosa_classic" "{cluster_name.replace('-', '_')}" {{
  name               = "{cluster_name}"
  cloud_region       = "{region}"
  aws_account_id     = data.aws_caller_identity.current.account_id
  
  # OpenShift Configuration
  version                = "{version}"
  channel_group         = "stable"
  compute_machine_type  = "{instance_type}"
  replicas              = {replicas}
  
  # Multi-AZ Configuration
  multi_az           = {str(multi_az).lower()}
  availability_zones = {availability_zones}
  
  # Network Configuration
  aws_subnet_ids = local.public_subnet_ids_{region}_{guid}
  machine_cidr   = local.vpc_cidr_{region}_{guid}
  
  # STS Role Configuration (automatically referenced)
  sts = {{
    role_arn               = aws_iam_role.rosa_installer_role.arn
    support_role_arn      = aws_iam_role.rosa_support_role.arn
    instance_iam_roles = {{
      master_role_arn = aws_iam_role.rosa_master_role.arn
      worker_role_arn = aws_iam_role.rosa_worker_role.arn
    }}
    operator_role_prefix = local.operator_role_prefix
    oidc_config_id      = rhcs_rosa_oidc_config.oidc_config.id
  }}
  
  # Cluster Properties
  properties = {{
    rosa_creator_arn = data.aws_caller_identity.current.arn
  }}
  
  # Dependencies - ensure all prerequisites are created first
  depends_on = [
    aws_iam_role.rosa_installer_role,
    aws_iam_role.rosa_support_role,
    aws_iam_role.rosa_worker_role,
    aws_iam_role.rosa_master_role,
    rhcs_rosa_oidc_config.oidc_config,
    rhcs_rosa_operator_roles.operator_roles,
    aws_vpc.main_vpc_{region}_{guid},
    aws_subnet.public_subnet_{region}_{guid}
  ]
  
  tags = {{
    Environment = var.environment
    ManagedBy = "yamlforge"
    "red.hat.managed" = "true"
    Region = "{region}"
  }}
  
  # Lifecycle management
  lifecycle {{
    prevent_destroy = true
  }}
}}

# Cluster outputs
output "{cluster_name.replace('-', '_')}_cluster_id" {{
  description = "ROSA cluster ID"
  value       = rhcs_cluster_rosa_classic.{cluster_name.replace('-', '_')}.id
}}

output "{cluster_name.replace('-', '_')}_cluster_state" {{
  description = "ROSA cluster state"
  value       = rhcs_cluster_rosa_classic.{cluster_name.replace('-', '_')}.state
}}

output "{cluster_name.replace('-', '_')}_api_url" {{
  description = "ROSA cluster API URL"
  value       = rhcs_cluster_rosa_classic.{cluster_name.replace('-', '_')}.api_url
}}

output "{cluster_name.replace('-', '_')}_console_url" {{
  description = "ROSA cluster console URL"
  value       = rhcs_cluster_rosa_classic.{cluster_name.replace('-', '_')}.console_url
}}

'''
        return terraform_config

    def generate_rosa_required_providers(self):
        """Generate required providers for ROSA cluster management."""
        
        terraform_config = '''
# =============================================================================
# ROSA TERRAFORM PROVIDERS (Required for Automated ROSA Management)
# =============================================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    rhcs = {
      source  = "terraform-redhat/rhcs"
      version = ">= 1.4.0"
    }
  }
  required_version = ">= 1.0"
}

# Configure the Red Hat Cloud Services provider
provider "rhcs" {
  # Configuration will be provided via environment variables:
  # RHCS_TOKEN or RHCS_CLIENT_ID + RHCS_CLIENT_SECRET
  # RHCS_URL (defaults to https://api.openshift.com)
}

'''
        return terraform_config
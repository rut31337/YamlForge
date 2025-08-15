"""
AWS Provider Module

Contains AWS-specific implementations for image resolution, VM generation,
networking, security groups, and other AWS cloud resources.
"""

import yaml
from pathlib import Path
import os # Added for create_rosa_account_roles_via_cli
from ..utils import find_yamlforge_file

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
        try:
            defaults_file = find_yamlforge_file("defaults/aws.yaml")
        except FileNotFoundError as e:
            raise Exception(f"Required AWS defaults file not found: defaults/aws.yaml")

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

        # Check if credentials are available for dynamic discovery (skip in no-credentials mode)
        if self.converter and self.converter.no_credentials:
            has_credentials = False
            print("  NO-CREDENTIALS MODE: Skipping AWS credential discovery in image resolver")
        else:
            has_credentials = self.credentials and self.credentials.get_aws_credentials()

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

            # Create EC2 client with timeout configuration to prevent hanging
            from botocore.config import Config
            config = Config(
                connect_timeout=10,  # Connection timeout in seconds
                read_timeout=30,     # Read timeout in seconds  
                retries={'max_attempts': 3, 'mode': 'adaptive'}
            )
            client = session.client('ec2', region_name=region, config=config)
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
            pass
        
        # If we still have suggestions, ensure they're sorted by creation date for final ordering
        if suggestions and not any('proximity_score' in s for s in suggestions):
            suggestions.sort(key=lambda x: x['creation_date'], reverse=True)
        
        return suggestions[:5]

    def find_latest_ami(self, name_pattern, owner, region, architecture='x86_64', additional_filters=None, instance_name=None, image_key=None):
        """Find the latest AMI matching the given pattern."""
        # Include additional filters in cache key for uniqueness
        filters_str = str(sorted(additional_filters or []))
        cache_key = f"{name_pattern}_{owner}_{region}_{architecture}_{hash(filters_str)}"

        # Check cache first
        if self.is_cache_valid(cache_key):
            cached_result = self.cache[cache_key]
            # Handle both old format (string) and new format (dict)
            if isinstance(cached_result, str):
                ami_id = cached_result
                ami_name = 'Unknown'
                result = {'ami_id': ami_id, 'ami_name': ami_name}
            else:
                ami_id = cached_result['ami_id']
                ami_name = cached_result['ami_name']
                result = cached_result
            
            # Display cached AMI with same format as fresh lookup
            if instance_name and image_key:
                self.converter.print_instance_output(instance_name, 'aws', f"Dynamic image search for {instance_name} on aws for {image_key} in {region} results in {ami_id} (cached)")
                if self.converter and hasattr(self.converter, 'verbose') and self.converter.verbose:
                    self.converter.print_instance_output(instance_name, 'aws', f"Verbose: {ami_name}")
            else:
                # Fallback to old format if context is not available
                print(f"Using cached AMI: {ami_id} ({ami_name}) for pattern '{name_pattern}' in {region}")
            
            return result

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

            # Query for AMIs with retry logic for transient failures
            import time
            max_retries = 3
            retry_delay = 1  # Start with 1 second
            
            for attempt in range(max_retries):
                try:
                    if attempt > 0:
                        print(f"  Retrying AMI search (attempt {attempt + 1}/{max_retries}) after {retry_delay}s delay...")
                        time.sleep(retry_delay)
                    
                    response = client.describe_images(
                        Filters=filters
                        # No MaxResults - get all available AMIs to find true latest version
                    )
                    break  # Success, exit retry loop
                    
                except Exception as retry_e:
                    if attempt == max_retries - 1:
                        # Last attempt failed, re-raise the exception
                        raise retry_e
                    else:
                        print(f"  AMI search attempt {attempt + 1} failed: {retry_e}")
                        retry_delay *= 2  # Exponential backoff

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
            import time
            self.cache_timestamps[cache_key] = time.time()

            return result

        except Exception as e:
            print(f"Warning: Failed to find AMI with pattern '{name_pattern}': {e}")
            return None




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
                "Or install all dependencies:\n"
                "   pip install -r requirements.txt\n\n"
                "Alternative: Use a different provider or remove AWS instances from your configuration."
            )

        # Skip credential validation in no-credentials mode
        if self.converter.no_credentials:
            self.converter.print_global_output("NO-CREDENTIALS MODE: Skipping AWS credential validation")
            return

        # Check if credentials are available when AWS instances are being processed
        has_credentials = self.converter.credentials and self.converter.credentials.get_aws_credentials()

        if not has_credentials:
            raise ValueError(
                "[ERROR] AWS Provider Error: No AWS credentials configured.\n\n"
                "NOTE: Please configure AWS credentials using one of these methods:\n\n"
                "1️⃣  AWS CLI (recommended):\n"
                "   aws configure\n\n"
                "2️⃣  Environment variables:\n"
                "   export AWS_ACCESS_KEY_ID=your-key-id\n"
                "   export AWS_SECRET_ACCESS_KEY=your-secret-key\n\n"
                "3️⃣  AWS credentials file:\n"
                "   ~/.aws/credentials\n\n"
                "4️⃣  IAM roles (for EC2 instances)\n\n"
                " Alternative: Use a different provider or use Terraform data sources by setting:\n"
                "   yamlforge:\n"
                "     aws:\n"
                "       use_data_sources: true"
            )

    def get_aws_resolver(self):
        """Get AWS image resolver, creating it only when needed."""
        if self._aws_resolver is None:
            self._aws_resolver = AWSImageResolver(self.converter.credentials, self.converter)
        return self._aws_resolver

    def get_aws_provider_reference(self, region, yaml_data=None):
        """Get the appropriate AWS provider reference for a specific region."""
        all_aws_regions = self.converter.get_all_aws_regions(yaml_data or {})
        provider_reference = self.converter.get_aws_provider_reference(region, all_aws_regions)
        return f"\n  {provider_reference}" if provider_reference else ""



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



    def resolve_aws_ami(self, image_key, instance_name, architecture="x86_64", region=None, yaml_data=None):
        """Resolve AWS AMI using dynamic discovery or graceful failure."""
        if not region:
            raise ValueError(f"Region must be specified for AWS AMI resolution for image '{image_key}'")

        # Check if we're in no-credentials mode
        if self.converter.no_credentials:
            print(f"  NO-CREDENTIALS MODE: Using placeholder AMI for '{image_key}' in region '{region}'")
            return "ami-PLACEHOLDER-REPLACE-WITH-ACTUAL-AMI", "placeholder"

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
                yamlforge_config = (yaml_data or {}).get('yamlforge', {})
                aws_yamlforge_config = yamlforge_config.get('aws', {})
                use_data_sources = aws_yamlforge_config.get('use_data_sources', False)
                
                if use_data_sources:
                    print(f"  Using Terraform data source for {image_key} (use_data_sources enabled)")
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

        # Check if user wants to use data sources instead of API calls
        yamlforge_config = (yaml_data or {}).get('yamlforge', {})
        aws_yamlforge_config = yamlforge_config.get('aws', {})
        use_data_sources = aws_yamlforge_config.get('use_data_sources', False)
        
        if use_data_sources:
            print(f"  Using Terraform data source for {image_key} (use_data_sources enabled)")
            return None, None

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
                    additional_filters=additional_filters,
                    instance_name=instance_name,
                    image_key=image_key
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
                    architecture=architecture,
                    instance_name=instance_name,
                    image_key=image_key
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
                    additional_filters=additional_filters,
                    instance_name=instance_name,
                    image_key=image_key
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
                    self.converter.print_instance_output(instance_name, 'aws', f"Dynamic image search for {instance_name} on aws for {image_key} in {region} results in {ami_id}")
                    if self.converter and hasattr(self.converter, 'verbose') and self.converter.verbose:
                        self.converter.print_instance_output(instance_name, 'aws', f"Verbose: {ami_name}")
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

    def generate_aws_security_group(self, sg_name, rules, region, yaml_data=None):  # noqa: vulture
        """Generate AWS security group."""
        # Replace {guid} placeholder in security group name
        sg_name = self.converter.replace_guid_placeholders(sg_name)
        clean_name = sg_name.replace("-", "_").replace(".", "_")
        clean_region = region.replace("-", "_").replace(".", "_")
        guid = self.converter.get_validated_guid(yaml_data)
        regional_sg_name = f"{clean_name}_{clean_region}"

        # Generate security group resource
        security_group_config = f'''
# AWS Security Group: {sg_name} (Region: {region})
resource "aws_security_group" "{regional_sg_name}_{guid}" {{{self.get_aws_provider_reference(region, yaml_data)}
  name_prefix = "{sg_name}-{region}-"
  description = "Security group for {sg_name} in {region}"
  vpc_id      = local.vpc_id_{clean_region}_{guid}

'''

        # Generate ingress and egress rules
        for rule in rules:
            rule_data = self.converter.generate_native_security_group_rule(rule, 'aws')
            direction = rule_data['direction']

            # Handle different source types
            if rule_data['is_source_cidr']:
                # CIDR block source
                source_config = f'''    cidr_blocks = {self.format_cidr_blocks_hcl(rule_data['source_cidr_blocks'])}'''
            else:
                # Provider-specific source (e.g., security group reference)
                source_config = f'''    security_groups = ["{rule_data['source']}"]'''

            # Handle different destination types (for egress rules)
            destination_config = ""
            if direction == 'egress' and rule_data['destination']:
                if rule_data['is_destination_cidr']:
                    # CIDR block destination
                    destination_config = f'''
    cidr_blocks = {self.format_cidr_blocks_hcl(rule_data['destination_cidr_blocks'])}'''
                else:
                    # Provider-specific destination (e.g., security group reference)
                    destination_config = f'''
    security_groups = ["{rule_data['destination']}"]'''

            rule_block = f'''  {direction} {{
    from_port   = {rule_data['from_port']}
    to_port     = {rule_data['to_port']}
    protocol    = "{rule_data['protocol']}"
{source_config}{destination_config}
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

    def generate_aws_vm(self, instance, index, clean_name, strategy_info, available_subnets=None, yaml_data=None, has_guid_placeholder=False):  # noqa: vulture
        """Generate AWS EC2 instance."""
        instance_name = instance.get("name", f"instance_{index}")
        # Replace {guid} placeholder in instance name
        instance_name = self.converter.replace_guid_placeholders(instance_name)
        image = instance.get("image", "RHEL_9_LATEST")

        # Resolve region using region/location logic
        aws_region = self.converter.resolve_instance_region(instance, "aws")
        
        # Check if user specified a zone (only valid with region-based configuration)
        user_specified_zone = instance.get('zone')
        has_region = 'region' in instance
        
        if user_specified_zone and has_region:
            # User specified both region and zone - validate the zone belongs to the region
            expected_region = user_specified_zone[:-1]  # Remove last character (e.g., us-east-1a -> us-east-1)
            
            if expected_region != aws_region:
                raise ValueError(f"Instance '{instance_name}': Specified zone '{user_specified_zone}' does not belong to region '{aws_region}'. "
                               f"Zone region: '{expected_region}', Instance region: '{aws_region}'")
            
            print(f"Using user-specified zone '{user_specified_zone}' for instance '{instance_name}' in region '{aws_region}'")
            aws_availability_zone = user_specified_zone
            
        elif user_specified_zone and not has_region:
            raise ValueError(f"Instance '{instance_name}': Zone '{user_specified_zone}' can only be specified when using 'region' (not 'location'). "
                           f"Either remove 'zone' or change 'location' to 'region'.")
        else:
            # Let Terraform automatically select the best available zone
            aws_availability_zone = None

        # Use the instance type from strategy
        aws_instance_type = strategy_info['instance_type']
        
        if not aws_instance_type:
            raise ValueError(f"Instance '{instance_name}': No instance type specified in strategy_info")
        
        # Get GUID for consistent naming
        guid = self.converter.get_validated_guid(yaml_data)

        # Resolve AMI using dynamic discovery or data source
        ami_reference, resolution_type = self.resolve_aws_ami(
            image, clean_name, strategy_info['architecture'], aws_region, yaml_data
        )

        if resolution_type == "placeholder":
            # No-credentials mode: use placeholder AMI directly
            ami_reference = ami_reference  # This is the placeholder AMI ID
            ami_data_source = ""
        elif not ami_reference:
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

        # Get security group references with regional awareness
        aws_sg_refs = []
        sg_names = instance.get('security_groups', [])
        
        # Define clean_region outside the loop so it can be used later
        clean_region = aws_region.replace("-", "_").replace(".", "_")
        
        for sg_name in sg_names:
            # Replace {guid} placeholder in security group name
            sg_name = self.converter.replace_guid_placeholders(sg_name)
            # Generate regional security group reference with GUID
            clean_sg = sg_name.replace("-", "_").replace(".", "_")
            aws_sg_refs.append(f"aws_security_group.{clean_sg}_{clean_region}_{guid}.id")



        # Get user data script
        user_data_script = instance.get('user_data_script')

        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})
        
        # Get the SSH username for this instance
        ssh_username = self.converter.get_instance_ssh_username(instance, 'aws', yaml_data or {})
        
        # Get the default username from core configuration
        default_username = self.converter.core_config.get('security', {}).get('default_username', 'cloud-user')
        
        # Generate user data script to create custom username (AWS doesn't have native cloud-user)
        custom_username_script = ""
        if ssh_username == default_username:
            # Create user data script to set up the configurable default account
            public_key = ssh_key_config.get('public_key', '') if ssh_key_config else ''
            custom_username_script = '''#!/bin/bash
# User data script for AWS instance
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
'''.format(ssh_username=ssh_username, public_key=public_key)
        elif ssh_username != 'ec2-user' and ssh_username != 'ubuntu':
            # Create user data script to set up other custom usernames
            public_key = ssh_key_config.get('public_key', '') if ssh_key_config else ''
            custom_username_script = '''#!/bin/bash
# User data script for AWS instance
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
'''.format(ssh_username=ssh_username, public_key=public_key)
        
        # Combine custom username script with user-provided script
        if custom_username_script:
            if user_data_script:
                # Prepend custom username script to user-provided script
                user_data_script = custom_username_script + "\n\n" + user_data_script
            else:
                user_data_script = custom_username_script

        # Generate AWS key pair resource if SSH key is provided
        ssh_key_resources = ""
        key_name_ref = "null"
        
        if ssh_key_config and ssh_key_config.get('public_key'):
            # Use clean_name directly if GUID is already present, otherwise add GUID
            ssh_key_name = clean_name if has_guid_placeholder else f"{clean_name}_key_pair_{guid}"
            ssh_key_resources = f'''
# AWS Key Pair for {instance_name}
resource "aws_key_pair" "{ssh_key_name}" {{{self.get_aws_provider_reference(aws_region, yaml_data)}
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

        # Use clean_name directly if GUID is already present, otherwise add GUID
        resource_name = clean_name if has_guid_placeholder else f"{clean_name}_{guid}"
        
        # Generate the EC2 instance
        vm_config = ssh_key_resources + f'''
# AWS EC2 Instance: {instance_name}
resource "aws_instance" "{resource_name}" {{{self.get_aws_provider_reference(aws_region, yaml_data)}
  ami           = {ami_reference}
  instance_type = "{aws_instance_type}"
  key_name      = {key_name_ref}
  
  availability_zone = {f'"{aws_availability_zone}"' if aws_availability_zone else 'null'}
  subnet_id         = local.vpc_subnet_id_{clean_region}_{guid}
  
  vpc_security_group_ids = [{", ".join(aws_sg_refs) if aws_sg_refs else ""}]
  
  root_block_device {{
    volume_size = {instance.get('disk_size', 20)}
    volume_type = "{instance.get('disk_type', 'gp3')}"
    encrypted   = true
  }}
  
  tags = {{
    Name = "{instance_name}"
    Environment = "{yaml_data.get('environment', 'unknown') if yaml_data else 'unknown'}"
    ManagedBy = "yamlforge"
  }}
  
  {("user_data = base64encode(<<-EOF" + chr(10) + user_data_script + chr(10) + "EOF" + chr(10)) if user_data_script else ""}
}}

{ami_data_source}
'''
        return vm_config

    def generate_aws_networking(self, deployment_name, deployment_config, region, yaml_data=None):  # noqa: vulture
        """Generate AWS networking resources for specific region."""
        network_config = deployment_config.get('network', {})
        network_name = network_config.get('name', f"{deployment_name}-vpc")
        # Replace {guid} placeholder in network name
        network_name = self.converter.replace_guid_placeholders(network_name)
        cidr_block = network_config.get('cidr_block', '10.0.0.0/16')
        
        clean_region = region.replace("-", "_").replace(".", "_")
        guid = self.converter.get_validated_guid(yaml_data)

        # Generate VPC resource
        networking_config = f'''
# AWS VPC: {network_name} (Region: {region})
resource "aws_vpc" "main_vpc_{clean_region}_{guid}" {{
  cidr_block           = "{cidr_block}"
  enable_dns_hostnames = true
  enable_dns_support   = true{self.get_aws_provider_reference(region, yaml_data)}

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
  vpc_id = local.vpc_id_{clean_region}_{guid}{self.get_aws_provider_reference(region, yaml_data)}

  tags = {{
    Name = "{network_name}-igw-{region}"
    Environment = "{yaml_data.get('environment', 'unknown') if yaml_data else 'unknown'}"
    ManagedBy = "yamlforge"
  }}
}}

# AWS Route Table
resource "aws_route_table" "main_rt_{clean_region}_{guid}" {{{self.get_aws_provider_reference(region, yaml_data)}
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

# Note: Route table associations are now handled within subnet generation for better organization
'''
        
        return networking_config

    def generate_rosa_compatible_subnets(self, network_name, cidr_block, region, guid, yaml_data=None):
        """Generate ROSA-compatible multi-AZ subnets (both public and private for ROSA Classic Multi-AZ)."""
        # Replace {guid} placeholder in network name
        network_name = self.converter.replace_guid_placeholders(network_name)
        clean_region = region.replace("-", "_").replace(".", "_")
        
        # Use Terraform data source to get actual available AZs for the region
        subnet_config = f'''
# Get available availability zones for {region}
data "aws_availability_zones" "available_{clean_region}_{guid}" {{{self.get_aws_provider_reference(region, yaml_data)}
  filter {{
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }}
  state = "available"
}}

# ROSA-compatible multi-AZ subnets (both public and private for ROSA Classic Multi-AZ)
# Dynamic subnet creation based on available AZs
'''
        
        # Generate optimal number of subnets (3 for good HA, minimum 2 for ROSA)
        # Choose intelligently from available AZs
        subnet_config += f'''
# Local values to select optimal AZs  
locals {{
  # Select up to 3 AZs for good HA (use what's available, maximum 3)
  # ROSA Classic Multi-AZ requires 6 subnets (3 public + 3 private)
  selected_az_count_{clean_region}_{guid} = min(length(data.aws_availability_zones.available_{clean_region}_{guid}.names), 3)
  selected_azs_{clean_region}_{guid} = slice(data.aws_availability_zones.available_{clean_region}_{guid}.names, 0, local.selected_az_count_{clean_region}_{guid})
}}

# Public subnets - create 2-3 subnets across selected AZs (optimal for HA without over-provisioning)
resource "aws_subnet" "public_subnet_{clean_region}_{guid}" {{{self.get_aws_provider_reference(region, yaml_data)}
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

# Private subnets - create 2-3 subnets across selected AZs (required for ROSA Classic Multi-AZ)
resource "aws_subnet" "private_subnet_{clean_region}_{guid}" {{{self.get_aws_provider_reference(region, yaml_data)}
  count = local.selected_az_count_{clean_region}_{guid}
  
  vpc_id            = local.vpc_id_{clean_region}_{guid}
  cidr_block        = cidrsubnet(local.vpc_cidr_{clean_region}_{guid}, 8, count.index + 3)
  availability_zone = local.selected_azs_{clean_region}_{guid}[count.index]

  tags = {{
    Name = "{network_name}-private-${{count.index + 1}}-${{local.selected_azs_{clean_region}_{guid}[count.index]}}"
    Environment = "{yaml_data.get('environment', 'unknown') if yaml_data else 'unknown'}"
    ManagedBy = "yamlforge"
    "kubernetes.io/role/internal-elb" = "1"  # Required for internal load balancers
  }}
}}
'''
        
        # Create local values for subnet IDs (ROSA provider needs these)
        subnet_config += f'''
# Local values for ROSA subnet references
locals {{
  public_subnet_ids_{clean_region}_{guid} = aws_subnet.public_subnet_{clean_region}_{guid}[*].id
  private_subnet_ids_{clean_region}_{guid} = aws_subnet.private_subnet_{clean_region}_{guid}[*].id
  
  # All subnet IDs for ROSA Classic Multi-AZ (6 total: 3 public + 3 private)
  all_subnet_ids_{clean_region}_{guid} = concat(
    aws_subnet.public_subnet_{clean_region}_{guid}[*].id,
    aws_subnet.private_subnet_{clean_region}_{guid}[*].id
  )
  
  # Availability zones for ROSA clusters (selected optimal AZs)
  region_azs_{clean_region}_{guid} = local.selected_azs_{clean_region}_{guid}
  
  # Primary subnet for non-ROSA resources (backwards compatibility)
  vpc_subnet_id_{clean_region}_{guid} = aws_subnet.public_subnet_{clean_region}_{guid}[0].id
}}

# Route table associations for public subnets
resource "aws_route_table_association" "public_subnet_rta_{clean_region}_{guid}" {{
  count = local.selected_az_count_{clean_region}_{guid}
  
  subnet_id      = aws_subnet.public_subnet_{clean_region}_{guid}[count.index].id
  route_table_id = aws_route_table.main_rt_{clean_region}_{guid}.id
}}

# Outputs for ROSA script access
output "public_subnet_ids_{clean_region}_{guid}" {{
  description = "Public subnet IDs for ROSA clusters in {region}"
  value       = local.public_subnet_ids_{clean_region}_{guid}
}}

output "private_subnet_ids_{clean_region}_{guid}" {{
  description = "Private subnet IDs for ROSA clusters in {region}"
  value       = local.private_subnet_ids_{clean_region}_{guid}
}}
'''
        
        return subnet_config

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

    def _generate_smart_aws_error(self, context, image_key=None, region=None):
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
                error_msg += "SDK Issue: boto3 not installed\n"
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
                error_msg += f"Connection Status: {cred_status['message']}\n"
                error_msg += "NOTE: To fix: Check internet connectivity and AWS service status\n\n"
        else:
            # Credentials are working, so the issue is likely image-specific
            error_msg += f"[CREDS] Credential Status: [OK] Valid (Account: {cred_status['account_id']})\n"
            if context == 'ami_resolution_failed':
                error_msg += f"Issue: No AMI found matching pattern for '{image_key}' in region '{region}'\n"
                
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
            error_msg += "Alternative: Enable Terraform data source fallback\n"
            error_msg += "   Add to your YAML:\n"
            error_msg += "   yamlforge:\n"
            error_msg += "     aws:\n"
            error_msg += "       use_data_sources: true\n\n"
        
        error_msg += "Or: Use a different cloud provider"
        
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

    def create_rosa_account_roles_via_cli(self, yaml_data=None):
        """Create ROSA account roles using ROSA CLI."""
        import subprocess
        
        guid = self.converter.get_validated_guid(yaml_data)
        
        try:
            # Skip account role creation in no-credentials mode
            if getattr(self.converter, 'no_credentials', False):
                print("  NO-CREDENTIALS MODE: Skipping ROSA account role creation")
                return True
            
            # Check if ROSA CLI is available
            result = subprocess.run(['rosa', 'version'], capture_output=True, text=True)
            if result.returncode != 0:
                print("ROSA CLI not found. Please install ROSA CLI first:")
                print("  curl -L https://mirror.openshift.com/pub/openshift-v4/amd64/clients/rosa/latest/rosa-linux.tar.gz | tar xz")
                print("  sudo mv rosa /usr/local/bin/")
                return False
                
            print("ROSA CLI found")
            
            # Check if ROSA is already logged in, or perform automatic login
            if not self._ensure_rosa_login():
                return False
            
            # Create account roles using ROSA CLI
            print("Creating ROSA account roles using ROSA CLI...")
            
            # Check if we have ROSA HCP clusters to determine what roles to create
            clusters = yaml_data.get('openshift_clusters', []) if yaml_data else []
            has_hcp_clusters = any(cluster.get('type') == 'rosa-hcp' for cluster in clusters)
            has_classic_clusters = any(cluster.get('type') == 'rosa-classic' for cluster in clusters)
            
            # Create HCP-specific roles if HCP clusters are present
            if has_hcp_clusters:
                cmd = [
                    'rosa', 'create', 'account-roles',
                    '--hosted-cp',
                    '--mode', 'auto',
                    '--yes',
                    '--prefix', f'ManagedOpenShift-{guid}'
                ]
                
                print(f"Running: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print("ROSA HCP account roles created successfully!")
                    # Only show detailed output in verbose mode
                    verbose = getattr(self.converter, 'verbose', False)
                    if verbose:
                        print("Detailed ROSA CLI output:")
                        print(result.stdout)
                else:
                    print("Failed to create ROSA HCP account roles:")
                    print(result.stderr)
                    return False
            
            # Create Classic roles if Classic clusters are present (or as fallback)
            if has_classic_clusters or not has_hcp_clusters:
                cmd = [
                    'rosa', 'create', 'account-roles',
                    '--mode', 'auto',
                    '--yes',
                    '--prefix', f'ManagedOpenShift-{guid}'
                ]
                
                print(f"Running: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print("ROSA Classic account roles created successfully!")
                    # Only show detailed output in verbose mode
                    verbose = getattr(self.converter, 'verbose', False)
                    if verbose:
                        print("Detailed ROSA CLI output:")
                        print(result.stdout)
                else:
                    print("Failed to create ROSA Classic account roles:")
                    print(result.stderr)
                    return False
            
            return True
                
        except Exception as e:
            print(f"Error creating ROSA account roles: {str(e)}")
            return False

    def _ensure_rosa_login(self):
        """Ensure ROSA CLI is logged in, attempting automatic login if needed."""
        import subprocess
        
        try:
            # First check if already logged in
            result = subprocess.run(['rosa', 'whoami'], capture_output=True, text=True)
            if result.returncode == 0:
                print("ROSA CLI already authenticated")
                verbose = getattr(self.converter, 'verbose', False)
                if verbose:
                    print(f"Logged in as: {result.stdout.strip()}")
                return True
            
            # Not logged in, try automatic login with environment variables
            print("ROSA CLI not authenticated, attempting automatic login...")
            
            # Check for Red Hat OpenShift token
            token_sources = ['REDHAT_OPENSHIFT_TOKEN']
            rhcs_token = None
            for token_var in token_sources:
                rhcs_token = os.getenv(token_var)
                if rhcs_token:
                    break
            
            if not rhcs_token:
                print("  WARNING: Red Hat OpenShift token not found")
                print("  Required for ROSA cluster creation")
                print("  Set the following environment variable:")
                print("  export REDHAT_OPENSHIFT_TOKEN='your_token_here'")
                return False

            # Attempt automatic login with token
            cmd = ['rosa', 'login', '--token', rhcs_token]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("ROSA CLI login successful!")
                return True
            else:
                print("ROSA CLI login failed with provided token:")
                print(result.stderr)
                return False
                
        except Exception as e:
            print(f"Error checking ROSA CLI authentication: {str(e)}")
            return False



    def generate_rosa_operator_roles(self, cluster_name, region, guid, yaml_data=None):
        """Generate reference to operator roles for ROSA clusters.
        
        Note: ROSA operator roles are created automatically by the RHCS cluster resource
        when it references the account roles and OIDC config. This method provides
        documentation and any additional configuration needed.
        """
        
        terraform_config = f'''
# =============================================================================
# ROSA OPERATOR ROLES - Cluster Specific (Created by RHCS cluster resource)
# =============================================================================
# Operator roles for cluster "{cluster_name}" are automatically created by the
# RHCS cluster resource when it references:
# - Account roles (installer, support, worker, master)
# - OIDC configuration
# - operator_role_prefix parameter in the cluster configuration
#
# No additional Terraform resources needed here - roles are managed by RHCS provider

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





    def generate_rosa_sts_data_sources(self, yaml_data=None):
        """Generate data sources for ROSA STS roles that were created via CLI."""
        guid = self.converter.get_validated_guid(yaml_data)
        
        # Check what types of ROSA clusters we have
        clusters = yaml_data.get('openshift_clusters', []) if yaml_data else []
        has_hcp_clusters = any(cluster.get('type') == 'rosa-hcp' for cluster in clusters)
        has_classic_clusters = any(cluster.get('type') == 'rosa-classic' for cluster in clusters)
        
        terraform_config = '''
# =============================================================================
# ROSA STS IAM ROLES - DATA SOURCES (Created by ROSA CLI)
# =============================================================================
# These data sources reference the ROSA account roles created by ROSA CLI
# ROSA CLI creates these roles automatically when yamlforge runs

'''

        # Generate HCP role data sources if HCP clusters are present
        if has_hcp_clusters:
            terraform_config += f'''
# ROSA HCP Roles - Used by Hosted Control Plane clusters
data "aws_iam_role" "rosa_hcp_installer_role" {{
  name = "ManagedOpenShift-{guid}-HCP-ROSA-Installer-Role"
}}

data "aws_iam_role" "rosa_hcp_support_role" {{
  name = "ManagedOpenShift-{guid}-HCP-ROSA-Support-Role"
}}

data "aws_iam_role" "rosa_hcp_worker_role" {{
  name = "ManagedOpenShift-{guid}-HCP-ROSA-Worker-Role"
}}

'''

        # Generate Classic role data sources if Classic clusters are present
        if has_classic_clusters:
            terraform_config += f'''
# ROSA Classic Roles - Used by Classic clusters
data "aws_iam_role" "rosa_classic_installer_role" {{
  name = "ManagedOpenShift-{guid}-Installer-Role"
}}

data "aws_iam_role" "rosa_classic_support_role" {{
  name = "ManagedOpenShift-{guid}-Support-Role"
}}

data "aws_iam_role" "rosa_classic_worker_role" {{
  name = "ManagedOpenShift-{guid}-Worker-Role"
}}

data "aws_iam_role" "rosa_classic_master_role" {{
  name = "ManagedOpenShift-{guid}-ControlPlane-Role"
}}

'''

        # Generate outputs for available role types
        terraform_config += '''
# =============================================================================
# ROSA STS ROLE OUTPUTS (from CLI-created roles)
# =============================================================================

'''

        if has_hcp_clusters:
            terraform_config += '''
# HCP Role Outputs
output "rosa_hcp_installer_role_arn" {
  description = "ARN of the ROSA HCP Installer Role (created via CLI)"
  value       = data.aws_iam_role.rosa_hcp_installer_role.arn
}

output "rosa_hcp_support_role_arn" {
  description = "ARN of the ROSA HCP Support Role (created via CLI)"
  value       = data.aws_iam_role.rosa_hcp_support_role.arn
}

output "rosa_hcp_worker_role_arn" {
  description = "ARN of the ROSA HCP Worker Role (created via CLI)"
  value       = data.aws_iam_role.rosa_hcp_worker_role.arn
}

'''

        if has_classic_clusters:
            terraform_config += '''
# Classic Role Outputs  
output "rosa_classic_installer_role_arn" {
  description = "ARN of the ROSA Classic Installer Role (created via CLI)"
  value       = data.aws_iam_role.rosa_classic_installer_role.arn
}

output "rosa_classic_support_role_arn" {
  description = "ARN of the ROSA Classic Support Role (created via CLI)"
  value       = data.aws_iam_role.rosa_classic_support_role.arn
}

output "rosa_classic_worker_role_arn" {
  description = "ARN of the ROSA Classic Worker Role (created via CLI)"
  value       = data.aws_iam_role.rosa_classic_worker_role.arn
}

output "rosa_classic_master_role_arn" {
  description = "ARN of the ROSA Classic Control Plane Role (created via CLI)"
  value       = data.aws_iam_role.rosa_classic_master_role.arn
}

'''

        return terraform_config

    def generate_s3_bucket(self, bucket, yaml_data):
        """Generate AWS S3 bucket configuration."""
        bucket_name = bucket.get('name', 'my-bucket')
        region = self.converter.resolve_bucket_region(bucket, 'aws')
        guid = self.converter.get_validated_guid(yaml_data)

        # Replace GUID placeholders
        final_bucket_name = self.converter.replace_guid_placeholders(bucket_name)
        clean_bucket_name, _ = self.converter.clean_name(final_bucket_name)
        
        # Bucket configuration
        public = bucket.get('public', False)
        versioning = bucket.get('versioning', False)
        encryption = bucket.get('encryption', True)
        tags = bucket.get('tags', {})

        terraform_config = f'''
# S3 Bucket: {final_bucket_name}
resource "aws_s3_bucket" "{clean_bucket_name}_{guid}" {{
  bucket = "{final_bucket_name}"

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

        # Public access configuration
        if public:
            terraform_config += f'''
resource "aws_s3_bucket_public_access_block" "{clean_bucket_name}_pab_{guid}" {{
  bucket = aws_s3_bucket.{clean_bucket_name}_{guid}.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}}

resource "aws_s3_bucket_acl" "{clean_bucket_name}_acl_{guid}" {{
  depends_on = [aws_s3_bucket_public_access_block.{clean_bucket_name}_pab_{guid}]
  bucket     = aws_s3_bucket.{clean_bucket_name}_{guid}.id
  acl        = "public-read"
}}

'''
        else:
            terraform_config += f'''
resource "aws_s3_bucket_public_access_block" "{clean_bucket_name}_pab_{guid}" {{
  bucket = aws_s3_bucket.{clean_bucket_name}_{guid}.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}}

'''

        # Versioning configuration
        if versioning:
            terraform_config += f'''
resource "aws_s3_bucket_versioning" "{clean_bucket_name}_versioning_{guid}" {{
  bucket = aws_s3_bucket.{clean_bucket_name}_{guid}.id
  versioning_configuration {{
    status = "Enabled"
  }}
}}

'''

        # Encryption configuration
        if encryption:
            terraform_config += f'''
resource "aws_s3_bucket_server_side_encryption_configuration" "{clean_bucket_name}_encryption_{guid}" {{
  bucket = aws_s3_bucket.{clean_bucket_name}_{guid}.id

  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm = "AES256"
    }}
  }}
}}

'''

        return terraform_config

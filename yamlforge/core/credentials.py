"""
Credentials Management Module

Handles cloud provider credentials for discovery and Terraform generation.
"""

import yaml
from pathlib import Path


class CredentialsManager:
    """Manages cloud provider credentials for discovery and Terraform generation."""

    def __init__(self, credentials_dir="credentials"):
        """Initialize the instance."""
        self.credentials_dir = Path(credentials_dir)
        self.aws_config = None
        self.azure_config = None
        self.gcp_config = None
        self.ibm_config = None
        self.openshift_config = None
        self.load_all_credentials()

    def load_all_credentials(self):
        """Load credentials for all cloud providers."""
        self.aws_config = self.load_credential_file("aws.yaml")
        self.azure_config = self.load_credential_file("azure.yaml")
        self.gcp_config = self.load_credential_file("gcp.yaml")
        self.ibm_config = self.load_credential_file("ibm.yaml")
        self.openshift_config = self.load_credential_file("openshift.yaml")

    def load_credential_file(self, filename):
        """Load a specific credential configuration file."""
        file_path = self.credentials_dir / filename
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                print(f"Warning: Could not load {filename}: {e}")
        return {}

    def get_aws_credentials(self):
        """Get AWS credentials and configuration with auto-discovery."""
        import os
        
        if not self.aws_config:
            return {}

        # Check which authentication method is enabled
        config = self.aws_config
        
        # Auto-detect environment variables first (highest priority)
        if (os.getenv('AWS_ACCESS_KEY_ID') and os.getenv('AWS_SECRET_ACCESS_KEY')) or os.getenv('AWS_PROFILE'):
            creds = {
                'type': 'environment',
                'region': os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
            }
        # Method 1: Access Keys (from config)
        elif config.get('access_key', {}).get('enabled', False):
            access_key_config = config['access_key']
            creds = {
                'type': 'access_key',
                'access_key_id': access_key_config.get('access_key_id'),
                'secret_access_key': access_key_config.get('secret_access_key'),
                'region': access_key_config.get('region', 'us-east-1')
            }
        # Method 2: IAM Role
        elif config.get('iam_role', {}).get('enabled', False):
            role_config = config['iam_role']
            creds = {
                'type': 'iam_role',
                'role_arn': role_config.get('role_arn'),
                'session_name': role_config.get('session_name', 'yamlforge'),
                'region': role_config.get('region', 'us-east-1')
            }
        # Method 3: AWS Profile
        elif config.get('profile', {}).get('enabled', False):
            profile_config = config['profile']
            profile_name = os.getenv('AWS_PROFILE', profile_config.get('profile_name', 'default'))
            creds = {
                'type': 'profile',
                'profile_name': profile_name,
                'region': profile_config.get('region', 'us-east-1')
            }
        # Method 4: Environment Variables (from config)
        elif config.get('environment', {}).get('enabled', False):
            env_config = config['environment']
            creds = {
                'type': 'environment',
                'region': env_config.get('region', 'us-east-1')
            }
        else:
            return {}

        # Auto-discover AWS account information using boto3
        try:
            aws_info = self._discover_aws_account_info(creds)
            creds.update(aws_info)
        except Exception as e:
            print(f"Warning: Could not auto-discover AWS account info: {e}")
            
        return creds

    def _discover_aws_account_info(self, creds):
        """Auto-discover AWS account information using STS."""
        import os
        
        try:
            import boto3
            from botocore.exceptions import ClientError, NoCredentialsError
        except ImportError:
            print("Warning: boto3 not available for AWS auto-discovery")
            return {}

        session = None
        
        try:
            # Create boto3 session based on credential type
            if creds['type'] == 'access_key':
                session = boto3.Session(
                    aws_access_key_id=creds['access_key_id'],
                    aws_secret_access_key=creds['secret_access_key'],
                    region_name=creds['region']
                )
            elif creds['type'] == 'profile':
                session = boto3.Session(
                    profile_name=creds['profile_name'],
                    region_name=creds['region']
                )
            elif creds['type'] == 'environment':
                session = boto3.Session(region_name=creds['region'])
            elif creds['type'] == 'iam_role':
                # For IAM roles, create base session first then assume role
                base_session = boto3.Session(region_name=creds['region'])
                sts = base_session.client('sts')
                assumed_role = sts.assume_role(
                    RoleArn=creds['role_arn'],
                    RoleSessionName=creds['session_name']
                )
                session = boto3.Session(
                    aws_access_key_id=assumed_role['Credentials']['AccessKeyId'],
                    aws_secret_access_key=assumed_role['Credentials']['SecretAccessKey'],
                    aws_session_token=assumed_role['Credentials']['SessionToken'],
                    region_name=creds['region']
                )
            
            if not session:
                return {}
                
            # Get caller identity using STS
            sts = session.client('sts')
            identity = sts.get_caller_identity()
            
            account_id = identity['Account']
            user_arn = identity['Arn']
            
            # Get billing account ID from environment variable or use current account
            billing_account_id = os.getenv('AWS_BILLING_ACCOUNT_ID', account_id)
            
            return {
                'account_id': account_id,
                'billing_account_id': billing_account_id,
                'user_arn': user_arn,
                'rosa_creator_arn': user_arn,  # ROSA creator ARN is the current user ARN
                'available': True
            }
            
        except (ClientError, NoCredentialsError) as e:
            print(f"Debug: AWS credential error: {e}")
            return {'available': False}
        except Exception as e:
            print(f"Debug: AWS discovery error: {e}")
            return {'available': False}

    def get_azure_credentials(self):
        """Get Azure credentials and configuration."""
        if not self.azure_config:
            return {}

        config = self.azure_config

        # Method 1: Service Principal
        if config.get('service_principal', {}).get('enabled', False):
            sp_config = config['service_principal']
            return {
                'type': 'service_principal',
                'client_id': sp_config.get('client_id'),
                'client_secret': sp_config.get('client_secret'),
                'tenant_id': sp_config.get('tenant_id'),
                'subscription_id': sp_config.get('subscription_id')
            }

        # Method 2: Managed Identity
        if config.get('managed_identity', {}).get('enabled', False):
            mi_config = config['managed_identity']
            return {
                'type': 'managed_identity',
                'client_id': mi_config.get('client_id'),
                'subscription_id': mi_config.get('subscription_id')
            }

        # Method 3: Azure CLI
        if config.get('azure_cli', {}).get('enabled', False):
            cli_config = config['azure_cli']
            return {
                'type': 'azure_cli',
                'subscription_id': cli_config.get('subscription_id'),
                'tenant_id': cli_config.get('tenant_id')
            }

        # Method 4: Environment Variables
        if config.get('environment', {}).get('enabled', False):
            env_config = config['environment']
            return {
                'type': 'environment',
                'subscription_id': env_config.get('subscription_id')
            }

        return {}

    def get_gcp_credentials(self):
        """Get GCP credentials and configuration."""
        if not self.gcp_config:
            return {}

        config = self.gcp_config

        # Method 1: Service Account Key File
        if config.get('service_account', {}).get('enabled', False):
            sa_config = config['service_account']
            return {
                'type': 'service_account',
                'key_file_path': sa_config.get('key_file_path'),
                'project_id': sa_config.get('project_id')
            }

        # Method 2: Application Default Credentials
        if config.get('application_default', {}).get('enabled', False):
            adc_config = config['application_default']
            return {
                'type': 'application_default',
                'project_id': adc_config.get('project_id')
            }

        # Method 3: Workload Identity
        if config.get('workload_identity', {}).get('enabled', False):
            wi_config = config['workload_identity']
            return {
                'type': 'workload_identity',
                'service_account_email': wi_config.get('service_account_email'),
                'project_id': wi_config.get('project_id')
            }

        # Method 4: Environment Variables
        if config.get('environment', {}).get('enabled', False):
            env_config = config['environment']
            return {
                'type': 'environment',
                'project_id': env_config.get('project_id')
            }

        return {}

    def get_ibm_credentials(self):
        """Get IBM Cloud credentials and configuration."""
        if not self.ibm_config:
            return {}

        config = self.ibm_config

        # Method 1: API Key
        if config.get('api_key', {}).get('enabled', False):
            api_key_config = config['api_key']
            return {
                'type': 'api_key',
                'api_key': api_key_config.get('api_key'),
                'account_id': api_key_config.get('account_id')
            }

        # Method 2: Service ID
        if config.get('service_id', {}).get('enabled', False):
            service_config = config['service_id']
            return {
                'type': 'service_id',
                'service_id': service_config.get('service_id'),
                'api_key': service_config.get('api_key')
            }

        # Method 3: Environment Variables
        if config.get('environment', {}).get('enabled', False):
            return {
                'type': 'environment'
            }

        return {}

    def get_terraform_variables(self):
        """Get Terraform variables from credential configurations."""
        variables = {}

        # AWS Variables
        aws_creds = self.get_aws_credentials()
        aws_terraform = self.aws_config.get('terraform_vars', {}) if self.aws_config else {}
        if aws_creds:
            variables['aws_region'] = aws_creds.get('region', aws_terraform.get('aws_region', 'us-east-1'))

        # Azure Variables
        azure_creds = self.get_azure_credentials()
        azure_terraform = self.azure_config.get('terraform_vars', {}) if self.azure_config else {}
        if azure_creds:
            variables['azure_subscription_id'] = azure_creds.get('subscription_id', azure_terraform.get('azure_subscription_id', ''))
            variables['azure_location'] = azure_terraform.get('azure_location', 'East US')
            variables['azure_resource_group_name'] = azure_terraform.get('azure_resource_group_name', 'yamlforge-rg')

        # GCP Variables
        gcp_creds = self.get_gcp_credentials()
        gcp_terraform = self.gcp_config.get('terraform_vars', {}) if self.gcp_config else {}
        if gcp_creds:
            variables['gcp_project_id'] = gcp_creds.get('project_id', gcp_terraform.get('gcp_project_id', ''))
            variables['gcp_region'] = gcp_terraform.get('gcp_region', 'us-east1')
            variables['gcp_zone'] = gcp_terraform.get('gcp_zone', 'us-east1-a')

        # IBM Variables
        ibm_creds = self.get_ibm_credentials()
        ibm_terraform = self.ibm_config.get('terraform_vars', {}) if self.ibm_config else {}
        if ibm_creds:
            variables['ibm_api_key'] = ibm_creds.get('api_key', ibm_terraform.get('ibm_api_key', ''))
            variables['ibm_region'] = ibm_terraform.get('ibm_region', 'us-south')
            variables['ibm_zone'] = ibm_terraform.get('ibm_zone', 'us-south-1')
            variables['ibm_resource_group_id'] = ibm_terraform.get('ibm_resource_group_id', '')

        return variables

    def get_openshift_credentials(self):
        """Get OpenShift credentials from environment variables."""
        import os
        
        # Red Hat OpenShift Cluster Manager API credentials (for ROSA, OpenShift Dedicated)
        redhat_token = os.getenv('REDHAT_OPENSHIFT_TOKEN')
        redhat_url = os.getenv('REDHAT_OPENSHIFT_URL', 'https://api.openshift.com')
        
        # OpenShift cluster connection credentials (for existing clusters)
        cluster_url = os.getenv('OPENSHIFT_CLUSTER_URL')
        cluster_token = os.getenv('OPENSHIFT_TOKEN')
        username = os.getenv('OPENSHIFT_USERNAME')
        password = os.getenv('OPENSHIFT_PASSWORD')
        namespace = os.getenv('OPENSHIFT_NAMESPACE', 'default')
        kubeconfig = os.getenv('OPENSHIFT_KUBECONFIG')
        
        return {
            'redhat_cluster_manager': {
                'token': redhat_token,
                'url': redhat_url,
                'available': bool(redhat_token)
            },
            'cluster_connection': {
                'url': cluster_url,
                'token': cluster_token,
                'username': username,
                'password': password,
                'namespace': namespace,
                'kubeconfig': kubeconfig,
                'available': bool(cluster_token or (username and password) or kubeconfig)
            }
        }

    def get_default_ssh_key(self):
        """Get default SSH public key from environment variables or core defaults."""
        import os
        
        # Priority order:
        # 1. SSH_PUBLIC_KEY environment variable
        # 2. YAMLFORGE_SSH_PUBLIC_KEY environment variable  
        # 3. defaults/core.yaml configuration
        # 4. Auto-detect from ~/.ssh/id_rsa.pub or ~/.ssh/id_ed25519.pub
        
        # Check environment variables first
        ssh_key = os.getenv('SSH_PUBLIC_KEY')
        if ssh_key:
            return {
                'public_key': ssh_key.strip(),
                'source': 'SSH_PUBLIC_KEY environment variable',
                'available': True
            }
            
        ssh_key = os.getenv('YAMLFORGE_SSH_PUBLIC_KEY')
        if ssh_key:
            return {
                'public_key': ssh_key.strip(),
                'source': 'YAMLFORGE_SSH_PUBLIC_KEY environment variable',
                'available': True
            }
        
        # Check core defaults configuration
        core_config = {}
        try:
            from pathlib import Path
            core_defaults_path = Path('defaults/core.yaml')
            if core_defaults_path.exists():
                import yaml
                with open(core_defaults_path, 'r') as f:
                    core_config = yaml.safe_load(f) or {}
                    default_key = core_config.get('security', {}).get('default_ssh_public_key', '')
                    if default_key and default_key.strip():
                        return {
                            'public_key': default_key.strip(),
                            'source': 'defaults/core.yaml configuration',
                            'available': True
                        }
        except Exception:
            pass  # Silently continue
        
        # Auto-detect from common SSH key locations (only if enabled)
        auto_detect_enabled = core_config.get('security', {}).get('auto_detect_ssh_keys', False)
        if auto_detect_enabled:
            ssh_dir = Path.home() / '.ssh'
            for key_file in ['id_ed25519.pub', 'id_rsa.pub']:
                key_path = ssh_dir / key_file
                if key_path.exists():
                    try:
                        with open(key_path, 'r') as f:
                            ssh_key = f.read().strip()
                            if ssh_key:
                                return {
                                    'public_key': ssh_key,
                                    'source': f'Auto-detected from {key_path}',
                                    'available': True
                                }
                    except Exception:
                        continue
        
        # No SSH key found
        return {
            'public_key': None,
            'source': 'No SSH key found',
            'available': False
        }
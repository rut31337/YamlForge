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
        self.load_all_credentials()

    def load_all_credentials(self):
        """Load credentials for all cloud providers."""
        self.aws_config = self.load_credential_file("aws.yaml")
        self.azure_config = self.load_credential_file("azure.yaml")
        self.gcp_config = self.load_credential_file("gcp.yaml")
        self.ibm_config = self.load_credential_file("ibm.yaml")

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
        """Get AWS credentials and configuration."""
        if not self.aws_config:
            return {}

        # Check which authentication method is enabled
        config = self.aws_config

        # Method 1: Access Keys
        if config.get('access_key', {}).get('enabled', False):
            access_key_config = config['access_key']
            return {
                'type': 'access_key',
                'access_key_id': access_key_config.get('access_key_id'),
                'secret_access_key': access_key_config.get('secret_access_key'),
                'region': access_key_config.get('region', 'us-east-1')
            }

        # Method 2: IAM Role
        if config.get('iam_role', {}).get('enabled', False):
            role_config = config['iam_role']
            return {
                'type': 'iam_role',
                'role_arn': role_config.get('role_arn'),
                'session_name': role_config.get('session_name', 'yamlforge'),
                'region': role_config.get('region', 'us-east-1')
            }

        # Method 3: AWS Profile
        if config.get('profile', {}).get('enabled', False):
            profile_config = config['profile']
            return {
                'type': 'profile',
                'profile_name': profile_config.get('profile_name', 'default'),
                'region': profile_config.get('region', 'us-east-1')
            }

        # Method 4: Environment Variables
        if config.get('environment', {}).get('enabled', False):
            env_config = config['environment']
            return {
                'type': 'environment',
                'region': env_config.get('region', 'us-east-1')
            }

        return {}

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
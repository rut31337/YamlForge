"""
Credentials Management Module

Handles cloud provider credentials via environment variables only.
All credential configuration moved to environment variables - no file loading.
"""

import os
from pathlib import Path
from ..utils import find_yamlforge_file


class CredentialsManager:
    """Manages cloud provider credentials via environment variables only."""

    def __init__(self):
        """Initialize the instance - all credentials come from environment variables only."""
        # All credentials now come from environment variables only
        pass

    def get_aws_credentials(self):
        """Get AWS credentials from environment variables with auto-discovery."""
        # Check for AWS credentials in environment variables
        access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
        secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_profile = os.getenv('AWS_PROFILE')
        
        if not (access_key_id and secret_access_key) and not aws_profile:
            return {'available': False}
        
        # Determine credential type
        if access_key_id and secret_access_key:
            creds = {
                'type': 'access_key',
                'access_key_id': access_key_id,
                'secret_access_key': secret_access_key
            }
        elif aws_profile:
            creds = {
                'type': 'profile',
                'profile_name': aws_profile
            }
        else:
            creds = {
                'type': 'environment'
            }

        # Auto-discover AWS account information using boto3
        try:
            aws_info = self._discover_aws_account_info(creds)
            creds.update(aws_info)
        except Exception as e:
            print(f"Warning: Could not auto-discover AWS account info: {e}")
            
        return creds

    def _discover_aws_account_info(self, creds):
        """Auto-discover AWS account information using STS."""
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
                    aws_secret_access_key=creds['secret_access_key']
                )
            elif creds['type'] == 'profile':
                session = boto3.Session(
                    profile_name=creds['profile_name']
                )
            elif creds['type'] == 'environment':
                session = boto3.Session()
            
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
            return {'available': False}
        except Exception as e:
            return {'available': False}

    def get_azure_credentials(self):
        """Get Azure credentials from environment variables."""
        # Check for Azure credentials in environment variables
        client_id = os.getenv('ARM_CLIENT_ID') or os.getenv('AZURE_CLIENT_ID')
        client_secret = os.getenv('ARM_CLIENT_SECRET') or os.getenv('AZURE_CLIENT_SECRET')
        subscription_id = os.getenv('ARM_SUBSCRIPTION_ID') or os.getenv('AZURE_SUBSCRIPTION_ID')
        tenant_id = os.getenv('ARM_TENANT_ID') or os.getenv('AZURE_TENANT_ID')
        
        if not all([client_id, client_secret, subscription_id, tenant_id]):
            return {'available': False}
        
        return {
            'type': 'service_principal',
            'client_id': client_id,
            'client_secret': client_secret,
            'tenant_id': tenant_id,
            'subscription_id': subscription_id,
            'available': True
        }

    def get_gcp_credentials(self):
        """Get GCP credentials from environment variables."""
        # Check for GCP credentials in environment variables
        service_account_key = os.getenv('GCP_SERVICE_ACCOUNT_KEY') or os.getenv('GOOGLE_CREDENTIALS')
        project_id = os.getenv('GCP_PROJECT_ID') or os.getenv('GOOGLE_PROJECT')
        
        if not service_account_key or not project_id:
            return {'available': False}
        
        return {
            'type': 'service_account_key',
            'service_account_key': service_account_key,
            'project_id': project_id,
            'available': True
        }



    def get_oci_credentials(self):
        """Get Oracle Cloud Infrastructure credentials from environment variables."""
        # Check for OCI credentials in environment variables
        user_ocid = os.getenv('OCI_USER_OCID') or os.getenv('TF_VAR_user_ocid')
        fingerprint = os.getenv('OCI_FINGERPRINT') or os.getenv('TF_VAR_fingerprint')
        tenancy_ocid = os.getenv('OCI_TENANCY_OCID') or os.getenv('TF_VAR_tenancy_ocid')
        region = os.getenv('OCI_REGION', 'us-ashburn-1')
        private_key = os.getenv('OCI_PRIVATE_KEY')
        private_key_path = os.getenv('OCI_PRIVATE_KEY_PATH') or os.getenv('TF_VAR_private_key_path')
        
        if not all([user_ocid, fingerprint, tenancy_ocid]):
            return {'available': False}
        
        if not private_key and not private_key_path:
            return {'available': False}
        
        return {
            'type': 'api_key',
            'user_ocid': user_ocid,
            'fingerprint': fingerprint,
            'tenancy_ocid': tenancy_ocid,
            'region': region,
            'private_key': private_key,
            'private_key_path': private_key_path,
            'available': True
        }

    def get_vmware_credentials(self):
        """Get VMware vSphere credentials from environment variables."""
        # Check for VMware credentials in environment variables
        user = os.getenv('VSPHERE_USER')
        password = os.getenv('VSPHERE_PASSWORD')
        server = os.getenv('VSPHERE_SERVER')
        
        if not all([user, password, server]):
            return {'available': False}
        
        return {
            'type': 'username_password',
            'user': user,
            'password': password,
            'server': server,
            'datacenter': os.getenv('VMWARE_DATACENTER', 'Datacenter'),
            'cluster': os.getenv('VMWARE_CLUSTER', 'Cluster'),
            'datastore': os.getenv('VMWARE_DATASTORE', 'datastore1'),
            'network': os.getenv('VMWARE_NETWORK', 'VM Network'),
            'allow_unverified_ssl': os.getenv('VMWARE_ALLOW_UNVERIFIED_SSL', 'true').lower() == 'true',
            'available': True
        }

    def get_alibaba_credentials(self):
        """Get Alibaba Cloud credentials from environment variables."""
        # Check for Alibaba Cloud credentials in environment variables
        access_key = os.getenv('ALICLOUD_ACCESS_KEY')
        secret_key = os.getenv('ALICLOUD_SECRET_KEY')
        region = os.getenv('ALICLOUD_REGION', 'us-east-1')
        
        if not all([access_key, secret_key]):
            return {'available': False}
        
        return {
            'type': 'access_key',
            'access_key': access_key,
            'secret_key': secret_key,
            'region': region,
            'available': True
        }

    def get_cert_manager_credentials(self):
        """Get cert-manager EAB credentials from environment variables."""
        # ZeroSSL EAB credentials
        zerossl_kid = os.getenv('ZEROSSL_EAB_KID')
        zerossl_hmac = os.getenv('ZEROSSL_EAB_HMAC')
        
        # SSL.com EAB credentials
        sslcom_kid = os.getenv('SSLCOM_EAB_KID')
        sslcom_hmac = os.getenv('SSLCOM_EAB_HMAC')
        
        return {
            'zerossl': {
                'eab_kid': zerossl_kid,
                'eab_hmac': zerossl_hmac,
                'available': bool(zerossl_kid and zerossl_hmac)
            },
            'sslcom': {
                'eab_kid': sslcom_kid,
                'eab_hmac': sslcom_hmac,
                'available': bool(sslcom_kid and sslcom_hmac)
            }
        }

    @property
    def oci_config(self):
        """Get OCI configuration for providers."""
        oci_creds = self.get_oci_credentials()
        if not oci_creds.get('available'):
            return None
        
        return {
            'user_ocid': oci_creds.get('user_ocid'),
            'key_file': oci_creds.get('private_key_path'),
            'fingerprint': oci_creds.get('fingerprint'),
            'tenancy_ocid': oci_creds.get('tenancy_ocid'),
            'region': oci_creds.get('region')
        }

    @property
    def alibaba_config(self):
        """Get Alibaba Cloud configuration for providers."""
        alibaba_creds = self.get_alibaba_credentials()
        if not alibaba_creds.get('available'):
            return None
        
        return {
            'access_key_id': alibaba_creds.get('access_key'),
            'access_key_secret': alibaba_creds.get('secret_key'),
            'region': alibaba_creds.get('region')
        }









    def get_default_ssh_key(self):
        """Get default SSH public key from environment variables or auto-detect."""
        # Priority order:
        # 1. SSH_PUBLIC_KEY environment variable
        # 2. YAMLFORGE_SSH_PUBLIC_KEY environment variable  
        # 3. Auto-detect from ~/.ssh/id_rsa.pub or ~/.ssh/id_ed25519.pub (if enabled in defaults)
        
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
        
        # Check core defaults configuration for auto-detection settings
        try:
            import yaml
            core_defaults_path = find_yamlforge_file('defaults/core.yaml')
            with open(core_defaults_path, 'r') as f:
                core_config = yaml.safe_load(f) or {}
                
                # Check for configured default key in core config
                default_key = core_config.get('security', {}).get('default_ssh_public_key', '')
                if default_key and default_key.strip():
                    return {
                        'public_key': default_key.strip(),
                        'source': 'defaults/core.yaml configuration',
                        'available': True
                    }
                    
                # Check if auto-detection is enabled
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
        except Exception:
            pass  # Silently continue
        
        # No SSH key found
        return {
            'public_key': None,
            'source': 'No SSH key found',
            'available': False
        }

"""
RHDP Integration Module

Provides functionality to integrate with Red Hat Demo Platform (RHDP) to extract
cloud credentials from ResourceClaim objects in OpenShift clusters.
"""

import os
import re
import subprocess
import json
import yaml
import tempfile
import base64
from typing import Dict, Any, Optional, List
import streamlit as st
from config.auth_config import get_auth_config

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False


class RHDPIntegration:
    """Handles RHDP ResourceClaim integration for credential extraction."""
    
    def __init__(self):
        self.enabled = self._is_rhdp_enabled()
        self.kubeconfig_secret_name = "rhdp-kubeconfig"
        self.kubeconfig_secret_key = "kubeconfig"
        
        # ResourceClaim patterns for different cloud providers
        self.claim_patterns = {
            'aws': 'sandboxes-gpte.sandbox-open.prod',
            'azure': 'azure-gpte.open-environment-azure-subscription.prod',
            'gcp': 'gcp-gpte.open-environment-gcp.prod'
        }
    
    def _is_rhdp_enabled(self) -> bool:
        """Check if RHDP functionality is enabled via environment variable."""
        return os.getenv('RHDP_FUNC_ENABLED', 'false').lower() in ['true', '1', 'yes']
    
    def _get_current_namespace(self) -> str:
        """
        Get the current namespace from the service account token.
        
        Returns:
            The current namespace, defaults to 'demobuilder' if not found
        """
        try:
            # Read namespace from service account token mount
            with open('/var/run/secrets/kubernetes.io/serviceaccount/namespace', 'r') as f:
                return f.read().strip()
        except:
            return 'demobuilder'

    def _get_kubeconfig_from_secret(self) -> Optional[str]:
        """
        Get kubeconfig content from Kubernetes secret using k8s client.
        
        Returns:
            The kubeconfig content as string, or None if not available
        """
        if not self.enabled or not K8S_AVAILABLE:
            return None
            
        try:
            # Load in-cluster config (when running in OpenShift)
            config.load_incluster_config()
            
            # Create API client
            v1 = client.CoreV1Api()
            
            # Get the current namespace from service account
            namespace = self._get_current_namespace()
            
            # Get the secret
            secret = v1.read_namespaced_secret(
                name=self.kubeconfig_secret_name,
                namespace=namespace
            )
            
            # Extract kubeconfig data
            if self.kubeconfig_secret_key in secret.data:
                kubeconfig_b64 = secret.data[self.kubeconfig_secret_key]
                kubeconfig_content = base64.b64decode(kubeconfig_b64).decode('utf-8')
                return kubeconfig_content
            
            return None
            
        except ApiException as e:
            return None
        except Exception as e:
            return None
    
    def transform_email_to_username(self, email: str) -> str:
        """
        Transform email to RHDP username format.
        Example: prutledg@redhat.com -> user-prutledg-redhat-com
        """
        if not email:
            return ""
        
        # Replace . and @ with -
        username = email.replace('.', '-').replace('@', '-')
        # Prepend with user-
        return f"user-{username}"
    
    def get_user_namespace(self) -> Optional[str]:
        """Get the user's namespace based on their email from authentication."""
        if not self.enabled:
            return None
            
        auth_config = get_auth_config()
        user = auth_config.get_current_user()
        
        if not user or not user.email:
            return None
            
        return self.transform_email_to_username(user.email)
    
    def _get_rhdp_client(self) -> Optional[client.CustomObjectsApi]:
        """
        Create a Kubernetes client for the RHDP cluster using kubeconfig from secret.
        
        Returns:
            CustomObjectsApi client for ResourceClaims, or None if not available
        """
        if not self.enabled or not K8S_AVAILABLE:
            return None
            
        try:
            # Get kubeconfig from secret
            kubeconfig_content = self._get_kubeconfig_from_secret()
            if not kubeconfig_content:
                return None
            
            # Parse kubeconfig
            kubeconfig_dict = yaml.safe_load(kubeconfig_content)
            
            # Create configuration from kubeconfig
            rhdp_config = client.Configuration()
            
            # Extract cluster info
            cluster = kubeconfig_dict['clusters'][0]['cluster']
            rhdp_config.host = cluster['server']
            
            # Handle certificate authority
            if 'certificate-authority-data' in cluster:
                cert_data = base64.b64decode(cluster['certificate-authority-data'])
                with tempfile.NamedTemporaryFile(delete=False, suffix='.crt') as f:
                    f.write(cert_data)
                    rhdp_config.ssl_ca_cert = f.name
            elif cluster.get('insecure-skip-tls-verify'):
                rhdp_config.verify_ssl = False
            
            # Extract user credentials
            user = kubeconfig_dict['users'][0]['user']
            if 'client-certificate-data' in user and 'client-key-data' in user:
                # Client certificate auth
                cert_data = base64.b64decode(user['client-certificate-data'])
                key_data = base64.b64decode(user['client-key-data'])
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.crt') as f:
                    f.write(cert_data)
                    rhdp_config.cert_file = f.name
                    
                with tempfile.NamedTemporaryFile(delete=False, suffix='.key') as f:
                    f.write(key_data)
                    rhdp_config.key_file = f.name
                    
            elif 'token' in user:
                # Token auth
                rhdp_config.api_key = {'authorization': f"Bearer {user['token']}"}
            
            # Create API client
            rhdp_api_client = client.ApiClient(rhdp_config)
            return client.CustomObjectsApi(rhdp_api_client)
            
        except Exception as e:
            return None

    def query_resource_claims(self, namespace: str, provider_patterns: List[str]) -> List[Dict[str, Any]]:
        """
        Query ResourceClaims in a specific namespace that match provider patterns.
        
        Args:
            namespace: The user's namespace to search in
            provider_patterns: List of patterns to match against ResourceClaim names
            
        Returns:
            List of ResourceClaim objects as dictionaries
        """
        if not self.enabled or not K8S_AVAILABLE:
            return []
            
        resource_claims = []
        
        try:
            # Get RHDP cluster client
            rhdp_client = self._get_rhdp_client()
            if not rhdp_client:
                return []
            
            # Query ResourceClaims using Custom Resource API
            # ResourceClaims are custom resources in the poolboy.gpte.redhat.com group
            claims_response = rhdp_client.list_namespaced_custom_object(
                group='poolboy.gpte.redhat.com',
                version='v1',
                namespace=namespace,
                plural='resourceclaims',
                timeout_seconds=30
            )
            
            # Filter claims by patterns
            for claim in claims_response.get('items', []):
                claim_name = claim.get('metadata', {}).get('name', '')
                
                # Check if claim name starts with any of the provider patterns
                for pattern in provider_patterns:
                    if claim_name.startswith(pattern):
                        resource_claims.append(claim)
                        break
                        
        except ApiException as e:
            # Log error but don't fail completely
            pass
        except Exception as e:
            # Log error but don't fail completely
            pass
            
        return resource_claims
    
    def extract_credentials_from_claim(self, claim: Dict[str, Any], provider: str) -> Dict[str, str]:
        """
        Extract credentials from a ResourceClaim's provision_data.
        
        Args:
            claim: ResourceClaim object as dictionary
            provider: Provider type ('aws', 'azure', 'gcp')
            
        Returns:
            Dictionary of credential environment variables
        """
        credentials = {}
        
        try:
            provision_data = claim.get('status', {}).get('summary', {}).get('provision_data', {})
            
            if not provision_data:
                # Try alternative path
                provision_data = claim.get('status', {}).get('provision_data', {})
            
            if provider == 'aws':
                credentials = self._map_aws_credentials(provision_data)
            elif provider == 'azure':
                credentials = self._map_azure_credentials(provision_data)
            elif provider == 'gcp':
                credentials = self._map_gcp_credentials(provision_data)
                
        except Exception as e:
            pass
            
        return credentials
    
    def _map_aws_credentials(self, provision_data: Dict[str, Any]) -> Dict[str, str]:
        """Map AWS provision_data to environment variables."""
        credentials = {}
        
        # RHDP AWS credential field mappings based on actual provision_data structure
        field_mappings = {
            'AWS_ACCESS_KEY_ID': ['aws_access_key_id'],
            'AWS_SECRET_ACCESS_KEY': ['aws_secret_access_key'],
            'AWS_DEFAULT_REGION': ['aws_default_region'],
            'AWS_SESSION_TOKEN': ['aws_session_token', 'session_token']
        }
        
        for env_var, possible_fields in field_mappings.items():
            for field in possible_fields:
                if field in provision_data:
                    credentials[env_var] = str(provision_data[field])
                    break
        
        return credentials
    
    def _map_azure_credentials(self, provision_data: Dict[str, Any]) -> Dict[str, str]:
        """Map Azure provision_data to environment variables."""
        credentials = {}
        
        # RHDP Azure credential field mappings based on actual provision_data structure
        field_mappings = {
            'ARM_CLIENT_ID': ['azure_service_principal_id'],
            'ARM_CLIENT_SECRET': ['azure_service_principal_password'],
            'ARM_SUBSCRIPTION_ID': ['azure_subscription'],
            'ARM_TENANT_ID': ['azure_tenant_id', 'azure_tenant']
        }
        
        for env_var, possible_fields in field_mappings.items():
            for field in possible_fields:
                if field in provision_data:
                    credentials[env_var] = str(provision_data[field])
                    break
        
        return credentials
    
    def _map_gcp_credentials(self, provision_data: Dict[str, Any]) -> Dict[str, str]:
        """Map GCP provision_data to environment variables."""
        credentials = {}
        
        # RHDP GCP credential field mappings based on actual provision_data structure
        field_mappings = {
            'GOOGLE_PROJECT': ['gcp_project_id', 'project_id'],
            'GCP_REGION': ['gcp_region', 'region'],
            'GCP_ZONE': ['gcp_zone', 'zone']
        }
        
        # Handle GCP credentials file separately (it's a nested object)
        if 'gcp_credentials_file' in provision_data:
            import json
            credentials['GOOGLE_CREDENTIALS'] = json.dumps(provision_data['gcp_credentials_file'])
        
        for env_var, possible_fields in field_mappings.items():
            for field in possible_fields:
                if field in provision_data:
                    credentials[env_var] = str(provision_data[field])
                    break
        
        return credentials
    
    def get_credentials_for_provider(self, provider: str) -> Dict[str, str]:
        """
        Get credentials for a specific provider from RHDP ResourceClaims.
        
        Args:
            provider: Provider name ('aws', 'azure', 'gcp')
            
        Returns:
            Dictionary of environment variables for the provider
        """
        if not self.enabled:
            return {}
            
        user_namespace = self.get_user_namespace()
        if not user_namespace:
            return {}
        
        # Get the pattern for this provider
        pattern = self.claim_patterns.get(provider)
        if not pattern:
            return {}
        
        # Query ResourceClaims
        claims = self.query_resource_claims(user_namespace, [pattern])
        
        # Extract credentials from the first matching claim
        for claim in claims:
            credentials = self.extract_credentials_from_claim(claim, provider)
            if credentials:
                return credentials
        
        return {}
    
    def get_all_available_credentials(self) -> Dict[str, Dict[str, str]]:
        """
        Get all available credentials from RHDP ResourceClaims.
        
        Returns:
            Dictionary with provider names as keys and credential dictionaries as values
        """
        if not self.enabled:
            return {}
            
        user_namespace = self.get_user_namespace()
        if not user_namespace:
            return {}
        
        all_credentials = {}
        
        # Query for all provider patterns
        all_patterns = list(self.claim_patterns.values())
        claims = self.query_resource_claims(user_namespace, all_patterns)
        
        # Group claims by provider and extract credentials
        for provider, pattern in self.claim_patterns.items():
            provider_claims = [c for c in claims if c.get('metadata', {}).get('name', '').startswith(pattern)]
            
            for claim in provider_claims:
                credentials = self.extract_credentials_from_claim(claim, provider)
                if credentials:
                    all_credentials[provider] = credentials
                    break  # Use first successful match per provider
        
        return all_credentials


def get_rhdp_integration() -> RHDPIntegration:
    """Get RHDP integration singleton."""
    if 'rhdp_integration' not in st.session_state:
        st.session_state.rhdp_integration = RHDPIntegration()
    return st.session_state.rhdp_integration
"""
ROSA Version Manager for YamlForge
Dynamically fetches supported OpenShift versions from Red Hat API
"""

import json
import os
import requests
import time
import random
from typing import List, Dict, Optional
from functools import wraps


def retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=60.0, backoff_factor=2.0):
    """
    Retry decorator with exponential backoff and jitter
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        backoff_factor: Multiplier for exponential backoff
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.RequestException, 
                        requests.exceptions.Timeout,
                        requests.exceptions.ConnectionError,
                        requests.exceptions.HTTPError) as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        # Final attempt failed, raise the exception
                        break
                    
                    # Calculate delay with exponential backoff and jitter
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    # Add jitter to prevent thundering herd
                    jitter = random.uniform(0.1, 0.3) * delay
                    total_delay = delay + jitter
                    
                    print(f"API request failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    print(f"Retrying in {total_delay:.2f} seconds...")
                    time.sleep(total_delay)
                except Exception as e:
                    # Non-retryable exception, fail immediately
                    raise e
            
            # All retries exhausted
            raise last_exception
        return wrapper
    return decorator


class ROSAVersionManager:
    """Manages ROSA versions by querying Red Hat API"""
    
    def __init__(self, token: Optional[str] = None, base_url: str = None):
        """Initialize with Red Hat API credentials"""
        self.token = token or os.getenv('REDHAT_OPENSHIFT_TOKEN')
        self.base_url = base_url or os.getenv('REDHAT_OPENSHIFT_API_URL', "https://api.openshift.com")
        self.versions_cache = None
        self.cache_timestamp = None
        
        if not self.token:
            raise ValueError("Red Hat OpenShift token required. Set REDHAT_OPENSHIFT_TOKEN environment variable.")
    
    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=30.0, backoff_factor=2.0)
    def get_access_token(self) -> str:
        """Get access token from Red Hat offline token"""
        if not self.token:
            raise ValueError("No offline token available")
        
        # Try to refresh the offline token to get an access token
        try:
            refresh_url = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
            refresh_data = {
                'grant_type': 'refresh_token',
                'client_id': 'cloud-services',
                'refresh_token': self.token
            }
            
            response = requests.post(refresh_url, data=refresh_data, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get('access_token')
                if access_token:
                    return access_token
                else:
                    raise ValueError("No access token in response")
            else:
                raise ValueError(f"Token refresh failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            raise ValueError(f"Failed to get access token: {e}")
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        access_token = self.get_access_token()
        return {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=60.0, backoff_factor=2.0)
    def fetch_supported_versions(self, cluster_type: str = "rosa", refresh_cache: bool = False) -> List[Dict]:
        """Fetch supported versions from Red Hat API"""
        
        # Check cache first (unless refresh requested)
        if not refresh_cache and self.versions_cache and self.cache_timestamp:
            cache_age = time.time() - self.cache_timestamp
            if cache_age < 3600:  # Cache for 1 hour
                return self.versions_cache
        
        # Map cluster types to API endpoints
        endpoint_map = {
            'rosa': '/api/upgrades_info/v1/graph',
            'hypershift': '/api/upgrades_info/v1/graph',
            'openshift-dedicated': '/api/upgrades_info/v1/graph'
        }
        
        endpoint = endpoint_map.get(cluster_type, '/api/upgrades_info/v1/graph')
        url = f"{self.base_url}{endpoint}"
        
        try:
            headers = self.get_headers()
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse the graph data to extract versions
                versions = []
                if 'nodes' in data:
                    for node in data['nodes']:
                        if 'version' in node:
                            version_info = {
                                'version': node['version'],
                                'available': node.get('available', True),
                                'channel': node.get('channel', 'stable'),
                                'cluster_type': cluster_type
                            }
                            versions.append(version_info)
                
                # Cache the results
                self.versions_cache = versions
                self.cache_timestamp = time.time()
                
                return versions
            else:
                raise ValueError(f"API request failed: {response.status_code} - {response.text}")
                
        except Exception as e:
            # Try ROSA CLI as fallback
            cli_versions = self._try_rosa_cli()
            if cli_versions:
                return cli_versions
            
            raise ValueError(f"Failed to fetch versions: {e}")
    
    def _try_rosa_cli(self) -> Optional[List[Dict]]:
        """Try to get versions using ROSA CLI as fallback"""
        try:
            import subprocess
            result = subprocess.run(['rosa', 'list', 'versions', '--output', 'json'], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                versions = []
                
                for version_info in data:
                    versions.append({
                        'version': version_info.get('version', ''),
                        'available': version_info.get('available', True),
                        'channel': version_info.get('channel', 'stable'),
                        'cluster_type': 'rosa'
                    })
                
                return versions
        except Exception:
            pass
        
        return None
    
    def get_version_list(self, cluster_type: str = "rosa") -> List[str]:
        """Get list of supported version strings"""
        versions = self.fetch_supported_versions(cluster_type)
        return [v['version'] for v in versions if v.get('available', True)]
    
    def get_latest_version(self, cluster_type: str = "rosa", channel: str = "stable") -> str:
        """Get the latest supported version"""
        versions = self.fetch_supported_versions(cluster_type)
        available_versions = [v for v in versions if v.get('available', True) and v.get('channel') == channel]
        
        if not available_versions:
            raise ValueError(f"No available versions found for {cluster_type} in {channel} channel")
        
        # Sort by version and return latest
        latest = max(available_versions, key=lambda x: x['version'])
        return latest['version']
    
    def is_version_supported(self, version: str, cluster_type: str = "rosa") -> bool:
        """Check if a version is supported"""
        versions = self.get_version_list(cluster_type)
        return version in versions
    
    def get_recommended_version(self, input_version: Optional[str] = None, cluster_type: str = "rosa", auto_discover_version: bool = False) -> str:
        """
        Get recommended version based on input
        
        Args:
            input_version: User-specified version (optional)
            cluster_type: Type of cluster (rosa, hypershift, etc.)
            auto_discover_version: If True, auto-discover and upgrade to latest if input version is unsupported
            
        Returns:
            Recommended version string
        """
        if not input_version:
            # No version specified, return latest
            return self.get_latest_version(cluster_type)
        
        # Check if input version is supported
        if self.is_version_supported(input_version, cluster_type):
            return input_version
        
        # Version not supported
        if auto_discover_version:
            # Auto-discover and upgrade to latest
            latest = self.get_latest_version(cluster_type)
            print(f"Version '{input_version}' not supported. Auto-upgrading to '{latest}'")
            return latest
        else:
            # Raise error
            supported_versions = self.get_version_list(cluster_type)
            raise ValueError(f"Version '{input_version}' not supported for {cluster_type}. "
                           f"Supported versions: {', '.join(supported_versions[:5])}...")
    
 
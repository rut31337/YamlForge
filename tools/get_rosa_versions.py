#!/usr/bin/env python3
"""
ROSA Version Manager
Dynamically fetches supported OpenShift versions from Red Hat API
"""

import json
import os
import sys
import requests
from typing import List, Dict, Optional
from datetime import datetime


class ROSAVersionManager:
    """Manages ROSA versions by querying Red Hat API"""
    
    def __init__(self, token: Optional[str] = None, base_url: str = "https://api.openshift.com"):
        """Initialize with Red Hat API credentials"""
        self.token = token or os.getenv('REDHAT_OPENSHIFT_TOKEN')
        self.base_url = base_url
        self.versions_cache = None
        self.cache_timestamp = None
        
        if not self.token:
            raise ValueError("Red Hat OpenShift token required. Set REDHAT_OPENSHIFT_TOKEN environment variable.")
    
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
            
            import requests
            response = requests.post(refresh_url, data=refresh_data, timeout=30)
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get('access_token')
                if access_token:
                    return access_token
            
            # If refresh fails, try using the offline token directly
            print(f"Token refresh failed (status {response.status_code}), using offline token directly")
            return self.token
            
        except Exception as e:
            print(f"Token refresh error: {e}, using offline token directly")
            return self.token

    def get_headers(self) -> Dict[str, str]:
        """Get API request headers with authentication"""
        access_token = self.get_access_token()
        return {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def fetch_supported_versions(self, cluster_type: str = "rosa", refresh_cache: bool = False) -> List[Dict]:
        """
        Fetch supported OpenShift versions from Red Hat API
        
        Args:
            cluster_type: Type of cluster (rosa, hypershift, etc.)
            refresh_cache: Force refresh of cached versions
            
        Returns:
            List of version dictionaries with metadata
        """
        # Use cache if available and recent (within last hour)
        if (not refresh_cache and 
            self.versions_cache and 
            self.cache_timestamp and 
            (datetime.now() - self.cache_timestamp).seconds < 3600):
            return self.versions_cache
        
        # Try rosa CLI first if available
        rosa_versions = self._try_rosa_cli()
        if rosa_versions:
            return rosa_versions
        
        # Try Red Hat API
        try:
            # Query versions endpoint
            params = {
                'order': 'default desc, id desc',
                'search': f"enabled = 'true' AND rosa_enabled = 'true' AND channel_group = 'stable'",
                'size': 100  # Get more versions to have options
            }
            
            url = f"{self.base_url}/api/clusters_mgmt/v1/versions"
            response = requests.get(url, headers=self.get_headers(), params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                versions = data.get('items', [])
                
                # Cache the results
                self.versions_cache = versions
                self.cache_timestamp = datetime.now()
                
                return versions
            else:
                print(f"Error: Failed to fetch versions from API (status {response.status_code})")
                if response.status_code == 401:
                    print("Hint: Token may be expired. Get a fresh token from: https://console.redhat.com/openshift/token")
                raise Exception(f"API request failed with status {response.status_code}")
                
        except Exception as e:
            print(f"Error: Cannot fetch versions from API: {e}")
            raise
    
    def _try_rosa_cli(self) -> Optional[List[Dict]]:
        """Try to get versions using rosa CLI if available"""
        try:
            import subprocess
            
            # Check if rosa CLI is available
            result = subprocess.run(['rosa', 'list', 'versions', '--output', 'json'], 
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                import json
                versions_data = json.loads(result.stdout)
                # Convert rosa CLI format to our expected format
                versions = []
                for version in versions_data:
                    if version.get('rosa_enabled', True):  # Assume rosa_enabled if not specified
                        version_id = version.get('id', version.get('version', ''))
                        # Normalize version format - remove "openshift-v" prefix if present
                        if version_id.startswith('openshift-v'):
                            version_id = version_id.replace('openshift-v', '')
                        versions.append({
                            'id': version_id,
                            'display_name': version.get('display_name', version_id)
                        })
                return versions
        except Exception:
            pass  # rosa CLI not available or failed
        
        return None
    

    
    def get_version_list(self, cluster_type: str = "rosa") -> List[str]:
        """Get simple list of supported version strings"""
        versions = self.fetch_supported_versions(cluster_type)
        version_list = []
        for v in versions:
            version_id = v.get('id', v.get('display_name', ''))
            if version_id:
                # Normalize version format - remove "openshift-v" prefix if present
                if version_id.startswith('openshift-v'):
                    version_id = version_id.replace('openshift-v', '')
                version_list.append(version_id)
        return version_list
    
    def get_latest_version(self, cluster_type: str = "rosa", channel: str = "stable") -> str:
        """Get the latest supported version"""
        versions = self.get_version_list(cluster_type)
        if not versions:
            raise Exception("No supported versions available from API")
        return versions[0]
    
    def is_version_supported(self, version: str, cluster_type: str = "rosa") -> bool:
        """Check if a specific version is supported"""
        supported_versions = self.get_version_list(cluster_type)
        return version in supported_versions
    
    def get_recommended_version(self, input_version: Optional[str] = None, cluster_type: str = "rosa", auto_upgrade_unsupported: bool = False) -> str:
        """
        Get recommended version based on input
        
        Args:
            input_version: User-specified version (can be None)
            cluster_type: Type of cluster
            auto_upgrade_unsupported: If False, raise exception for unsupported versions; if True, auto-upgrade to latest
            
        Returns:
            Recommended version string
            
        Raises:
            ValueError: If input_version is unsupported and auto_upgrade_unsupported is False
        """
        # Handle special keywords (always allowed)
        if input_version and input_version.lower() in ["latest", "stable"]:
            return self.get_latest_version(cluster_type)
        
        # If no version specified, always get latest
        if not input_version:
            return self.get_latest_version(cluster_type)
        
        # Check if explicitly requested version is supported
        if self.is_version_supported(input_version, cluster_type):
            return input_version
        
        # Version is unsupported - behavior depends on auto_upgrade_unsupported flag
        latest = self.get_latest_version(cluster_type)
        
        if auto_upgrade_unsupported:
            # Auto-upgrade to latest with warning
            print(f"Warning: Version {input_version} not supported, using {latest}")
            return latest
        else:
            # Fail with explicit error
            supported_versions = self.get_version_list(cluster_type)
            top_versions = supported_versions[:5] if len(supported_versions) > 5 else supported_versions
            raise ValueError(f"OpenShift version '{input_version}' is not supported. "
                           f"Supported versions include: {', '.join(top_versions)}. "
                           f"Latest version: {latest}. "
                           f"Use 'latest' or specify a supported version.")
    
    def validate_and_fix_versions(self, yaml_config: Dict, cluster_type: str = "rosa") -> Dict:
        """
        Validate and fix versions in a YAML configuration
        
        Args:
            yaml_config: YAML configuration dictionary
            cluster_type: Type of cluster
            
        Returns:
            Updated configuration with valid versions
        """
        if 'openshift_clusters' not in yaml_config:
            return yaml_config
        
        updated_config = yaml_config.copy()
        
        for i, cluster in enumerate(updated_config['openshift_clusters']):
            current_version = cluster.get('version')
            recommended_version = self.get_recommended_version(current_version, cluster_type)
            
            if current_version != recommended_version:
                print(f"Cluster '{cluster.get('name', f'cluster-{i}')}': "
                      f"Updating version {current_version} -> {recommended_version}")
                updated_config['openshift_clusters'][i]['version'] = recommended_version
        
        return updated_config


def main():
    """CLI interface for ROSA version management"""
    import argparse
    
    parser = argparse.ArgumentParser(description='ROSA Version Manager')
    parser.add_argument('--list', action='store_true', help='List all supported versions')
    parser.add_argument('--latest', action='store_true', help='Get latest supported version')
    parser.add_argument('--check', type=str, help='Check if specific version is supported')
    parser.add_argument('--json', action='store_true', help='Output in JSON format')
    parser.add_argument('--cluster-type', default='rosa', help='Cluster type (default: rosa)')
    
    args = parser.parse_args()
    
    try:
        manager = ROSAVersionManager()
        
        if args.list:
            versions = manager.get_version_list(args.cluster_type)
            if args.json:
                print(json.dumps({"supported_versions": versions}, indent=2))
            else:
                print("Supported ROSA versions:")
                for version in versions:
                    print(f"  - {version}")
        
        elif args.latest:
            latest = manager.get_latest_version(args.cluster_type)
            if args.json:
                print(json.dumps({"latest_version": latest}))
            else:
                print(f"Latest supported version: {latest}")
        
        elif args.check:
            is_supported = manager.is_version_supported(args.check, args.cluster_type)
            if args.json:
                print(json.dumps({
                    "version": args.check,
                    "supported": is_supported
                }))
            else:
                status = "✅ SUPPORTED" if is_supported else "❌ NOT SUPPORTED"
                print(f"Version {args.check}: {status}")
                
                if not is_supported:
                    recommended = manager.get_latest_version(args.cluster_type)
                    print(f"Recommended: {recommended}")
        
        else:
            # Default: show summary
            latest = manager.get_latest_version(args.cluster_type)
            versions = manager.get_version_list(args.cluster_type)
            
            if args.json:
                print(json.dumps({
                    "latest_version": latest,
                    "supported_versions": versions,
                    "total_versions": len(versions)
                }, indent=2))
            else:
                print(f"🚀 ROSA Version Summary")
                print(f"Latest version: {latest}")
                print(f"Total supported versions: {len(versions)}")
                print(f"Newest 5 versions: {', '.join(versions[:5])}")
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main() 
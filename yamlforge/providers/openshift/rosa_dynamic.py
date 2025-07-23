"""
Dynamic ROSA Version Integration for YamlForge
Integrates dynamic version checking into the ROSA provider
"""

import os
import sys
from pathlib import Path

# Add the root directory to path to import get_rosa_versions
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tools"))

try:
    from get_rosa_versions import ROSAVersionManager
    DYNAMIC_VERSIONS_AVAILABLE = True
except ImportError:
    DYNAMIC_VERSIONS_AVAILABLE = False


class DynamicROSAVersionProvider:
    """Provides dynamic ROSA version management for YamlForge"""
    
    def __init__(self):
        self.version_manager = None
        if DYNAMIC_VERSIONS_AVAILABLE:
            try:
                self.version_manager = ROSAVersionManager()
            except Exception:
                pass  # Fall back to static versions
    
    def get_recommended_version(self, input_version=None, cluster_type="rosa", auto_upgrade_unsupported=False):
        """
        Get recommended ROSA version
        
        Args:
            input_version: User-specified version (optional)
            cluster_type: Type of cluster (rosa, hypershift, etc.)
            auto_upgrade_unsupported: If False, raise exception for unsupported versions; if True, auto-upgrade to latest
            
        Returns:
            Recommended version string
        """
        if self.version_manager:
            return self.version_manager.get_recommended_version(input_version, cluster_type, auto_upgrade_unsupported)
        
        # No fallback - require API connectivity
        raise Exception("Cannot get recommended ROSA version: API connectivity required")
    
    def is_version_supported(self, version, cluster_type="rosa"):
        """Check if a version is supported"""
        if self.version_manager:
            return self.version_manager.is_version_supported(version, cluster_type)
        
        # No fallback - require API connectivity
        raise Exception("Cannot validate ROSA version: API connectivity required")
    
    def get_latest_version(self, cluster_type="rosa"):
        """Get the latest supported version"""
        if self.version_manager:
            return self.version_manager.get_latest_version(cluster_type)
        
        # No fallback - require API connectivity
        raise Exception("Cannot get latest ROSA version: API connectivity required")
    

    
    def validate_and_fix_cluster_config(self, cluster_config):
        """
        Validate and fix a single cluster configuration
        
        Args:
            cluster_config: Dictionary with cluster configuration
            
        Returns:
            Updated cluster configuration
        """
        if not isinstance(cluster_config, dict):
            return cluster_config
        
        current_version = cluster_config.get('version')
        cluster_type = cluster_config.get('type', 'rosa')
        
        # Map cluster types to version check type
        version_type = 'rosa'
        if 'hypershift' in cluster_type.lower():
            version_type = 'hypershift'
        
        recommended_version = self.get_recommended_version(current_version, version_type)
        
        if current_version != recommended_version:
            print(f"ROSA: Updating cluster '{cluster_config.get('name', 'unnamed')}' "
                  f"version {current_version} -> {recommended_version}")
            cluster_config = cluster_config.copy()
            cluster_config['version'] = recommended_version
        
        return cluster_config


# Global instance for use in ROSA provider
_dynamic_provider = DynamicROSAVersionProvider()


def get_recommended_rosa_version(input_version=None, cluster_type="rosa"):
    """Get recommended ROSA version (module-level function)"""
    return _dynamic_provider.get_recommended_version(input_version, cluster_type)


def validate_rosa_cluster_config(cluster_config):
    """Validate and fix ROSA cluster configuration (module-level function)"""
    return _dynamic_provider.validate_and_fix_cluster_config(cluster_config) 
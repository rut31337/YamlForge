"""
Dynamic ROSA Version Integration for YamlForge
Integrates dynamic version checking into the ROSA provider
"""

import os

try:
    from ...core.rosa_versions import ROSAVersionManager
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
    
    def get_recommended_version(self, input_version=None, cluster_type="rosa", auto_discover_version=False):
        """
        Get recommended ROSA version
        
        Args:
            input_version: User-specified version (optional)
            cluster_type: Type of cluster (rosa, hypershift, etc.)
            auto_discover_version: If False, raise exception for unsupported versions; if True, auto-discover and upgrade to latest
            
        Returns:
            Recommended version string
        """
        if self.version_manager:
            return self.version_manager.get_recommended_version(input_version, cluster_type, auto_discover_version)
        
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
    

    



# Global instance for use in ROSA provider
_dynamic_provider = DynamicROSAVersionProvider()


 
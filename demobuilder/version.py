"""
Version information for DemoBuilder.

DemoBuilder uses the same version as the main YamlForge package.
"""

import sys
import os
from pathlib import Path

def get_version():
    """
    Get version from the main YamlForge package.
    
    Returns:
        str: Version string
    """
    try:
        # Add parent directory to path to import yamlforge
        parent_dir = Path(__file__).parent.parent
        if str(parent_dir) not in sys.path:
            sys.path.insert(0, str(parent_dir))
        
        from yamlforge._version import __version__
        return __version__
    except ImportError:
        # Fallback - try to read from pyproject.toml directly
        try:
            pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
            if pyproject_path.exists():
                with open(pyproject_path, 'r') as f:
                    for line in f:
                        if line.strip().startswith('version = '):
                            version_line = line.strip()
                            version = version_line.split('=')[1].strip().strip('"').strip("'")
                            return version
        except Exception:
            pass
        
        # Final fallback
        return "1.0.0b5"

# Export the version
__version__ = get_version()
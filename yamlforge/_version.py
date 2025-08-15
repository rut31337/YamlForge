"""
Version information for YamlForge.

This module provides version information that can be imported by other modules.
The authoritative version is defined in pyproject.toml.
"""

import os
import sys
from pathlib import Path

def get_version():
    """
    Get version from pyproject.toml if available, otherwise use fallback.
    
    Returns:
        str: Version string
    """
    try:
        # Try to read from pyproject.toml
        current_dir = Path(__file__).parent.parent
        pyproject_path = current_dir / "pyproject.toml"
        
        if pyproject_path.exists():
            with open(pyproject_path, 'r') as f:
                for line in f:
                    if line.strip().startswith('version = '):
                        version_line = line.strip()
                        version = version_line.split('=')[1].strip().strip('"').strip("'")
                        return version
    except Exception:
        pass
    
    # Fallback version if pyproject.toml can't be read
    return "1.0.0b5"

# Export the version
__version__ = get_version()
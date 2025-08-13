"""
YamlForge Utilities

Common utility functions for YamlForge including path resolution
for defaults, mappings, and docs files across different installation modes.
"""

from pathlib import Path
import tempfile


def find_yamlforge_file(filename):
    """
    Find a YamlForge data file (defaults, mappings, docs), checking multiple possible locations:
    1. Environment variable path prefix (YAMLFORGE_DATA_PATH)
    2. Relative to current working directory (development mode)
    3. Relative to this module's location (repository mode)
    4. Within the installed yamlforge package (pip install mode)
    
    Args:
        filename (str): Relative path to the file (e.g., "defaults/gcp.yaml", "mappings/images.yaml")
    
    Returns:
        Path: Path object pointing to the found file
        
    Raises:
        FileNotFoundError: If the file cannot be found in any location
        
    Environment Variables:
        YAMLFORGE_DATA_PATH: Optional prefix path to prepend to filename for custom data locations
    """
    import os
    
    # Try environment variable path prefix first
    env_data_path = os.environ.get('YAMLFORGE_DATA_PATH')
    if env_data_path:
        env_path = Path(env_data_path) / filename
        if env_path.exists():
            return env_path
    
    # Try current working directory (original behavior)
    cwd_path = Path(filename)
    if cwd_path.exists():
        return cwd_path
    
    # Try relative to this module's location (repository mode)
    module_dir = Path(__file__).parent.parent  # Go up to yamlforge root
    repo_path = module_dir / filename
    if repo_path.exists():
        return repo_path
    
    # Try to find in installed package (pip mode with package-data)
    try:
        # Use importlib.resources to access package data files
        from importlib.resources import files
        data_content = files('yamlforge').joinpath(filename).read_text()
        # Create a temporary file with the data
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        temp_file.write(data_content)
        temp_file.close()
        return Path(temp_file.name)
    except (ImportError, FileNotFoundError, Exception):
        pass
    
    # If not found anywhere, raise the original exception
    error_msg = f"Required YamlForge file not found: {filename}"
    if env_data_path:
        error_msg += f"\nChecked paths:\n  - {env_data_path}/{filename} (YAMLFORGE_DATA_PATH)\n  - {cwd_path}\n  - {repo_path}\n  - yamlforge package resources"
    raise FileNotFoundError(error_msg)
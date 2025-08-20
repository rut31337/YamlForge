import json
import jsonschema
import yaml
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import sys

# Import YamlForge utilities for loading location mappings
def find_yamlforge_root():
    """Find YamlForge root directory using multiple strategies"""
    current_file = Path(__file__).resolve()
    
    # Strategy 1: Standard relative path from demobuilder/core/validation.py
    yamlforge_root = current_file.parent.parent.parent
    if (yamlforge_root / 'yamlforge' / 'utils.py').exists():
        return str(yamlforge_root)
    
    # Strategy 2: Search upward from current file location
    search_path = current_file.parent
    for _ in range(5):  # Limit search to 5 levels up
        if (search_path / 'yamlforge' / 'utils.py').exists():
            return str(search_path)
        search_path = search_path.parent
        if search_path == search_path.parent:  # Reached filesystem root
            break
    
    # Strategy 3: Check if yamlforge is already importable (pip installed)
    try:
        import yamlforge.utils
        return None  # Already available in path
    except ImportError:
        pass
    
    raise ImportError("Could not find YamlForge installation")

yamlforge_path = find_yamlforge_root()
if yamlforge_path and str(yamlforge_path) not in sys.path:
    sys.path.insert(0, str(yamlforge_path))

try:
    from yamlforge.utils import find_yamlforge_file
    YAMLFORGE_AVAILABLE = True
except ImportError:
    YAMLFORGE_AVAILABLE = False


class YamlForgeValidator:
    def __init__(self, schema_path: Optional[str] = None):
        # Load available locations from YamlForge mappings
        self.valid_locations = self._load_valid_locations()
        
        if schema_path is None:
            # Try multiple paths to find the schema file
            schema_paths = [
                Path(__file__).parent.parent / "yamlforge-schema.json",  # S2I working directory
                Path(__file__).parent.parent.parent / "docs" / "yamlforge-schema.json",  # Relative from demobuilder
                Path("/opt/app-root/src/yamlforge-schema.json"),  # S2I working directory
                Path("yamlforge-schema.json")  # Current directory
            ]
            schema_path = None
            for path in schema_paths:
                if path.exists():
                    schema_path = path
                    break
            
            if not schema_path:
                raise FileNotFoundError(f"Could not find yamlforge-schema.json in any of: {schema_paths}")
        
        with open(schema_path, 'r') as f:
            self.schema = json.load(f)
        
        self.validator = jsonschema.Draft7Validator(self.schema)
    
    def _load_valid_locations(self) -> List[str]:
        """Load valid locations from YamlForge mappings"""
        if not YAMLFORGE_AVAILABLE:
            return []
        
        try:
            locations_file = find_yamlforge_file("mappings/locations.yaml")
            with open(locations_file, 'r') as f:
                locations_data = yaml.safe_load(f)
                return list(locations_data.keys()) if locations_data else []
        except (FileNotFoundError, yaml.YAMLError):
            return []
    
    def validate_yaml_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        
        try:
            # First run standard JSON schema validation
            self.validator.validate(config)
            
            # Additional custom validation for YamlForge requirements
            if not self._validate_yamlforge_requirements(config):
                errors.append("Configuration Error: At least one of 'instances', 'openshift_clusters', or 'storage' is required in YamlForge configurations.")
            
            # Validate locations
            location_errors = self._validate_locations(config)
            if location_errors:
                errors.extend(location_errors)
                errors.append("")
                errors.append("Add at least one of these to your YAML file:")
                errors.append("")
                errors.append("For cloud instances:")
                errors.append("yamlforge:")
                errors.append("  cloud_workspace:")
                errors.append("    name: \"your-workspace-name\"")
                errors.append("  instances:")
                errors.append("    - name: \"my-instance-{guid}\"")
                errors.append("      provider: \"aws\"")
                errors.append("      flavor: \"small\"")
                errors.append("      image: \"RHEL9-latest\"")
                errors.append("      region: \"us-east-1\"")
                errors.append("      ssh_key: \"my-key\"")
                errors.append("")
                errors.append("For OpenShift clusters:")
                errors.append("yamlforge:")
                errors.append("  cloud_workspace:")
                errors.append("    name: \"your-workspace-name\"")
                errors.append("  openshift_clusters:")
                errors.append("    - name: \"my-cluster-{guid}\"")
                errors.append("      type: \"rosa-classic\"")
                errors.append("      region: \"us-east-1\"")
                errors.append("      size: \"small\"")
                errors.append("")
                errors.append("For object storage:")
                errors.append("yamlforge:")
                errors.append("  cloud_workspace:")
                errors.append("    name: \"your-workspace-name\"")
                errors.append("  storage:")
                errors.append("    - name: \"my-storage-bucket\"")
                errors.append("      provider: \"aws\"")
                errors.append("      location: \"us-east\"")
                errors.append("      public: false")
                errors.append("      encryption: true")
                return False, errors
            
            return True, []
            
        except jsonschema.ValidationError as e:
            errors.append(f"Schema validation error: {e.message}")
            if e.path:
                errors.append(f"  Path: {' -> '.join(str(p) for p in e.path)}")
            return False, errors
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
            return False, errors
    
    def _validate_yamlforge_requirements(self, config: Dict[str, Any]) -> bool:
        """Check that yamlforge has either instances, openshift_clusters, or storage"""
        if 'yamlforge' not in config:
            return False
        
        yamlforge_config = config['yamlforge']
        
        # Must have at least one of: instances, openshift_clusters, or storage
        has_instances = 'instances' in yamlforge_config and yamlforge_config['instances']
        has_openshift = 'openshift_clusters' in yamlforge_config and yamlforge_config['openshift_clusters']
        has_storage = 'storage' in yamlforge_config and yamlforge_config['storage']
        
        return has_instances or has_openshift or has_storage
    
    def _validate_locations(self, config: Dict[str, Any]) -> List[str]:
        """Validate that all locations used in the config exist in YamlForge mappings"""
        if not self.valid_locations:
            return []  # Skip validation if locations couldn't be loaded
        
        errors = []
        
        if 'yamlforge' not in config:
            return errors
        
        yamlforge_config = config['yamlforge']
        
        # Check instance locations
        if 'instances' in yamlforge_config:
            for i, instance in enumerate(yamlforge_config['instances']):
                location = instance.get('location') or instance.get('region')
                if location and location not in self.valid_locations:
                    errors.append(f"Invalid location '{location}' in instance {i+1} ('{instance.get('name', 'unnamed')}')")
        
        # Check cluster regions
        if 'openshift_clusters' in yamlforge_config:
            for i, cluster in enumerate(yamlforge_config['openshift_clusters']):
                region = cluster.get('region') or cluster.get('location')
                if region and region not in self.valid_locations:
                    errors.append(f"Invalid location '{region}' in cluster {i+1} ('{cluster.get('name', 'unnamed')}')")
        
        # Check storage bucket locations
        if 'storage' in yamlforge_config:
            for i, bucket in enumerate(yamlforge_config['storage']):
                location = bucket.get('location') or bucket.get('region')
                if location and location not in self.valid_locations:
                    errors.append(f"Invalid location '{location}' in storage bucket {i+1} ('{bucket.get('name', 'unnamed')}')")
        
        if errors:
            errors.append("")
            errors.append(f"Valid locations are: {', '.join(sorted(self.valid_locations[:10]))}{'...' if len(self.valid_locations) > 10 else ''}")
        
        return errors
    
    def _find_similar_location(self, invalid_location: str) -> Optional[str]:
        """Find a similar valid location for an invalid one"""
        if not self.valid_locations:
            return None
        
        invalid_lower = invalid_location.lower()
        
        # Common mappings for invalid locations
        location_mappings = {
            'us': 'us-east-1',
            'usa': 'us-east-1', 
            'america': 'us-east-1',
            'east': 'us-east-1',
            'west': 'us-west-1',
            'eu': 'eu-west-1',
            'europe': 'eu-west-1',
            'asia': 'ap-southeast-1',
            'ap': 'ap-southeast-1',
            'pacific': 'ap-southeast-1'
        }
        
        # Direct mapping first
        if invalid_lower in location_mappings:
            mapped = location_mappings[invalid_lower]
            if mapped in self.valid_locations:
                return mapped
        
        # Partial matching - find the first valid location that contains the invalid string
        for valid_location in self.valid_locations:
            if invalid_lower in valid_location.lower() or valid_location.lower().startswith(invalid_lower):
                return valid_location
        
        # If no match found, return the first valid location
        return self.valid_locations[0] if self.valid_locations else None
    
    def validate_yaml_string(self, yaml_string: str) -> Tuple[bool, List[str], Optional[Dict[str, Any]]]:
        try:
            config = yaml.safe_load(yaml_string)
            if config is None:
                return False, ["Empty YAML configuration"], None
            
            is_valid, errors = self.validate_yaml_config(config)
            return is_valid, errors, config
            
        except yaml.YAMLError as e:
            return False, [f"YAML parsing error: {str(e)}"], None
    
    def get_required_fields(self) -> Dict[str, Any]:
        required = {}
        
        if 'required' in self.schema:
            required['root'] = self.schema['required']
        
        if 'definitions' in self.schema:
            for def_name, definition in self.schema['definitions'].items():
                if 'required' in definition:
                    required[def_name] = definition['required']
        
        return required
    
    def fix_common_issues(self, config: Dict[str, Any]) -> Dict[str, Any]:
        fixed_config = config.copy()
        
        if 'yamlforge' not in fixed_config:
            fixed_config['yamlforge'] = {}
        
        yamlforge_config = fixed_config['yamlforge']
        
        if 'cloud_workspace' not in yamlforge_config:
            yamlforge_config['cloud_workspace'] = {
                'name': 'demo-workspace'
            }
        elif 'name' not in yamlforge_config['cloud_workspace']:
            yamlforge_config['cloud_workspace']['name'] = 'demo-workspace'
        
        if 'instances' in yamlforge_config:
            for instance in yamlforge_config['instances']:
                if 'provider' in instance and instance['provider'] not in [
                    'aws', 'azure', 'gcp', 'oci', 'ibm_vpc', 'ibm_classic', 
                    'vmware', 'alibaba', 'cheapest', 'cheapest-gpu', 'cnv'
                ]:
                    instance['provider'] = 'cheapest'
                
                if instance.get('provider') != 'cnv' and 'region' not in instance and 'location' not in instance:
                    # Use first valid location if available, otherwise fallback
                    instance['location'] = self.valid_locations[0] if self.valid_locations else 'us-east-1'
                
                # Fix invalid locations
                location = instance.get('location') or instance.get('region')
                if location and self.valid_locations and location not in self.valid_locations:
                    # Try to find a similar valid location
                    valid_location = self._find_similar_location(location)
                    if valid_location:
                        if 'location' in instance:
                            instance['location'] = valid_location
                        elif 'region' in instance:
                            instance['region'] = valid_location
                
                # Fix common AI error: flavor set to object with cores/memory
                if 'flavor' in instance and isinstance(instance['flavor'], dict):
                    flavor_obj = instance['flavor']
                    # Extract cores and memory from flavor object
                    cores = None
                    memory = None
                    
                    if 'cores' in flavor_obj:
                        cores = flavor_obj['cores']
                    elif 'cpu' in flavor_obj:
                        cores = flavor_obj['cpu']
                    
                    if 'memory' in flavor_obj:
                        mem_val = flavor_obj['memory']
                        if isinstance(mem_val, str):
                            # Convert "2gb" to 2048
                            if mem_val.lower().endswith('gb'):
                                memory = int(mem_val[:-2]) * 1024
                            elif mem_val.lower().endswith('mb'):
                                memory = int(mem_val[:-2])
                            else:
                                memory = 2048  # Default
                        else:
                            memory = mem_val
                    elif 'ram' in flavor_obj:
                        ram_val = flavor_obj['ram']
                        if isinstance(ram_val, str):
                            # Convert "2gb" to 2048
                            if ram_val.lower().endswith('gb'):
                                memory = int(ram_val[:-2]) * 1024
                            elif ram_val.lower().endswith('mb'):
                                memory = int(ram_val[:-2])
                            else:
                                memory = 2048  # Default
                        else:
                            memory = ram_val
                    
                    # Remove the invalid flavor object and set correct fields
                    del instance['flavor']
                    if cores:
                        instance['cores'] = cores
                    if memory:
                        instance['memory'] = memory
                
                if 'flavor' not in instance and ('cores' not in instance or 'memory' not in instance):
                    instance['flavor'] = 'medium'
        
        if 'security_groups' in yamlforge_config:
            for sg in yamlforge_config['security_groups']:
                if 'rules' in sg:
                    for rule in sg['rules']:
                        if 'port_range' not in rule and 'port' in rule:
                            rule['port_range'] = str(rule['port'])
                            del rule['port']
        
        return fixed_config
    
    def suggest_fixes(self, errors: List[str]) -> List[str]:
        suggestions = []
        
        for error in errors:
            if "yamlforge" in error and "required" in error:
                suggestions.append("Add 'yamlforge:' section to your configuration")
            
            if "cloud_workspace" in error:
                suggestions.append("Add 'cloud_workspace:' with 'name:' field under yamlforge")
            
            if "instances" in error and "openshift_clusters" in error:
                suggestions.append("Add either 'instances:' or 'openshift_clusters:' section")
            
            if "region" in error or "location" in error:
                suggestions.append("Add 'region:' or 'location:' field to instances (not required for CNV)")
            
            if "flavor" in error or "cores" in error or "memory" in error:
                suggestions.append("Add either 'flavor:' OR both 'cores:' and 'memory:' to instances")
            
            if "port_range" in error:
                suggestions.append("Use 'port_range:' instead of 'port:' in security group rules")
        
        return list(set(suggestions))


def validate_and_fix_yaml(yaml_string: str, auto_fix: bool = True) -> Tuple[bool, str, List[str]]:
    validator = YamlForgeValidator()
    
    is_valid, errors, config = validator.validate_yaml_string(yaml_string)
    
    if is_valid:
        return True, yaml_string, []
    
    if auto_fix and config is not None:
        max_fix_attempts = 5
        current_config = config
        fix_messages = []
        
        for attempt in range(max_fix_attempts):
            try:
                # Apply fixes
                fixed_config = validator.fix_common_issues(current_config)
                
                # Add missing GUID if not present
                if 'guid' not in fixed_config:
                    fixed_config['guid'] = 'demo1'
                
                # Ensure GUID is valid format
                if 'guid' in fixed_config:
                    guid = str(fixed_config['guid'])
                    if len(guid) != 5 or not guid.islower() or not guid.isalnum():
                        fixed_config['guid'] = 'demo1'
                
                # Validate the fixed config
                is_fixed_valid, fixed_errors = validator.validate_yaml_config(fixed_config)
                
                if is_fixed_valid:
                    fixed_yaml = yaml.dump(fixed_config, default_flow_style=False, sort_keys=False)
                    fix_messages.append(f"Auto-fixed configuration issues (attempt {attempt + 1})")
                    return True, fixed_yaml, fix_messages
                else:
                    # Continue fixing in next iteration
                    current_config = fixed_config
                    fix_messages.append(f"Attempt {attempt + 1}: Fixed some issues, {len(fixed_errors)} remaining")
                    
                    # Add more aggressive fixes based on remaining errors
                    for error in fixed_errors:
                        if "Either 'instances' or 'openshift_clusters'" in str(error) or "Configuration Error" in str(error):
                            # Force add instances if neither exists
                            yamlforge_config = current_config.get('yamlforge', {})
                            has_instances = 'instances' in yamlforge_config and yamlforge_config.get('instances')
                            has_openshift = 'openshift_clusters' in yamlforge_config and yamlforge_config.get('openshift_clusters')
                            
                            if not has_instances and not has_openshift:
                                if 'yamlforge' not in current_config:
                                    current_config['yamlforge'] = {}
                                current_config['yamlforge']['instances'] = [{
                                    'name': 'default-instance',
                                    'provider': 'cheapest',
                                    'flavor': 'medium',
                                    'image': 'RHEL9-latest',
                                    'location': 'us-east'
                                }]
                                fix_messages.append("Added default instance to satisfy schema requirements")
                        
                        if "'name' is a required property" in str(error) and 'instances' in current_config.get('yamlforge', {}):
                            # Fix instances missing names
                            for i, instance in enumerate(current_config['yamlforge']['instances']):
                                if 'name' not in instance:
                                    instance['name'] = f'instance-{i+1}'
                        
                        if "'provider' is a required property" in str(error) and 'instances' in current_config.get('yamlforge', {}):
                            # Fix instances missing providers
                            for instance in current_config['yamlforge']['instances']:
                                if 'provider' not in instance:
                                    instance['provider'] = 'cheapest'
                
            except Exception as e:
                fix_messages.append(f"Auto-fix attempt {attempt + 1} failed: {str(e)}")
                break
        
        # If we get here, auto-fix didn't completely succeed
        suggestions = validator.suggest_fixes(fixed_errors if 'fixed_errors' in locals() else errors)
        return False, yaml_string, fix_messages + (fixed_errors if 'fixed_errors' in locals() else errors) + suggestions
    
    suggestions = validator.suggest_fixes(errors)
    return False, yaml_string, errors + suggestions
import json
import jsonschema
import yaml
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path


class YamlForgeValidator:
    def __init__(self, schema_path: Optional[str] = None):
        if schema_path is None:
            schema_path = Path(__file__).parent.parent.parent / "docs" / "yamlforge-schema.json"
        
        with open(schema_path, 'r') as f:
            self.schema = json.load(f)
        
        self.validator = jsonschema.Draft7Validator(self.schema)
    
    def validate_yaml_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        
        try:
            # First run standard JSON schema validation
            self.validator.validate(config)
            
            # Additional custom validation for YamlForge requirements
            if not self._validate_yamlforge_requirements(config):
                errors.append("Configuration Error: Either 'instances' or 'openshift_clusters' (or both) are required in YamlForge configurations.")
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
        """Check that yamlforge has either instances or openshift_clusters"""
        if 'yamlforge' not in config:
            return False
        
        yamlforge_config = config['yamlforge']
        
        # Must have either instances or openshift_clusters (or both)
        has_instances = 'instances' in yamlforge_config and yamlforge_config['instances']
        has_openshift = 'openshift_clusters' in yamlforge_config and yamlforge_config['openshift_clusters']
        
        return has_instances or has_openshift
    
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
                    instance['location'] = 'us-east'
                
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
import sys
import os
import tempfile
import subprocess
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path
import yaml
import json

# Find YamlForge root directory but don't import yet
current_path = Path(__file__).resolve()
yamlforge_root = None

# Start from current file and go up until we find YamlForge root
for parent in current_path.parents:
    if parent.name == 'YamlForge' and (parent / 'yamlforge.py').exists():
        yamlforge_root = parent
        break

# Store for later use but don't import yet to avoid path issues
YAMLFORGE_AVAILABLE = yamlforge_root is not None


class YamlForgeAnalyzer:
    def __init__(self):
        self.yamlforge_available = YAMLFORGE_AVAILABLE
        self.yamlforge_root = yamlforge_root if yamlforge_root else Path.cwd()
        self._converter_imported = False
    
    async def analyze_configuration(self, yaml_config: str, enabled_providers: Optional[List[str]] = None) -> Tuple[bool, Dict[str, Any], List[str]]:
        # Always use subprocess to avoid import-time path issues
        return await self._analyze_via_subprocess(yaml_config, enabled_providers)
    
    async def _analyze_via_import(self, yaml_config: str) -> Tuple[bool, Dict[str, Any], List[str]]:
        try:
            config_dict = yaml.safe_load(yaml_config)
            
            # Change to YamlForge directory before creating converter
            original_cwd = os.getcwd()
            try:
                os.chdir(str(self.yamlforge_root))
                
                converter = YamlForgeConverter()
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                    f.write(yaml_config)
                    config_file = f.name
                
                try:
                    converter.load_config(config_file)
                    
                    analysis_result = {
                        'providers_detected': converter.get_detected_providers(),
                        'estimated_costs': converter.get_cost_estimates() if hasattr(converter, 'get_cost_estimates') else {},
                        'resource_summary': converter.get_resource_summary() if hasattr(converter, 'get_resource_summary') else {},
                        'validation_status': 'valid',
                        'guid': config_dict.get('guid', 'Not specified'),
                        'workspace_name': config_dict.get('yamlforge', {}).get('cloud_workspace', {}).get('name', 'Unknown')
                    }
                    
                    return True, analysis_result, []
                    
                finally:
                    os.unlink(config_file)
                    
            finally:
                # Always restore original directory
                os.chdir(original_cwd)
                
        except Exception as e:
            return False, {}, [f"Analysis failed: {str(e)}"]
    
    async def _analyze_via_subprocess(self, yaml_config: str, enabled_providers: Optional[List[str]] = None) -> Tuple[bool, Dict[str, Any], List[str]]:
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                f.write(yaml_config)
                config_file = f.name
            
            try:
                yamlforge_path = self.yamlforge_root / "yamlforge.py"
                
                # Verify the YamlForge directory structure
                if not yamlforge_path.exists():
                    return False, {}, [f"YamlForge script not found at: {yamlforge_path}"]
                
                defaults_dir = self.yamlforge_root / "defaults"
                if not defaults_dir.exists():
                    return False, {}, [f"YamlForge defaults directory not found at: {defaults_dir}"]
                
                mappings_dir = self.yamlforge_root / "mappings"
                if not mappings_dir.exists():
                    return False, {}, [f"YamlForge mappings directory not found at: {mappings_dir}"]
                
                # Ensure YamlForge can find its mappings and defaults
                env = os.environ.copy()
                env['PYTHONPATH'] = str(self.yamlforge_root)
                
                # Handle provider selection from DemoBuilder
                temp_core_config = None
                if enabled_providers is not None:
                    # Get all available providers
                    all_providers = ['aws', 'azure', 'gcp', 'ibm_vpc', 'ibm_classic', 'oci', 'vmware', 'alibaba', 'cnv']
                    
                    # Calculate disabled providers (those not in enabled_providers)
                    disabled_providers = [p for p in all_providers if p not in enabled_providers]
                    
                    if disabled_providers:
                        # Create temporary core config with disabled providers excluded
                        core_config_path = self.yamlforge_root / "defaults" / "core.yaml"
                        
                        # Read existing core config
                        with open(core_config_path, 'r') as f:
                            core_config = yaml.safe_load(f)
                        
                        # Update provider exclusions
                        if 'provider_selection' not in core_config:
                            core_config['provider_selection'] = {}
                        
                        # Merge disabled providers with existing exclusions
                        existing_excluded = core_config['provider_selection'].get('exclude_from_cheapest', [])
                        all_excluded = list(set(existing_excluded + disabled_providers))
                        core_config['provider_selection']['exclude_from_cheapest'] = all_excluded
                        
                        # Write temporary core config
                        temp_core_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, dir=str(self.yamlforge_root / "defaults"))
                        yaml.dump(core_config, temp_core_config, default_flow_style=False)
                        temp_core_config.close()
                        
                        # Backup original and use temporary
                        original_core_config = core_config_path.with_suffix('.yaml.backup')
                        core_config_path.rename(original_core_config)
                        Path(temp_core_config.name).rename(core_config_path)
                
                cmd = [
                    sys.executable,
                    str(yamlforge_path),
                    config_file,
                    "--analyze",
                    "--no-credentials"
                ]
                
                # Change to YamlForge directory before running
                original_cwd = os.getcwd()
                try:
                    os.chdir(str(self.yamlforge_root))
                    
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=30,
                        env=env
                    )
                finally:
                    # Always restore original directory
                    os.chdir(original_cwd)
                
                if result.returncode == 0:
                    analysis_result = self._parse_analyze_output(result.stdout, yaml_config)
                    return True, analysis_result, []
                else:
                    errors = result.stderr.strip().split('\n') if result.stderr else []
                    return False, {}, errors
                    
            finally:
                os.unlink(config_file)
                
                # Restore original core config if we created a temporary one
                if temp_core_config is not None:
                    try:
                        core_config_path = self.yamlforge_root / "defaults" / "core.yaml"
                        original_core_config = core_config_path.with_suffix('.yaml.backup')
                        
                        # Remove temporary config and restore original
                        if core_config_path.exists():
                            core_config_path.unlink()
                        if original_core_config.exists():
                            original_core_config.rename(core_config_path)
                    except Exception as e:
                        # Log error but don't fail the analysis
                        pass
                
        except subprocess.TimeoutExpired:
            return False, {}, ["Analysis timed out after 30 seconds"]
        except Exception as e:
            return False, {}, [f"Analysis failed: {str(e)}"]
    
    def _parse_analyze_output(self, output: str, yaml_config: str) -> Dict[str, Any]:
        try:
            config_dict = yaml.safe_load(yaml_config)
        except:
            config_dict = {}
        
        lines = output.strip().split('\n')
        
        analysis_result = {
            'providers_detected': [],
            'estimated_costs': {},
            'resource_summary': {},
            'instances': [],
            'cost_summary': {},
            'validation_status': 'valid',
            'guid': config_dict.get('guid', 'Not specified'),
            'workspace_name': config_dict.get('yamlforge', {}).get('cloud_workspace', {}).get('name', 'Unknown'),
            'raw_output': output
        }
        
        current_section = None
        current_instance = None
        cost_analysis_for_instance = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Section detection
            if line.startswith('INSTANCES ('):
                current_section = 'instances'
                continue
            elif line.startswith('REQUIRED PROVIDERS:'):
                current_section = 'providers'
                continue
            elif line.startswith('COST SUMMARY:'):
                current_section = 'cost_summary'
                continue
            elif line.startswith('================'):
                current_section = None
                continue
            
            if current_section == 'instances':
                # Instance header (e.g., "1. instance-1:")
                if line and line[0].isdigit() and '. ' in line and line.endswith(':'):
                    if current_instance:
                        analysis_result['instances'].append(current_instance)
                    
                    instance_name = line.split('. ', 1)[1].rstrip(':')
                    current_instance = {
                        'name': instance_name,
                        'provider': 'Unknown',
                        'region': 'Unknown',
                        'flavor': 'Unknown',
                        'instance_type': 'Unknown',
                        'hourly_cost': 'Unknown',
                        'image': 'Unknown',
                        'cost_analysis': [],
                        'errors': []
                    }
                    cost_analysis_for_instance = None
                    continue
                
                if current_instance:
                    # Parse instance details
                    if line.startswith('Provider: '):
                        provider_info = line[10:].strip()
                        if '(' in provider_info and ')' in provider_info:
                            current_instance['provider'] = provider_info.split('(')[0].strip()
                            selected_provider = provider_info.split('(')[1].split(')')[0].strip()
                            current_instance['selected_provider'] = selected_provider
                        else:
                            current_instance['provider'] = provider_info
                    elif line.startswith('Region: '):
                        current_instance['region'] = line[8:].strip()
                    elif line.startswith('Flavor: '):
                        flavor_info = line[8:].strip()
                        if '(' in flavor_info and ')' in flavor_info:
                            current_instance['flavor'] = flavor_info.split('(')[0].strip()
                            current_instance['instance_type'] = flavor_info.split('(')[1].split(')')[0].strip()
                        else:
                            current_instance['flavor'] = flavor_info
                    elif line.startswith('Hourly Cost: '):
                        current_instance['hourly_cost'] = line[13:].strip()
                    elif line.startswith('Image: '):
                        current_instance['image'] = line[7:].strip()
                    elif line.startswith('→ Error: '):
                        current_instance['errors'].append(line[9:].strip())
                    elif line.startswith('Cost analysis for instance'):
                        cost_analysis_for_instance = current_instance['name']
                        continue
                    elif cost_analysis_for_instance and line.strip() and cost_analysis_for_instance == current_instance['name']:
                        # Parse cost analysis lines (e.g., "     azure: $0.0208/hour (Standard_B2s, 2 vCPU, 4GB) ← SELECTED")
                        # Only parse if we have a cost analysis section active for this instance
                        if ':' in line and '$' in line and line.strip().startswith((' ', '\t')):
                            provider_line = line.strip()
                            if provider_line and not provider_line.startswith(('1.', '2.', '3.', '4.', '5.')):
                                cost_entry = self._parse_cost_analysis_line(provider_line)
                                if cost_entry:
                                    current_instance['cost_analysis'].append(cost_entry)
                        elif not line.strip().startswith((' ', '\t')):
                            # End of cost analysis section
                            cost_analysis_for_instance = None
            
            elif current_section == 'providers':
                if line.startswith('• '):
                    provider = line[2:].strip()
                    analysis_result['providers_detected'].append(provider)
            
            elif current_section == 'cost_summary':
                if ':' in line and ('$' in line or 'hour' in line or 'monthly' in line.lower()):
                    key, value = line.split(':', 1)
                    analysis_result['cost_summary'][key.strip()] = value.strip()
        
        # Add the last instance if exists
        if current_instance:
            analysis_result['instances'].append(current_instance)
        
        return analysis_result
    
    def _parse_cost_analysis_line(self, line: str) -> Dict[str, Any]:
        """Parse a cost analysis line like 'azure: $0.0208/hour (Standard_B2s, 2 vCPU, 4GB) ← SELECTED'"""
        try:
            # Check if this provider is selected
            is_selected = '← SELECTED' in line
            line = line.replace('← SELECTED', '').strip()
            
            # Split provider and cost info
            if ':' not in line:
                return None
            
            provider, cost_info = line.split(':', 1)
            provider = provider.strip()
            cost_info = cost_info.strip()
            
            # Extract cost
            cost = 'Unknown'
            if '$' in cost_info:
                cost_part = cost_info.split('(')[0].strip()
                cost = cost_part
            
            # Extract instance details from parentheses
            instance_details = ''
            if '(' in cost_info and ')' in cost_info:
                start = cost_info.find('(')
                end = cost_info.find(')', start)
                instance_details = cost_info[start+1:end]
            
            return {
                'provider': provider,
                'cost': cost,
                'instance_details': instance_details,
                'is_selected': is_selected
            }
        except Exception:
            return None
    
    def get_provider_capabilities(self, provider: str) -> Dict[str, Any]:
        capabilities = {
            'aws': {
                'supports_gpu': True,
                'supports_openshift': True,
                'supports_cnv': False,
                'regions': ['us-east-1', 'us-west-2', 'eu-west-1', 'ap-southeast-1'],
                'instance_types': ['t3.micro', 't3.small', 't3.medium', 't3.large', 'm5.large', 'c5.large']
            },
            'azure': {
                'supports_gpu': True,
                'supports_openshift': True,
                'supports_cnv': False,
                'regions': ['eastus', 'westus2', 'northeurope', 'southeastasia'],
                'instance_types': ['Standard_B1s', 'Standard_B2s', 'Standard_D2s_v3', 'Standard_D4s_v3']
            },
            'gcp': {
                'supports_gpu': True,
                'supports_openshift': False,
                'supports_cnv': False,
                'regions': ['us-central1', 'us-west1', 'europe-west1', 'asia-southeast1'],
                'instance_types': ['e2-micro', 'e2-small', 'e2-medium', 'n1-standard-1', 'n1-standard-2']
            },
            'cnv': {
                'supports_gpu': True,
                'supports_openshift': True,
                'supports_cnv': True,
                'regions': ['cluster-default'],
                'instance_types': ['small', 'medium', 'large', 'xlarge', 'gpu-small', 'gpu-large']
            },
            'cheapest': {
                'supports_gpu': False,
                'supports_openshift': True,
                'supports_cnv': False,
                'regions': ['auto-select'],
                'instance_types': ['auto-select']
            },
            'cheapest-gpu': {
                'supports_gpu': True,
                'supports_openshift': False,
                'supports_cnv': False,
                'regions': ['auto-select'],
                'instance_types': ['auto-select']
            }
        }
        
        return capabilities.get(provider, {
            'supports_gpu': False,
            'supports_openshift': False,
            'supports_cnv': False,
            'regions': [],
            'instance_types': []
        })
    
    def suggest_cost_optimization(self, config_dict: Dict[str, Any]) -> List[str]:
        suggestions = []
        
        if 'yamlforge' not in config_dict or 'instances' not in config_dict['yamlforge']:
            return suggestions
        
        instances = config_dict['yamlforge']['instances']
        
        has_gpu_instances = any(
            instance.get('gpu_type') or instance.get('gpu_count') 
            for instance in instances
        )
        
        providers_used = set(instance.get('provider', 'unknown') for instance in instances)
        
        # Only suggest cheaper alternatives if user specified a specific provider
        specific_providers = [p for p in providers_used if p not in ['cheapest', 'cheapest-gpu', 'cnv']]
        
        if specific_providers:
            if has_gpu_instances and 'cheapest-gpu' not in providers_used:
                suggestions.append(
                    "Tell me 'cheapest' if you want me to provide a cheaper GPU alternative"
                )
            elif not has_gpu_instances and 'cheapest' not in providers_used:
                suggestions.append(
                    "Tell me 'cheapest' if you want me to provide a cheaper alternative"
                )
        
        for instance in instances:
            if instance.get('flavor') in ['xlarge', 'large'] and instance.get('count', 1) > 1:
                suggestions.append(
                    f"Instance '{instance.get('name', 'unnamed')}' uses large instances with high count - consider smaller instances"
                )
        
        return suggestions
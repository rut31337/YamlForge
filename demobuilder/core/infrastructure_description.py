"""
Infrastructure description generation for DemoBuilder.

This module generates structured infrastructure descriptions that can be used
to create visual diagrams, independent of YamlForge analysis results.
"""

import yaml
import json
from typing import Dict, List, Any
import re


def generate_infrastructure_description(yaml_content: str, user_requirements: str) -> Dict:
    """
    Generate a structured infrastructure description from YAML content and user requirements.
    This creates a standardized format that can be used for diagram generation.
    """
    
    try:
        # Parse YAML content
        yaml_data = yaml.safe_load(yaml_content)
        if not yaml_data:
            return {}
            
    except yaml.YAMLError:
        return {}
    
    description = {
        'metadata': {
            'title': yaml_data.get('yamlforge', {}).get('cloud_workspace', {}).get('name', 'Infrastructure'),
            'description': yaml_data.get('yamlforge', {}).get('cloud_workspace', {}).get('description', user_requirements[:100]),
            'guid': yaml_data.get('yamlforge', {}).get('cloud_workspace', {}).get('guid', 'unknown'),
            'generated_from': 'yaml_analysis'
        },
        'providers': [],
        'instances': [],
        'networks': [],
        'storage': [],
        'connections': []
    }
    
    # Extract instances directly from yamlforge.instances
    instances_section = yaml_data.get('yamlforge', {}).get('instances', [])
    providers_found = set()
    
    for instance in instances_section:
        if isinstance(instance, dict):
            provider = instance.get('provider', 'unknown')
            providers_found.add(provider)
            
            # Create instance info
            instance_info = {
                'id': f"{provider}_{instance.get('name', 'instance').replace('-', '_')}",
                'name': instance.get('name', f'{provider}-instance'),
                'provider': provider,
                'type': instance.get('flavor', instance.get('instance_type', 'unknown')),
                'region': instance.get('location', instance.get('region', 'unknown')),
                'cores': instance.get('cores', 'N/A'),
                'memory': instance.get('memory', 'N/A'),
                'purpose': _determine_instance_purpose(instance, user_requirements),
                'os': instance.get('image', 'Linux')
            }
            description['instances'].append(instance_info)
    
    # Extract OpenShift clusters
    clusters_section = yaml_data.get('yamlforge', {}).get('openshift_clusters', [])
    
    for cluster in clusters_section:
        if isinstance(cluster, dict):
            provider = cluster.get('provider', 'unknown')
            providers_found.add(provider)
            
            # Create cluster as instance info
            cluster_info = {
                'id': f"{provider}_{cluster.get('name', 'cluster').replace('-', '_')}",
                'name': cluster.get('name', f'{provider}-cluster'),
                'provider': provider,
                'type': f"OpenShift {cluster.get('type', 'cluster')}",
                'region': cluster.get('region', cluster.get('location', 'unknown')),
                'cores': cluster.get('workers', 3) * 4,  # Estimate cores
                'memory': cluster.get('workers', 3) * 16384,  # Estimate memory
                'purpose': 'openshift',
                'os': 'RHCOS'
            }
            description['instances'].append(cluster_info)
    
    # Create provider info for found providers
    for provider_name in providers_found:
        provider_info = {
            'name': provider_name,
            'display_name': _get_provider_display_name(provider_name),
            'region': 'unknown',
            'enabled': True
        }
        description['providers'].append(provider_info)
        
        # Generate networks based on instance distribution and purposes
        networks_for_provider = _generate_networks_for_provider(provider_name, description['instances'], user_requirements)
        description['networks'].extend(networks_for_provider)
    
    # Generate logical connections
    description['connections'] = _generate_logical_connections(description)
    
    return description


def _get_provider_display_name(provider_name: str) -> str:
    """Get human-readable provider display name"""
    provider_names = {
        'aws': 'Amazon Web Services',
        'azure': 'Microsoft Azure',
        'gcp': 'Google Cloud Platform',
        'ibm_vpc': 'IBM Cloud VPC', 
        'ibm_classic': 'IBM Cloud Classic',
        'oci': 'Oracle Cloud Infrastructure',
        'alibaba': 'Alibaba Cloud',
        'vmware': 'VMware vSphere',
        'cnv': 'Container Native Virtualization',
        'cheapest': 'Cost Optimized',
        'cheapest-gpu': 'Cost Optimized GPU'
    }
    return provider_names.get(provider_name, provider_name.upper())


def _extract_instances_from_provider(provider_name: str, provider_config: Dict, user_requirements: str) -> List[Dict]:
    """Extract instance information from provider configuration - DEPRECATED"""
    # This function is no longer used since we extract directly from yamlforge.instances
    return []


def _determine_instance_purpose(instance: Dict, user_requirements: str) -> str:
    """Determine the purpose of an instance based on configuration and requirements"""
    
    # Check instance name/type for clues - prioritize name over user requirements
    name = instance.get('name', '').lower()
    instance_type = instance.get('instance_type', instance.get('flavor', '')).lower()
    user_req_lower = user_requirements.lower()
    
    # Check for specific patterns in instance names first (more reliable)
    if 'gpu' in instance_type or 'gpu' in name:
        return 'gpu'
    elif 'web' in name or 'frontend' in name or 'nginx' in name or 'apache' in name:
        return 'web'
    elif 'db' in name or 'database' in name or 'mysql' in name or 'postgres' in name:
        return 'database'
    elif 'load' in name and 'balance' in name or 'lb' in name or 'haproxy' in name:
        return 'loadbalancer'
    elif 'api' in name or 'app' in name or 'application' in name:
        return 'application'
    elif 'cache' in name or 'redis' in name or 'memcache' in name:
        return 'cache'
    elif 'worker' in name or 'compute' in name:
        return 'compute'
    elif 'bastion' in name or 'jump' in name:
        return 'bastion'
    # Enhanced user requirements checking for three-tier detection
    elif any(term in user_req_lower for term in ['three tier', '3 tier', 'three-tier', '3-tier', 'multi tier', 'multi-tier']):
        # For three-tier apps, assign purposes based on instance order/context but don't assume load balancer
        if 'server-1' in name or name.endswith('-1'):
            return 'web'  # First server is web tier, not load balancer
        elif 'server-2' in name or name.endswith('-2'):
            return 'application'  # Second server is app tier
        elif 'server-3' in name or name.endswith('-3'):
            return 'database'  # Third server is database tier
        elif 'server-4' in name or name.endswith('-4'):
            return 'database'  # Additional database server
        else:
            return 'web'  # Default for three-tier
    elif any(gpu_term in user_req_lower for gpu_term in ['gpu', 'machine learning', 'ml', 'ai', 'training']):
        return 'gpu'
    else:
        return 'general'


def _infer_instances_from_requirements(provider_name: str, provider_config: Dict, user_requirements: str) -> List[Dict]:
    """Infer likely instances from user requirements when not explicitly defined"""
    instances = []
    
    requirements_lower = user_requirements.lower()
    
    # Common instance patterns
    if any(term in requirements_lower for term in ['web', 'website', 'frontend']):
        instances.append({
            'id': f"{provider_name}_web_server",
            'name': f'{provider_name}-web-server',
            'provider': provider_name,
            'type': 't3.medium' if provider_name == 'aws' else 'Standard_B2s' if provider_name == 'azure' else 'e2-medium',
            'region': provider_config.get('region', 'unknown'),
            'cores': 2,
            'memory': 4,
            'purpose': 'web',
            'os': 'Linux'
        })
    
    if any(term in requirements_lower for term in ['database', 'db', 'mysql', 'postgres']):
        instances.append({
            'id': f"{provider_name}_database",
            'name': f'{provider_name}-database',
            'provider': provider_name,
            'type': 't3.large' if provider_name == 'aws' else 'Standard_D2s_v3' if provider_name == 'azure' else 'e2-standard-2',
            'region': provider_config.get('region', 'unknown'),
            'cores': 2,
            'memory': 8,
            'purpose': 'database',
            'os': 'Linux'
        })
    
    if any(term in requirements_lower for term in ['gpu', 'machine learning', 'ml', 'ai']):
        instances.append({
            'id': f"{provider_name}_gpu_worker",
            'name': f'{provider_name}-gpu-worker',
            'provider': provider_name,
            'type': 'p3.2xlarge' if provider_name == 'aws' else 'Standard_NC6' if provider_name == 'azure' else 'n1-standard-4',
            'region': provider_config.get('region', 'unknown'),
            'cores': 8,
            'memory': 61,
            'purpose': 'gpu',
            'os': 'Linux'
        })
    
    # If no specific requirements, add a general compute instance
    if not instances:
        instances.append({
            'id': f"{provider_name}_compute",
            'name': f'{provider_name}-instance',
            'provider': provider_name,
            'type': 't3.medium' if provider_name == 'aws' else 'Standard_B2s' if provider_name == 'azure' else 'e2-medium',
            'region': provider_config.get('region', 'unknown'),
            'cores': 2,
            'memory': 4,
            'purpose': 'general',
            'os': 'Linux'
        })
    
    return instances


def _extract_networks_from_provider(provider_name: str, provider_config: Dict) -> List[Dict]:
    """Extract network information from provider configuration - DEPRECATED"""
    # This function is no longer used since we generate default networks in main function
    return []


def _extract_storage_from_provider(provider_name: str, provider_config: Dict) -> List[Dict]:
    """Extract storage information from provider configuration - DEPRECATED"""
    # This function is no longer used since YamlForge doesn't have explicit storage sections
    return []


def _create_isolated_networks(provider_name: str, provider_instances: List[Dict]) -> List[Dict]:
    """Create separate isolated networks for each instance"""
    networks = []
    
    for i, instance in enumerate(provider_instances):
        instance_name = instance.get('name', f'instance-{i+1}')
        # Clean instance name for network naming
        clean_name = instance_name.lower().replace('-', '_')
        
        # Create unique CIDR for each network (10.X.0.0/24 where X is instance index + 10)
        cidr_third_octet = (i + 10) % 255
        
        network_info = {
            'id': f"{provider_name}_{clean_name}_network",
            'name': f'{provider_name}-{instance_name}-net',
            'provider': provider_name,
            'type': 'private_subnet',
            'cidr': f'10.{cidr_third_octet}.0.0/24',
            'region': instance.get('region', 'unknown'),
            'description': f'Isolated network for {instance_name}'
        }
        networks.append(network_info)
    
    return networks


def _generate_networks_for_provider(provider_name: str, instances: List[Dict], user_requirements: str = '') -> List[Dict]:
    """Generate multiple networks for a provider based on instance distribution and user requirements"""
    networks = []
    
    # Get instances for this provider
    provider_instances = [inst for inst in instances if inst.get('provider') == provider_name]
    
    if not provider_instances:
        return networks
    
    # Check if user explicitly requested network isolation
    isolation_keywords = [
        'isolated', 'separate', 'own network', 'new private network', 
        'isolation', 'segregated', 'dedicated network', 'independent network'
    ]
    user_req_lower = user_requirements.lower()
    wants_isolation = any(keyword in user_req_lower for keyword in isolation_keywords)
    
    # If isolation is requested, create separate networks for each instance
    if wants_isolation:
        return _create_isolated_networks(provider_name, provider_instances)
    
    # Group instances by region and purpose for network segmentation
    regions = set()
    purposes = set()
    
    for instance in provider_instances:
        region = instance.get('region', 'unknown')
        purpose = instance.get('purpose', 'general')
        regions.add(region)
        purposes.add(purpose)
    
    # Create networks based on regions and purposes
    region_list = list(regions)
    purpose_list = list(purposes)
    
    # If multiple regions, create region-specific networks
    if len(region_list) > 1:
        base_cidr = 10
        for i, region in enumerate(region_list):
            network_info = {
                'id': f"{provider_name}_{region.replace('-', '_')}_vpc",
                'name': f'{provider_name}-{region}-vpc',
                'provider': provider_name,
                'type': 'vpc',
                'cidr': f'10.{base_cidr + i}.0.0/16',
                'region': region
            }
            networks.append(network_info)
    
    # If multiple purposes (web, database, etc.), create purpose-specific subnets
    elif len(purpose_list) > 1:
        # Create networks based on three-tier architecture
        has_web_tier = any(purpose in ['web', 'loadbalancer'] for purpose in purpose_list)
        has_app_tier = 'application' in purpose_list
        has_db_tier = 'database' in purpose_list
        
        # Public subnet for web servers and load balancers (internet-facing)
        if has_web_tier:
            network_info = {
                'id': f"{provider_name}_public_subnet",
                'name': f'{provider_name}-public-subnet',
                'provider': provider_name,
                'type': 'public_subnet',
                'cidr': '10.0.1.0/24',
                'region': region_list[0] if region_list else 'unknown',
                'description': 'Public subnet for web servers and load balancers'
            }
            networks.append(network_info)
        
        # Application subnet for application servers (accessible from web tier)
        if has_app_tier:
            network_info = {
                'id': f"{provider_name}_app_subnet",
                'name': f'{provider_name}-app-subnet',
                'provider': provider_name,
                'type': 'app_subnet',
                'cidr': '10.0.2.0/24',
                'region': region_list[0] if region_list else 'unknown',
                'description': 'Application subnet for application servers'
            }
            networks.append(network_info)
        
        # Database subnet for database servers (accessible only from app tier)
        if has_db_tier:
            network_info = {
                'id': f"{provider_name}_db_subnet",
                'name': f'{provider_name}-db-subnet',
                'provider': provider_name,
                'type': 'db_subnet',
                'cidr': '10.0.3.0/24',
                'region': region_list[0] if region_list else 'unknown',
                'description': 'Database subnet for database servers'
            }
            networks.append(network_info)
    
    # If no complex networking needed, create a simple default VPC
    if not networks:
        network_info = {
            'id': f"{provider_name}_default_vpc",
            'name': f'{provider_name}-vpc',
            'provider': provider_name,
            'type': 'vpc',
            'cidr': '10.0.0.0/16',
            'region': region_list[0] if region_list else 'unknown'
        }
        networks.append(network_info)
    
    return networks


def _should_instance_connect_to_network(instance_purpose: str, network: Dict) -> bool:
    """Determine if an instance should connect to a network based on three-tier architecture security"""
    network_type = network.get('type', '')
    network_name = network.get('name', '').lower()
    
    # For isolated networks (one per instance), always connect
    if 'isolated' in network.get('description', '').lower():
        return True
    
    # For VPC networks, always connect
    if network_type == 'vpc':
        return True
    
    # Three-tier security rules with proper inter-tier connectivity:
    
    # Web servers: Connect to public subnet (for internet) AND app subnet (to reach app servers)
    if instance_purpose == 'web':
        return network_type in ['public_subnet', 'app_subnet'] or any(x in network_name for x in ['public', 'app'])
    
    # Load balancers: Public subnet only (internet-facing)
    elif instance_purpose == 'loadbalancer':
        return network_type == 'public_subnet' or 'public' in network_name
    
    # Application servers: App subnet (primary) AND db subnet (to reach databases)
    elif instance_purpose == 'application':
        return network_type in ['app_subnet', 'db_subnet'] or any(x in network_name for x in ['app', 'db', 'database'])
    
    # Database servers: Database subnet only (most restricted)
    elif instance_purpose == 'database':
        return network_type == 'db_subnet' or any(x in network_name for x in ['db', 'database'])
    
    # Legacy private subnet support (fallback for existing configs)
    elif instance_purpose in ['application', 'database'] and network_type == 'private_subnet':
        return True
    
    # General purpose instances -> connect to any network (fallback)
    else:
        return True


def _generate_logical_connections(description: Dict) -> List[Dict]:
    """Generate logical connections between infrastructure components"""
    connections = []
    
    instances = description.get('instances', [])
    networks = description.get('networks', [])
    storage = description.get('storage', [])
    
    # Connect instances to networks (same provider) with tier-based isolation
    for instance in instances:
        instance_purpose = instance.get('purpose', 'general')
        
        for network in networks:
            if instance['provider'] == network['provider']:
                # Determine if instance should connect to this network based on purpose and network type
                should_connect = _should_instance_connect_to_network(instance_purpose, network)
                
                if should_connect:
                    connections.append({
                        'from': instance['id'],
                        'to': network['id'],
                        'type': 'network_connection',
                        'description': f"{instance['name']} connects to {network['name']}"
                    })
    
    # Connect instances to storage (same provider)
    for instance in instances:
        for storage_item in storage:
            if instance['provider'] == storage_item['provider']:
                connections.append({
                    'from': instance['id'],
                    'to': storage_item['id'],
                    'type': 'storage_attachment',
                    'description': f"{instance['name']} uses {storage_item['name']}"
                })
    
    # Connect instances across providers (multi-cloud)
    providers = {}
    for instance in instances:
        provider = instance['provider']
        if provider not in providers:
            providers[provider] = []
        providers[provider].append(instance)
    
    provider_list = list(providers.keys())
    for i, provider1 in enumerate(provider_list):
        for j, provider2 in enumerate(provider_list[i+1:], i+1):
            if providers[provider1] and providers[provider2]:
                inst1 = providers[provider1][0]  # Representative instance
                inst2 = providers[provider2][0]  # Representative instance
                connections.append({
                    'from': inst1['id'],
                    'to': inst2['id'],
                    'type': 'inter_cloud',
                    'description': f"Multi-cloud connection: {provider1} <-> {provider2}"
                })
    
    return connections


def save_infrastructure_description(description: Dict, file_path: str) -> bool:
    """Save infrastructure description to a JSON file"""
    try:
        with open(file_path, 'w') as f:
            json.dump(description, f, indent=2)
        return True
    except Exception:
        return False


def load_infrastructure_description(file_path: str) -> Dict:
    """Load infrastructure description from a JSON file"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception:
        return {}
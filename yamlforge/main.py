#!/usr/bin/env python3
"""
Main entry point for the yamlforge multi-cloud infrastructure converter.

This module provides the command-line interface for YamlForge, which converts
unified YAML infrastructure definitions into provider-specific Terraform configurations.

Copyright 2025 Patrick T. Rutledge III

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import argparse
import os
import sys
import yaml
import subprocess
import json
from datetime import datetime
from .utils import find_yamlforge_file

from .core.converter import YamlForgeConverter

# Optional jsonschema for validation
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

# Version information
from ._version import __version__

def validate_yaml_against_schema(yaml_data, input_file_path, ansible_mode=False):
    """Validate YAML configuration against YamlForge schema"""
    
    if not HAS_JSONSCHEMA:
        # Skip validation if jsonschema is not available
        if not ansible_mode:
            print("INFO: jsonschema library not found, skipping schema validation")
            print("      Install with: pip install jsonschema")
        return True
    
    # Find the schema file
    try:
        schema_path = find_yamlforge_file('docs/yamlforge-schema.json')
    except FileNotFoundError:
        schema_path = None
    
    if not schema_path or not os.path.exists(schema_path):
        # Schema not found, skip validation
        if not ansible_mode:
            print(f"INFO: Schema file not found at {schema_path}, skipping validation")
        return True
    
    # Load the schema
    try:
        with open(schema_path, 'r') as f:
            schema = json.load(f)
    except Exception as e:
        # Schema loading failed, skip validation
        if not ansible_mode:
            print(f"INFO: Could not load schema file: {e}")
        return True
    
    # Validate the configuration
    try:
        jsonschema.validate(yaml_data, schema)
        return True
    except jsonschema.ValidationError as e:
        # Format the validation error nicely
        error_msg = f"YAML configuration validation failed in '{input_file_path}':\n\n"
        error_msg += f"Error: {e.message}\n"
        
        if e.path:
            path_str = '.'.join(str(p) for p in e.path)
            error_msg += f"Location: {path_str}\n"
        
        if e.schema_path:
            schema_path_str = '.'.join(str(p) for p in e.schema_path)
            error_msg += f"Schema rule: {schema_path_str}\n"
        
        # Add helpful hints for common errors
        if "instances" in str(e.path) and "not of type 'array'" in e.message:
            error_msg += "\nHint: 'instances' should be an array (list) of objects, not a dictionary.\n"
            error_msg += "Correct format:\n"
            error_msg += "yamlforge:\n"
            error_msg += "  instances:\n"
            error_msg += "    - name: \"my-instance\"\n"
            error_msg += "      provider: aws\n"
            error_msg += "      # ... other properties\n"
        elif "'yamlforge' is a required property" in e.message:
            error_msg += "\nHint: YAML file must have a 'yamlforge' root element.\n"
            error_msg += "Correct format:\n"
            error_msg += "yamlforge:\n"
            error_msg += "  cloud_workspace:\n"
            error_msg += "    name: \"my-workspace\"\n"
            error_msg += "  instances:\n"
            error_msg += "    - name: \"my-instance\"\n"
            error_msg += "      provider: aws\n"
        elif "guid" in str(e.path) and "pattern" in str(e.schema_path):
            error_msg += "\nHint: GUID must be exactly 5 characters (lowercase letters and numbers only).\n"
            error_msg += "Examples: test1, web01, app42, dev99\n"
        
        raise ValueError(error_msg)
    except Exception as e:
        # Other validation errors, skip validation
        if not ansible_mode:
            print(f"INFO: Schema validation error: {e}")
        return True

def run_command(command, cwd=None, description=""):
    """Run a shell command and return success status."""
    try:
        print(f"  {description}")
        print(f"   Executing: {command}")
        subprocess.run(command, shell=True, cwd=cwd, check=True, 
                      capture_output=False, text=True)
        print(f"Success: {description}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed: {description} - Failed with exit code {e.returncode}")
        return False

def analyze_configuration(converter, config, raw_yaml_data):
    """Analyze configuration and show provider selections, cost analysis, and flavor mappings."""
    print("\n" + "="*80)
    print("  YAMLFORGE CLOUD ANALYSIS")
    print("="*80)
    
    # Check for GUID early in analyze mode and provide placeholder if missing
    try:
        # Try to get GUID, but don't fail if missing in analyze mode
        guid = converter.get_validated_guid(raw_yaml_data)
    except ValueError as e:
        if "GUID is required" in str(e):
            # Provide placeholder GUID for analyze mode and show warning
            print("WARNING: No GUID found. Using placeholder 'test1' for analysis.")
            print("         Set GUID=yourcode or add 'guid: yourcode' to YAML for real deployment.")
            print()
            # Set a temporary placeholder GUID for analyze mode
            converter._validated_guid = "test1"
        else:
            # Re-raise other GUID validation errors (like invalid format)
            print(f"ERROR: {e}")
            return
    
    # Validate configuration early to catch issues
    try:
        converter.validate_provider_setup(raw_yaml_data)
    except ValueError as e:
        print(f"ERROR: {e}")
        return
    
    # Reset cost tracking lists for analysis
    converter.instance_costs = []
    converter.openshift_costs = []
    converter.storage_cost_tracking = []
    
    # Get instances from yamlforge section
    instances = config.get('instances', [])
    
    # Show global provider exclusions before INSTANCES section
    global_excluded = converter.core_config.get('provider_selection', {}).get('exclude_from_cheapest', [])
    if global_excluded:
        excluded_list = ', '.join(global_excluded)
        print(f"Global provider exclusions: {excluded_list} (excluded from cost comparison)")
        available_providers = converter.get_effective_providers()
        available_list = ', '.join(available_providers)
        print(f"Global unexcluded providers: {available_list}")
        print()
    
    # Analyze instances
    if instances:
        # Calculate total instance count including count multipliers
        total_instance_count = sum(instance.get('count', 1) for instance in instances)
        instance_def_count = len(instances)
        
        if total_instance_count == instance_def_count:
            print(f"INSTANCES ({total_instance_count} found):")
        else:
            print(f"INSTANCES ({total_instance_count} found, {instance_def_count} definitions):")
        print("-" * 40)
        
        # Track which exclusions have been shown to avoid repetition
        shown_exclusions = set()
        
        # Expand instances with count > 1 into separate entries
        expanded_instances = []
        for instance in instances:
            instance_count = instance.get('count', 1)
            if instance_count > 1:
                # Create separate entries for each instance in the count
                for instance_index in range(instance_count):
                    instance_copy = instance.copy()
                    original_name = instance_copy['name']
                    # Resolve GUID first before applying count naming logic
                    if '{guid}' in original_name:
                        guid = converter.get_validated_guid(raw_yaml_data)
                        original_name = original_name.replace('{guid}', guid)
                    
                    # Check if name ends with a number and increment from there
                    import re
                    match = re.search(r'(.+?)(\d+)$', original_name)
                    if match:
                        # Name ends with number, increment from that base
                        base_name = match.group(1)
                        base_number_str = match.group(2)
                        base_number = int(base_number_str)
                        # Preserve padding (e.g., 01, 02, 003) by using the same width
                        padding_width = len(base_number_str)
                        new_number = base_number + instance_index
                        instance_copy['name'] = f"{base_name}{new_number:0{padding_width}d}"
                    else:
                        # Name doesn't end with number, append -X
                        instance_copy['name'] = f"{original_name}-{instance_index + 1}"
                    instance_copy['_is_counted'] = True
                    instance_copy['_original_name'] = original_name
                    expanded_instances.append(instance_copy)
            else:
                # Single instance, add as-is
                instance_copy = instance.copy()
                instance_copy['_is_counted'] = False
                expanded_instances.append(instance_copy)
        
        for i, instance in enumerate(expanded_instances, 1):
            name = instance.get('name', 'unnamed')
            provider = instance.get('provider', 'unspecified')
            region = instance.get('region', 'unspecified')
            flavor = instance.get('flavor')
            cores = instance.get('cores')
            memory = instance.get('memory')
            gpu_type = instance.get('gpu_type')
            gpu_count = instance.get('gpu_count')
            image = instance.get('image', 'unspecified')
            instance_exclusions = instance.get('exclude_providers', [])
            
            # Resolve {guid} in instance name for display
            resolved_name = name
            if '{guid}' in name:
                guid = converter.get_validated_guid(raw_yaml_data)
                resolved_name = name.replace('{guid}', guid)
            
            print(f"\n{i}. {resolved_name}:")
            
            # Show per-instance exclusions and included providers
            if instance_exclusions:
                # Show per-instance excluded providers
                global_excluded = converter.core_config.get('provider_selection', {}).get('exclude_from_cheapest', [])
                all_excluded = list(set(global_excluded + instance_exclusions))
                excluded_list = ', '.join(all_excluded)
                print(f"   Per instance excluded providers: {excluded_list} (excluded from cost comparison)")
                # Show per-instance included providers
                available_providers = converter.get_effective_providers(instance_exclusions=instance_exclusions)
                available_list = ', '.join(available_providers)
                print(f"   Per instance included providers: {available_list}")
            
            # Resolve provider for meta-providers
            resolved_provider = provider
            
            if provider in ['cheapest', 'cheapest-gpu']:
                try:
                    if provider == 'cheapest':
                        resolved_provider = converter.find_cheapest_provider(instance, suppress_output=True)
                    elif provider == 'cheapest-gpu':
                        resolved_provider = converter.find_cheapest_gpu_provider(instance, suppress_output=True)
                except Exception as e:
                    resolved_provider = f"{provider} (error: {e})"
            
            # Show resolved provider
            if provider in ['cheapest', 'cheapest-gpu']:
                print(f"   Provider: {provider} ({resolved_provider})")
            else:
                print(f"   Provider: {provider}")
            
            # Show resolved region with mapped value (skip for CNV provider)
            if resolved_provider != 'cnv':
                mapped_region = converter.locations.get(region, {}).get(resolved_provider, region)
                if region == mapped_region:
                    print(f"   Region: {region}")
                else:
                    print(f"   Region: {region} ({mapped_region})")
            
            # Show resolved flavor/specs with mapped value and calculate cost
            instance_type = None
            if flavor:
                # Get mapped flavor for the resolved provider
                try:
                    instance_type = converter.resolve_instance_type(resolved_provider, flavor, instance)
                    mapped_flavor = converter.flavors.get(flavor, {}).get(resolved_provider, flavor)
                    if hasattr(converter, 'verbose') and converter.verbose:
                        print(f"   Flavor mapping: '{flavor}' -> '{mapped_flavor}'")
                    if flavor == mapped_flavor:
                        print(f"   Flavor: {flavor}")
                    else:
                        print(f"   Flavor: {flavor} ({mapped_flavor})")
                    
                    # Get and display cost for this instance
                    provider_flavors = converter.flavors.get(resolved_provider, {})
                    cost_info = converter.get_instance_cost_info(resolved_provider, instance_type, flavor, provider_flavors)
                    if cost_info and cost_info.get('cost') is not None:
                        original_cost = cost_info['cost']
                        discounted_cost = converter.apply_discount(original_cost, resolved_provider)
                        cost_display = converter._format_cost_with_discount(resolved_provider, original_cost, discounted_cost)
                        print(f"   Hourly Cost: {cost_display}")
                        
                        # Track the discounted cost for each individual instance
                        converter.instance_costs.append({
                            'instance_name': resolved_name,
                            'provider': resolved_provider,
                            'cost': discounted_cost,
                            'count': 1,
                            'per_instance_cost': discounted_cost
                        })
                    else:
                        print(f"   Hourly Cost: Cost information not available")
                except Exception as e:
                    mapped_flavor = converter.flavors.get(flavor, {}).get(resolved_provider, flavor)
                    if hasattr(converter, 'verbose') and converter.verbose:
                        print(f"   Flavor mapping: '{flavor}' -> '{mapped_flavor}'")
                    if flavor == mapped_flavor:
                        print(f"   Flavor: {flavor}")
                    else:
                        print(f"   Flavor: {flavor} ({mapped_flavor})")
                    print(f"   Hourly Cost: Error calculating cost - {e}")
            elif cores and memory:
                # For CNV provider, memory is in GB, for others it might be in MB
                if provider == 'cnv':
                    print(f"   Specs: {cores} cores, {memory}GB RAM")
                else:
                    print(f"   Specs: {cores} cores, {memory}MB RAM")
                
                # For spec-based instances, try to find closest matching flavor and cost
                if provider in ['cheapest', 'cheapest-gpu']:
                    try:
                        if provider == 'cheapest':
                            memory_value = memory
                            if memory_value < 100:  # Assume GB if less than 100
                                memory_mb = memory_value * 1024
                            else:  # Assume MB if 100 or greater
                                memory_mb = memory_value
                            
                            provider_costs = converter.find_cheapest_by_specs(
                                cores, memory_mb, instance.get('gpu_count', 0), 
                                instance.get('gpu_type'), instance_exclusions
                            )
                            if provider_costs and resolved_provider in provider_costs:
                                selected_option = provider_costs[resolved_provider]
                                original_cost = selected_option.get('original_cost', selected_option['cost'])
                                discounted_cost = selected_option['cost']
                                instance_type = selected_option['instance_type']
                                print(f"   Flavor: {instance_type}")
                                cost_display = converter._format_cost_with_discount(resolved_provider, original_cost, discounted_cost)
                                print(f"   Hourly Cost: {cost_display}")
                                
                                converter.instance_costs.append({
                                    'instance_name': resolved_name,
                                    'provider': resolved_provider,
                                    'cost': discounted_cost,
                                    'count': 1,
                                    'per_instance_cost': discounted_cost
                                })
                        elif provider == 'cheapest-gpu':
                            provider_costs = converter.find_cheapest_gpu_by_specs(gpu_type, instance_exclusions)
                            if provider_costs and resolved_provider in provider_costs:
                                selected_option = provider_costs[resolved_provider]
                                original_cost = selected_option.get('original_cost', selected_option['cost'])
                                discounted_cost = selected_option['cost']
                                instance_type = selected_option['instance_type']
                                print(f"   Flavor: {instance_type}")
                                cost_display = converter._format_cost_with_discount(resolved_provider, original_cost, discounted_cost)
                                print(f"   Hourly Cost: {cost_display}")
                                
                                converter.instance_costs.append({
                                    'instance_name': resolved_name,
                                    'provider': resolved_provider,
                                    'cost': discounted_cost,
                                    'count': 1,
                                    'per_instance_cost': discounted_cost
                                })
                    except Exception as e:
                        print(f"   Hourly Cost: Error calculating cost - {e}")
                else:
                    # For specific providers (azure, aws, etc.), find closest matching flavor
                    try:
                        # Convert memory to MB if needed for consistency
                        memory_mb = memory
                        if memory < 100:  # Assume GB if less than 100
                            memory_mb = memory * 1024
                        
                        # Find closest matching flavor for this specific provider
                        closest_flavor_info = converter.find_closest_flavor_for_provider(
                            resolved_provider, cores, memory_mb, gpu_count, gpu_type
                        )
                        
                        if closest_flavor_info:
                            instance_type = closest_flavor_info['instance_type']
                            flavor_name = closest_flavor_info['flavor']
                            cost = closest_flavor_info.get('cost')
                            print(f"   Closest Flavor: {flavor_name} ({instance_type})")
                            
                            if cost is not None:
                                original_cost = cost
                                discounted_cost = converter.apply_discount(original_cost, resolved_provider)
                                cost_display = converter._format_cost_with_discount(resolved_provider, original_cost, discounted_cost)
                                print(f"   Hourly Cost: {cost_display}")
                                
                                # Track cost for this instance
                                converter.instance_costs.append({
                                    'instance_name': resolved_name,
                                    'provider': resolved_provider,
                                    'cost': discounted_cost,
                                    'count': 1,
                                    'per_instance_cost': discounted_cost
                                })
                            else:
                                print(f"   Hourly Cost: Cost information not available")
                        else:
                            print(f"   Hourly Cost: No matching flavor found for {cores} cores, {memory_mb}MB RAM")
                    except Exception as e:
                        print(f"   Hourly Cost: Error finding closest flavor - {e}")
            
            # Show resolved GPU info
            if gpu_type and gpu_count:
                print(f"   GPU Count: {gpu_count}")
                print(f"   GPU Type: {gpu_type}")
                # Show GPU flavor for cheapest-gpu provider
                if provider == 'cheapest-gpu':
                    try:
                        gpu_flavor = converter.get_cheapest_gpu_instance_type(instance, resolved_provider)
                        print(f"   GPU Flavor: {gpu_flavor}")
                    except Exception as e:
                        print(f"   GPU Flavor: {resolved_provider} (error getting flavor)")
            elif gpu_count:
                print(f"   GPU Count: {gpu_count}")
            
            # Show resolved image with mapped value
            if resolved_provider == 'cnv':
                # Special handling for CNV images
                if hasattr(converter, 'no_credentials') and converter.no_credentials:
                    # In no-credentials mode, show placeholder for CNV images
                    mapped_image = "placeholder - no cluster access"
                else:
                    # Normal CNV image resolution
                    try:
                        # Get CNV provider to resolve image
                        cnv_provider = converter.get_cnv_provider()
                        if cnv_provider:
                            cnv_config = config.get('cnv', {})
                            datavolume_namespace = cnv_config.get('datavolume_namespace', 'cnv-images')
                            image_config = cnv_provider.get_cnv_image_config(image, datavolume_namespace)
                            mapped_image = f"PVC: {image_config.get('pvc_name', image)}"
                        else:
                            mapped_image = f"DataVolume: {image}"
                    except Exception as e:
                        mapped_image = f"DataVolume: {image} (error: {str(e)})"
            else:
                # Standard image resolution for other providers
                image_config = converter.images.get(image, {}).get(resolved_provider, {})
                if isinstance(image_config, dict):
                    # Extract a simple identifier from the image config
                    if resolved_provider == 'aws':
                        mapped_image = image_config.get('name_pattern', image)
                    elif resolved_provider == 'azure':
                        mapped_image = f"{image_config.get('publisher', '')}/{image_config.get('offer', '')}/{image_config.get('sku', '')}"
                    elif resolved_provider == 'gcp':
                        mapped_image = f"{image_config.get('project', '')}/{image_config.get('family', '')}"
                    else:
                        mapped_image = str(image_config)
                else:
                    mapped_image = str(image_config)
            print(f"   Image: {image} ({mapped_image})")
            
            # Show cost analysis for meta-providers
            if provider in ['cheapest', 'cheapest-gpu']:
                # Always show cost analysis for the first instance of each type
                # Don't show per-instance exclusions in cost analysis since they're shown under instance name
                exclusion_key = tuple(sorted(instance_exclusions)) if instance_exclusions else 'default'
                should_show_cost_analysis = exclusion_key not in shown_exclusions
                
                # For GPU instances, always show cost analysis for the first one
                if provider == 'cheapest-gpu' and 'gpu' not in shown_exclusions:
                    should_show_cost_analysis = True
                
                try:
                    if provider == 'cheapest':
                        converter.find_cheapest_provider(instance, suppress_output=not should_show_cost_analysis)
                    elif provider == 'cheapest-gpu':
                        converter.find_cheapest_gpu_provider(instance, suppress_output=not should_show_cost_analysis)
                    
                    # Mark these exclusions as shown
                    if should_show_cost_analysis:
                        shown_exclusions.add(exclusion_key)
                    
                    # Mark GPU instances as shown
                    if provider == 'cheapest-gpu':
                        shown_exclusions.add('gpu')
                        
                except Exception as e:
                    print(f"   → Error: {e}")
    
    # Analyze storage buckets
    storage = config.get('storage', [])
    if storage:
        print(f"\nSTORAGE BUCKETS ({len(storage)} found):")
        print("-" * 40)
        
        for i, bucket in enumerate(storage, 1):
            bucket_name = bucket.get('name', 'unnamed')
            provider = bucket.get('provider', 'unspecified')
            
            # Replace GUID in name for display
            if '{guid}' in bucket_name:
                guid = converter.get_validated_guid(raw_yaml_data)
                resolved_name = bucket_name.replace('{guid}', guid)
            else:
                resolved_name = bucket_name
            
            print(f"\n{i}. {resolved_name}:")
            
            # Resolve provider and calculate costs
            resolved_provider = provider
            if provider == 'cheapest':
                # Show cost analysis for cheapest provider
                try:
                    resolved_provider = converter.find_cheapest_storage_provider(bucket, suppress_output=False)
                except Exception as e:
                    print(f"   → Error in cost analysis: {e}")
                    resolved_provider = 'aws'
                    print(f"   → Using fallback: {resolved_provider}")
            else:
                print(f"   Provider: {provider}")
            
            # Calculate and display storage cost
            try:
                # Get storage cost for this bucket
                storage_location = bucket.get('location') or bucket.get('region', 'us-east')
                storage_cost = converter.calculate_storage_cost(resolved_provider, storage_location)
                
                if storage_cost is not None:
                    print(f"   Monthly Cost: ${storage_cost:.4f}/month")
                    # Track cost for summary
                    converter.storage_cost_tracking.append({
                        'bucket_name': resolved_name,
                        'provider': resolved_provider,
                        'cost': storage_cost
                    })
                else:
                    print(f"   Monthly Cost: Cost information not available for {resolved_provider}")
            except Exception as e:
                print(f"   Monthly Cost: Error calculating cost - {e}")
            
            # Show region/location
            region = bucket.get('region')
            location = bucket.get('location') 
            if region:
                print(f"   Region: {region}")
            elif location:
                print(f"   Location: {location}")
            
            # Show storage configuration
            public = bucket.get('public', False)
            versioning = bucket.get('versioning', False)
            encryption = bucket.get('encryption', True)
            
            print(f"   Access: {'public-read' if public else 'private'}")
            print(f"   Versioning: {'enabled' if versioning else 'disabled'}")
            print(f"   Encryption: {'enabled' if encryption else 'disabled'}")
            
            # Show tags if present
            tags = bucket.get('tags', {})
            if tags:
                tag_list = [f"{k}={v}" for k, v in tags.items()]
                print(f"   Tags: {', '.join(tag_list)}")
    
    # Analyze OpenShift clusters
    openshift_clusters = config.get('openshift_clusters', [])
    if openshift_clusters:
        print(f"\nOPENSHIFT CLUSTERS ({len(openshift_clusters)} found):")
        print("-" * 40)
        
        for i, cluster in enumerate(openshift_clusters, 1):
            name = cluster.get('name', 'unnamed')
            cluster_type = cluster.get('type', 'unspecified')
            region = cluster.get('region', 'unspecified')
            version = cluster.get('version', 'unspecified')
            size = cluster.get('size', 'unspecified')
            
            # Resolve {guid} in cluster name for display
            resolved_name = name
            if '{guid}' in name:
                guid = converter.get_validated_guid(raw_yaml_data)
                resolved_name = name.replace('{guid}', guid)
            
            print(f"\n{i}. {resolved_name}:")
            print(f"   Type: {cluster_type}")
            print(f"   Region: {region}")
            print(f"   Version: {version}")
            print(f"   Size: {size}")
            
            # Calculate and display cluster cost
            try:
                cluster_cost = converter.calculate_openshift_cluster_cost(cluster, cluster_type)
                if cluster_cost is not None and cluster_cost > 0:
                    print(f"   Cluster Nodes:")
                    
                    # Get detailed node breakdown from cluster size configuration
                    size_config = converter.openshift_provider.get_cluster_size_config(size, cluster_type)
                    
                    # Determine provider based on cluster type (handle all deployment methods)
                    provider = None
                    if cluster_type == 'rosa-classic' or cluster_type == 'rosa-hcp':
                        provider = 'aws'
                    elif cluster_type == 'aro':
                        provider = 'azure'
                    elif cluster_type == 'self-managed':
                        provider = cluster.get('provider', 'aws')
                    elif cluster_type == 'openshift-dedicated':
                        provider = cluster.get('provider', 'aws')
                    elif cluster_type == 'hypershift':
                        provider = cluster.get('provider', 'aws')
                    
                    # Extract node counts and types from size config or cluster config
                    controlplane_count = cluster.get('controlplane_count') or size_config.get('controlplane_count', 3)  # Default 3 control plane nodes for HA
                    worker_count = cluster.get('worker_count') or size_config.get('worker_count', 3)
                    
                    # Get machine types from OpenShift mappings if provider is available
                    controlplane_machine_type = ''
                    worker_machine_type = ''
                    if provider:
                        controlplane_machine_type = converter.openshift_provider.get_openshift_machine_type(
                            provider, size_config.get('controlplane_size', 'medium'), 'controlplane'
                        )
                        worker_machine_type = converter.openshift_provider.get_openshift_machine_type(
                            provider, size_config.get('worker_size', 'medium'), 'worker'
                        )
                    
                    if provider:
                        provider_flavors = converter.flavors.get(provider, {})
                        
                        # Track all node types and their costs
                        node_breakdown = []
                        
                        # Handle control plane nodes
                        if controlplane_count > 0 and controlplane_machine_type:
                            controlplane_cost = None
                            for size, instances in provider_flavors.get('flavor_mappings', {}).items():
                                if controlplane_machine_type in instances:
                                    controlplane_cost = instances[controlplane_machine_type]
                                    break
                            
                            if controlplane_cost and controlplane_cost.get('hourly_cost'):
                                node_cost = controlplane_cost['hourly_cost']
                                total_cost = node_cost * controlplane_count
                                node_breakdown.append(f"     • {controlplane_count} control plane nodes ({controlplane_machine_type}): ${node_cost:.4f}/hour each = ${total_cost:.4f}/hour")
                        
                        # Handle worker nodes
                        if worker_count > 0 and worker_machine_type:
                            worker_cost = None
                            for size, instances in provider_flavors.get('flavor_mappings', {}).items():
                                if worker_machine_type in instances:
                                    worker_cost = instances[worker_machine_type]
                                    break
                            
                            if worker_cost and worker_cost.get('hourly_cost'):
                                node_cost = worker_cost['hourly_cost']
                                total_cost = node_cost * worker_count
                                node_breakdown.append(f"     • {worker_count} worker nodes ({worker_machine_type}): ${node_cost:.4f}/hour each = ${total_cost:.4f}/hour")
                        
                        # Display all nodes
                        for line in node_breakdown:
                            print(line)
                    
                    print(f"   Total Cluster Cost: ${cluster_cost:.4f}/hour")
                    converter.openshift_costs.append({
                        'cluster_name': resolved_name,
                        'cluster_type': cluster_type,
                        'cost': cluster_cost
                    })
                elif cluster_cost is not None and cluster_cost == 0:
                    print(f"   Hourly Cost: ${cluster_cost:.4f} (no detailed node specifications)")
                else:
                    print(f"   Hourly Cost: Cost information not available")
            except Exception as e:
                print(f"   Hourly Cost: Error calculating cost - {e}")
    
    # Show required providers
    try:
        required_providers = converter.detect_required_providers(raw_yaml_data)
        print(f"\nREQUIRED PROVIDERS:")
        print("-" * 40)
        for provider in required_providers:
            print(f"  • {provider}")
    except Exception as e:
        print(f"\nREQUIRED PROVIDERS: Error analyzing - {e}")
    
    # Display total cost summary
    if converter.instance_costs or converter.openshift_costs or converter.storage_cost_tracking:
        print(f"\nCOST SUMMARY:")
        print("-" * 40)
        
        # Show instance costs breakdown
        if converter.instance_costs:
            instance_total = 0.0
            print("Instances:")
            for cost_info in converter.instance_costs:
                print(f"  • {cost_info['instance_name']} ({cost_info['provider']}): ${cost_info['cost']:.4f}/hour")
                instance_total += cost_info['cost']
            print(f"  Instance Subtotal: ${instance_total:.4f}/hour")
        
        # Show OpenShift cluster costs breakdown
        if converter.openshift_costs:
            cluster_total = 0.0
            print("OpenShift Clusters:")
            for cost_info in converter.openshift_costs:
                print(f"  • {cost_info['cluster_name']} ({cost_info['cluster_type']}): ${cost_info['cost']:.4f}/hour")
                cluster_total += cost_info['cost']
            print(f"  Cluster Subtotal: ${cluster_total:.4f}/hour")
        
        # Show total hourly cost (instances + clusters)
        hourly_total = sum(cost_info['cost'] for cost_info in converter.instance_costs) + sum(cost_info['cost'] for cost_info in converter.openshift_costs)
        if hourly_total > 0:
            print(f"\nTOTAL HOURLY COST: ${hourly_total:.4f}")
        
        # Show storage costs breakdown
        if converter.storage_cost_tracking:
            storage_total = 0.0
            print("\nStorage Buckets:")
            for cost_info in converter.storage_cost_tracking:
                print(f"  • {cost_info['bucket_name']} ({cost_info['provider']}): ${cost_info['cost']:.4f}/month")
                storage_total += cost_info['cost']
            print(f"  Storage Subtotal: ${storage_total:.4f}/month")
        
        # Calculate totals for monthly estimate  
        hourly_total = sum(cost_info['cost'] for cost_info in converter.instance_costs) + sum(cost_info['cost'] for cost_info in converter.openshift_costs)
        monthly_storage_total = sum(cost_info['cost'] for cost_info in converter.storage_cost_tracking) if converter.storage_cost_tracking else 0.0
        
        # Show estimated monthly cost (24 hours * 30 days = 720 hours)
        if hourly_total > 0:
            monthly_compute_estimate = hourly_total * 720
            total_monthly = monthly_compute_estimate + monthly_storage_total
            print(f"\nESTIMATED MONTHLY COST:")
            if monthly_compute_estimate > 0:
                print(f"  Compute & Clusters: ${monthly_compute_estimate:.2f}/month")
            if monthly_storage_total > 0:
                print(f"  Storage: ${monthly_storage_total:.2f}/month")
            print(f"  TOTAL: ${total_monthly:.2f}/month")
        elif monthly_storage_total > 0:
            print(f"\nESTIMATED MONTHLY COST: ${monthly_storage_total:.2f}")
    
    print("\n" + "="*80)
    print("  ANALYSIS COMPLETE")
    print("="*80)
    print("Use 'yamlforge <file> -d <output_dir>' to generate Terraform files")
    print("Use 'yamlforge <file> -d <output_dir> --auto-deploy' to deploy automatically")

def generate_deployment_instructions(config, output_dir, converter=None, raw_yaml_data=None):
    """Generate specific deployment instructions based on YAML configuration."""
    
    # Analyze OpenShift cluster types present in the YAML
    clusters = config.get('openshift_clusters', [])
    
    # Get all cluster types from config
    rosa_classic_clusters = config.get('rosa_classic_clusters', [])
    aro_clusters = config.get('aro_clusters', [])
    rosa_hcp_clusters = config.get('rosa_hcp_clusters', [])
    openshift_clusters = config.get('openshift_clusters', [])
    
    # Detect cluster types from openshift_clusters (legacy format)
    if openshift_clusters:
        for cluster in openshift_clusters:
            cluster_type = cluster.get('type', '')
            if cluster_type == 'rosa-classic' and not cluster.get('hypershift', {}).get('role'):
                rosa_classic_clusters.append(cluster)
            elif cluster_type == 'rosa-hcp':
                rosa_hcp_clusters.append(cluster)
            elif cluster_type == 'aro':
                aro_clusters.append(cluster)
    
    # Detect hypershift clusters
    hypershift_mgmt_clusters = [c for c in openshift_clusters if c.get('type') == 'rosa-classic' and c.get('hypershift', {}).get('role') == 'management']
    hypershift_hosted_clusters = [c for c in openshift_clusters if c.get('type') == 'hypershift']
    
    # Combine all clusters for total count
    all_clusters = rosa_classic_clusters + aro_clusters + rosa_hcp_clusters + openshift_clusters + hypershift_mgmt_clusters + hypershift_hosted_clusters
    
    # Check deployment method (CLI vs Terraform) - only relevant if ROSA clusters exist
    rosa_deployment = config.get('rosa_deployment', {})
    deployment_method = rosa_deployment.get('method', 'terraform') if clusters else 'terraform'
    
    # Check if day2 operations are configured
    openshift_operators = config.get('openshift_operators', [])
    openshift_applications = config.get('openshift_applications', [])
    applications = config.get('applications', [])
    
    has_day2_ops = bool(openshift_operators or openshift_applications or applications)
    
    # Start building instructions - show deployment method and cluster types first
    instructions = ""
    
    # Only show OpenShift cluster types if there are actual OpenShift clusters
    if all_clusters:
        instructions += "OpenShift Clusters:\n"
        
        # List each cluster individually with details
        if rosa_classic_clusters:
            for cluster in rosa_classic_clusters:
                cluster_name = cluster.get('name', 'unnamed')
                
                # Resolve {guid} in cluster name for display
                resolved_cluster_name = cluster_name
                if '{guid}' in cluster_name and raw_yaml_data:
                    guid = raw_yaml_data.get('guid', 'unknown')
                    resolved_cluster_name = cluster_name.replace('{guid}', guid)
                
                region = cluster.get('region', 'unspecified')
                version = cluster.get('version', 'unspecified')
                size = cluster.get('size', 'unspecified')
                compute_nodes = cluster.get('compute_nodes', 'unspecified')
                compute_machine_type = cluster.get('compute_machine_type', 'unspecified')
                worker_nodes = cluster.get('worker_nodes', 'unspecified')
                worker_machine_type = cluster.get('worker_machine_type', 'unspecified')
                instructions += f" * {resolved_cluster_name} (ROSA Classic):\n"
                instructions += f"     Region: {region}\n"
                instructions += f"     Version: {version}\n"
                instructions += f"     Size: {size}\n"
                instructions += f"     Compute nodes: {compute_nodes} ({compute_machine_type})\n"
                instructions += f"     Worker nodes: {worker_nodes} ({worker_machine_type})\n"
                instructions += f"     Deployment Method: {deployment_method.upper()}\n"
                
                # Calculate and display cost if converter is available
                if converter:
                    hourly_cost = converter.calculate_openshift_cluster_cost(cluster, 'rosa-classic')
                    cost_string = converter.get_openshift_cluster_cost_string(resolved_cluster_name, 'rosa-classic', hourly_cost)
                    instructions += f"{cost_string}\n"
        if rosa_hcp_clusters:
            for cluster in rosa_hcp_clusters:
                cluster_name = cluster.get('name', 'unnamed')
                
                # Resolve {guid} in cluster name for display
                resolved_cluster_name = cluster_name
                if '{guid}' in cluster_name and raw_yaml_data:
                    guid = raw_yaml_data.get('guid', 'unknown')
                    resolved_cluster_name = cluster_name.replace('{guid}', guid)
                
                region = cluster.get('region', 'unspecified')
                version = cluster.get('version', 'unspecified')
                size = cluster.get('size', 'unspecified')
                compute_nodes = cluster.get('compute_nodes', 'unspecified')
                compute_machine_type = cluster.get('compute_machine_type', 'unspecified')
                instructions += f" * {resolved_cluster_name} (ROSA HCP):\n"
                instructions += f"     Region: {region}\n"
                instructions += f"     Version: {version}\n"
                instructions += f"     Size: {size}\n"
                instructions += f"     Compute nodes: {compute_nodes} ({compute_machine_type})\n"
                instructions += f"     Deployment Method: {deployment_method.upper()}\n"
                
                # Calculate and display cost if converter is available
                if converter:
                    hourly_cost = converter.calculate_openshift_cluster_cost(cluster, 'rosa-hcp')
                    cost_string = converter.get_openshift_cluster_cost_string(resolved_cluster_name, 'rosa-hcp', hourly_cost)
                    instructions += f"{cost_string}\n"
        if aro_clusters:
            for cluster in aro_clusters:
                cluster_name = cluster.get('name', 'unnamed')
                
                # Resolve {guid} in cluster name for display
                resolved_cluster_name = cluster_name
                if '{guid}' in cluster_name and raw_yaml_data:
                    guid = raw_yaml_data.get('guid', 'unknown')
                    resolved_cluster_name = cluster_name.replace('{guid}', guid)
                
                location = cluster.get('location', 'unspecified')
                version = cluster.get('version', 'unspecified')
                size = cluster.get('size', 'unspecified')
                compute_nodes = cluster.get('compute_nodes', 'unspecified')
                compute_machine_type = cluster.get('compute_machine_type', 'unspecified')
                worker_nodes = cluster.get('worker_nodes', 'unspecified')
                worker_machine_type = cluster.get('worker_machine_type', 'unspecified')
                instructions += f" * {resolved_cluster_name} (ARO):\n"
                instructions += f"     Location: {location}\n"
                instructions += f"     Version: {version}\n"
                instructions += f"     Size: {size}\n"
                instructions += f"     Compute nodes: {compute_nodes} ({compute_machine_type})\n"
                instructions += f"     Worker nodes: {worker_nodes} ({worker_machine_type})\n"
                
                # Calculate and display cost if converter is available
                if converter:
                    hourly_cost = converter.calculate_openshift_cluster_cost(cluster, 'aro')
                    cost_string = converter.get_openshift_cluster_cost_string(resolved_cluster_name, 'aro', hourly_cost)
                    instructions += f"{cost_string}\n"
        if openshift_clusters:
            for cluster in openshift_clusters:
                cluster_name = cluster.get('name', 'unnamed')
                
                # Resolve {guid} in cluster name for display
                resolved_cluster_name = cluster_name
                if '{guid}' in cluster_name and raw_yaml_data:
                    guid = raw_yaml_data.get('guid', 'unknown')
                    resolved_cluster_name = cluster_name.replace('{guid}', guid)
                
                provider = cluster.get('provider', 'unspecified')
                region = cluster.get('region', 'unspecified')
                version = cluster.get('version', 'unspecified')
                size = cluster.get('size', 'unspecified')
                controlplane_count = cluster.get('controlplane_count', 'unspecified')
                worker_count = cluster.get('worker_count', 'unspecified')
                controlplane_type = cluster.get('compute_machine_type', 'unspecified')
                worker_type = cluster.get('worker_machine_type', 'unspecified')
                instructions += f" * {resolved_cluster_name} (Self-Managed):\n"
                instructions += f"     Provider: {provider}\n"
                instructions += f"     Region: {region}\n"
                instructions += f"     Version: {version}\n"
                instructions += f"     Size: {size}\n"
                instructions += f"     Control plane count: {controlplane_count} ({controlplane_type})\n"
                instructions += f"     Worker count: {worker_count} ({worker_type})\n"
                
                # Calculate and display cost if converter is available
                if converter:
                    hourly_cost = converter.calculate_openshift_cluster_cost(cluster, 'self-managed')
                    cost_string = converter.get_openshift_cluster_cost_string(resolved_cluster_name, 'self-managed', hourly_cost)
                    instructions += f"{cost_string}\n"
        if hypershift_mgmt_clusters:
            for cluster in hypershift_mgmt_clusters:
                cluster_name = cluster.get('name', 'unnamed')
                
                # Resolve {guid} in cluster name for display
                resolved_cluster_name = cluster_name
                if '{guid}' in cluster_name and raw_yaml_data:
                    guid = raw_yaml_data.get('guid', 'unknown')
                    resolved_cluster_name = cluster_name.replace('{guid}', guid)
                
                instructions += f" * {resolved_cluster_name} HyperShift Management\n"
        if hypershift_hosted_clusters:
            for cluster in hypershift_hosted_clusters:
                cluster_name = cluster.get('name', 'unnamed')
                
                # Resolve {guid} in cluster name for display
                resolved_cluster_name = cluster_name
                if '{guid}' in cluster_name and raw_yaml_data:
                    guid = raw_yaml_data.get('guid', 'unknown')
                    resolved_cluster_name = cluster_name.replace('{guid}', guid)
                
                instructions += f" * {resolved_cluster_name} HyperShift Hosted\n"
        
        # List Day-2 operations with headers for different types
        if has_day2_ops:
            
            # Applications Section
            if openshift_applications:
                instructions += "Applications:\n"
                for app in openshift_applications:
                    app_name = app.get('name', 'unnamed')
                    target_cluster = app.get('target_cluster', 'default')
                    namespace = app.get('namespace', 'default')
                    
                    # Extract image from deployment.containers or fallback to simple image field
                    image = 'unknown'
                    if 'deployment' in app and 'containers' in app['deployment']:
                        containers = app['deployment']['containers']
                        if containers and len(containers) > 0:
                            image = containers[0].get('image', 'unknown')
                    elif 'image' in app:
                        image = app.get('image', 'unknown')
                        
                    instructions += f" * {app_name} {target_cluster} {namespace} {image}\n"
            
            # GitOps Applications Section  
            if applications:
                instructions += "GitOps Applications:\n"
                for app in applications:
                    app_name = app.get('name', 'unnamed')
                    target_cluster = app.get('target_cluster', 'default')
                    namespace = app.get('namespace', 'default') 
                    image = app.get('image', 'unknown')
                    instructions += f" * {app_name} {target_cluster} {namespace} {image}\n"
            
            # Operators Section
            if openshift_operators:
                instructions += "Operators:\n"
                for operator in openshift_operators:
                    op_name = operator.get('name', 'unnamed')
                    target_cluster = operator.get('target_cluster', 'default')
                    namespace = operator.get('namespace', 'default')
                    operator_type = operator.get('type', 'unknown')
                    instructions += f" * {op_name} {target_cluster} {namespace} {operator_type}\n"
    
    # Check for regular instances
    instances = config.get('instances', [])
    if not instances:
        instructions += " * No clusters or instances detected\n"
    
    # Add total cost right after all OpenShift clusters are listed
    if converter:
        instructions += converter.get_total_hourly_cost_string()
        instructions += "\n"
    
    # Add deployment instructions header
    instructions += "\n"
    instructions += "Deployment Instructions:\n"
    instructions += "=" * 60 + "\n\n"
    
    # Add Terraform success message after deployment instructions header
    instructions += f"Terraform configuration generated successfully in '{output_dir}'\n\n"
    
    # Handle case with no OpenShift clusters (just regular infrastructure)
    if not clusters:
        instructions += f"Deploy Infrastructure and VM Instances:\n"
        instructions += f"  cd {output_dir}\n"
        instructions += f"  terraform init\n"
        instructions += f"  terraform plan\n" 
        instructions += f"  terraform apply\n\n"
        
        instructions += f"Quick Deploy (Auto-approve):\n"
        instructions += f"  cd {output_dir} && terraform init && terraform apply -auto-approve\n\n"
        
        instructions += f"Pro Tip: Use --auto-deploy flag to skip Terraform commands entirely:\n"
        instructions += f"  yamlforge your-config.yaml -d {output_dir} --auto-deploy\n\n"
        
        instructions += "Cleanup (When no longer needed):\n"
        instructions += f"  cd {output_dir} && terraform destroy\n"
        return instructions
    

    
    # Handle CLI vs Terraform deployment methods
    if deployment_method == 'cli':
        # CLI method - simple 2-phase deployment
        instructions += "ROSA CLI Deployment\n\n"
        
        instructions += "Phase 1: Deploy Infrastructure:\n"
        instructions += f"  cd {output_dir}\n"
        instructions += f"  terraform init\n"
        instructions += f"  terraform plan\n"
        instructions += f"  terraform apply\n\n"
        
        instructions += "Phase 1 (Quick Deploy):\n"
        instructions += f"  cd {output_dir} && terraform init && terraform apply -auto-approve\n\n"
        
        instructions += "Phase 2: Deploy ROSA Clusters:\n"
        instructions += f"  ./rosa-setup.sh\n"
        instructions += "Wait for clusters to be ready (~15-20 minutes)\n\n"
        
        if has_day2_ops:
            instructions += "Phase 3: Deploy Day-2 Operations:\n"
            instructions += f"  terraform apply -var=\"deploy_day2_operations=true\"\n\n"
        
        instructions += "Cleanup (When no longer needed):\n"
        instructions += f"  ./rosa-cleanup.sh --delete-all\n"
        instructions += f"  terraform destroy\n"
    
    else:
        # Terraform method - detailed phased deployment
        
        # Simplified deployment - everything deploys together with proper terraform dependencies
        instructions += f"Deploy All Infrastructure and Clusters:\n"
        instructions += f"  cd {output_dir}\n"
        instructions += f"  terraform init\n"
        instructions += f"  terraform plan\n"
        
        # Build deployment variables for any remaining conditional features (HyperShift, Day-2 ops)
        deploy_vars = []
        if hypershift_mgmt_clusters:
            deploy_vars.append("deploy_hypershift_mgmt=true")
        if hypershift_hosted_clusters:
            deploy_vars.append("deploy_hypershift_hosted=true")
        if has_day2_ops:
            deploy_vars.append("deploy_day2_operations=true")
        
        # Create the deployment command
        if deploy_vars:
            var_string = " ".join([f'-var="{v}"' for v in deploy_vars])
            instructions += f"  terraform apply {var_string}\n\n"
        else:
            instructions += f"  terraform apply\n\n"
        
        # Add quick deploy option
        instructions += f"Quick Deploy (Auto-approve):\n"
        if deploy_vars:
            var_string = " ".join([f'-var="{v}"' for v in deploy_vars])
            instructions += f"  cd {output_dir} && terraform init && terraform apply -auto-approve {var_string}\n\n"
        else:
            instructions += f"  cd {output_dir} && terraform init && terraform apply -auto-approve\n\n"
        
        instructions += f"Pro Tip: Use --auto-deploy flag to skip Terraform commands entirely:\n"
        instructions += f"  yamlforge your-config.yaml -d {output_dir} --auto-deploy\n\n"
        
        instructions += f"Infrastructure, ROSA clusters, and any optional components will deploy automatically\n"
        instructions += f"based on terraform dependencies. ROSA clusters typically take 15-20 minutes.\n\n"
        
        instructions += "Cleanup (When no longer needed):\n"
        instructions += f"  cd {output_dir} && terraform destroy\n"
    
    return instructions

def auto_deploy_infrastructure(output_dir, yaml_data):
    """Automatically deploy infrastructure with Terraform and ROSA."""
    print("\nStarting automatic deployment...")
    
    # Check if ROSA clusters exist (look in yamlforge config structure)
    has_rosa_clusters = False
    config = yaml_data.get('yamlforge', {})
    if 'openshift_clusters' in config:
        for cluster in config['openshift_clusters']:
            if cluster.get('type') in ['rosa-classic', 'rosa-hcp']:
                has_rosa_clusters = True
                break
    
    rosa_script_path = os.path.join(output_dir, 'rosa-setup.sh')
    has_rosa_script = os.path.exists(rosa_script_path)
    
    print(f"Deployment Plan:")
    print(f" * Terraform infrastructure")
    print(f" * ROSA clusters: {'YES' if has_rosa_clusters else 'NO'}")
    print(f" * ROSA script: {'YES' if has_rosa_script else 'NO'}")
    
    # Check for ROSA authentication
    rosa_token = os.getenv('REDHAT_OPENSHIFT_TOKEN')
    print(f" * ROSA authentication: {'YES' if rosa_token else 'WARNING: token needed for full automation'}")
    
    if not rosa_token:
        print(f"   Get token from: https://console.redhat.com/openshift/token/rosa")
        print(f"   export REDHAT_OPENSHIFT_TOKEN='your_token_here'")
    
    print(f"")
    
    # Phase 1: Terraform Infrastructure
    print(f"\nPHASE 1: Deploying Terraform Infrastructure")
    
    if not run_command("terraform init", cwd=output_dir, description="Initializing Terraform"):
        return False
    
    if not run_command("terraform plan", cwd=output_dir, description="Planning Terraform deployment"):
        return False
    
    if not run_command("terraform apply -auto-approve", cwd=output_dir, description="Applying Terraform configuration"):
        return False
    
    print(f"[SUCCESS] PHASE 1 Complete: AWS infrastructure deployed successfully")
    
    # Phase 2: ROSA Clusters (if present)
    if has_rosa_clusters and has_rosa_script:
        print(f"\nPHASE 2: Creating ROSA Clusters")
        print(f"This may take 15-20 minutes for cluster provisioning...")
        
        # Make script executable
        os.chmod(rosa_script_path, 0o755)
        
        if run_command("./rosa-setup.sh", cwd=output_dir, description="Creating ROSA clusters"):
            print(f"PHASE 2 Complete: ROSA clusters created successfully")
            print(f"\nCOMPLETE DEPLOYMENT SUCCESS!")
            print(f" * AWS infrastructure: Ready")
            print(f" * ROSA clusters: Ready")
            print(f" * Access via: rosa describe cluster <cluster-name>")
        else:
            print(f"PHASE 2 Failed: ROSA cluster creation failed")
            print(f"NOTE: Infrastructure is still available. Check ROSA CLI logs and retry manually.")
            return False
    else:
        print(f"\nPHASE 2: Skipped (No ROSA clusters configured)")
        print(f"DEPLOYMENT COMPLETE: Infrastructure ready")
    
    return True

def main():
    """Main entry point for yamlforge CLI."""
    parser = argparse.ArgumentParser(description='YamlForge - Convert unified YAML infrastructure to provider-specific Terraform')
    parser.add_argument('input_file', help='YAML infrastructure definition file')
    parser.add_argument('-d', '--output-dir', help='Output directory for generated Terraform files (not required with --analyze)')
    parser.add_argument('--analyze', action='store_true', help='Analyze configuration and show provider selections, cost analysis, and flavor mappings without generating Terraform files. Perfect for AI chatbots and exploring options.')
    parser.add_argument('--auto-deploy', action='store_true', help='Automatically execute Terraform and ROSA deployment after generation. WARNING: This will provision REAL cloud infrastructure and incur ACTUAL costs on your cloud provider accounts (VMs, storage, networking, OpenShift clusters can cost $100s+ per month). Use only when you understand the financial implications.')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output (show generated files, detailed AMI search info, etc.)')
    parser.add_argument('--no-credentials', action='store_true', help='Skip credential-dependent operations (dynamic image lookup, zone lookup, ROSA version lookup, etc.). WARNING: Generated Terraform will likely not work without manual updates to placeholders.')
    parser.add_argument('--ansible', action='store_true', help='Output structured JSON for Ansible module consumption instead of human-readable text')
    
    args = parser.parse_args()
    
    # Validate incompatible flags
    if args.analyze and args.auto_deploy:
        print("ERROR: --analyze and --auto-deploy cannot be used together")
        print("  --analyze: Analyze configuration without generating Terraform")
        print("  --auto-deploy: Generate Terraform and deploy automatically")
        print("  Use one or the other, not both")
        sys.exit(1)
    
    # Initialize Ansible output structure
    ansible_output = {
        'terraform_files': [],
        'deployment_status': 'not_attempted',
        'providers_detected': [],
        'warnings': [],
        'errors': []
    }
    
    # Print startup message (suppress if ansible mode)
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not args.ansible:
        print(f"YamlForge {__version__} begins at {current_time}")
    
    # Show warning if no-credentials mode is enabled
    if args.no_credentials and not args.ansible:
        print("\n" + "="*80)
        print("  NO-CREDENTIALS MODE ENABLED")
        print("="*80)
        print("This mode skips all credential-dependent operations:")
        print("  • Dynamic image lookup (AMIs, GCP images, etc.)")
        print("  • Zone availability checking")
        print("  • ROSA version discovery")
        print("  • Machine type validation")
        print("  • DNS zone discovery")
        print()
        print("  WARNING: The generated Terraform will likely NOT work without")
        print("   manual updates to replace placeholders with actual values.")
        print("   This mode is intended for testing and development only.")
        print("="*80 + "\n")
    
    # Validate that the input file exists
    if not os.path.exists(args.input_file):
        error_msg = f"Input file '{args.input_file}' does not exist"
        if args.ansible:
            ansible_output['errors'].append(error_msg)
            print(json.dumps(ansible_output))
        else:
            print(f"ERROR: {error_msg}")
        sys.exit(1)
    
    # Validate output directory (not required for analyze mode)
    if not args.analyze:
        if not args.output_dir:
            print("ERROR: Output directory (-d/--output-dir) is required unless using --analyze")
            sys.exit(1)
        
        if not os.path.exists(args.output_dir):
            print("Please create the directory first or use an existing directory")
            sys.exit(1)
        
        if not os.path.isdir(args.output_dir):
            print(f"ERROR: '{args.output_dir}' is not a directory")
            sys.exit(1)
    
    try:
        # Load the YAML configuration
        with open(args.input_file, 'r') as f:
            raw_yaml_data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"ERROR: Input file '{args.input_file}' not found")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"ERROR: Invalid YAML syntax in '{args.input_file}': {e}")
        sys.exit(1)
    
    try:
        # Validate YAML against schema
        validate_yaml_against_schema(raw_yaml_data, args.input_file, args.ansible)
        
        # Create converter instance (skip Terraform validation in analyze mode)
        converter = YamlForgeConverter(analyze_mode=args.analyze, ansible_mode=args.ansible)
        
        # Check for root-level instances (old format) and warn
        root_instances = raw_yaml_data.get('instances', [])
        if root_instances:
            print("WARNING: Found 'instances' at root level. This is deprecated and will be ignored.")
            print("Move 'instances' under 'yamlforge' section:")
            print("yamlforge:")
            print("  cloud_workspace:")
            print("    name: \"your-workspace-name\"")
            print("  instances:")
            print("    # ... your instances here")
            print()
        
        # Extract yamlforge configuration from root and merge defaults
        if 'yamlforge' not in raw_yaml_data:
            print("ERROR: YAML file must have a 'yamlforge' root element")
            print("Example structure:")
            print("yamlforge:")
            print("  providers:")
            print("    - aws")
            print("  instances:")
            print("    - name: my-instance")
            print("      provider: aws")
            sys.exit(1)
        
        config = raw_yaml_data['yamlforge']
        
        # Merge OpenShift defaults if OpenShift clusters are present but defaults are missing
        if 'openshift_clusters' in config and not config.get('rosa_deployment'):
            # Load OpenShift defaults
            try:
                import yaml as yaml_loader
                from .utils import find_yamlforge_file
                openshift_defaults_path = find_yamlforge_file('defaults/openshift.yaml')
                with open(openshift_defaults_path, 'r') as f:
                    openshift_defaults = yaml_loader.safe_load(f)
                
                # Merge OpenShift defaults at root level (not under 'openshift' key)
                openshift_config = openshift_defaults.get('openshift', {})
                for key, value in openshift_config.items():
                    if key not in config:
                        config[key] = value
                        if args.verbose:
                            print(f"Merged OpenShift default: {key}")
            except Exception as e:
                if args.verbose:
                    print(f"Could not load OpenShift defaults: {e}")
        
        # Set flags on converter so providers can access them
        converter.verbose = args.verbose
        converter.no_credentials = args.no_credentials
        
        # Import and run the converter
        if args.analyze:
            # Set analysis mode flag to suppress duplicate output
            # Run analysis mode
            analyze_configuration(converter, config, raw_yaml_data)
        else:
            # Pass the full YAML data so GUID can be extracted from root level
            converter.convert(config, args.output_dir, verbose=args.verbose, full_yaml_data=raw_yaml_data)
            
            # Collect generated Terraform files for Ansible output
            if args.ansible:
                for root, _, files in os.walk(args.output_dir):
                    for file in files:
                        if file.endswith('.tf'):
                            ansible_output['terraform_files'].append(os.path.join(root, file))
                
                # Get detected providers from converter
                if hasattr(converter, 'detected_providers'):
                    ansible_output['providers_detected'] = list(converter.detected_providers)
            
            if args.auto_deploy:
                if args.ansible:
                    ansible_output['deployment_status'] = 'attempting'
                try:
                    auto_deploy_infrastructure(args.output_dir, raw_yaml_data)
                    if args.ansible:
                        ansible_output['deployment_status'] = 'deployed'
                except Exception as deploy_error:
                    if args.ansible:
                        ansible_output['deployment_status'] = 'failed'
                        ansible_output['errors'].append(f"Deployment failed: {str(deploy_error)}")
                    else:
                        raise
            else:
                if not args.ansible:
                    deployment_instructions = generate_deployment_instructions(config, args.output_dir, converter, raw_yaml_data)
                    print(deployment_instructions)
        
        # Output JSON for Ansible if requested
        if args.ansible:
            print(json.dumps(ansible_output))

    except ValueError as e:
        # Handle user-friendly errors (like GUID validation) without stack trace
        error_msg = str(e)
        if args.ansible:
            ansible_output['errors'].append(error_msg)
            print(json.dumps(ansible_output))
        else:
            if "GUID is required" in error_msg or "GUID must be exactly" in error_msg or "Invalid GUID format" in error_msg:
                print(f"\nERROR: {e}\n")
            elif error_msg.startswith("ERROR:"):
                # Error message is already well-formatted (e.g., AWS smart errors), print as-is
                print(f"\n{e}\n")
            else:
                # Other ValueError - add generic formatting
                print(f"\nERROR: Configuration Error: {e}\n")
        sys.exit(1)
    except FileNotFoundError as e:
        error_msg = f"File Error: {e}"
        if args.ansible:
            ansible_output['errors'].append(error_msg)
            print(json.dumps(ansible_output))
        else:
            print(f"ERROR: {error_msg}")
        sys.exit(1)
    except Exception as e:
        error_msg = f"Unexpected Error: {e}"
        if args.ansible:
            ansible_output['errors'].append(error_msg)
            print(json.dumps(ansible_output))
        else:
            print(f"ERROR: {error_msg}")
        sys.exit(1)

if __name__ == "__main__":
    main()

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
from datetime import datetime

from .core.converter import YamlForgeConverter

# Version information
__version__ = "0.99.0a1"

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
    
    # Get instances
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
        print(f"INSTANCES ({len(instances)} found):")
        print("-" * 40)
        
        # Track which exclusions have been shown to avoid repetition
        shown_exclusions = set()
        
        for i, instance in enumerate(instances, 1):
            name = instance.get('name', 'unnamed')
            provider = instance.get('provider', 'unspecified')
            region = instance.get('region', 'unspecified')
            size = instance.get('size')
            cores = instance.get('cores')
            memory = instance.get('memory')
            gpu_type = instance.get('gpu_type')
            gpu_count = instance.get('gpu_count')
            image = instance.get('image', 'unspecified')
            instance_exclusions = instance.get('exclude_providers', [])
            
            print(f"\n{i}. {name}:")
            
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
            
            # Show resolved region with mapped value
            mapped_region = converter.locations.get(region, {}).get(resolved_provider, region)
            print(f"   Region: {region} ({mapped_region})")
            
            # Show resolved size/specs with mapped value
            if size:
                # Get mapped flavor for the resolved provider
                mapped_flavor = converter.flavors.get(size, {}).get(resolved_provider, size)
                print(f"   Size: {size} ({mapped_flavor})")
            elif cores and memory:
                print(f"   Specs: {cores} cores, {memory}MB RAM")
            
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
            
            print(f"\n{i}. {name}:")
            print(f"   Type: {cluster_type}")
            print(f"   Region: {region}")
            print(f"   Version: {version}")
            print(f"   Size: {size}")
    
    # Show required providers
    try:
        required_providers = converter.detect_required_providers(config)
        print(f"\nREQUIRED PROVIDERS:")
        print("-" * 40)
        for provider in required_providers:
            print(f"  • {provider}")
    except Exception as e:
        print(f"\nREQUIRED PROVIDERS: Error analyzing - {e}")
    
    print("\n" + "="*80)
    print("  ANALYSIS COMPLETE")
    print("="*80)
    print("Use 'yamlforge <file> -d <output_dir>' to generate Terraform files")
    print("Use 'yamlforge <file> -d <output_dir> --auto-deploy' to deploy automatically")

def generate_deployment_instructions(config, output_dir):
    """Generate specific deployment instructions based on YAML configuration."""
    
    # Analyze OpenShift cluster types present in the YAML
    clusters = config.get('openshift_clusters', [])
    
    # Detect cluster types
    rosa_classic_clusters = [c for c in clusters if c.get('type') == 'rosa-classic' and not c.get('hypershift', {}).get('role')]
    rosa_hcp_clusters = [c for c in clusters if c.get('type') == 'rosa-hcp']
    hypershift_mgmt_clusters = [c for c in clusters if c.get('type') == 'rosa-classic' and c.get('hypershift', {}).get('role') == 'management']
    hypershift_hosted_clusters = [c for c in clusters if c.get('type') == 'hypershift']
    
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
    
    # Show deployment method first (if applicable)
    if clusters:
        instructions += f"ROSA Deployment Method: {deployment_method.upper()}\n"
    
    instructions += "Detected OpenShift Cluster Types:\n"
    
    # List each cluster individually with format: * CLUSTERNAME CLUSTER_TYPE
    if rosa_classic_clusters:
        for cluster in rosa_classic_clusters:
            cluster_name = cluster.get('name', 'unnamed')
            instructions += f" * {cluster_name} ROSA Classic\n"
    
    if rosa_hcp_clusters:
        for cluster in rosa_hcp_clusters:
            cluster_name = cluster.get('name', 'unnamed')
            instructions += f" * {cluster_name} ROSA HCP\n"
    
    if hypershift_mgmt_clusters:
        for cluster in hypershift_mgmt_clusters:
            cluster_name = cluster.get('name', 'unnamed')
            instructions += f" * {cluster_name} HyperShift Management\n"
    
    if hypershift_hosted_clusters:
        for cluster in hypershift_hosted_clusters:
            cluster_name = cluster.get('name', 'unnamed')
            instructions += f" * {cluster_name} HyperShift Hosted\n"
    
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
    
    if not clusters:
        # Check for regular instances
        instances = config.get('instances', [])
        if instances:
            instance_names = [i.get('name', 'unnamed') for i in instances]
            instructions += f" * VM Instances: {', '.join(instance_names)}\n"
        else:
            instructions += " * No clusters or instances detected\n"
    
    instructions += "\n"
    
    # Add deployment instructions header
    instructions += "Deployment Instructions:\n"
    instructions += "=" * 60 + "\n\n"
    
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
    
    # Check for ROSA authentication if ROSA clusters are present
    if has_rosa_clusters:
        rosa_token = (os.getenv('ROSA_TOKEN') or 
                     os.getenv('OCM_TOKEN') or 
                     os.getenv('REDHAT_OPENSHIFT_TOKEN'))
        print(f" * ROSA authentication: {'YES' if rosa_token else 'WARNING: token needed for full automation'}")
        
        if not rosa_token:
            print(f"")
            print(f"NOTE: For complete automation, set a ROSA token:")
            print(f" export ROSA_TOKEN='your_token_here'")
            print(f" Get token from: https://console.redhat.com/openshift/token/rosa")
    
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
    
    args = parser.parse_args()
    
    # Validate incompatible flags
    if args.analyze and args.auto_deploy:
        print("ERROR: --analyze and --auto-deploy cannot be used together")
        print("  --analyze: Analyze configuration without generating Terraform")
        print("  --auto-deploy: Generate Terraform and deploy automatically")
        print("  Use one or the other, not both")
        sys.exit(1)
    
    # Print startup message
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"YamlForge {__version__} begins at {current_time}")
    
    # Show warning if no-credentials mode is enabled
    if args.no_credentials:
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
        print(f"ERROR: Input file '{args.input_file}' does not exist")
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
        # Create converter instance (skip Terraform validation in analyze mode)
        converter = YamlForgeConverter(analyze_mode=args.analyze)
        # Load and validate the YAML configuration
        with open(args.input_file, 'r') as f:
            raw_yaml_data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"ERROR: Input file '{args.input_file}' not found")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"ERROR: Invalid YAML syntax in '{args.input_file}': {e}")
        sys.exit(1)
    
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
            openshift_defaults_path = os.path.join(os.path.dirname(__file__), '..', 'defaults', 'openshift.yaml')
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
    try:
        if args.analyze:
            # Run analysis mode
            analyze_configuration(converter, config, raw_yaml_data)
        else:
            # Pass the full YAML data so GUID can be extracted from root level
            converter.convert(config, args.output_dir, verbose=args.verbose, full_yaml_data=raw_yaml_data)
            print(f"Terraform configuration generated successfully in '{args.output_dir}'")
            print()
            
            if args.auto_deploy:
                auto_deploy_infrastructure(args.output_dir, raw_yaml_data)
            else:
                deployment_instructions = generate_deployment_instructions(config, args.output_dir)
                print(deployment_instructions)

    except ValueError as e:
        # Handle user-friendly errors (like GUID validation) without stack trace
        error_msg = str(e)
        if "GUID is required" in error_msg or "GUID must be exactly" in error_msg or "Invalid GUID format" in error_msg:
            print(f"\nERROR: {e}\n")
            sys.exit(1)
        elif error_msg.startswith("ERROR:"):
            # Error message is already well-formatted (e.g., AWS smart errors), print as-is
            print(f"\n{e}\n")
            sys.exit(1)
        else:
            # Other ValueError - add generic formatting
            print(f"\nERROR: Configuration Error: {e}\n")
            sys.exit(1)
    except FileNotFoundError as e:
        print(f"ERROR: File Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

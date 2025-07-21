#!/usr/bin/env python3
"""
Main entry point for the yamlforge multi-cloud infrastructure converter.

This module provides the command-line interface for YamlForge, which converts
unified YAML infrastructure definitions into provider-specific Terraform configurations.
"""

import argparse
import os
import sys
import yaml

def main():
    """Main entry point for the yamlforge command-line tool."""
    parser = argparse.ArgumentParser(
        description='YamlForge - Convert unified YAML infrastructure to provider-specific Terraform',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('input_file', help='YAML infrastructure definition file')
    parser.add_argument('-d', '--output-dir', required=True, help='Output directory for generated Terraform files')
    
    args = parser.parse_args()
    
    # Load and validate the YAML configuration
    try:
        with open(args.input_file, 'r') as f:
            yaml_data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_file}' not found")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML syntax in '{args.input_file}': {e}")
        sys.exit(1)
    
    # Extract yamlforge configuration from root
    if 'yamlforge' not in yaml_data:
        print("Error: YAML file must have a 'yamlforge' root element")
        print("Example structure:")
        print("yamlforge:")
        print("  providers:")
        print("    - aws")
        print("  instances:")
        print("    - name: my-instance")
        print("      provider: aws")
        sys.exit(1)
    
    config = yaml_data['yamlforge']
    
    # Validate output directory exists
    if not os.path.exists(args.output_dir):
        print(f"Error: Output directory '{args.output_dir}' does not exist")
        print("Please create the directory first or use an existing directory")
        sys.exit(1)
    
    # Import and run the converter
    from .core.converter import InfrastructureConverter
    
    converter = InfrastructureConverter()
    converter.convert(config, args.output_dir)
    
    print(f"✅ Terraform configuration generated successfully in '{args.output_dir}'")

if __name__ == "__main__":
    main()
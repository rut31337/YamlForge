#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2025, Patrick T. Rutledge III
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: yamlforge
short_description: Generate multi-cloud infrastructure using YamlForge
description:
    - Convert unified YAML configurations into provider-specific Terraform code
    - Support for AWS, Azure, GCP, IBM, OCI, Alibaba, VMware, and OpenShift
    - Intelligent cost optimization and provider selection
    - Generate complete Terraform modules with variables and outputs
version_added: "1.0.0"
author:
    - Patrick T. Rutledge III
requirements:
    - python >= 3.8
    - yamlforge-infra >= 1.0.0b3
    - terraform >= 1.12.0 (for OpenShift/ROSA support)
options:
    config_file:
        description:
            - Path to the YamlForge YAML configuration file
        required: true
        type: path
    output_dir:
        description:
            - Directory where Terraform files will be generated
        required: true
        type: path
    auto_deploy:
        description:
            - Automatically deploy infrastructure after generation
        required: false
        default: false
        type: bool
    no_credentials:
        description:
            - Generate configuration without cloud credentials (testing mode)
        required: false
        default: false
        type: bool
    verbose:
        description:
            - Enable verbose output
        required: false
        default: false
        type: bool
    exclude_providers:
        description:
            - List of providers to exclude from cheapest analysis
        required: false
        type: list
        elements: str
    guid:
        description:
            - 5-character GUID for resource identification
        required: false
        type: str
notes:
    - Requires cloud provider credentials configured via environment variables
    - See yamlforge documentation for credential configuration details
    - Always use unique GUIDs to prevent resource naming conflicts
'''

EXAMPLES = r'''
- name: Generate Terraform files
  rut31337.yamlforge.infrastructure:
    config_file: /path/to/config.yaml
    output_dir: /tmp/terraform-output
    verbose: true

- name: Generate and auto-deploy infrastructure
  rut31337.yamlforge.infrastructure:
    config_file: /path/to/config.yaml
    output_dir: /tmp/terraform-output
    auto_deploy: true
    guid: "abc12"

- name: Generate without credentials (testing)
  rut31337.yamlforge.infrastructure:
    config_file: /path/to/config.yaml
    output_dir: /tmp/terraform-output
    no_credentials: true

- name: Exclude specific providers from cost optimization
  rut31337.yamlforge.infrastructure:
    config_file: /path/to/config.yaml
    output_dir: /tmp/terraform-output
    exclude_providers:
      - aws
      - azure
'''

RETURN = r'''
terraform_files:
    description: List of generated Terraform files
    returned: always
    type: list
    sample: ["/tmp/terraform-output/aws/main.tf", "/tmp/terraform-output/aws/variables.tf"]
deployment_status:
    description: Deployment status when auto_deploy is enabled
    returned: when auto_deploy is true
    type: str
    sample: "deployed"
changed:
    description: Whether Terraform files were generated or infrastructure was deployed
    returned: always
    type: bool
    sample: true
'''

import os
import sys
import subprocess
import tempfile
import json
import yaml
from ansible.module_utils.basic import AnsibleModule

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


def validate_yaml_config(module, config_file, yamlforge_root):
    """Validate YAML configuration against YamlForge schema"""
    
    if not HAS_JSONSCHEMA:
        # Skip validation if jsonschema is not available
        return True
    
    # Load the YAML configuration
    try:
        with open(config_file, 'r') as f:
            yaml_data = yaml.safe_load(f)
    except Exception as e:
        module.fail_json(msg=f"Failed to load YAML configuration: {str(e)}")
    
    # Find the schema file
    schema_path = None
    if yamlforge_root:
        potential_schema_path = os.path.join(yamlforge_root, 'docs', 'yamlforge-schema.json')
        if os.path.exists(potential_schema_path):
            schema_path = potential_schema_path
    
    if not schema_path:
        # Schema not found, skip validation but warn
        return True
    
    # Load the schema
    try:
        with open(schema_path, 'r') as f:
            schema = json.load(f)
    except Exception as e:
        # Schema loading failed, skip validation but warn
        return True
    
    # Validate the configuration
    try:
        jsonschema.validate(yaml_data, schema)
        return True
    except jsonschema.ValidationError as e:
        # Format the validation error nicely
        error_msg = f"YAML configuration validation failed:\n\n"
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
            error_msg += "instances:\n"
            error_msg += "  - name: \"my-instance\"\n"
            error_msg += "    provider: aws\n"
            error_msg += "    # ... other properties\n"
        
        module.fail_json(msg=error_msg)
    except Exception as e:
        # Other validation errors, skip validation but warn
        return True


def run_yamlforge_command(module, config_file, output_dir, **kwargs):
    """Execute yamlforge command with specified parameters"""
    
    # Find YamlForge root directory first to locate yamlforge.py
    yamlforge_root = None
    
    # Start from current directory and work up
    current_path = os.getcwd()
    search_paths = [current_path]
    
    # Add parent directories up to root
    path = current_path
    for _ in range(10):  # Limit search to avoid infinite loops
        parent = os.path.dirname(path)
        if parent == path:  # Reached filesystem root
            break
        search_paths.append(parent)
        path = parent
    
    # Also check if this collection is within the YamlForge repository
    # The collection should be at ansible_collections/rut31337/yamlforge/
    module_file = os.path.abspath(__file__)
    module_dir = os.path.dirname(module_file)
    collection_root = os.path.dirname(os.path.dirname(os.path.dirname(module_dir)))  # Go up 3 levels from plugins/modules/
    if 'ansible_collections' in collection_root:
        yamlforge_repo_root = os.path.dirname(collection_root)  # Parent of ansible_collections
        search_paths.append(yamlforge_repo_root)
    
    for path in search_paths:
        if os.path.exists(os.path.join(path, 'defaults')) and os.path.exists(os.path.join(path, 'mappings')):
            yamlforge_root = path
            break
    
    # Try to find yamlforge.py in YamlForge root, then fall back to module
    yamlforge_script = None
    if yamlforge_root:
        yamlforge_script_path = os.path.join(yamlforge_root, 'yamlforge.py')
        if os.path.exists(yamlforge_script_path):
            yamlforge_script = yamlforge_script_path
    
    if yamlforge_script:
        cmd = [sys.executable, yamlforge_script, config_file, '-d', output_dir, '--ansible']
    else:
        cmd = [sys.executable, '-m', 'yamlforge.main', config_file, '-d', output_dir, '--ansible']
    
    if kwargs.get('auto_deploy', False):
        cmd.append('--auto-deploy')
    
    if kwargs.get('no_credentials', False):
        cmd.append('--no-credentials')
    
    if kwargs.get('verbose', False):
        cmd.append('--verbose')
    
    if kwargs.get('guid'):
        os.environ['YAMLFORGE_GUID'] = kwargs['guid']
    
    if kwargs.get('exclude_providers'):
        os.environ['YAMLFORGE_EXCLUDE_PROVIDERS'] = ','.join(kwargs['exclude_providers'])
    
    # Use the yamlforge_root found earlier, or fallback to current directory
    if not yamlforge_root:
        yamlforge_root = os.getcwd()  # Fallback to current directory
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            cwd=yamlforge_root
        )
        
        return result.returncode, result.stdout, result.stderr
        
    except FileNotFoundError:
        module.fail_json(
            msg="yamlforge command not found. Please install yamlforge-infra package: pip install yamlforge-infra>=1.0.0b3",
            cmd=' '.join(cmd)
        )
    except Exception as e:
        module.fail_json(
            msg=f"Failed to execute yamlforge: {str(e)}",
            cmd=' '.join(cmd)
        )


def parse_yamlforge_output(stdout, stderr, output_dir):
    """Parse yamlforge JSON output (with --ansible flag)"""
    
    result = {
        'terraform_files': [],
        'deployment_status': 'not_attempted',
        'providers_detected': [],
        'warnings': [],
        'errors': []
    }
    
    # Try to parse JSON output from YamlForge --ansible mode
    try:
        # Look for JSON in stdout
        stdout_lines = stdout.strip().split('\n')
        for line in stdout_lines:
            if line.strip().startswith('{') and line.strip().endswith('}'):
                json_output = json.loads(line.strip())
                result.update(json_output)
                return result
    except (json.JSONDecodeError, ValueError):
        # Fall back to file system scan if JSON parsing fails
        pass
    
    # Fallback: Look for actual generated files in output directory
    if os.path.exists(output_dir):
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                if file.endswith('.tf'):
                    result['terraform_files'].append(os.path.join(root, file))
    
    # Parse any errors from stderr
    if stderr:
        result['errors'].append(stderr.strip())
    
    return result


def main():
    module_args = dict(
        config_file=dict(type='path', required=True),
        output_dir=dict(type='path', required=True),
        auto_deploy=dict(type='bool', required=False, default=False),
        no_credentials=dict(type='bool', required=False, default=False),
        verbose=dict(type='bool', required=False, default=False),
        exclude_providers=dict(type='list', elements='str', required=False),
        guid=dict(type='str', required=False),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    config_file = module.params['config_file']
    output_dir = module.params['output_dir']
    
    # Validate input files and directories
    if not os.path.exists(config_file):
        module.fail_json(msg=f"Configuration file not found: {config_file}")
    
    # Find YamlForge root directory for schema validation
    yamlforge_root = None
    current_path = os.getcwd()
    search_paths = [current_path]
    
    # Add parent directories up to root
    path = current_path
    for _ in range(10):  # Limit search to avoid infinite loops
        parent = os.path.dirname(path)
        if parent == path:  # Reached filesystem root
            break
        search_paths.append(parent)
        path = parent
    
    # Also check if this collection is within the YamlForge repository
    module_file = os.path.abspath(__file__)
    module_dir = os.path.dirname(module_file)
    collection_root = os.path.dirname(os.path.dirname(os.path.dirname(module_dir)))  # Go up 3 levels from plugins/modules/
    if 'ansible_collections' in collection_root:
        yamlforge_repo_root = os.path.dirname(collection_root)  # Parent of ansible_collections
        search_paths.append(yamlforge_repo_root)
    
    for path in search_paths:
        if os.path.exists(os.path.join(path, 'defaults')) and os.path.exists(os.path.join(path, 'mappings')):
            yamlforge_root = path
            break
    
    # Validate YAML configuration against schema
    validate_yaml_config(module, config_file, yamlforge_root)
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    if not os.path.isdir(output_dir):
        module.fail_json(msg=f"Output directory is not accessible: {output_dir}")
    
    # Check mode - don't actually run yamlforge
    if module.check_mode:
        module.exit_json(
            changed=True,
            msg="Would generate Terraform files with YamlForge",
            config_file=config_file,
            output_dir=output_dir
        )
    
    # Execute yamlforge
    kwargs = {k: v for k, v in module.params.items() if k not in ['config_file', 'output_dir']}
    returncode, stdout, stderr = run_yamlforge_command(
        module, config_file, output_dir, **kwargs
    )
    
    # Parse output
    parsed_result = parse_yamlforge_output(stdout, stderr, output_dir)
    
    # Determine if changes were made
    changed = len(parsed_result['terraform_files']) > 0
    
    if module.params['auto_deploy'] and parsed_result['deployment_status'] == 'deployed':
        changed = True
    
    # Handle errors
    if returncode != 0:
        module.fail_json(
            msg="yamlforge execution failed",
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            **parsed_result
        )
    
    # Success
    module.exit_json(
        changed=changed,
        msg="yamlforge execution completed successfully",
        stdout=stdout,
        stderr=stderr,
        **parsed_result
    )


if __name__ == '__main__':
    main()
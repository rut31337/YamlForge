# Using YamlForge as a Python Library

This document shows how to use YamlForge as a Python library from external programs to analyze YAML configurations and determine required cloud providers.

## Overview

YamlForge can be used as a library to:
- Parse YAML infrastructure configurations (from dictionaries or files)
- Detect required cloud providers (including resolving `cheapest` meta-providers)
- Validate configurations without generating Terraform
- Analyze costs across providers

## Basic Usage

### Installation

```bash
pip install yamlforge-infra
```

### Import and Initialize

```python
from yamlforge.core.converter import YamlForgeConverter

# Initialize converter in analyze mode (no Terraform validation)
converter = YamlForgeConverter(analyze_mode=True)
```

### Analyze Configuration from Dictionary

```python
# Define your infrastructure configuration as a dictionary
yamlforge_config = {
    'guid': 'test1',  # Optional: can also be set via environment variable
    'yamlforge': {
        'cloud_workspace': {'name': 'my-workspace'},
        'instances': [
            {
                'name': 'web-server-{guid}',
                'provider': 'aws',
                'flavor': 'small',
                'region': 'us-east-1'
            }
        ]
    }
}

# Set the configuration for processing
converter.set_yaml_data(yamlforge_config)

# Detect required providers
required_providers = converter.detect_required_providers(yamlforge_config)
print("Required providers:", required_providers)
```

## Handling Different Provider Types

### Declarative Providers

When instances specify explicit providers:

```python
config = {
    'yamlforge': {
        'cloud_workspace': {'name': 'my-workspace'},
        'instances': [
            {
                'name': 'web-server',
                'provider': 'aws',
                'flavor': 'small',
                'region': 'us-east-1'
            },
            {
                'name': 'database',
                'provider': 'gcp', 
                'flavor': 'medium',
                'region': 'us-central1'
            }
        ]
    }
}

converter.set_yaml_data(config)
providers = converter.detect_required_providers(config)
# Result: ['aws', 'gcp']
```

### Cheapest Meta-Provider

When instances use the `cheapest` meta-provider, YamlForge resolves them to actual providers:

```python
config = {
    'yamlforge': {
        'cloud_workspace': {'name': 'my-workspace'},
        'instances': [
            {
                'name': 'worker-{guid}',
                'provider': 'cheapest',
                'cores': 4,
                'memory': 8192,  # MB
                'location': 'us-east'
            },
            {
                'name': 'gpu-node',
                'provider': 'cheapest-gpu',
                'gpu_type': 'NVIDIA T4',
                'location': 'us-west'
            }
        ]
    }
}

converter.set_yaml_data(config)
providers = converter.detect_required_providers(config)
# Result might be: ['aws', 'gcp'] (after cost analysis)
```

### Mixed Configurations

Combining declarative and cheapest providers:

```python
config = {
    'yamlforge': {
        'cloud_workspace': {'name': 'hybrid-deployment'},
        'instances': [
            {
                'name': 'frontend',
                'provider': 'aws',  # Explicit
                'flavor': 'small',
                'region': 'us-east-1'
            },
            {
                'name': 'backend',
                'provider': 'cheapest',  # Will be resolved
                'cores': 2,
                'memory': 4096,
                'location': 'us-east'
            }
        ],
        'storage': [
            {
                'name': 'data-bucket',
                'provider': 'cheapest',  # Will be resolved
                'location': 'us-east'
            }
        ],
        'openshift_clusters': [
            {
                'name': 'prod-cluster',
                'type': 'rosa-classic',  # Implies AWS
                'region': 'us-east-1'
            }
        ]
    }
}

converter.set_yaml_data(config)
providers = converter.detect_required_providers(config)
# Result might be: ['aws', 'azure', 'rhcs', 'kubernetes', 'helm']
```

## Complete Example

```python
#!/usr/bin/env python3
"""
Example: Using YamlForge as a library to analyze provider requirements
"""

import os
from yamlforge.core.converter import YamlForgeConverter

def analyze_yamlforge_config(config_dict):
    """
    Analyze a YamlForge configuration dictionary and return required providers
    """
    try:
        # Initialize converter in analyze mode
        converter = YamlForgeConverter(analyze_mode=True)
        
        # Validate basic structure
        if 'yamlforge' not in config_dict:
            raise ValueError("Configuration must contain 'yamlforge' section")
        
        # Set configuration for processing
        converter.set_yaml_data(config_dict)
        
        # Validate provider setup (this will resolve cheapest providers)
        converter.validate_provider_setup(config_dict)
        
        # Detect all required providers
        required_providers = converter.detect_required_providers(config_dict)
        
        return {
            'success': True,
            'providers': sorted(required_providers),
            'config': config_dict['yamlforge']
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def main():
    # Example configuration dictionary
    config = {
        'guid': 'test1',
        'yamlforge': {
            'cloud_workspace': {
                'name': 'demo-environment'
            },
            'instances': [
                {
                    'name': 'web-{guid}',
                    'provider': 'cheapest',
                    'cores': 2,
                    'memory': 4096,
                    'location': 'us-east'
                },
                {
                    'name': 'database-{guid}',
                    'provider': 'aws',
                    'flavor': 'medium',
                    'region': 'us-east-1'
                }
            ],
            'storage': [
                {
                    'name': 'app-data-{guid}',
                    'provider': 'cheapest',
                    'location': 'us-east'
                }
            ]
        }
    }
    
    # Analyze configuration
    result = analyze_yamlforge_config(config)
    
    if result['success']:
        print("Analysis successful!")
        print(f"Required providers: {result['providers']}")
        print(f"Workspace: {result['config']['cloud_workspace']['name']}")
        print(f"Instance count: {len(result['config'].get('instances', []))}")
        print(f"Storage count: {len(result['config'].get('storage', []))}")
    else:
        print(f"Analysis failed: {result['error']}")

if __name__ == '__main__':
    main()
```

## Loading from YAML Files (Alternative)

If you need to load from YAML files:

```python
import yaml

def analyze_from_file(yaml_file_path):
    """Load and analyze a YAML file"""
    # Load YAML configuration from file
    with open(yaml_file_path, 'r') as f:
        config_dict = yaml.safe_load(f)
    
    # Use the same analysis function
    return analyze_yamlforge_config(config_dict)

# Usage
result = analyze_from_file('infrastructure.yaml')
```

## Advanced Usage

### Setting Provider Exclusions

```python
import os

# Exclude specific providers from cheapest analysis
os.environ['YAMLFORGE_EXCLUDE_PROVIDERS'] = 'aws,azure'

converter = YamlForgeConverter(analyze_mode=True)
# Now cheapest provider will not consider AWS or Azure
```

### Setting GUID for Analysis

```python
import os

# Option 1: Set GUID via environment variable
os.environ['GUID'] = 'prod1'

# Option 2: Include in configuration dictionary
config = {
    'guid': 'dev01',
    'yamlforge': {
        # ... configuration
    }
}
```

### Cost Analysis

```python
# Enable cost analysis by resolving cheapest providers
converter.set_yaml_data(config)

# Get cost information for specific instance
instance = {
    'name': 'test-instance',
    'provider': 'cheapest',
    'cores': 4,
    'memory': 8192
}

# This will analyze costs and return the cheapest provider
cheapest_provider = converter.find_cheapest_provider(instance, suppress_output=True)
print(f"Cheapest provider for instance: {cheapest_provider}")
```

### Validation Only

```python
def validate_config(config_dict):
    """Validate configuration without provider detection"""
    try:
        converter = YamlForgeConverter(analyze_mode=True)
        converter.set_yaml_data(config_dict)
        converter.validate_provider_setup(config_dict)
        return True, "Configuration is valid"
    except Exception as e:
        return False, str(e)

# Usage
is_valid, message = validate_config(my_config)
print(f"Valid: {is_valid}, Message: {message}")
```

## Provider Types Returned

The `detect_required_providers()` method can return:

### Cloud Providers
- `aws` - Amazon Web Services
- `azure` - Microsoft Azure  
- `gcp` - Google Cloud Platform
- `ibm_vpc` - IBM Cloud VPC
- `ibm_classic` - IBM Cloud Classic
- `oci` - Oracle Cloud Infrastructure
- `alibaba` - Alibaba Cloud
- `vmware` - VMware vSphere
- `cnv` - Container Native Virtualization

### OpenShift Providers
- `rhcs` - Red Hat Cloud Services (for ROSA)
- `kubernetes` - Kubernetes provider
- `helm` - Helm provider
- `kubectl` - kubectl provider

## Error Handling

```python
try:
    converter.set_yaml_data(config_dict)
    providers = converter.detect_required_providers(config_dict)
except ValueError as e:
    print(f"Configuration error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Integration Examples

### Flask Web Application

```python
from flask import Flask, request, jsonify
from yamlforge.core.converter import YamlForgeConverter

app = Flask(__name__)

@app.route('/analyze', methods=['POST'])
def analyze_infrastructure():
    config = request.get_json()
    result = analyze_yamlforge_config(config)
    return jsonify(result)
```

### Django View

```python
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def analyze_view(request):
    if request.method == 'POST':
        config = json.loads(request.body)
        result = analyze_yamlforge_config(config)
        return JsonResponse(result)
```

## Notes

- Use `analyze_mode=True` when initializing the converter to skip Terraform version validation
- The converter automatically resolves `cheapest` and `cheapest-gpu` meta-providers to actual cloud providers
- Provider exclusions can be set via environment variables or YAML configuration
- GUID resolution follows this priority: environment variable > configuration dictionary > error if missing
- The library respects all YamlForge configuration options including cost analysis and provider selection rules
- Dictionary input is the primary method; file loading is provided as a convenience wrapper
# Core Configuration

YamlForge uses a core configuration system that provides global defaults and settings that affect all deployments across all cloud providers.

## Overview

The core configuration is loaded from `defaults/core.yaml` and provides centralized control over YamlForge's behavior. This configuration is separate from your deployment YAML files and is designed to be organization-wide settings.

## Configuration File Location

- **Default**: `defaults/core.yaml`
- **Fallback**: If the file is not found, YamlForge uses built-in defaults

## Security Configuration

### Default Username

The most important core configuration is the default username for SSH access to instances:

```yaml
security:
  # Default username for instances across all cloud providers
  # This username will be used as the default for SSH access and VM creation
  # Can be overridden per instance with the 'username' field
  default_username: "cloud-user"
```

#### How It Works

1. **Global Default**: The `default_username` setting applies to all cloud providers (AWS, Azure, GCP, OCI, etc.)
2. **Provider Integration**: Each provider automatically uses this username for:
   - SSH key configuration
   - User data scripts (where needed)
   - Terraform outputs
   - SSH command generation
3. **Override Support**: Individual instances can override this with their own `username` field

#### Provider-Specific Behavior

| Provider | Native Support | User Data Scripts | Notes |
|----------|----------------|-------------------|-------|
| **AWS** | ❌ No | ✅ Required | Creates user via user data |
| **Azure** | ❌ No | ✅ Required | Creates user via custom data |
| **GCP** | ✅ Yes | ❌ Not needed | Native support in RHEL images |
| **OCI** | ✅ Yes | ❌ Not needed | Native support in Oracle Linux |
| **IBM VPC** | ✅ Yes | ❌ Not needed | Native support in RHEL images |

#### Examples

**Default behavior** (uses `cloud-user`):
```yaml
# No core configuration needed - uses defaults/core.yaml
yamlforge:
  instances:
    - name: "my-vm"
      provider: "aws"
      # Will use cloud-user as default username
```

**Custom username**:
```yaml
yamlforge:
  core:
    security:
      default_username: "my-custom-user"
  instances:
    - name: "my-vm"
      provider: "aws"
      # Will use my-custom-user as default username
```

**Per-instance override**:
```yaml
yamlforge:
  instances:
    - name: "my-vm"
      provider: "aws"
      username: "instance-specific-user"  # Overrides default
```

### SSH Key Configuration

```yaml
security:
  # Default SSH public key for instances (can be overridden per provider)
  default_ssh_public_key: ""
  
  # Auto-detect SSH keys from ~/.ssh/ directory (default: false)
  auto_detect_ssh_keys: false
```

## Provider Selection Configuration

```yaml
provider_selection:
  # Providers to EXCLUDE from "cheapest" provider selection
  exclude_from_cheapest:
    - "vmware"      # Exclude on-premises VMware from cost comparisons
    - "alibaba"     # Exclude Alibaba Cloud for compliance reasons

  # Provider priority order for tie-breaking in cost comparisons
  priority_order:
    - "ibm_classic"   # IBM Classic infrastructure
    - "ibm_vpc"       # IBM Cloud VPC
    - "gcp"           # Google Cloud Platform
    - "aws"           # Amazon Web Services
    - "azure"         # Microsoft Azure
    - "vmware"        # VMware vSphere (on-premises)
    - "oci"           # Oracle Cloud (often cheapest)
    - "alibaba"       # Alibaba Cloud (competitive in APAC)
```

## Cost Analysis Configuration

```yaml
cost_analysis:
  # Default currency for cost calculations
  default_currency: "USD"
  
  # Regional cost adjustment factors (multipliers)
  regional_cost_factors:
    "cn-hangzhou": 0.85    # Alibaba Cloud China regions often cheaper
    "ap-southeast-1": 1.05  # Singapore slightly more expensive
    
  # Provider-specific cost factors (for on-premises or special pricing)
  provider_cost_factors:
    "vmware": 0.8           # Assume 20% cheaper than cloud (amortized hardware)
```

## Resource Tagging Defaults

```yaml
default_tags:
  # Tags automatically applied to ALL resources across ALL providers
  global_tags:
    ManagedBy: "yamlforge"
    Framework: "terraform"
    CreatedBy: "yamlforge-v2"
    
  # Organization-specific tags (customize these)
  organization_tags:
    Environment: "production"
    Department: "infrastructure"
    CostCenter: "12345"
```

## Image and Template Preferences

```yaml
image_preferences:
  # Preferred operating system families in order of preference
  os_family_priority:
    - "rhel"          # Red Hat Enterprise Linux (enterprise standard)
    - "ubuntu"        # Ubuntu (developer friendly)
    - "centos"        # CentOS (free RHEL alternative)
    
  # Default to latest stable versions
  prefer_latest_versions: true
  
  # Avoid beta/preview images in production
  exclude_preview_images: true
```

## Networking Defaults

```yaml
networking:
  # Default CIDR blocks for new deployments
  default_cidr_blocks:
    vpc: "10.0.0.0/16"
    subnet: "10.0.1.0/24"
    
  # Preferred availability zone distribution
  multi_az_preference: true
  min_availability_zones: 2
  
  # Default security posture
  default_internet_access: true
  default_private_subnets: false
```

## Feature Flags

```yaml
features:
  # Enable experimental features
  experimental_features: false
  
  # Enable cost optimization recommendations
  cost_optimization_suggestions: true
  
  # Enable automatic resource tagging
  auto_tagging: true
  
  # Enable multi-region deployments
  multi_region_support: true
  
  # Enable provider health checks before deployment
  provider_health_checks: false
```

## Deployment Behavior

```yaml
deployment:
  # Default behavior for handling provider failures
  provider_failure_behavior: "skip"  # "skip", "fail", "retry"
  
  # Maximum number of retries for failed provider operations
  max_retries: 3
  
  # Timeout for provider operations (seconds)
  provider_timeout: 300
  
  # Enable parallel provider operations
  parallel_deployments: true
```

## Logging and Monitoring

```yaml
logging:
  # Log level for yamlforge operations
  log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  
  # Enable detailed cost analysis logging
  log_cost_analysis: true
  
  # Enable provider selection reasoning logs
  log_provider_selection: true
```

## Customizing Core Configuration

### Method 1: Edit defaults/core.yaml

Modify the `defaults/core.yaml` file directly to change organization-wide defaults.

### Method 2: Environment-Specific Overrides

Create environment-specific core configuration files and use them with the `--core-config` flag (if implemented).

### Method 3: YAML Overrides

Override specific core settings in your YAML configuration:

```yaml
yamlforge:
  core:
    security:
      default_username: "my-custom-user"
  instances:
    - name: "my-vm"
      provider: "aws"
```

## Best Practices

1. **Consistent Usernames**: Use the same default username across all environments for consistency
2. **Security**: Keep default usernames simple but secure (avoid common names like "admin")
3. **Documentation**: Document your core configuration choices for team members
4. **Version Control**: Keep your `defaults/core.yaml` in version control for consistency
5. **Testing**: Test core configuration changes in a development environment first

## Troubleshooting

### Username Issues

If SSH connections fail with "Permission denied":

1. **Check the username**: Verify the correct username is being used
2. **Check SSH keys**: Ensure SSH keys are properly configured
3. **Check user data scripts**: For AWS/Azure, verify user data scripts are creating the user
4. **Check firewall rules**: Ensure port 22 is open

### Configuration Loading Issues

If core configuration isn't loading:

1. **Check file path**: Ensure `defaults/core.yaml` exists
2. **Check permissions**: Ensure the file is readable
3. **Check syntax**: Verify YAML syntax is correct
4. **Check logs**: Use `--verbose` flag to see configuration loading details

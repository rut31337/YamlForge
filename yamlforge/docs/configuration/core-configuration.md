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
guid: "cor01"

yamlforge:
  cloud_workspace:
    name: "core-config-example-{guid}"
    description: "Core configuration example"
  
  instances:
    - name: "my-vm"
      provider: "aws"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east"
      # Will use cloud-user as default username
```

**Custom username**:
```yaml
guid: "cor02"

yamlforge:
  cloud_workspace:
    name: "custom-username-{guid}"
    description: "Custom username configuration example"
  
  core:
    security:
      default_username: "my-custom-user"
  instances:
    - name: "my-vm"
      provider: "aws"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east"
      # Will use my-custom-user as default username
```

**Per-instance override**:
```yaml
guid: "cor03"

yamlforge:
  cloud_workspace:
    name: "instance-username-{guid}"
    description: "Per-instance username override example"
  
  instances:
    - name: "my-vm"
      provider: "aws"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east"
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
  
  # Provider-specific discount percentages (0-100)
  # These discounts are applied to displayed costs and analysis
  # Can be overridden by environment variables: YAMLFORGE_DISCOUNT_<PROVIDER>
  provider_discounts:
    "aws": 10             # 10% enterprise agreement discount
    "azure": 20           # 20% EA discount  
    "gcp": 10             # 10% committed use discount
    "oci": 25             # 25% promotional discount
    "ibm_vpc": 18         # 18% corporate agreement
    "ibm_classic": 12     # 12% legacy infrastructure discount
    "alibaba": 30         # 30% APAC regional discount
    "vmware": 5           # 5% support contract discount
```

### Provider Discounts

Provider discounts allow organizations to reflect their actual pricing agreements with cloud providers in YamlForge's cost analysis and provider selection.

#### Configuration Methods

**1. Core Configuration (Organization-wide)**
```yaml
# defaults/core.yaml
cost_analysis:
  provider_discounts:
    "aws": 15             # 15% volume discount
    "azure": 25           # 25% enterprise agreement
    "gcp": 12             # 12% committed use discount
```

**2. Environment Variables (Override)**
```bash
# Environment variables take precedence over core configuration
export YAMLFORGE_DISCOUNT_AWS=20        # 20% AWS discount
export YAMLFORGE_DISCOUNT_AZURE=30      # 30% Azure discount
export YAMLFORGE_DISCOUNT_GCP=15        # 15% GCP discount
export YAMLFORGE_DISCOUNT_OCI=35        # 35% OCI discount
export YAMLFORGE_DISCOUNT_IBM_VPC=22    # 22% IBM VPC discount
export YAMLFORGE_DISCOUNT_IBM_CLASSIC=18 # 18% IBM Classic discount
export YAMLFORGE_DISCOUNT_ALIBABA=40    # 40% Alibaba discount
export YAMLFORGE_DISCOUNT_VMWARE=8      # 8% VMware discount
```

#### Features

- **Percentage-based**: Discounts are specified as percentages (0-100)
- **Environment precedence**: Environment variables override core configuration
- **Input validation**: Invalid values (non-numeric, out of range) show warnings and default to 0%
- **Cost integration**: Applied to all cost displays and cheapest provider selection
- **Clear display**: Shows both original and discounted prices

#### Cost Display Format

When discounts are applied, YamlForge shows both original and discounted costs:

```bash
Cost analysis for instance 'web-server-test1':
  aws: $0.0416/hour → $0.0312/hour (25.0% discount) (t3.medium, 2 vCPU, 4GB) ← SELECTED
  gcp: $0.0335/hour (e2-medium, 1 vCPU, 4GB)
  azure: $0.0752/hour (Standard_B4ms, 4 vCPU, 16GB)
```

#### Impact on Provider Selection

Discounts are applied **before** cheapest provider selection, ensuring accurate cost comparisons. A provider with a high list price but significant discount may become the cheapest option.

#### Use Cases

- **Enterprise Agreements**: Reflect negotiated discounts in cost analysis
- **Volume Pricing**: Account for usage-based discounts
- **Promotional Pricing**: Factor in temporary promotional rates
- **Contract Commitments**: Include committed use or reserved instance discounts
- **Regional Variations**: Apply region-specific pricing agreements

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

**Configuration in `defaults/core.yaml`:**
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
guid: "cor04"

yamlforge:
  cloud_workspace:
    name: "core-override-{guid}"
    description: "Core configuration override example"
  
  core:
    security:
      default_username: "my-custom-user"
  instances:
    - name: "my-vm"
      provider: "aws"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east"
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

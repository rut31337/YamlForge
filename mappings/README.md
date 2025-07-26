# Mappings Directory

This directory contains all the configuration files that define how YAML infrastructure specifications are mapped to native cloud provider resources. The mappings are organized into separate files for better maintainability and easier customization.

## Configuration Sources

### **Credentials vs Defaults**
- **Environment Variables** (`envvars.example.sh`): Authentication and API access configuration via environment variables
- **Defaults** (`defaults/{provider}.yaml`): Essential provider-specific mappings and settings (always used)

### **GCP Image Discovery**
- **Primary**: Environment variables with GCP SDK authentication
- **Fallback**: Built-in image discovery settings
- **Benefits**: Always-available image resolution with minimal dependencies

### **AWS AMI Resolution**
- **Configuration**: `defaults/aws.yaml` with AMI owner mappings (always loaded)
- **API Access**: Environment variables for dynamic AWS API calls
- **Benefits**: Flexible owner configuration with secure credential management

## Directory Structure

```
mappings/
├── cloud_patterns.yaml # Cloud provider patterns and defaults
├── flavors/             # Instance type mappings per cloud provider
│   ├── aws.yaml        # AWS EC2 instance types (t3.micro, m5.large, etc.)
│   ├── azure.yaml      # Azure VM sizes (Standard_B1s, Standard_D4s_v3, etc.)
│   ├── gcp.yaml        # GCP machine types (e2-micro, n1-standard-2, etc.)
│   ├── ibm_vpc.yaml    # IBM Cloud VPC profiles (bx2-4x16, cx2-8x16, etc.)
│   ├── ibm_classic.yaml # IBM Classic instance types (B1.4x8x100, C1.8x8x25, etc.)
│   └── generic.yaml    # Cloud-agnostic size mappings (all providers)
├── images.yaml         # Operating system image mappings
├── locations.yaml      # Cloud region mappings

└── README.md          # This file
```

## File Descriptions

### `cloud_patterns.yaml`
Contains cloud provider patterns, defaults, and general configuration settings.

### `flavors/`
Contains advanced instance type mappings with multiple options per size category and cost optimization:

- **generic.yaml**: Simple cross-cloud instance size mappings (nano, micro, small, medium, etc.) for basic compatibility
- **aws.yaml**: Advanced AWS EC2 instance type mappings with multiple options per size, including vCPU, memory, and cost factors
- **azure.yaml**: Advanced Azure VM size mappings with multiple options per category, including specifications and cost factors  
- **gcp.yaml**: Advanced GCP machine type mappings with multiple options per size, including performance and cost characteristics
- **ibm_vpc.yaml**: Advanced IBM Cloud VPC instance profile mappings (bx2-, cx2-, mx2-) for modern VPC infrastructure
- **ibm_classic.yaml**: IBM Cloud Classic Infrastructure instance types (B1., C1., M1.) for classic infrastructure

**Advanced Flavor System:**
Each cloud-specific flavor file provides multiple instance options per size category (e.g., small, medium, large), allowing the system to select the most appropriate instance type based on workload requirements and cost considerations. Each option includes:
- vCPU count and memory specifications
- Cost factor for budget optimization
- Hourly cost in USD for accurate budget planning
- Performance characteristics for workload matching

### `images.yaml`
Maps operating system image references to cloud-specific AMI IDs, image names, or URNs.

**Owner ID Behavior:**
- If `owner` is **not specified** for an AWS image, the appropriate default owner is determined automatically based on image type (from `defaults/aws.yaml`)
- If `owner` **is specified** for an AWS image, that exact owner ID is used (allows for custom/private AMIs)
- This enables both standardized defaults and custom overrides

**AWS Filters for GOLD Images:**
- AWS GOLD images (Cloud Access) automatically get `is-public=false` filter applied during AMI resolution
- This ensures GOLD images are correctly identified as private Red Hat Cloud Access images  
- No need to specify `aws_filters` with `is-public=false` for GOLD images - it's automatic
- Other custom filters can still be  if needed and will be merged with the automatic filter

**RHEL Pattern-Based Images:**
- Any RHEL version can use automatic pattern generation if not explicitly mapped
- Explicit mappings in images.yaml take priority, then fallback to pattern generation
- Pattern examples: `RHEL-8-GOLD-latest` → `RHEL-8.*_HVM_*Access*`, `RHEL-10.1-GOLD-latest` → `RHEL-10.1.*_HVM_*Access*`
- Supports both major (`RHEL-8-GOLD-latest`) and major.minor (`RHEL-9.4-GOLD-latest`) versions
- Works for both GOLD and public images across all RHEL versions
- Existing RHEL 9 and older mappings remain for backwards compatibility
- System will provide clear error messages if the requested AMI version doesn't exist yet

### `locations.yaml`
Maps cloud-specific region names to standardized location format for cross-cloud deployments.

## Usage

The yamlforge converter loads all these files automatically when using the default `mappings` directory:

```bash
# Use default mappings
python3 yamlforge.py input.yaml

# Use custom mappings directory
python3 yamlforge.py input.yaml --mappings /path/to/custom/mappings
```

## Customization

### Adding  Cloud Providers

1. Create a  flavor file: `flavors/cloud.yaml`
2. Add image mappings in `images.yaml`
3. Add location mappings in `locations.yaml`
4. Update `cloud_patterns.yaml` with provider defaults

### Adding  Instance Types

Edit the appropriate cloud flavor file:

```yaml
# flavors/aws.yaml
small:
  instance_type: "t3.small"
  cores: 2
  memory: 2048
  
# Add  instance type
custom_compute:
  instance_type: "c5.4xlarge"
  cores: 16
  memory: 32768
```

### Adding  Images

Add entries to `images.yaml`:

```yaml
# Uses default owner from defaults/aws.yaml (automatically determined)
Custom-RHEL9:
  description: "Custom RHEL 9 build"
  aws:
    name_pattern: "custom-rhel-9-*"
    # No owner specified - will use redhat_public from defaults

# Uses custom owner (e.g., private AMI from your account)  
CUSTOM_IMAGE:
  aws:
    name_pattern: "custom-image-*"
    owner: "123456789012"    # Custom owner not in defaults
    architecture: "x86_64"
  azure:
    publisher: "CustomPublisher"
    offer: "CustomOffer"
    sku: "custom-sku"
    version: "latest"

# GOLD image - automatically gets is-public=false filter  
Custom-RHEL9-GOLD:
  description: "Custom RHEL 9 Gold build"
  aws:
    name_pattern: "custom-rhel-9-gold-*"
    # No owner specified - uses redhat_gold from defaults
    # No aws_filters needed - automatically gets is-public=false

# Special case requiring owner override (like RHEL AI)
RHELAI12:
  description: "RHEL AI 1.2 - requires special owner"
  aws:
    name_pattern: "rhel-ai-nvidia-1.2*"
    owner: "809721187735"  # Special owner not in defaults
    aws_filters:
      - name: "is-public"
        values: ["false"]

# RHEL 10+ pattern-based examples (no explicit mapping needed)
# These work automatically:
# RHEL-10-GOLD-latest       → RHEL-10.*_HVM_*Access*
# RHEL-10.0-GOLD-latest     → RHEL-10.0.*_HVM_*Access*
# RHEL-10.1-GOLD-latest     → RHEL-10.1.*_HVM_*Access*
# RHEL-10-latest             → RHEL-10.*
# RHEL-11-GOLD-latest       → RHEL-11.*_HVM_*Access* (future)
```

### Adding  Regions

Add entries to `locations.yaml`:

```yaml
#  AWS region
custom-region-1:
  aws: "us-custom-1"
  azure: "Custom Region"
  gcp: "us-custom1"
```

## Cloud-Specific vs Generic Flavors

The system supports both cloud-specific and generic flavors:

### Cloud-Specific Flavors
```yaml
# Instance using AWS-specific flavor
- name: "aws-instance"
  provider: "aws"
  flavor: "t3.medium"  # AWS instance type
```

### Generic Flavors
```yaml
# Instance using generic flavor (mapped to cloud-specific)
- name: "generic-instance"  
  provider: "aws"
  flavor: "medium"  # Maps to appropriate AWS instance type
```

This enables automatic detection of cloud-specific flavors for native deployment vs generic flavors for cross-cloud compatibility.

## Loading Custom Mappings

You can override default mappings by specifying a custom mappings directory:

```bash
# Use custom mappings
python3 yamlforge.py input.yaml --mappings custom_mappings
```

### Custom Mappings Directory Structure
```
custom_mappings/
├── flavors/
│   ├── aws.yaml             # Standard AWS instance types
│   ├── azure.yaml           # Standard Azure VM sizes
│   ├── gcp.yaml             # Standard GCP machine types
│   ├── oci.yaml             # Standard OCI compute shapes
│   ├── ibm_vpc.yaml         # Standard IBM VPC instances
│   ├── ibm_classic.yaml     # Standard IBM Classic instances
│   ├── vmware.yaml          # Standard VMware VM configurations
│   ├── alibaba.yaml         # Standard Alibaba Cloud instances
│   └── generic.yaml         # Generic size mappings
├── flavors_openshift/
│   ├── openshift_aws.yaml   # OpenShift-optimized AWS instances
│   ├── openshift_azure.yaml # OpenShift-optimized Azure VMs
│   ├── openshift_gcp.yaml   # OpenShift-optimized GCP machines
│   ├── openshift_oci.yaml   # OpenShift-optimized OCI shapes
│   ├── openshift_ibm_vpc.yaml # OpenShift-optimized IBM VPC instances
│   ├── openshift_ibm_classic.yaml # OpenShift-optimized IBM Classic instances
│   ├── openshift_vmware.yaml # OpenShift-optimized VMware VMs
│   ├── openshift_alibaba.yaml # OpenShift-optimized Alibaba instances
│   └── openshift_generic.yaml # Generic OpenShift configurations
├── images.yaml              # Custom image mappings
└── locations.yaml           # Custom region mappings
```

### OpenShift-Specific Flavors

The `openshift_*` flavor files provide OpenShift-optimized machine configurations with proper sizing for control plane and worker nodes. These configurations are automatically loaded and used by the OpenShift provider instead of hardcoded values.

#### Available OpenShift Flavor Files (in `mappings/flavors_openshift/`)
- `openshift_aws.yaml` - AWS EC2 instances optimized for OpenShift clusters
- `openshift_azure.yaml` - Azure VM sizes optimized for OpenShift clusters  
- `openshift_gcp.yaml` - GCP machine types optimized for OpenShift clusters
- `openshift_oci.yaml` - OCI compute shapes optimized for OpenShift clusters
- `openshift_ibm_vpc.yaml` - IBM VPC instance types optimized for OpenShift clusters
- `openshift_ibm_classic.yaml` - IBM Classic bare metal instances optimized for OpenShift clusters
- `openshift_vmware.yaml` - VMware vSphere VM configurations optimized for OpenShift clusters
- `openshift_alibaba.yaml` - Alibaba Cloud ECS instance types optimized for OpenShift clusters
- `openshift_generic.yaml` - Generic configurations for unsupported providers

#### Structure Example
```yaml
# Example: openshift_aws.yaml
flavor_mappings:
  master_medium:
    m5.xlarge:
      vcpus: 4
      memory_gb: 16
      cost_factor: 2.0
      use_case: "Production control plane"
      
  worker_large:
    m5.4xlarge:
      vcpus: 16
      memory_gb: 64
      cost_factor: 8.0
      use_case: "Heavy production workloads"
      
size_mappings:
  small: "worker_small"
  medium: "worker_medium"
  large: "worker_large"
  
cluster_sizes:
  micro:
    master_count: 1
    master_size: "master_small"
    worker_count: 1
    worker_size: "worker_micro"
    use_case: "Development/Testing - single node"
    
  medium:
    master_count: 3
    master_size: "master_medium" 
    worker_count: 3
    worker_size: "worker_medium"
    use_case: "Standard production workloads"
```

#### How It Works
1. **OpenShift provider automatically detects cluster type** (rosa, aro, self-managed)
2. **Loads appropriate OpenShift-specific flavor file** (e.g., `openshift_aws` for ROSA)
3. **Uses cluster_sizes configurations** instead of hardcoded values
4. **Maps abstract sizes to cloud-specific machine types** via size_mappings
5. **Falls back to generic configurations** if cloud-specific file unavailable

#### Benefits
- **No hardcoded machine types** in Python code
- **OpenShift-optimized sizing** for better performance
- **Easy customization** by editing YAML files
- **Cost transparency** with documented cost factors
- **Cloud-agnostic abstractions** with provider-specific implementations
- **Organized structure** with dedicated OpenShift directory
- **Clear separation** between standard and OpenShift-optimized configurations

## File Format Examples

### Flavor File (`flavors/aws.yaml`)
```yaml
# AWS EC2 Instance Types
micro:
  instance_type: "t3.micro"
  cores: 1
  memory: 1024

small:
  instance_type: "t3.small"
  cores: 2
  memory: 2048

medium:
  instance_type: "t3.medium"
  cores: 2
  memory: 4096
```

### Image File (`images.yaml`)
```yaml
RHEL_9_LATEST:
  aws:
    name_pattern: "RHEL-9*"
    owner: "309956199498"
    architecture: "x86_64"
  azure:
    publisher: "RedHat"
    offer: "RHEL"
    sku: "9-lvm-gen2"
    version: "latest"
```

### Location File (`locations.yaml`)
```yaml
us-east-1:
  aws: "us-east-1"
  azure: "East US"
  gcp: "us-east1"
  ibm: "us-south"
```

## Advanced Flavor System Usage

The advanced flavor system automatically selects the best instance type for each cloud provider based on your specified size category:

### Using the Cheapest Provider (Cost Optimization)
```yaml
instances:
  - name: "cost-optimized-web"
    provider: "cheapest"
    size: "medium"        # Automatically finds cheapest medium instance across ALL clouds
    image: "RHEL9-latest"

  - name: "budget-database"
    provider: "cheapest"
    cores: 4              # Finds cheapest instance with ≥4 cores, ≥8GB RAM
    memory: 8192
    image: "RHEL9-latest"

  - name: "efficient-compute"
    provider: "cheapest"
    size: "compute_large" # Finds cheapest compute-optimized instance across all providers
    image: "RHEL9-latest"
```

**How Cheapest Provider Works:**
1. Compares hourly costs from all cloud provider flavor mappings
2. Considers resource efficiency (CPU/memory utilization) 
3. Automatically selects the lowest-cost option
4. Provides transparent cost comparison output
5. Deploys to the actually cheapest cloud (AWS, Azure, GCP, or IBM)

### Using Abstract Sizes
```yaml
instances:
  - name: "web-server"
    provider: "aws"
    size: "medium"        # Automatically maps to best AWS instance for medium workloads
    image: "RHEL9-latest"

  - name: "database" 
    provider: "azure"
    size: "memory_large"  # Automatically maps to best Azure memory-optimized VM
    image: "RHEL9-latest"

  - name: "compute-node"
    provider: "gcp"
    size: "compute_large" # Automatically maps to best GCP compute-optimized instance
```

### Using Cloud-Specific Instance Types
```yaml
instances:
  - name: "specific-aws"
    provider: "aws"
    flavor: "m5.2xlarge"     # Direct AWS instance type
    image: "RHEL9-latest"

  - name: "specific-azure"
    provider: "azure" 
    flavor: "Standard_D8s_v3" # Direct Azure VM size
    image: "RHEL9-latest"
```

### Available Size Categories
- **Basic**: `nano`, `micro`, `small`, `medium`, `large`, `xlarge`, `2xlarge`
- **Optimized**: `compute_large`, `memory_large`, `general_*`
- **Cloud-specific**: Additional categories available per provider

### Cost Optimization
The system automatically selects cost-effective options within each size category based on cost factors and hourly pricing. Each instance type includes:
- **Cost Factor**: Relative cost comparison within the cloud provider (0.1 = very low cost, 3.0 = high cost)
- **Hourly Cost**: Actual USD hourly rate based on current cloud provider pricing
- **Automatic Selection**: First option in each size category represents the best cost/performance balance

For custom cost optimization, specify exact instance types using the `flavor` parameter or review the hourly costs in the flavor mapping files.

## Best Practices

1. **Consistent Naming**: Use consistent flavor names across cloud providers
2. **Resource Planning**: Ensure mapped instance types have similar compute resources
3. **Cost Optimization**: Include cost-effective options in generic mappings
4. **Architecture Support**: Consider x86_64 and ARM64 architecture mappings
5. **Regional Availability**: Verify instance types are available in target regions

## Troubleshooting

### Unknown Flavor Warning
```
Warning: Unknown flavor 'custom_flavor', falling back to CPU/memory specs
```
**Solution**: Add the flavor to the appropriate cloud flavor file.

### Missing Image Warning  
```
Warning: Image 'CUSTOM_IMAGE' not found for cloud 'aws'
```
**Solution**: Add the image mapping to `images.yaml`.

### Invalid Region Warning
```
Warning: Region 'invalid-region' not found for cloud 'aws'
```
**Solution**: Add the region mapping to `locations.yaml` or use a valid region.

---

**Part of yamlforge** - Native multi-cloud infrastructure automation 
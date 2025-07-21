# YamlForge - Multi-Cloud Infrastructure as Code and PaaS Management Suite

> **⚠️ ALPHA SOFTWARE WARNING ⚠️**  
> **This is v0.99 ALPHA - Work in Progress**  
> **This software may not work as expected and could break at any time.**  
> **Use at your own risk. Not recommended for production environments.**  
> **Features are experimental and subject to major changes.**

A comprehensive enterprise-grade platform for managing multi-cloud infrastructure and Platform-as-a-Service deployments through unified YAML definitions, supporting AWS, Azure, GCP, IBM Cloud, Oracle Cloud, Alibaba Cloud, VMware, and advanced OpenShift/Kubernetes PaaS management.

## 🚀 Features

### **Native Multi-Cloud Support**
- **AWS**: Native EC2, VPC, Security Groups, and AMI discovery
- **Azure**: Native Virtual Machines, VNets, Network Security Groups, and BYOS images  
- **GCP**: Native Compute Engine with dynamic gold image discovery via Cloud API
- **IBM Cloud**: Native VPC Gen 2 and Classic Infrastructure support with advanced instance profiles

### **Enterprise Features**
- **Smart Provider Detection** - Only configures Terraform providers actually used in your configuration for clean, efficient output
- **Cloud-Agnostic Workspace Organization** - Unified workspace organization across all clouds (Azure Resource Groups, GCP Projects, IBM Resource Groups, AWS organization)
- **Cheapest Provider Auto-Selection** - "cheapest" meta-provider automatically finds lowest-cost option across all clouds
- **Automatic Flavor Discovery** - Specify exact hardware requirements and get recommended generic flavors automatically
- **Comprehensive Tagging System** - Unified tagging with cloud-specific format handling (key-value, single-value with colons)
- **Dynamic GCP Image Discovery** - Automatically finds latest Red Hat Cloud Access images via Google Cloud API
- **Red Hat Cloud Access Gold Images** - Full support for BYOS across all cloud providers
- **Unified Security Groups** - Define once, use anywhere across instances
- **Unified Subnets** - Define subnets once, reference by name across instances
- **Multi-AZ Support** - Subnets across multiple availability zones
- **User Data Scripts** - Cloud-init support across all providers

### **Red Hat Ecosystem Integration**
- **RHEL AI support** with optimized image patterns  
- **Red Hat Cloud Access compliance** with proper BYOS image mapping
- **agnosticd naming compliance** following enterprise best practices
- **Architecture detection** for x86_64 and ARM64 deployments

## 🔴 Alpha Status & Disclaimer

**YamlForge v0.99 is ALPHA SOFTWARE** - This means:

- ❌ **Not Production Ready** - Do not use in production environments
- ⚠️ **Breaking Changes Expected** - APIs, configs, and features may change drastically
- 🐛 **Bugs & Issues** - Expect functionality to be incomplete or broken
- 📚 **Limited Documentation** - Many features may be undocumented or poorly documented
- 🧪 **Experimental Features** - Core functionality is still being developed and tested
- 💥 **No Stability Guarantees** - Updates may completely break existing configurations

### What This Means for You:
- Use only for **testing, development, and experimentation**
- Always **backup your work** before updating
- **Contribute feedback** but don't expect immediate fixes
- **Monitor the repository** for major changes and updates
- **Test thoroughly** in safe environments before any real usage

### Getting Support:
- Issues and bugs are **expected** in alpha software
- Create GitHub issues for problems, but expect limited support
- Contributions and pull requests are welcome
- Join discussions to help shape the final product

## 🎯 Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd yamlforge

# Install dependencies
pip install -r requirements.txt

# For GCP dynamic image discovery (optional)
pip install google-cloud-compute>=1.14.0
```

### Basic Usage

```bash
# Generate native multi-cloud Terraform (default)
python yamlforge.py infrastructure.yaml

# Output to file
python yamlforge.py infrastructure.yaml -o terraform/main.tf
```

## 📁 Examples Directory

Get started quickly by using the comprehensive example configurations in the `examples/` directory:

### **Available Examples**

| Example File | Description | Use Case |
|--------------|-------------|----------|
| `architecture_example.yaml` | Simple single-cloud deployment | Learning basics |
| `gcp_example.yaml` | GCP-specific configuration | GCP deployments |
| `hybrid_rhel_deployment.yaml` | Multi-cloud RHEL deployment | Enterprise hybrid cloud |
| `cheapest_provider_example.yaml` | Automatic cost optimization | Cost-conscious deployments |
| `cloud_access_test.yaml` | Red Hat Cloud Access testing | RHEL Gold images |
| `gcp_dynamic_example.yaml` | Dynamic GCP image discovery | Latest RHEL images |
| `security_groups_example.yaml` | Security group configurations | Network security |
| `subnets_example.yaml` | Advanced subnet management | Network architecture |
| `region_specification_example.yaml` | Multi-region deployment | Geographic distribution |

### **Quick Start with Examples**

```bash
# Copy and customize an example
cp examples/architecture_example.yaml my-infrastructure.yaml

# Generate Terraform from example
python yamlforge.py examples/gcp_example.yaml -o gcp-infrastructure.tf

# Test multi-cloud configuration
python yamlforge.py examples/hybrid_rhel_deployment.yaml
```

### **Example Categories**

**🏗️ Architecture Examples:**
- Basic single-cloud setups
- Multi-cloud hybrid deployments
- Region and zone specifications

**🔒 Security Examples:**
- Security group configurations
- Network access control
- RHEL Gold image deployments

**🌐 Network Examples:**
- VPC/VNet configurations  
- Subnet management
- Multi-availability zone setups

**☁️ Provider-Specific Examples:**
- GCP dynamic image discovery
- IBM Classic vs VPC
- Azure BYOS configurations

## ⚡ Smart Provider Detection

YamlForge intelligently analyzes your configuration and includes only the Terraform providers you actually need, resulting in cleaner, faster, and more efficient Terraform code.

### **How It Works**

Instead of blindly including all possible cloud providers, yamlforge scans your configuration and detects which providers are actually being used:

#### **Single Cloud Detection**
```yaml
# Only AWS instances defined
instances:
  - name: "web-server"
    provider: "aws"
    size: "medium"
    image: "RHEL9-latest"
```

**Generated Terraform includes ONLY:**
```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}
```

#### **Multi-Cloud Detection**
```yaml
# AWS + GCP instances defined
instances:
  - name: "aws-server"
    provider: "aws"
    size: "medium"
    image: "RHEL9-latest"
    
  - name: "gcp-server"
    provider: "gcp" 
    size: "medium"
    image: "RHEL9-latest"
```

**Generated Terraform includes ONLY AWS and GCP:**
```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# Variables for AWS and GCP only (no Azure or IBM variables)
```

### **Benefits**

#### **🚀 Performance**
- **Faster `terraform init`** - fewer providers to download
- **Quicker planning** - no unused provider configurations
- **Reduced complexity** - only necessary providers loaded

#### **🧹 Clean Output** 
- **No unused providers** in `required_providers` block
- **No unnecessary variables** for unused clouds
- **Minimal configuration** focused on your actual needs

#### **💰 Cost Efficiency**
- **No accidental resource creation** in unused clouds
- **Clear cost attribution** - only configured providers can incur costs
- **Simpler billing** - fewer cloud accounts to manage

#### **🔒 Security**
- **Reduced attack surface** - fewer provider credentials needed
- **Principle of least privilege** - only necessary cloud access
- **Simplified credential management** - fewer secrets to maintain

### **Supported Scenarios**

#### **Development vs Production**
```yaml
# Development (single cloud for cost)
instances:
  - provider: "aws"  # Only AWS configured

# Production (multi-cloud for resilience) 
instances:
  - provider: "aws"     # AWS + Azure + GCP
  - provider: "azure"   # configured automatically
  - provider: "gcp"
```

#### **Cost Optimization**
```yaml
# Let cheapest provider decide, but only configure what's selected
instances:
  - provider: "cheapest"  # May resolve to any provider
                         # Only selected provider gets configured
```

#### **Migration Scenarios**
```yaml
# Start with one cloud
instances:
  - provider: "aws"

# Add second cloud incrementally  
instances:
  - provider: "aws"    # Terraform automatically includes
  - provider: "gcp"    # both providers now
```

### **Examples**

- `testing/provider_selection_example.yaml` - AWS-only configuration
- `testing/multi_provider_example.yaml` - AWS + GCP + IBM detection
- `cost-conscious/cheapest_provider_example.yaml` - Dynamic provider selection

## 🏷️ Comprehensive Tagging System

YamlForge provides a unified tagging system that handles the differences between cloud provider tagging formats automatically, ensuring consistent resource organization and automation support across all clouds.

### **Universal Tag Support**

#### **Key Features**
- **Project-level tags** applied to all instances
- **Instance-level tags** for specific resource tagging  
- **Automatic format conversion** for each cloud provider
- **Common automation tags** (`guid`, `ansible_group`)
- **Compliance and governance** support

#### **Cloud Provider Handling**

| Provider | Format | Conversion |
|----------|--------|------------|
| **AWS** | Key-value pairs | `key = "value"` |
| **Azure** | Key-value pairs | `key = "value"` (spaces → underscores) |
| **GCP** | Labels + Network tags | Labels: `key = "value"` (lowercase, hyphens)<br/>Network: `["key:value"]` (colon delimiter) |
| **IBM Cloud** | Key-value pairs | `"key" = "value"` |

### **Usage Examples**

#### **Global Project Tags**
```yaml
yamlforge:
  cloud_workspace:
    name: "production-app"
    description: "Production application workspace"

  # Applied to ALL instances
  tags:
    guid: "abc123-def456-ghi789"
    ansible_group: "web_servers"
    environment: "production"
    owner: "devops-team"
    cost_center: "engineering"

  instances:
    - name: "web-server"
      provider: "aws"
      size: "medium"
      image: "RHEL9-latest"
```

#### **Instance-Specific Tags**
```yaml
instances:
  - name: "database-server"
    provider: "azure"
    size: "large"
    image: "RHEL9-latest"
    tags:
      role: "database"
      backup_policy: "daily"
      data_classification: "sensitive"
      ssl_enabled: "true"
```

#### **Mixed Global + Instance Tags**
```yaml
# Global tags for all instances
tags:
  guid: "project-abc-123"
  ansible_group: "production_cluster"
  environment: "production"

instances:
  - name: "web-tier"
    provider: "gcp"
    size: "medium"
    image: "RHEL9-latest"
    tags:
      role: "web_server"      # Instance-specific
      tier: "frontend"        # Instance-specific
      # Inherits: guid, ansible_group, environment

  - name: "app-tier"  
    provider: "cheapest"
    size: "large"
    image: "RHEL9-latest"
    tags:
      role: "app_server"      # Instance-specific
      tier: "middleware"      # Instance-specific
      # Inherits: guid, ansible_group, environment
```

### **Generated Output Examples**

#### **AWS Tags**
```hcl
tags = {
  Name                = "web-server"
  Environment         = "agnosticd"
  ManagedBy          = "yamlforge"
  guid               = "abc123-def456-ghi789"
  ansible_group      = "web_servers"
  role               = "web_server"
  backup_policy      = "daily"
}
```

#### **Azure Tags**
```hcl
tags = {
  Name                = "web-server"
  Environment         = "agnosticd"
  ManagedBy          = "yamlforge"
  guid               = "abc123-def456-ghi789"
  ansible_group      = "web_servers"
  role               = "web_server"
  backup_policy      = "daily"
}
```

#### **GCP Labels + Network Tags**
```hcl
# Resource labels (key-value)
labels = {
  name                = "web-server"
  environment         = "agnosticd"
  managed-by         = "yamlforge"
  guid               = "abc123-def456-ghi789"
  ansible-group      = "web-servers"
  role               = "web-server"
  backup-policy      = "daily"
}

# Network tags (single values with colons)
tags = [
  "guid:abc123-def456-ghi789",
  "ansible-group:web-servers", 
  "role:web-server",
  "backup-policy:daily"
]
```

#### **IBM Cloud Tags**
```hcl
tags = {
  "Name"             = "web-server"
  "Environment"      = "agnosticd"
  "ManagedBy"       = "yamlforge"
  "guid"            = "abc123-def456-ghi789"
  "ansible_group"   = "web_servers"
  "role"            = "web_server"
  "backup_policy"   = "daily"
}
```

### **Automation Integration**

#### **Ansible Inventory Integration**
The `ansible_group` tag automatically groups instances for Ansible automation:

```yaml
tags:
  ansible_group: "web_servers"    # Groups instances for Ansible
  guid: "deployment-123"          # Unique deployment identifier
```

#### **Common Tag Patterns**
```yaml
# Governance tags
tags:
  owner: "devops-team"
  cost_center: "engineering"
  project: "customer-portal"
  
# Operational tags  
tags:
  environment: "production"
  tier: "frontend"
  role: "web_server"
  
# Compliance tags
tags:
  data_classification: "sensitive"
  backup_policy: "daily"
  monitoring: "enabled"
  
# Automation tags
tags:
  ansible_group: "web_servers"
  scaling_group: "auto"
  deployment_id: "deploy-456"
```

### **Best Practices**

#### **Naming Conventions**
- Use **lowercase** with **underscores** for consistency
- Avoid spaces (automatically converted per cloud provider)
- Use **descriptive values** for automation scripts

#### **Required Tags**
Consider standardizing these tags across your organization:
```yaml
tags:
  guid: "<unique-deployment-id>"     # Required: Unique deployment identifier
  ansible_group: "<group-name>"      # Required: Ansible automation grouping
  environment: "<env-name>"          # Recommended: Environment classification
  owner: "<team-name>"               # Recommended: Responsible team
  cost_center: "<cost-center>"       # Optional: Cost allocation
```

#### **Tag Inheritance**
- **Project tags** are applied to ALL instances
- **Instance tags** are added to individual instances  
- **Instance tags override** project tags with same key
- **Base tags** (Name, Environment, ManagedBy) are always included

### **Cloud-Specific Considerations**

#### **AWS**
- Supports unlimited key-value tags
- Case-sensitive keys and values
- Used for cost allocation and resource grouping

#### **Azure**
- Key names cannot contain spaces (converted to underscores)
- Used for cost management and resource organization
- Applied to all resource types

#### **GCP**
- **Labels**: Key-value pairs for resource organization (lowercase, hyphens)
- **Network Tags**: Single values for firewall targeting (colon-delimited)
- Both formats generated automatically

#### **IBM Cloud**
- Supports key-value pairs with quoted keys
- Used for resource grouping and billing
- Applied across both Classic and VPC infrastructure

## 💰 Cheapest Provider Auto-Selection

The **"cheapest"** meta-provider automatically finds the lowest-cost instance across AWS, Azure, GCP, and IBM Cloud, providing significant cost savings without vendor lock-in.

### **How It Works**

1. **Specify Requirements**: Use either generic size (`medium`) or exact specs (`cores: 4, memory: 8192`)
2. **Automatic Cost Comparison**: System compares hourly costs across all cloud providers
3. **Real-Time Selection**: Automatically deploys to the cheapest option
4. **Transparent Output**: Shows cost comparison and selection reasoning

### **Usage Examples**

#### **Generic Size Specification**
```yaml
instances:
  - name: "web-server"
    provider: "cheapest"
    size: "medium"              # Finds cheapest medium instance
    image: "RHEL9-latest"
    location: "us-east-1"
```

#### **Exact CPU/Memory Requirements**
```yaml
instances:
  - name: "database"
    provider: "cheapest"
    cores: 8                    # 8 vCPUs required
    memory: 16384               # 16GB RAM required (in MB)
    image: "RHEL9-latest"
    location: "us-east-1"
```

#### **Workload-Optimized Selection**
```yaml
instances:
  - name: "analytics"
    provider: "cheapest"
    size: "memory_large"        # Cheapest memory-optimized instance
    image: "RHEL9-latest"
    
  - name: "compute-worker"
    provider: "cheapest"
    size: "compute_large"       # Cheapest compute-optimized instance
    image: "RHEL9-latest"
```

### **Sample Output**

```
🎯 Resolving cheapest provider for instance 'web-server'...
🔍 Finding cheapest option for size 'medium' with auto cores, auto memory...
💰 Cheapest option: gcp e2-medium ($0.0335/hour, 1 vCPU, 4GB RAM)
📊 Cost comparison (top 3):
  1. gcp: e2-medium - $0.0335/hour (1 vCPU, 4GB)
  2. azure: Standard_B2ms - $0.0376/hour (2 vCPU, 8GB)
  3. aws: t3.medium - $0.0416/hour (2 vCPU, 4GB)
```

### **Key Benefits**

- **🏆 Maximum Cost Savings**: Automatically finds lowest-cost option across all clouds
- **🚀 No Vendor Lock-in**: Deploy to actually cheapest provider, not predetermined choice  
- **📊 Transparent Pricing**: See real hourly costs and comparison before deployment
- **🎯 Intelligent Matching**: Considers both cost and resource efficiency
- **🔄 Multi-Cloud by Default**: Different instances can land on different optimal providers
- **⚡ Real-Time Optimization**: Uses current pricing data from all flavor mappings

### **Requirements**

- Must specify **either** `size` (generic) **or** `cores` + `memory` (exact)
- Supported sizes: `micro`, `small`, `medium`, `large`, `xlarge`, `2xlarge`, `memory_large`, `compute_large`
- Memory specified in MB (e.g., `memory: 8192` for 8GB)
- All other instance features work normally (security groups, user data, etc.)

## 🎮 GPU Instance Support

### **Comprehensive GPU Support**

YamlForge provides **complete GPU support** across all cloud providers with intelligent cost optimization for AI/ML workloads.

### **GPU Type-Specific Flavors**

#### **Generic GPU Sizes**
```yaml
instances:
  - name: "ml-dev"
    provider: "aws"
    size: "gpu_small"          # Cross-cloud GPU flavor
    
  - name: "ai-training"  
    provider: "azure"
    size: "gpu_large"          # Maps to best GPU instance
```

#### **GPU Type-Specific Flavors**
```yaml
instances:
  # NVIDIA T4 (Entry-level AI/ML)
  - name: "dev-workstation"
    provider: "gcp" 
    size: "gpu_t4_small"       # Specific T4 instance
    
  # NVIDIA V100 (High-performance training)
  - name: "training-cluster"
    provider: "aws"
    size: "gpu_v100_large"     # Specific V100 instance
    
  # NVIDIA A100 (State-of-the-art AI)
  - name: "research-node"
    provider: "azure"
    size: "gpu_a100_xlarge"    # Specific A100 instance
    
  # AMD Radeon Pro (Cost-effective alternative)
  - name: "budget-compute"
    provider: "aws"
    size: "gpu_amd_medium"     # AMD GPU instance
```

### **GPU-Aware Cost Optimization**

#### **Hardware + GPU Requirements**
```yaml
instances:
  - name: "custom-training"
    provider: "cheapest"       # Finds cheapest GPU option
    cores: 8
    memory: 32768             # 32GB RAM
    gpu_count: 1              # Requires 1 GPU
    region: "us-east-1"
```

## 🎯 Automatic Flavor Discovery

### **Find Closest Matching Flavor**

Don't know which flavor to use? Specify your exact hardware requirements and let the system **automatically recommend** the closest matching generic flavor!

#### **How It Works**
```yaml
instances:
  - name: "auto-discovery"
    provider: "cheapest"
    cores: 8                  # Your CPU requirement
    memory: 32768            # Your memory requirement (32GB)
    gpu_count: 1             # Optional: GPU requirement
    gpu_type: "NVIDIA T4"    # Optional: Specific GPU type
    find_flavor: true        # 🆕 Enable automatic flavor discovery
    region: "us-east-1"
```

**Output:**
```bash
📋 Auto-matched flavor for 8 cores, 32.0GB RAM, 1 NVIDIA T4 GPU(s):
  🎯 Recommended flavor: gpu_medium
  📊 Avg specs: 10.0 vCPUs, 61.5GB RAM, 1.0 GPUs (NVIDIA T4, NVIDIA L4)
  ✅ Available on: aws, azure, gcp, ibm_vpc

Cost analysis for size 'gpu_medium':
  aws: $0.752/hour (g4dn.2xlarge, 8 vCPU, 32GB, 1x NVIDIA T4) ← SELECTED
```

### **Intelligent Matching Examples**

#### **1. Simple Compute Workload**
```yaml
# Request: 2 cores, 8GB RAM
find_flavor: true
# Result: Recommends 'medium' flavor
# Avg specs: 2.3 vCPUs, 8.0GB RAM
```

#### **2. Memory-Intensive Workload**
```yaml
# Request: 4 cores, 32GB RAM  
find_flavor: true
# Result: Recommends 'memory_xlarge' flavor
# Avg specs: 6.7 vCPUs, 49.3GB RAM
```

#### **3. GPU Workload**
```yaml
# Request: 8 cores, 32GB RAM, 1 GPU
find_flavor: true
# Result: Recommends 'gpu_medium' flavor
# Avg specs: 10.0 vCPUs, 61.5GB RAM, 1.0 GPUs
```

#### **4. High-End AI Training**
```yaml
# Request: 32 cores, 128GB RAM, 2 A100 GPUs
find_flavor: true  
# Result: Recommends 'gpu_a100_large' flavor
# Provides A100-specific optimization
```

### **Benefits of Automatic Discovery**

- **🎯 Perfect Matches**: Finds the most efficient flavor for your exact needs
- **📚 Learn Standard Flavors**: Get reusable flavor names for future deployments  
- **💰 Cost Optimization**: Still uses cheapest provider logic with recommended flavor
- **🔧 Avoid Over-Provisioning**: Minimizes resource waste through intelligent matching
- **🌐 Multi-Cloud Compatibility**: Shows which providers support the recommended flavor
- **🎮 GPU Intelligence**: Prefers non-GPU flavors unless GPU explicitly requested
- **📊 Transparent Analysis**: See exact specs comparison and efficiency scoring

#### **GPU Type Filtering**
```yaml
instances:
  # Find cheapest NVIDIA T4 specifically
  - name: "t4-optimized"
    provider: "cheapest"
    cores: 8
    memory: 32768
    gpu_count: 1
    gpu_type: "NVIDIA T4"     # 🆕 Only T4 instances
    
  # Find cheapest NVIDIA A100 specifically  
  - name: "a100-optimized"
    provider: "cheapest"
    cores: 32
    memory: 131072
    gpu_count: 2
    gpu_type: "NVIDIA A100"   # 🆕 Only A100 instances
    
  # Find cheapest AMD GPU
  - name: "amd-optimized"
    provider: "cheapest"
    cores: 4
    memory: 16384
    gpu_count: 1
    gpu_type: "AMD Radeon Pro V520"  # 🆕 AMD-specific
```

### **Sample GPU Cost Analysis**

```bash
Cost analysis for 8 cores, 32.0GB RAM, 1 NVIDIA T4 GPU(s):
  aws: $0.752/hour (g4dn.2xlarge, 8 vCPU, 32GB, 1x NVIDIA T4) ← SELECTED
  azure: $0.752/hour (Standard_NC8as_T4_v3, 8 vCPU, 56GB, 1x NVIDIA T4)
  ibm_vpc: $1.420/hour (gx3-16x128x1l4, 16 vCPU, 128GB, 1x NVIDIA L4)

Cost analysis for 8 cores, 32.0GB RAM, 1 GPU(s):
  aws: $0.689/hour (g4ad.2xlarge, 8 vCPU, 32GB, 1x AMD Radeon Pro V520) ← SELECTED
  azure: $0.752/hour (Standard_NC8as_T4_v3, 8 vCPU, 56GB, 1x NVIDIA T4)
  gcp: $2.933/hour (a2-highgpu-1g, 12 vCPU, 85GB, 1x NVIDIA A100)
```

### **Supported GPU Types**

| GPU Type | Use Case | Providers | Cost Range |
|----------|----------|-----------|------------|
| **NVIDIA T4** | Development, Inference | AWS, Azure, GCP, IBM VPC | $0.35 - $0.75/hour |
| **NVIDIA V100** | High-performance Training | AWS, Azure, GCP, IBM VPC | $1.89 - $12.67/hour |
| **NVIDIA A100** | State-of-the-art AI/ML | AWS, Azure, GCP, IBM VPC | $2.93 - $32.77/hour |
| **NVIDIA L4/L40S** | Modern Workloads | IBM VPC | $1.42 - $12.48/hour |
| **AMD Radeon Pro** | Cost-effective Alternative | AWS | $0.38 - $0.69/hour |

### **Available GPU Flavors**

#### **Generic GPU Sizes**
- `gpu_small`, `gpu_medium`, `gpu_large`, `gpu_xlarge`, `gpu_multi`

#### **NVIDIA T4 Flavors**
- `gpu_t4_small`, `gpu_t4_medium`, `gpu_t4_large`

#### **NVIDIA V100 Flavors**
- `gpu_v100_small`, `gpu_v100_medium`, `gpu_v100_large`

#### **NVIDIA A100 Flavors**
- `gpu_a100_small`, `gpu_a100_medium`, `gpu_a100_large`, `gpu_a100_xlarge`

#### **AMD Radeon Pro Flavors**
- `gpu_amd_small`, `gpu_amd_medium`

### **GPU Type Validation & Provider Compatibility**

The system validates GPU types and provides **clear error messages** for both invalid GPU types and incompatible provider combinations:

#### **❌ Error Example: Invalid GPU Type**
```yaml
instances:
  - name: "unknown-gpu"
    provider: "cheapest"
    gpu_type: "NVIDIA H100"    # Not available in our mappings
```

**Error Message:**
```
GPU type 'NVIDIA H100' is not available in any cloud provider. 
Available GPU types:

NVIDIA GPUs:
  - NVIDIA A100
  - NVIDIA L4  
  - NVIDIA L40S
  - NVIDIA T4
  - NVIDIA V100

AMD GPUs:
  - AMD Radeon Pro V520

Consider using:
  - Exact GPU name from the list above
  - Short GPU name (e.g., 'T4', 'V100', 'A100')
  - Generic GPU size: gpu_small, gpu_medium, gpu_large
  - Remove gpu_type to find cheapest GPU regardless of type
```

Not all GPU types are available on every cloud provider. The system also provides **clear error messages** when you request incompatible combinations:

#### **❌ Error Example: AMD GPU on Unsupported Provider**
```yaml
instances:
  - name: "amd-azure-error"
    provider: "azure"      # Azure doesn't support AMD GPUs
    size: "gpu_amd_small"  # AMD-specific flavor
```

**Error Message:**
```
AMD GPU flavor 'gpu_amd_small' is only available on AWS. 
Provider 'azure' does not support AMD GPUs. 
Consider using:
  - AWS provider: provider: 'aws'
  - Different GPU type: gpu_t4_small, gpu_v100_small, etc.
  - Cost optimization: provider: 'cheapest' with gpu_type: 'AMD Radeon Pro V520'
```

#### **✅ Solutions for Invalid GPU Types:**

**Option 1: Use Valid GPU Type**
```yaml
instances:
  - name: "valid-gpu"
    provider: "cheapest"
    gpu_type: "NVIDIA A100"  # Valid GPU from the list
```

**Option 2: Use Short GPU Name**
```yaml
instances:
  - name: "short-name"
    provider: "cheapest" 
    gpu_type: "T4"          # Short names work too
```

**Option 3: Use Generic GPU Size**
```yaml
instances:
  - name: "generic-gpu"
    provider: "azure"
    size: "gpu_large"       # Let system choose GPU type
```

**Option 4: Remove GPU Type Constraint**
```yaml
instances:
  - name: "any-gpu"
    provider: "cheapest"
    gpu_count: 1            # Find cheapest GPU regardless of type
```

#### **✅ Solutions for Provider Compatibility:**

**Option 1: Use Supported Provider**
```yaml
instances:
  - name: "amd-aws-success"
    provider: "aws"        # AWS supports AMD GPUs
    size: "gpu_amd_small"
```

**Option 2: Use Alternative GPU Type**
```yaml
instances:
  - name: "t4-azure-alternative"
    provider: "azure"      # Use T4 instead of AMD
    size: "gpu_t4_small"
```

**Option 3: Let System Choose**
```yaml
instances:
  - name: "cheapest-amd"
    provider: "cheapest"   # Automatically selects AWS for AMD
    gpu_type: "AMD Radeon Pro V520"
```

### **GPU Provider Matrix**

| GPU Type | AWS | Azure | GCP | IBM VPC |
|----------|:---:|:-----:|:---:|:-------:|
| **NVIDIA T4** | ✅ | ✅ | ✅ | ✅ |
| **NVIDIA V100** | ✅ | ✅ | ✅ | ✅ |
| **NVIDIA A100** | ✅ | ✅ | ✅ | ✅ |
| **NVIDIA L4/L40S** | ❌ | ❌ | ❌ | ✅ |
| **AMD Radeon Pro** | ✅ | ❌ | ❌ | ❌ |

### **GPU Benefits**

- **🎯 Intelligent GPU Selection**: Find optimal GPU for workload and budget
- **💰 Cross-Cloud Cost Optimization**: Compare GPU costs across all providers
- **🔧 Flexible Requirements**: Specify exact GPU type or let system choose cheapest
- **📊 Transparent GPU Analysis**: See exact GPU specs and costs before deployment
- **🚀 Production-Ready**: Full Terraform generation with proper GPU instance types
- **🎮 Complete Coverage**: Support for all major GPU types across all cloud providers
- **✅ GPU Type Validation**: Validates GPU types exist before attempting deployment
- **⚠️ Clear Error Messages**: Helpful guidance for both invalid GPU types and unsupported provider combinations
- **🏷️ Flexible GPU Naming**: Supports both full names ("NVIDIA T4") and short names ("T4")
- **📋 Comprehensive GPU Inventory**: Shows all available GPU types organized by vendor
- **🎯 Automatic Flavor Discovery**: Specify exact requirements and get recommended generic flavors

## 📖 Command-Line Reference

### Synopsis
```bash
python yamlforge.py input_file -d OUTPUT_DIR
```

### Arguments

#### **`input_file`** (required)
Path to the input YAML infrastructure configuration file.

**Usage:**
```bash
python yamlforge.py my-infrastructure.yaml -d terraform/
python yamlforge.py examples/gcp_example.yaml -d gcp-project/
python yamlforge.py /path/to/config.yaml -d /path/to/terraform/
```

**Notes:**
- Must be a valid YAML file
- Supports relative and absolute paths
- See `examples/` directory for sample configurations

#### **`-d`, `--output-dir DIR`** (required)
Specify output directory for generated Terraform project files.

**Usage:**
```bash
# Create organized Terraform project
python yamlforge.py config.yaml -d terraform/

# Generate project in existing directory
python yamlforge.py config.yaml --output-dir infrastructure/
```

**Generated Files:**
- **`main.tf`** - Terraform resources (providers, networking, instances)
- **`variables.tf`** - Variable definitions with descriptions and defaults
- **`terraform.tfvars`** - Example variable values (customize with your settings)

**Directory Requirements:**
- Output directory **must exist** before running yamlforge
- Directory **must be empty** or you'll risk overwriting existing files
- Use `mkdir terraform/` to create directory if needed

**Examples:**
```bash
# Create and generate Terraform project
mkdir terraform-project
python yamlforge.py multi-cloud.yaml -d terraform-project/

# Generate in organized subdirectory
mkdir -p projects/production
python yamlforge.py production.yaml -d projects/production/
```

### Complete Examples

#### **Basic Conversion**
```bash
# Create directory and convert YAML to Terraform
mkdir terraform-output
python yamlforge.py infrastructure.yaml -d terraform-output/
```

#### **Production Workflow**
```bash
# Create organized Terraform project
mkdir terraform
python yamlforge.py production.yaml -d terraform/

# Customize variables and deploy
cd terraform/
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
terraform init
terraform plan
terraform apply
```

#### **Development Workflow**
```bash
# Start with example from examples directory
cp examples/gcp_example.yaml dev-config.yaml

# Create project directory and generate
mkdir dev-infrastructure
python yamlforge.py dev-config.yaml -d dev-infrastructure/
```

#### **Multi-Environment Setup**
```bash
# Development environment
mkdir terraform/dev
python yamlforge.py configs/dev.yaml -d terraform/dev/

# Staging environment  
mkdir terraform/staging
python yamlforge.py configs/staging.yaml -d terraform/staging/

# Production environment
mkdir terraform/prod
python yamlforge.py configs/prod.yaml -d terraform/prod/
```

### Error Handling

#### **Exit Codes**
- **0**: Success
- **1**: Error (file not found, invalid YAML, directory issues, etc.)

#### **Common Errors**

**File not found:**
```bash
$ python yamlforge.py nonexistent.yaml -d terraform/
Error: File 'nonexistent.yaml' not found
```

**Invalid YAML syntax:**
```bash
$ python yamlforge.py bad-syntax.yaml -d terraform/
Error parsing YAML: while parsing a block mapping...
```

**Directory not found:**
```bash
$ python yamlforge.py config.yaml -d nonexistent-dir/
Error: Output directory 'nonexistent-dir/' does not exist
```

**Missing output directory:**
```bash
$ python yamlforge.py config.yaml
usage: yamlforge.py [-h] -d OUTPUT_DIR input_file
yamlforge.py: error: the following arguments are required: -d/--output-dir
```

#### **Debugging Tips**

**Validate YAML first:**
```bash
# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('config.yaml'))"

# Or use yq if available
yq eval . config.yaml
```

**Test with example:**
```bash
# Start with working example from examples directory
mkdir test-output
python yamlforge.py examples/architecture_example.yaml -d test-output/
```

**Organize by environment:**
```bash
# Create organized directory structure
mkdir -p terraform/{dev,staging,prod}
python yamlforge.py dev.yaml -d terraform/dev/
python yamlforge.py staging.yaml -d terraform/staging/
python yamlforge.py prod.yaml -d terraform/prod/
```

### Example YAML

```yaml
# Multi-cloud deployment example
deployments:
  aws-prod:
    provider: aws
    network:
      name: "aws-prod-vpc"
      cidr_block: "10.1.0.0/16"
  
  azure-prod:
    provider: azure
    network:
      name: "azure-prod-vnet"
      cidr_block: "10.2.0.0/16"
  
  gcp-prod:
    provider: gcp
    network:
      name: "gcp-prod-network"
      cidr_block: "10.3.0.0/16"
  
  ibm-vpc-prod:
    provider: ibm_vpc
    network:
      name: "ibm-vpc-network"
      cidr_block: "10.4.0.0/16"
  
  ibm-classic-legacy:
    provider: ibm_classic
    network:
      name: "legacy-network"
      domain: "example.com"

# Unified security groups
security_groups:
  web-servers:
    description: "Web server access"
    rules:
      - protocol: tcp
        port: 80
        cidr: "0.0.0.0/0"
      - protocol: tcp
        port: 443
        cidr: "0.0.0.0/0"
      - protocol: tcp
        port: 22
        cidr: "10.0.0.0/8"

# Instances across multiple clouds
instances:
  # AWS instance with Red Hat Cloud Access
  - name: "web-aws-01"
    provider: aws
    image: "RHEL9GOLD-latest"  # Cloud Access gold image
    size: medium
    location: "us-east-1"
    security_groups:
      - "web-servers"
    
  # Azure instance with BYOS
  - name: "web-azure-01"
    provider: azure
    image: "RHEL9GOLD-latest"  # BYOS image
    size: medium
    location: "us-east-1"
    security_groups:
      - "web-servers"
    
  # GCP instance with dynamic image discovery
  - name: "web-gcp-01"
    provider: gcp
    image: "RHEL9GOLD-latest"  # Latest image via API
    size: medium
    location: "us-east-1"
    zone: "us-east1-a"
    security_groups:
      - "web-servers"
    
  # IBM Cloud VPC instance
  - name: "web-ibm-vpc-01"
    provider: ibm_vpc
    flavor: "bx2-4x16"  # 4 vCPU, 16GB RAM
    image: "RHEL9-latest"
    location: "us-south"
    zone: "us-south-1"
    security_groups:
      - "web-servers"
      
  # IBM Cloud Classic instance
  - name: "web-ibm-classic-01"
    provider: ibm_classic
    flavor: "B1.4x16x100"  # 4 CPU, 16GB RAM, 100GB disk
    image: "RHEL9-latest"
    location: "dal10"
    security_groups:
      - "web-servers"
```

## 📋 Configuration Structure

### Deployments

The `deployments:` field is the foundation for organizing multi-cloud infrastructure. It defines cloud-specific environments and network configurations that instances can utilize.

#### **What Deployments Do**

- **🌍 Multi-Cloud Organization**: Define separate environments for each cloud provider
- **🔧 Network Configuration**: Set up VPCs, VNets, and networking per cloud
- **🎯 Smart Provider Detection**: Only generate Terraform for clouds you actually use
- **🏗️ Environment Isolation**: Separate dev/staging/prod environments by cloud
- **📦 Resource Grouping**: Organize infrastructure by purpose or team

#### **When to Use Deployments**

✅ **Use deployments when you have:**
- Multi-cloud infrastructure across AWS, Azure, GCP, or IBM Cloud
- Different network requirements per cloud provider
- Environment separation (dev/staging/prod)
- Team-based cloud resource isolation

❌ **Skip deployments for:**
- Single-cloud, simple deployments
- Basic testing with default networking

#### **How Deployments Work**

1. **Define Environment**: Each deployment creates a named environment with a cloud provider
2. **Network Generation**: YamlForge generates provider-specific networking resources
3. **Instance Association**: Instances automatically use the networking from their provider's deployment
4. **Terraform Optimization**: Only includes Terraform providers for clouds you actually use

#### **Deployment Structure**

```yaml
deployments:
  deployment-name:           # Custom name for this environment
    provider: aws            # Cloud provider: aws|azure|gcp|ibm_vpc|ibm_classic
    network:                 # Network configuration
      name: "network-name"   # VPC/VNet name
      cidr_block: "10.x.0.0/16"  # Network CIDR
      subnets:               # Optional: Define subnets
        subnet-name:
          cidr_block: "10.x.1.0/24"
          availability_zone: "us-east-1a"
```

#### **Complete Multi-Cloud Example**

```yaml
# Three-cloud enterprise deployment
deployments:
  aws-production:
    provider: aws
    network:
      name: "aws-prod-vpc"
      cidr_block: "10.1.0.0/16"
      subnets:
        web-tier:
          cidr_block: "10.1.1.0/24"
          availability_zone: "us-east-1a"
        app-tier:
          cidr_block: "10.1.2.0/24"
          availability_zone: "us-east-1b"
  
  azure-disaster-recovery:
    provider: azure
    network:
      name: "azure-dr-vnet"
      cidr_block: "10.2.0.0/16"
  
  gcp-analytics:
    provider: gcp
    network:
      name: "gcp-analytics-vpc"
      cidr_block: "10.3.0.0/16"

# Security groups work across all deployments
security_groups:
  web-servers:
    description: "Web tier access"
    rules:
      - protocol: tcp
        port: 80
        cidr: "0.0.0.0/0"

# Instances automatically use their provider's deployment networking
instances:
  - name: "web-server-aws"
    provider: aws              # Uses aws-production deployment
    image: "RHEL9GOLD-latest"
    size: medium
    security_groups: ["web-servers"]
    
  - name: "backup-server-azure"
    provider: azure            # Uses azure-disaster-recovery deployment  
    image: "RHEL9GOLD-latest"
    size: large
    security_groups: ["web-servers"]
    
  - name: "analytics-server-gcp"
    provider: gcp              # Uses gcp-analytics deployment
    image: "RHEL9GOLD-latest"
    size: "n1-highmem-4"       # GCP-specific instance type
    zone: "us-central1-a"
    security_groups: ["web-servers"]
```

#### **Generated Resources Per Cloud**

| Provider | Generated Networking |
|----------|---------------------|
| **AWS** | VPC, Subnets, Internet Gateway, Route Tables, Security Groups |
| **Azure** | Resource Group, Virtual Network, Subnets, Network Security Groups |
| **GCP** | VPC Network, Subnetworks, Firewall Rules |
| **IBM VPC** | VPC, Subnets, Public Gateways, Security Groups |
| **IBM Classic** | VLANs, Security Groups |

#### **Benefits of Using Deployments**

🚀 **Smart Terraform Generation**: Only includes providers you actually use
🔒 **Network Isolation**: Separate network configurations per cloud
🎯 **Environment Organization**: Clean separation of dev/staging/prod
📈 **Scalability**: Easy to support additional clouds or environments
🔧 **Flexibility**: Mix cloud-specific and abstract configurations

**💡 Pro Tip**: Deployments are optional! For simple single-cloud setups, you can use just the `instances:` section and yamlforge will create default networking.

## 🌐 Multi-Cloud Support

### Generated Terraform

The tool generates **native** cloud provider resources and **automatically detects** which providers you're actually using:

**🧠 Smart Provider Detection:**
- **AWS-only config** → Only AWS provider & variables
- **Multi-cloud config** → Only the providers you specify
- **No unused dependencies** → Cleaner, faster Terraform

#### AWS
```hcl
resource "aws_instance" "web_aws_01" {
  ami           = data.aws_ami.web_aws_01_ami.id
  instance_type = "t3.medium"
  subnet_id     = aws_subnet.main_subnet.id
  vpc_security_group_ids = [aws_security_group.web_servers.id]
}
```

#### Azure
```hcl
resource "azurerm_linux_virtual_machine" "web_azure_01" {
  name                = "web-azure-01"
  size                = "Standard_B2s"
  resource_group_name = azurerm_resource_group.main.name
  
  source_image_reference {
    publisher = "redhat"
    offer     = "rhel-byos"
    sku       = "rhel-lvm9"
    version   = "latest"
  }
}
```

#### GCP
```hcl
resource "google_compute_instance" "web_gcp_01" {
  name         = "web-gcp-01"
  machine_type = "e2-medium"
  zone         = "us-east1-a"
  
  boot_disk {
    initialize_params {
      image = "rhel-byos-cloud/rhel-9-byos-v20250709"  # Dynamic!
    }
  }
}
```

#### IBM Cloud VPC
```hcl
resource "ibm_is_instance" "web_ibm_01" {
  name    = "web-ibm-01"
  image   = data.ibm_is_image.rhel_image.id
  profile = "bx2-4x16"  # 4 vCPU, 16GB RAM
  
  primary_network_interface {
    subnet = ibm_is_subnet.main_subnet.id
    security_groups = [ibm_is_security_group.web_servers.id]
  }
  
  vpc  = ibm_is_vpc.main_vpc.id
  zone = "us-south-1"
}
```

#### IBM Cloud Classic
```hcl
resource "ibm_compute_vm_instance" "web_classic_01" {
  hostname        = "web-classic-01"
  flavor_key_name = "B1.4x16x100"  # 4 CPU, 16GB RAM
  datacenter      = "dal10"
  hourly_billing  = true
}
```

## 🎨 Security Groups Support

### Unified Security Groups
Define security groups once and use across multiple instances:

```yaml
security_groups:
  database-tier:
    description: "Database access"
    rules:
      - protocol: tcp
        port: 5432
        cidr: "10.0.0.0/16"
      - protocol: tcp
        port: 22
        cidr: "10.0.1.0/24"

instances:
  - name: "db-primary"
    security_groups: ["database-tier"]
  - name: "db-replica"  
    security_groups: ["database-tier"]
```

### Inline Security Groups
Create instance-specific security groups automatically:

```yaml
instances:
  - name: "special-server"
    security_groups:
      # Reference existing group
      - "web-servers"
    # Inline rules (creates special-server-sg automatically)
    inline_security_rules:
      - protocol: tcp
        port: 8080
        cidr: "0.0.0.0/0"
```

## 🌐 Subnet Management

### Unified Subnets
Define subnets once at the top level:

```yaml
subnets:
  web-subnet:
    cidr_block: "10.0.1.0/24"
    availability_zone: "us-east-1a"
  app-subnet:
    cidr_block: "10.0.2.0/24"
    availability_zone: "us-east-1b"

instances:
  - name: "web-server"
    subnet: "web-subnet"
  - name: "app-server"
    subnet: "app-subnet"
```

### Network-Level Subnets
Define subnets within network configuration:

```yaml
deployments:
  enterprise:
    provider: aws
    network:
      name: "enterprise-vpc"
      cidr_block: "10.0.0.0/16"
      subnets:
        public-web:
          cidr_block: "10.0.1.0/24"
          availability_zone: "us-east-1a"
        private-app:
          cidr_block: "10.0.2.0/24" 
          availability_zone: "us-east-1b"
```

## 🔧 GCP Dynamic Image Discovery

For GCP deployments, the tool can automatically discover the latest Red Hat Cloud Access images:

### Setup
```bash
# Install GCP client library
pip install google-cloud-compute>=1.14.0

# Authenticate with GCP
gcloud auth application-default login

# Or set service account credentials
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

### Configuration
Update `credentials/gcp.yaml`:

```yaml
gcp:
  byos_project: "rhel-byos-cloud"
  auth_method: "application_default"
  cache:
    enabled: true
    ttl_minutes: 60
  families:
    rhel8_x86_64: "rhel-8-byos"
    rhel9_x86_64: "rhel-9-byos"
    rhel8_arm64: "rhel-8-byos-arm64"
    rhel9_arm64: "rhel-9-byos-arm64"
```

### Usage
```yaml
instances:
  - name: "rhel-server"
    provider: gcp
    image: "RHEL9GOLD-latest"  # Resolves to latest timestamped image
```

Automatically resolves to the latest available image like `rhel-9-byos-v20250709`.

## 🎯 Red Hat Cloud Access Support

Full support for Red Hat Cloud Access (BYOS) across all cloud providers:

| Cloud | Image Type | Generated Reference |
|-------|------------|-------------------|
| **AWS** | Gold AMIs | `owner: "309956199498"`, `name_pattern: "RHEL-9.*Access*"` |
| **Azure** | BYOS Images | `publisher: "redhat"`, `offer: "rhel-byos"` |
| **GCP** | BYOS Images | `project: "rhel-byos-cloud"`, dynamic discovery |

## 📁 Directory Structure

```
yamlforge/
├── yamlforge.py              # Main converter tool
├── requirements.txt          # Python dependencies
├── credentials/              # 🔒 Cloud provider credentials
│   ├── README.md             # Credentials setup guide
│   ├── aws.yaml              # AWS credential configuration
│   ├── azure.yaml            # Azure credential configuration
│   ├── gcp.yaml              # GCP credential configuration
│   ├── ibm.yaml              # IBM Cloud credential configuration
│   └── .gitignore            # Security protection
├── mappings/
│   ├── cloud_patterns.yaml   # Cloud flavor patterns
│   ├── images.yaml           # Image mappings
│   ├── locations.yaml        # Region mappings
│   ├── sizes.yaml            # Size mappings
│   └── flavors/
│       ├── aws.yaml          # AWS instance types
│       ├── azure.yaml        # Azure VM sizes
│       └── gcp.yaml          # GCP machine types
└── examples/
    ├── multi_cloud_example.yaml
    ├── security_groups_example.yaml
    ├── subnets_example.yaml
    ├── cloud_access_test.yaml
    └── gcp_dynamic_example.yaml
```

## 🚀 Advanced Features

### SSH Key Management
YamlForge provides centralized SSH key management with global configuration in YAML instead of Terraform variables.

#### **Global SSH Key Configuration**
```yaml
yamlforge:
  # Define SSH keys globally
  ssh_keys:
    # Simple format: just the public key
    default: "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7... user@example.com"
    
    # Full format: complete configuration
    admin:
      public_key: "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQDJ... admin@company.com"
      username: "admin"
      comment: "Administrator access key"
```

#### **Per-Instance SSH Key Selection**
```yaml
instances:
  # Uses 'default' SSH key automatically
  - name: "web-server"
    provider: "aws"
    # No ssh_key specified = uses 'default'
    
  # Explicitly specify which SSH key to use
  - name: "database-server"
    provider: "azure"
    ssh_key: "admin"  # Use the 'admin' SSH key
```

#### **Cloud Provider Support**
- **AWS**: Creates `aws_key_pair` resources automatically
- **Azure**: Embeds SSH keys in `admin_ssh_key` blocks
- **GCP**: Adds SSH keys to instance metadata
- **IBM VPC**: Creates `ibm_is_ssh_key` resources
- **IBM Classic**: Creates `ibm_compute_ssh_key` resources

### Architecture Support
- **x86_64**: Standard Intel/AMD processors
- **ARM64**: AWS Graviton, Azure Ampere, GCP Tau T2A

### Hybrid Deployments
Mix cloud-specific flavors with abstract sizes:

```yaml
instances:
  # Abstract size (works on any cloud)
  - name: "web-server"
    size: medium
    
  # Cloud-specific flavor
  - name: "aws-graviton"
    flavor: "m6g.large"  # AWS ARM instance
    
  - name: "azure-memory"
    flavor: "Standard_E4s_v3"  # Azure memory-optimized
    
  - name: "gcp-compute"
    flavor: "c2-standard-8"  # GCP compute-optimized
```

### User Data Scripts
Support for cloud-init across all providers:

```yaml
instances:
  - name: "web-server"
    user_data_script: |
      #!/bin/bash
      dnf update -y
      dnf install -y httpd
      systemctl enable httpd
      systemctl start httpd
      echo "<h1>Hello from Multi-Cloud!</h1>" > /var/www/html/index.html
```

## 🔧 Configuration

### Global Settings
Configure cloud-specific behavior in mapping files:

- `mappings/images.yaml` - Image references for all clouds
- `mappings/sizes.yaml` - Size translations between clouds  
- `mappings/locations.yaml` - Region mappings
- `mappings/flavors/` - Cloud-specific instance types

### Environment Variables
```bash
# GCP dynamic image discovery
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"

# AWS credentials (if using AWS features)
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"

# Azure credentials (if using Azure features)  
export ARM_CLIENT_ID="your-client-id"
export ARM_CLIENT_SECRET="your-secret"
```

## 🆘 Troubleshooting

### GCP Image Discovery Issues
```bash
# Test GCP authentication
gcloud auth application-default login

# Verify permissions
gcloud projects get-iam-policy PROJECT_ID

# Check image availability
gcloud compute images list --project rhel-byos-cloud --filter="family:rhel-9-byos"
```

### Common Issues

**No GCP credentials configured**
```
Warning: GCP credentials not configured. Using static image names.
```
Solution: Set up GCP authentication using one of the methods above.

**Missing image mappings**
```
Warning: No image mapping found for 'CustomImage'
```
Solution: Add custom image mappings to `mappings/images.yaml`.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Add your changes and tests
4. Commit your changes (`git commit -m 'Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🎯 Why YamlForge?

**YamlForge** provides enterprise-grade multi-cloud infrastructure automation:

✅ **True Multi-Cloud**: Native resources for AWS, Azure, and GCP  
✅ **Enterprise Ready**: Red Hat Cloud Access, dynamic discovery, caching  
✅ **No Vendor Lock-in**: Generate standard Terraform, no proprietary dependencies  
✅ **Production Tested**: Used for enterprise RHEL deployments  
✅ **Future Proof**: Extensible architecture for additional cloud providers  

**Migrate from vendor-specific tools to open, standardized, multi-cloud infrastructure as code!** 🚀

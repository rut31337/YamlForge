# Cost Optimization Guide

YamlForge provides powerful cost optimization features that automatically select the most cost-effective cloud providers and instance types for your workloads.

## Quick Start

### Basic Cost Optimization

```yaml
guid: "cst01"

yamlforge:
  cloud_workspace:
    name: "cost-optimized-{guid}"
    description: "Basic cost optimization example"
  
  instances:
    - name: "cost-optimized-{guid}"
      provider: "cheapest"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east-1"
```

### GPU Cost Optimization

```yaml
guid: "gpu01"

yamlforge:
  cloud_workspace:
    name: "gpu-cost-optimized-{guid}"
    description: "GPU cost optimization example"
  
  instances:
    - name: "gpu-optimized-{guid}"
      provider: "cheapest-gpu"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA T4"
      gpu_count: 1
```

## Provider Discounts

YamlForge supports configurable provider-specific discounts for accurate cost analysis in enterprise environments with existing cloud contracts and volume pricing.

### Configuration

**Core Configuration (`defaults/core.yaml`):**
```yaml
cost_analysis:
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

**Environment Variable Overrides:**
```bash
# Environment variables take precedence over core configuration
export YAMLFORGE_DISCOUNT_AWS=15        # 15% AWS discount
export YAMLFORGE_DISCOUNT_AZURE=20      # 20% Azure discount
export YAMLFORGE_DISCOUNT_GCP=10        # 10% GCP discount
export YAMLFORGE_DISCOUNT_OCI=25        # 25% OCI discount
export YAMLFORGE_DISCOUNT_IBM_VPC=18    # 18% IBM VPC discount
export YAMLFORGE_DISCOUNT_IBM_CLASSIC=12 # 12% IBM Classic discount
export YAMLFORGE_DISCOUNT_ALIBABA=30    # 30% Alibaba discount
export YAMLFORGE_DISCOUNT_VMWARE=5      # 5% VMware discount
```

### Features

- **Percentage-based**: Discounts specified as 0-100%
- **Environment precedence**: Environment variables override core configuration
- **Cost analysis integration**: Applied to all cost displays and cheapest provider selection
- **Input validation**: Invalid values show warnings and default to 0%
- **Clear display**: Shows both original and discounted prices

### Cost Display with Discounts

```bash
# Example analysis output with discounts applied
Cost analysis for instance 'web-server-test1':
  aws: $0.0416/hour → $0.0312/hour (25.0% discount) (t3.medium, 2 vCPU, 4GB) ← SELECTED
  gcp: $0.0335/hour (e2-medium, 1 vCPU, 4GB)
  azure: $0.0752/hour (Standard_B4ms, 4 vCPU, 16GB)
```

### Impact on Provider Selection

Discounts are applied **before** cheapest provider selection, ensuring accurate cost comparisons:

```yaml
# AWS becomes cheapest with 25% discount
# Without discount: GCP ($0.0335) < AWS ($0.0416)
# With 25% AWS discount: AWS ($0.0312) < GCP ($0.0335)
guid: "dsc01"

yamlforge:
  cloud_workspace:
    name: "discount-example-{guid}"
    description: "Provider discount impact example"
  
  instances:
    - name: "cost-optimized-{guid}"
      provider: "cheapest"  # Will select AWS with discount applied
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east"
```

## Cost Analysis

### Using the Analyze Command

```bash
# Analyze configuration for cost optimization
python yamlforge.py my-config.yaml --analyze
```

**Sample Output:**
```
Instance Analysis:
- Name: cost-optimized-cost1
- Provider: GCP (selected for lowest cost)
- Flavor: medium (e2-medium)
- Estimated Cost: $0.0335/hour
- Total Monthly: ~$24.12
```

### Cost Comparison

YamlForge automatically compares costs across all providers:

```
Cost analysis for instance 'web-server-cost1':
  gcp: $0.0335/hour (e2-medium, 2 vCPU, 4GB) ← SELECTED
  aws: $0.0416/hour (t3.medium, 2 vCPU, 4GB)
  azure: $0.0752/hour (Standard_B4ms, 4 vCPU, 16GB)
```

## Optimization Strategies

### 1. Generic Size Optimization

```yaml
guid: "siz01"

yamlforge:
  cloud_workspace:
    name: "size-optimization-{guid}"
    description: "Generic size optimization example"
  
  instances:
    # Automatically finds cheapest medium instance across ALL clouds
    - name: "medium-optimized-{guid}"
      provider: "cheapest"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east-1"
```

### 2. Specialized Workload Optimization

```yaml
guid: "spc01"

yamlforge:
  cloud_workspace:
    name: "specialized-workload-{guid}"
    description: "Specialized workload optimization"
  
  instances:
    # Finds cheapest compute-optimized instance across all providers
    - name: "compute-optimized-{guid}"
      provider: "cheapest"
      flavor: "compute_large"
      image: "RHEL9-latest"
      location: "us-east-1"
      
    # Finds cheapest memory-optimized instance across all providers
    - name: "memory-optimized-{guid}"
      provider: "cheapest"
      flavor: "memory_large"
      image: "RHEL9-latest"
      location: "us-east-1"
```

### 3. Provider-Specific Optimization

```yaml
guid: "prv01"

yamlforge:
  cloud_workspace:
    name: "provider-specific-{guid}"
    description: "Provider-specific optimization"
  
  instances:
    # Automatically maps to best AWS instance for medium workloads
    - name: "aws-optimized-{guid}"
      provider: "aws"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east-1"
      
    # Automatically maps to best Azure memory-optimized VM
    - name: "azure-optimized-{guid}"
      provider: "azure"
      flavor: "memory_large"
      image: "RHEL9-latest"
      location: "eastus"
      
    # Automatically maps to best GCP compute-optimized instance
    - name: "gcp-optimized-{guid}"
      provider: "gcp"
      flavor: "compute_large"
      image: "RHEL9-latest"
      location: "us-central1"
```

## Advanced Cost Optimization

### 1. Custom Specifications

```yaml
guid: "cst01"

yamlforge:
  cloud_workspace:
    name: "custom-specs-{guid}"
    description: "Custom CPU/memory specification optimization"
  
  instances:
    # Find cheapest instance with specific CPU/memory requirements
    - name: "custom-specs-{guid}"
      provider: "cheapest"
      cores: 8
      memory: 16384  # 16GB in MB
      image: "RHEL9-latest"
      location: "us-east-1"
```

### 2. Multi-Region Optimization

```yaml
guid: "mul01"

yamlforge:
  cloud_workspace:
    name: "multi-region-{guid}"
    description: "Multi-region cost optimization"
  
  instances:
    # Compare costs across different regions
    - name: "east-cost-{guid}"
      provider: "cheapest"
      flavor: "large"
      image: "RHEL9-latest"
      location: "us-east-1"
      
    - name: "west-cost-{guid}"
      provider: "cheapest"
      flavor: "large"
      image: "RHEL9-latest"
      location: "us-west-2"
```

### 3. GPU Cost Optimization

```yaml
guid: "gpu02"

yamlforge:
  cloud_workspace:
    name: "gpu-cost-optimization-{guid}"
    description: "Advanced GPU cost optimization"
  
  instances:
    # Find cheapest GPU instance across all providers
    - name: "gpu-cheapest-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA T4"
      gpu_count: 1
      
    # Compare different GPU types
    - name: "gpu-v100-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA V100"
      gpu_count: 1
      
    - name: "gpu-a100-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA A100"
      gpu_count: 1
```

## Provider Exclusions

### Global Exclusions

```yaml
guid: "exc01"

yamlforge:
  cloud_workspace:
    name: "provider-exclusions-{guid}"
    description: "Provider exclusion example"
  
  # Exclude providers from cost comparison
  exclude_providers: ["vmware", "alibaba"]
  
  instances:
    - name: "excluded-optimized-{guid}"
      provider: "cheapest"  # Only considers aws, azure, gcp, oci, ibm_vpc, ibm_classic
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east-1"
```

### Instance-Specific Exclusions

```yaml
guid: "ins01"

yamlforge:
  cloud_workspace:
    name: "instance-exclusions-{guid}"
    description: "Instance-specific provider exclusions"
  
  instances:
    - name: "selective-optimized-{guid}"
      provider: "cheapest"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east-1"
      exclude_providers: ["aws", "azure"]  # Only consider gcp, oci, ibm_vpc, ibm_classic
```

## Cost Monitoring

### Monthly Cost Estimation

```bash
# Get detailed cost breakdown
python yamlforge.py my-config.yaml --analyze
```

**Output includes:**
- Hourly cost per instance
- Monthly cost estimation
- Provider selection rationale
- Alternative provider costs

### Cost Tracking

```yaml
guid: "trk01"

yamlforge:
  cloud_workspace:
    name: "cost-tracking-{guid}"
    description: "Cost tracking and monitoring example"
  
  instances:
    - name: "tracked-instance-{guid}"
      provider: "cheapest"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east-1"
      tags:
        cost_center: "development"
        budget: "monthly"
        owner: "team-a"
```

## Best Practices

### 1. Use Generic Flavors

```yaml
# ✅ Good - YamlForge finds cheapest option
flavor: "medium"

# ❌ Less optimal - Provider-specific may not be cheapest
flavor: "t3.medium"  # AWS-specific
```

### 2. Leverage Cost Analysis

```bash
# Always analyze before deployment
python yamlforge.py my-config.yaml --analyze

# Compare different configurations
python yamlforge.py config-a.yaml --analyze
python yamlforge.py config-b.yaml --analyze
```

### 3. Consider Spot Instances

```yaml
# YamlForge automatically considers spot/preemptible instances
# when they provide cost savings
provider: "cheapest"
flavor: "large"
```

### 4. Monitor Usage

```yaml
# Tag resources for cost tracking
tags:
  environment: "development"
  cost_center: "engineering"
  project: "web-app"
```

## Cost Optimization Examples

### Development Environment

```yaml
guid: "dev01"

yamlforge:
  cloud_workspace:
    name: "development-environment-{guid}"
    description: "Cost-optimized development environment"
  
  instances:
    - name: "dev-server-{guid}"
      provider: "cheapest"
      flavor: "small"
      image: "RHEL9-latest"
      location: "us-east-1"
      tags:
        environment: "development"
        auto_shutdown: "true"
```

### Production Environment

```yaml
guid: "prd01"

yamlforge:
  cloud_workspace:
    name: "production-environment-{guid}"
    description: "Cost-optimized production environment"
  
  instances:
    - name: "prod-web-{guid}"
      provider: "cheapest"
      flavor: "large"
      image: "RHEL9-latest"
      location: "us-east-1"
      tags:
        environment: "production"
        sla: "99.9"
```

### High-Performance Computing

```yaml
guid: "hpc01"

yamlforge:
  cloud_workspace:
    name: "hpc-environment-{guid}"
    description: "High-performance computing cost optimization"
  
  instances:
    - name: "hpc-compute-{guid}"
      provider: "cheapest"
      flavor: "memory_xlarge"
      image: "RHEL9-latest"
      location: "us-east-1"
      tags:
        workload: "hpc"
        priority: "high"
```

## Troubleshooting

### Common Issues

1. **No Cost Data Available**
   ```bash
   # Check provider exclusions
   python yamlforge.py my-config.yaml --analyze
   ```

2. **Unexpected Provider Selection**
   ```bash
   # Review cost analysis output
   python yamlforge.py my-config.yaml --analyze --verbose
   ```

3. **High Costs**
   ```yaml
   # Try smaller flavors or different regions
   flavor: "small"
   location: "us-west-2"  # May be cheaper than us-east-1
   ```

## Next Steps

- [Multi-Cloud Configuration](multi-cloud.md)
- [GPU Optimization](ai-training.md)
- [Troubleshooting Guide](troubleshooting.md) 

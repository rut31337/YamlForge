# Cost Optimization Guide

YamlForge provides powerful cost optimization features that automatically select the most cost-effective cloud providers and instance types for your workloads.

## Quick Start

### Basic Cost Optimization

```yaml
guid: "cost1"

yamlforge:
  instances:
    - name: "cost-optimized-{guid}"
      provider: "cheapest"
      flavor: "medium"
      image: "RHEL9-latest"
      region: "us-east-1"
```

### GPU Cost Optimization

```yaml
guid: "gpu1"

yamlforge:
  instances:
    - name: "gpu-optimized-{guid}"
      provider: "cheapest-gpu"
      flavor: "medium"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA T4"
      gpu_count: 1
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
guid: "size1"

yamlforge:
  instances:
    # Automatically finds cheapest medium instance across ALL clouds
    - name: "medium-optimized-{guid}"
      provider: "cheapest"
      flavor: "medium"
      image: "RHEL9-latest"
      region: "us-east-1"
```

### 2. Specialized Workload Optimization

```yaml
guid: "spec1"

yamlforge:
  instances:
    # Finds cheapest compute-optimized instance across all providers
    - name: "compute-optimized-{guid}"
      provider: "cheapest"
      flavor: "compute_large"
      image: "RHEL9-latest"
      region: "us-east-1"
      
    # Finds cheapest memory-optimized instance across all providers
    - name: "memory-optimized-{guid}"
      provider: "cheapest"
      flavor: "memory_large"
      image: "RHEL9-latest"
      region: "us-east-1"
```

### 3. Provider-Specific Optimization

```yaml
guid: "prov1"

yamlforge:
  instances:
    # Automatically maps to best AWS instance for medium workloads
    - name: "aws-optimized-{guid}"
      provider: "aws"
      flavor: "medium"
      image: "RHEL9-latest"
      region: "us-east-1"
      
    # Automatically maps to best Azure memory-optimized VM
    - name: "azure-optimized-{guid}"
      provider: "azure"
      flavor: "memory_large"
      image: "RHEL9-latest"
      region: "eastus"
      
    # Automatically maps to best GCP compute-optimized instance
    - name: "gcp-optimized-{guid}"
      provider: "gcp"
      flavor: "compute_large"
      image: "RHEL9-latest"
      region: "us-central1"
```

## Advanced Cost Optimization

### 1. Custom Specifications

```yaml
guid: "cust1"

yamlforge:
  instances:
    # Find cheapest instance with specific CPU/memory requirements
    - name: "custom-specs-{guid}"
      provider: "cheapest"
      cores: 8
      memory: 16384  # 16GB in MB
      image: "RHEL9-latest"
      region: "us-east-1"
```

### 2. Multi-Region Optimization

```yaml
guid: "multi1"

yamlforge:
  instances:
    # Compare costs across different regions
    - name: "east-cost-{guid}"
      provider: "cheapest"
      flavor: "large"
      image: "RHEL9-latest"
      region: "us-east-1"
      
    - name: "west-cost-{guid}"
      provider: "cheapest"
      flavor: "large"
      image: "RHEL9-latest"
      region: "us-west-2"
```

### 3. GPU Cost Optimization

```yaml
guid: "gpu2"

yamlforge:
  instances:
    # Find cheapest GPU instance across all providers
    - name: "gpu-cheapest-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA T4"
      gpu_count: 1
      
    # Compare different GPU types
    - name: "gpu-v100-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA V100"
      gpu_count: 1
      
    - name: "gpu-a100-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA A100"
      gpu_count: 1
```

## Provider Exclusions

### Global Exclusions

```yaml
guid: "excl1"

yamlforge:
  # Exclude providers from cost comparison
  exclude_providers: ["vmware", "alibaba"]
  
  instances:
    - name: "excluded-optimized-{guid}"
      provider: "cheapest"  # Only considers aws, azure, gcp, oci, ibm_vpc, ibm_classic
      flavor: "medium"
      image: "RHEL9-latest"
      region: "us-east-1"
```

### Instance-Specific Exclusions

```yaml
guid: "inst1"

yamlforge:
  instances:
    - name: "selective-optimized-{guid}"
      provider: "cheapest"
      flavor: "medium"
      image: "RHEL9-latest"
      region: "us-east-1"
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
guid: "track1"

yamlforge:
  instances:
    - name: "tracked-instance-{guid}"
      provider: "cheapest"
      flavor: "medium"
      image: "RHEL9-latest"
      region: "us-east-1"
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
guid: "dev1"

yamlforge:
  instances:
    - name: "dev-server-{guid}"
      provider: "cheapest"
      flavor: "small"
      image: "RHEL9-latest"
      region: "us-east-1"
      tags:
        environment: "development"
        auto_shutdown: "true"
```

### Production Environment

```yaml
guid: "prod1"

yamlforge:
  instances:
    - name: "prod-web-{guid}"
      provider: "cheapest"
      flavor: "large"
      image: "RHEL9-latest"
      region: "us-east-1"
      tags:
        environment: "production"
        sla: "99.9"
```

### High-Performance Computing

```yaml
guid: "hpc1"

yamlforge:
  instances:
    - name: "hpc-compute-{guid}"
      provider: "cheapest"
      flavor: "memory_xlarge"
      image: "RHEL9-latest"
      region: "us-east-1"
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
   region: "us-west-2"  # May be cheaper than us-east-1
   ```

## Next Steps

- [Multi-Cloud Configuration](multi-cloud.md)
- [GPU Optimization](ai-training.md)
- [Troubleshooting Guide](troubleshooting.md) 

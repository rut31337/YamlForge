# Cost Optimization

YamlForge provides powerful cost optimization features to automatically find the cheapest cloud providers and instance types.

## Cheapest Provider Auto-Selection

The **"cheapest"** meta-provider automatically finds the lowest-cost instance across AWS, Azure, GCP, and IBM Cloud.

### How It Works

1. **Specify Requirements**: Use either generic size (`medium`) or exact specs (`cores: 4, memory: 8192`)
2. **Automatic Cost Comparison**: System compares hourly costs across all cloud providers
3. **Real-Time Selection**: Automatically deploys to the cheapest option
4. **Transparent Output**: Shows cost comparison and selection reasoning

### Usage Examples

#### Generic Size Specification
```yaml
instances:
  - name: "web-server"
    provider: "cheapest"
    size: "medium"              # Finds cheapest medium instance
    image: "RHEL9-latest"
    region: "us-east-1"
```

#### Exact CPU/Memory Requirements
```yaml
instances:
  - name: "database"
    provider: "cheapest"
    cores: 8                    # 8 vCPUs required
    memory: 16384               # 16GB RAM required (in MB)
    image: "RHEL9-latest"
    region: "us-east-1"
```

#### Workload-Optimized Selection
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

### Sample Output

```
🎯 Resolving cheapest provider for instance 'web-server'...
🔍 Finding cheapest option for size 'medium' with auto cores, auto memory...
💰 Cheapest option: gcp e2-medium ($0.0335/hour, 1 vCPU, 4GB RAM)
📊 Cost comparison (top 3):
  1. gcp: e2-medium - $0.0335/hour (1 vCPU, 4GB)
  2. azure: Standard_B2ms - $0.0376/hour (2 vCPU, 8GB)
  3. aws: t3.medium - $0.0416/hour (2 vCPU, 4GB)
```

## GPU Cost Optimization

### Cheapest GPU Provider

For GPU workloads, use the **"cheapest-gpu"** meta-provider:

```yaml
instances:
  - name: "ml-training"
    provider: "cheapest-gpu"    # GPU-focused optimization
    cores: 8
    memory: 32768
    gpu_count: 1
    gpu_type: "NVIDIA T4"       # Optional: specific GPU type
```

### GPU Type-Specific Cost Analysis

```yaml
instances:
  # Find cheapest NVIDIA T4 specifically
  - name: "t4-optimized"
    provider: "cheapest"
    cores: 8
    memory: 32768
    gpu_count: 1
    gpu_type: "NVIDIA T4"       # Only T4 instances
    
  # Find cheapest NVIDIA A100 specifically  
  - name: "a100-optimized"
    provider: "cheapest"
    cores: 32
    memory: 131072
    gpu_count: 2
    gpu_type: "NVIDIA A100"     # Only A100 instances
```

### Sample GPU Cost Analysis

```bash
Cost analysis for 8 cores, 32.0GB RAM, 1 NVIDIA T4 GPU(s):
  aws: $0.752/hour (g4dn.2xlarge, 8 vCPU, 32GB, 1x NVIDIA T4) ← SELECTED
  azure: $0.752/hour (Standard_NC8as_T4_v3, 8 vCPU, 56GB, 1x NVIDIA T4)
  ibm_vpc: $1.420/hour (gx3-16x128x1l4, 16 vCPU, 128GB, 1x NVIDIA L4)
```

## Cost Exclusion Policies

### Exclude Specific Providers

You can exclude providers from cost optimization in `defaults/core.yaml`:

```yaml
cheapest_provider:
  exclude_providers:
    - "alibaba"        # Exclude Alibaba Cloud
    - "vmware"         # Exclude VMware
  
  # Include only specific providers
  include_only:
    - "aws"
    - "azure"
    - "gcp"
```

### Example with Exclusions

```yaml
# This configuration in defaults/core.yaml:
cheapest_provider:
  exclude_providers: ["alibaba", "oci"]

# Will only compare costs across:
# AWS, Azure, GCP, IBM VPC, IBM Classic, VMware
```

## Multi-Cloud Cost Strategies

### Strategy 1: Pure Cost Optimization
```yaml
guid: "cost01"

instances:
  # Let cheapest provider decide everything
  - name: "web-tier"
    provider: "cheapest"
    size: "medium"
    count: 3
    
  - name: "api-tier"
    provider: "cheapest"
    size: "large"
    count: 2
    
  - name: "db-tier"
    provider: "cheapest"
    size: "memory_xlarge"
    count: 1
```

### Strategy 2: Mixed Optimization
```yaml
guid: "mix01"

instances:
  # Critical workload on preferred provider
  - name: "critical-db"
    provider: "aws"
    size: "memory_xlarge"
    
  # Non-critical workloads optimized for cost
  - name: "batch-workers"
    provider: "cheapest"
    size: "compute_large"
    count: 10
    
  - name: "cache-servers"
    provider: "cheapest"
    size: "memory_large"
    count: 3
```

### Strategy 3: GPU Cost Optimization
```yaml
guid: "gpu01"

instances:
  # Training workloads - cost optimized
  - name: "training-nodes"
    provider: "cheapest-gpu"
    gpu_count: 1
    gpu_type: "NVIDIA T4"
    count: 5
    
  # Inference workloads - specific provider
  - name: "inference-cluster"
    provider: "aws"
    size: "gpu_t4_large"
    count: 3
```

## Cost Benefits

### Key Advantages

- **🏆 Maximum Cost Savings**: Automatically finds lowest-cost option across all clouds
- **🚀 No Vendor Lock-in**: Deploy to actually cheapest provider, not predetermined choice  
- **📊 Transparent Pricing**: See real hourly costs and comparison before deployment
- **🎯 Intelligent Matching**: Considers both cost and resource efficiency
- **🔄 Multi-Cloud by Default**: Different instances can land on different optimal providers
- **⚡ Real-Time Optimization**: Uses current pricing data from all flavor mappings

### Cost Comparison Examples

**Development Environment:**
```
Cheapest option: gcp e2-small ($0.0201/hour)
Savings vs AWS t3.small: 52%
Savings vs Azure Standard_B1s: 37%
```

**Production Environment:**
```
Cheapest option: aws m5.large ($0.096/hour)
Savings vs Azure Standard_D2s_v3: 23%
Savings vs GCP n2-standard-2: 15%
```

**GPU Workload:**
```
Cheapest option: aws g4dn.xlarge ($0.526/hour)
Savings vs Azure NC6s_v3: 31%
Savings vs GCP nvidia-tesla-t4: 18%
```

## Best Practices

### 1. Use Provider Exclusions
- Exclude providers you don't have access to
- Focus cost comparison on available options

### 2. Consider Regional Pricing
- Different regions have different pricing
- Use region-specific cost optimization

### 3. GPU Type Specificity
- Specify GPU type for accurate cost comparison
- Consider performance vs cost for GPU workloads

### 4. Monitor and Adjust
- Review cost reports regularly
- Adjust exclusions based on actual usage

## Related Documentation

- [Multi-Cloud Support](multi-cloud.md)
- [GPU Support](gpu-support.md)
- [Auto Discovery](auto-discovery.md)
- [Configuration Guide](../configuration/mappings.md) 
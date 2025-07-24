# Cost-Conscious Examples

This directory demonstrates YamlForge's intelligent cost optimization capabilities across multiple cloud providers.

## 📁 **Directory Contents**

### **Core Cost Optimization Examples**

- **`cheapest_provider_example.yaml`** - Automatic cheapest provider selection demonstration  
- **`mixed_cheapest_example.yaml`** - Mixed deployment with cheapest provider logic

### **GPU-Focused Cost Optimization**
- **`../cheapest_gpu_example.yaml`** - Cheapest-gpu meta provider demonstration

## 🎯 **Cost Optimization Strategies**

YamlForge provides multiple cost optimization approaches:

### **1. Cheapest Provider Selection**
```yaml
guid: "cost1"

yamlforge:
  cloud_workspace:
    name: "cost-optimization"
    description: "Cost-optimized deployment"

  instances:
    - name: "cost-optimized-instance"
      provider: "cheapest"  # Automatically selects lowest cost provider
      size: "small"
      image: "RHEL9-latest"
```

### **2. Provider Exclusions**
```yaml
guid: "excl1"

yamlforge:
  cloud_workspace:
    name: "provider-exclusions"
    description: "Deployment with provider exclusions"

  # Use specific providers instead of exclusions
  instances:
    - name: "web-server"
      provider: "aws"  # Specifically use AWS
      size: "medium"
      image: "RHEL9-latest"
```

### **3. GPU Cost Optimization**
```yaml
guid: "gpu01"

yamlforge:
  cloud_workspace:
    name: "gpu-optimization"
    description: "GPU cost-optimized deployment"

  instances:
    - name: "ml-workload"
      provider: "cheapest"  # Cost-optimized GPU deployment
      size: "gpu_small"
      gpu_type: "nvidia-tesla-v100"
      gpu_count: 1
      image: "RHEL9-latest"
```

## 📊 **Cost Optimization Features**

- **GPU-only optimization** (`cheapest-gpu` ignores CPU/memory, focuses on GPU cost)
- **Provider exclusion policies** (exclude expensive or unwanted providers)
- **Real-time cost comparison** across all enabled providers
- **Intelligent instance type mapping** for consistent cost comparisons

## 🚀 **Quick Start Examples**

### **Basic Cost Optimization**
```bash
# Run cheapest provider example
python3 ../../yamlforge.py cheapest_provider_example.yaml -d terraform-output/

# Mixed deployment with cost optimization
python3 ../../yamlforge.py mixed_cheapest_example.yaml -d terraform-output/
```

### **GPU Cost Optimization Approach**

For AI/ML workloads where GPU cost is the primary concern:

```yaml
yamlforge:
  instances:
    - name: ai-training
      provider: "cheapest-gpu"    # Ignores CPU/memory, focuses on GPU cost
      size: "gpu-medium"
      image: "RHEL9-latest"
      gpu:
        type: "nvidia-v100"
        count: 1

    - name: ai-inference  
      provider: "cheapest-gpu"    # Cheapest GPU of any type
      size: "gpu-small"
      image: "RHEL9-latest"       # Ignores cores/memory completely
      gpu:
        type: "any"
        count: 1
```

## 💡 **Cost Optimization Best Practices**

1. **Use `cheapest` provider** for CPU-focused workloads
2. **Use `cheapest-gpu` provider** for GPU-intensive applications
3. **Set provider exclusions** in `yamlforge.core.exclude_providers`
4. **Monitor costs** across different regions and instance types
5. **Test different configurations** to find optimal cost/performance balance

## 🔍 **Cost Analysis Output**

YamlForge provides detailed cost analysis during generation:

```bash
💰 Cost Analysis Results:
├── AWS us-east-1: $0.045/hour (t3.medium)
├── Azure East US: $0.052/hour (Standard_B2s) 
├── GCP us-central1: $0.048/hour (e2-medium)
└── ✅ Selected: AWS us-east-1 (lowest cost)
```

This enables you to make informed decisions about infrastructure costs while maintaining performance requirements. 
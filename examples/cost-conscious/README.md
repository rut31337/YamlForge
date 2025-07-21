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
yamlforge:
  instances:
    - name: cost-optimized-instance
      provider: "cheapest"  # Automatically selects lowest cost provider
      size: "small"
      image: "RHEL9-latest"
```

### **2. Provider Exclusions**
```yaml
yamlforge:
  core:
    exclude_providers:
      - "gcp"  # Exclude Google Cloud from cost comparisons
      - "azure"  # Exclude Azure from cost comparisons
```

### **3. GPU Cost Optimization**
```yaml
yamlforge:
  instances:
    - name: ml-workload
      provider: "cheapest-gpu"  # Focuses only on GPU costs
      size: "gpu-small"
      gpu:
        type: "any"
        count: 1
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
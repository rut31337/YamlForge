# AI/ML Training Infrastructure with YamlForge

YamlForge provides comprehensive support for AI/ML training workloads across multiple cloud providers with automatic cost optimization and GPU selection.

## Quick Start

### Basic GPU Training Setup

```yaml
guid: "ai001"

yamlforge:
  cloud_workspace:
    name: "ai-training-{guid}"
    description: "AI/ML training infrastructure"
  
  instances:
    - name: "training-gpu-{guid}"
      provider: "cheapest-gpu"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA T4"
      gpu_count: 1
```

### Multi-GPU Training Setup

```yaml
guid: "ai002"

yamlforge:
  cloud_workspace:
    name: "multi-gpu-training-{guid}"
    description: "Multi-GPU training setup"
  
  instances:
    - name: "multi-gpu-{guid}"
      provider: "cheapest-gpu"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA V100"
      gpu_count: 4
```

### Custom Specifications

```yaml
guid: "ai003"

yamlforge:
  cloud_workspace:
    name: "custom-gpu-training-{guid}"
    description: "Custom GPU specifications for training"
  
  instances:
    - name: "custom-gpu-{guid}"
      provider: "cheapest-gpu"
      cores: 16
      memory: 65536  # 64GB
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA A100"
      gpu_count: 2
```

## Cost Optimization Strategies

### 1. Spot Instances for Training

```yaml
guid: "spt01"

yamlforge:
  cloud_workspace:
    name: "spot-training-{guid}"
    description: "Cost-effective spot instance training"
  
  instances:
    - name: "spot-training-{guid}"
      provider: "cheapest-gpu"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA T4"
      gpu_count: 1
      # YamlForge automatically selects cheapest GPU provider
```

### 2. Multi-Cloud GPU Selection

```yaml
guid: "gpu01"

yamlforge:
  cloud_workspace:
    name: "multi-cloud-gpu-{guid}"
    description: "Multi-cloud GPU selection for training"
  
  instances:
    # Development - T4 GPU (cost-effective)
    - name: "dev-gpu-{guid}"
      provider: "cheapest-gpu"
      flavor: "small"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA T4"
      
    # Training - V100 GPU (performance)
    - name: "train-gpu-{guid}"
      provider: "cheapest-gpu"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA V100"
      
    # Production - A100 GPU (latest)
    - name: "prod-gpu-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA A100"
```

## Provider-Specific GPU Options

### AWS GPU Instances

```yaml
guid: "aws01"

yamlforge:
  cloud_workspace:
    name: "aws-gpu-training-{guid}"
    description: "AWS-specific GPU training setup"
  
  instances:
    - name: "aws-gpu-{guid}"
      provider: "aws"
      flavor: "gpu_large"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA T4"
      gpu_count: 1
```

### Azure GPU Instances

```yaml
guid: "az001"

yamlforge:
  cloud_workspace:
    name: "azure-gpu-training-{guid}"
    description: "Azure-specific GPU training setup"
  
  instances:
    - name: "azure-gpu-{guid}"
      provider: "azure"
      flavor: "gpu_medium"
      image: "RHEL9-latest"
      location: "eastus"
      gpu_type: "NVIDIA V100"
      gpu_count: 1
```

### GCP GPU Instances

```yaml
guid: "gcp01"

yamlforge:
  cloud_workspace:
    name: "gcp-gpu-training-{guid}"
    description: "GCP-specific GPU training setup"
  
  instances:
    - name: "gcp-gpu-{guid}"
      provider: "gcp"
      flavor: "gpu_large"
      image: "RHEL9-latest"
      location: "us-central1"
      gpu_type: "NVIDIA A100"
      gpu_count: 1
```

## Training Workflow Examples

### 1. Development → Training → Production Pipeline

```yaml
guid: "pip01"

yamlforge:
  cloud_workspace:
    name: "training-pipeline-{guid}"
    description: "Development to production training pipeline"
  
  instances:
    # Development environment
    - name: "dev-env-{guid}"
      provider: "cheapest"
      flavor: "small"
      image: "RHEL9-latest"
      location: "us-east-1"
      
    # Training environment
    - name: "train-env-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA V100"
      gpu_count: 2
      
    # Production inference
    - name: "prod-inference-{guid}"
      provider: "cheapest"
      flavor: "large"
      image: "RHEL9-latest"
      location: "us-east-1"
```

### 2. Distributed Training Setup

```yaml
guid: "dst01"

yamlforge:
  cloud_workspace:
    name: "distributed-training-{guid}"
    description: "Distributed training cluster setup"
  
  instances:
    # Control plane node
    - name: "controlplane-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA A100"
      gpu_count: 1
      
    # Worker nodes
    - name: "worker-1-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA A100"
      gpu_count: 1
      
    - name: "worker-2-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA A100"
      gpu_count: 1
```

## Cost Analysis

YamlForge automatically analyzes costs for GPU instances:

```bash
python yamlforge.py ai-training.yaml --analyze
```

**Sample Output:**
```
Instance Analysis:
- Name: training-gpu-ai01
- Provider: AWS (selected for cheapest GPU)
- Flavor: medium (g4dn.xlarge)
- GPU: NVIDIA T4 (1x)
- Estimated Cost: $0.526/hour
- Total Monthly: ~$378.72
```

## Best Practices

### 1. Size Selection Guidelines

Use these guidelines for different workloads:

- **Development/Testing** → `flavor: "small"`
- **Standard Training** → `flavor: "medium"`
- **Large Models** → `flavor: "large"`
- **Enterprise Training** → `flavor: "xlarge"`

### 2. GPU Selection

- **NVIDIA T4**: Cost-effective, good for development
- **NVIDIA V100**: Balanced performance/cost for training
- **NVIDIA A100**: Latest generation, best performance
- **NVIDIA L4**: Latest cost-effective option

### 3. Region Selection

- Use `location: "us-east-1"` for best GPU availability
- Consider spot instances for cost savings
- Use `provider: "cheapest-gpu"` for automatic optimization

## Advanced Configurations

### Custom Training Environment

```yaml
guid: "cst01"

yamlforge:
  cloud_workspace:
    name: "custom-training-{guid}"
    description: "Custom training environment with specific requirements"
  
  instances:
    - name: "custom-training-{guid}"
      provider: "cheapest-gpu"
      cores: 32
      memory: 131072  # 128GB
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA A100"
      gpu_count: 4
      user_data_script: |
        #!/bin/bash
        # Install CUDA, PyTorch, etc.
        yum install -y cuda-toolkit
        pip install torch torchvision
```

### Multi-Region Training

```yaml
guid: "mul01"

yamlforge:
  cloud_workspace:
    name: "multi-region-training-{guid}"
    description: "Multi-region training deployment"
  
  instances:
    - name: "training-east-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      location: "us-east-1"
      gpu_type: "NVIDIA V100"
      
    - name: "training-west-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      location: "us-west-2"
      gpu_type: "NVIDIA V100"
```

## Troubleshooting

### Common Issues

1. **GPU Not Available**: Try different regions or GPU types
2. **High Costs**: Use spot instances or smaller GPU types
3. **Performance Issues**: Upgrade to larger instances or better GPUs

### Cost Optimization Tips

1. Use `provider: "cheapest-gpu"` for automatic optimization
2. Consider spot instances for non-critical training
3. Use smaller GPU types for development
4. Monitor usage and scale down when not needed

## Next Steps

- [Cost Optimization Guide](features/cost-optimization.md)
- [Multi-Cloud GPU Support](features/multi-cloud.md)
- [Troubleshooting Guide](troubleshooting.md) 

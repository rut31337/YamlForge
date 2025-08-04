# AI/ML Training Infrastructure with YamlForge

YamlForge provides comprehensive support for AI/ML training workloads across multiple cloud providers with automatic cost optimization and GPU selection.

## Quick Start

### Basic GPU Training Setup

```yaml
guid: "ai01"

yamlforge:
  instances:
    - name: "training-gpu-{guid}"
      provider: "cheapest-gpu"
      flavor: "medium"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA T4"
      gpu_count: 1
```

### Multi-GPU Training Setup

```yaml
guid: "ai02"

yamlforge:
  instances:
    - name: "multi-gpu-{guid}"
      provider: "cheapest-gpu"
      flavor: "medium"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA V100"
      gpu_count: 4
```

### Custom Specifications

```yaml
guid: "ai03"

yamlforge:
  instances:
    - name: "custom-gpu-{guid}"
      provider: "cheapest-gpu"
      cores: 16
      memory: 65536  # 64GB
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA A100"
      gpu_count: 2
```

## Cost Optimization Strategies

### 1. Spot Instances for Training

```yaml
guid: "spot1"

yamlforge:
  instances:
    - name: "spot-training-{guid}"
      provider: "cheapest-gpu"
      flavor: "medium"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA T4"
      gpu_count: 1
      # YamlForge automatically selects cheapest GPU provider
```

### 2. Multi-Cloud GPU Selection

```yaml
guid: "gpu1"

yamlforge:
  instances:
    # Development - T4 GPU (cost-effective)
    - name: "dev-gpu-{guid}"
      provider: "cheapest-gpu"
      flavor: "small"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA T4"
      
    # Training - V100 GPU (performance)
    - name: "train-gpu-{guid}"
      provider: "cheapest-gpu"
      flavor: "medium"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA V100"
      
    # Production - A100 GPU (latest)
    - name: "prod-gpu-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA A100"
```

## Provider-Specific GPU Options

### AWS GPU Instances

```yaml
guid: "aws1"

yamlforge:
  instances:
    - name: "aws-gpu-{guid}"
      provider: "aws"
      flavor: "gpu_large"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA T4"
      gpu_count: 1
```

### Azure GPU Instances

```yaml
guid: "az1"

yamlforge:
  instances:
    - name: "azure-gpu-{guid}"
      provider: "azure"
      flavor: "gpu_medium"
      image: "RHEL9-latest"
      region: "eastus"
      gpu_type: "NVIDIA V100"
      gpu_count: 1
```

### GCP GPU Instances

```yaml
guid: "gcp1"

yamlforge:
  instances:
    - name: "gcp-gpu-{guid}"
      provider: "gcp"
      flavor: "gpu_large"
      image: "RHEL9-latest"
      region: "us-central1"
      gpu_type: "NVIDIA A100"
      gpu_count: 1
```

## Training Workflow Examples

### 1. Development → Training → Production Pipeline

```yaml
guid: "pipe1"

yamlforge:
  instances:
    # Development environment
    - name: "dev-env-{guid}"
      provider: "cheapest"
      flavor: "small"
      image: "RHEL9-latest"
      region: "us-east-1"
      
    # Training environment
    - name: "train-env-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA V100"
      gpu_count: 2
      
    # Production inference
    - name: "prod-inference-{guid}"
      provider: "cheapest"
      flavor: "large"
      image: "RHEL9-latest"
      region: "us-east-1"
```

### 2. Distributed Training Setup

```yaml
guid: "dist1"

yamlforge:
  instances:
    # Control plane node
    - name: "controlplane-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA A100"
      gpu_count: 1
      
    # Worker nodes
    - name: "worker-1-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA A100"
      gpu_count: 1
      
    - name: "worker-2-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      region: "us-east-1"
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

- Use `region: "us-east-1"` for best GPU availability
- Consider spot instances for cost savings
- Use `provider: "cheapest-gpu"` for automatic optimization

## Advanced Configurations

### Custom Training Environment

```yaml
guid: "cust1"

yamlforge:
  instances:
    - name: "custom-training-{guid}"
      provider: "cheapest-gpu"
      cores: 32
      memory: 131072  # 128GB
      image: "RHEL9-latest"
      region: "us-east-1"
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
guid: "multi1"

yamlforge:
  instances:
    - name: "training-east-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA V100"
      
    - name: "training-west-{guid}"
      provider: "cheapest-gpu"
      flavor: "large"
      image: "RHEL9-latest"
      region: "us-west-2"
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

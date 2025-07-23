# Quick Start Guide

Get up and running with YamlForge in 5 minutes!

## Step 1: Set Your GUID

Every YamlForge deployment needs a unique 5-character identifier:

```bash
# Set your unique identifier (5 chars, lowercase alphanumeric)
export GUID=web01
```

**Valid GUID examples:** `web01`, `app42`, `test1`, `dev99`, `prod1`

## Step 2: Choose an Example

Start with a pre-built example:

```bash
# Single cloud deployment
cp examples/simple_test.yaml my-first-deployment.yaml

# Multi-cloud deployment  
cp examples/multi-cloud/hybrid_rhel_deployment.yaml my-deployment.yaml

# Cost-optimized deployment
cp examples/cost-conscious/cheapest_provider_example.yaml my-deployment.yaml
```

## Step 3: Generate Terraform

```bash
# Create output directory
mkdir terraform-output

# Generate Terraform configuration
python yamlforge.py my-deployment.yaml -d terraform-output/
```

## Step 4: Deploy (Optional)

```bash
cd terraform-output/

# Initialize Terraform
terraform init

# Review the plan
terraform plan

# Apply (with confirmation)
terraform apply
```

## Example Configurations

### Multi-Cloud Setup

```yaml
guid: "web01"

yamlforge:
  cloud_workspace:
    name: "my-multi-cloud-app"

instances:
  - name: "web-aws"
    provider: "aws"
    size: "medium"
    image: "RHEL9-latest"
    region: "us-east-1"
    
  - name: "web-azure"
    provider: "azure"
    size: "medium"
    image: "RHEL9-latest"
    region: "us-east-1"
```

### Cost-Optimized Setup

```yaml
guid: "save01"

instances:
  - name: "api-server"
    provider: "cheapest"    # Automatically finds lowest cost
    size: "large"
    image: "RHEL9-latest"
    
  - name: "worker-nodes"
    provider: "cheapest"
    size: "medium"
    image: "RHEL9-latest"
    count: 3
```

### OpenShift Setup

```yaml
guid: "ocp01"

openshift_clusters:
  - name: "prod-cluster"
    type: "rosa-classic"
    region: "us-east-1"
    version: "4.14.15"
    size: "medium"
    worker_count: 3

openshift_applications:
  - name: "web-app"
    type: "deployment"
    cluster: "prod-cluster"
    image: "nginx:1.21"
    replicas: 2
    port: 80
```

## What Gets Generated

YamlForge creates:

- **`main.tf`** - Terraform resources (providers, networking, instances)
- **`variables.tf`** - Variable definitions with descriptions
- **`terraform.tfvars`** - Example variable values

## Common Patterns

### 1. Development Environment
```yaml
guid: "dev01"
instances:
  - name: "dev-server"
    provider: "aws"
    size: "small"
    image: "RHEL9-latest"
```

### 2. Production Environment
```yaml
guid: "prod1"
instances:
  - name: "web-tier"
    provider: "aws"
    size: "large"
    count: 3
    image: "RHEL9-latest"
    
  - name: "db-tier"
    provider: "aws"
    size: "xlarge"
    image: "RHEL9-latest"
```

### 3. GPU Workload
```yaml
guid: "gpu01"
instances:
  - name: "ml-training"
    provider: "cheapest-gpu"
    size: "gpu_large"
    gpu_count: 1
    gpu_type: "NVIDIA T4"
```

## Next Steps

- [GUID Configuration](guid-configuration.md) - Understand GUID requirements
- [Examples Gallery](examples.md) - Explore more examples
- [Multi-Cloud Support](features/multi-cloud.md) - Deep dive into multi-cloud
- [Cost Optimization](features/cost-optimization.md) - Save money with smart selection

## Need Help?

- Check [Troubleshooting](troubleshooting.md)
- Explore the [Examples Directory](../examples/)
- Review [Configuration Guides](configuration/) 
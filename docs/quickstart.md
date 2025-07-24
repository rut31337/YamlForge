# Quick Start Guide

Get up and running with YamlForge in 5 minutes!

## Step 1: Set Up Environment Variables

YamlForge requires environment variables for cloud credentials and configuration. Create an environment variables file:

### Create envvars.sh

**Option A: Use the template (Recommended)**

```bash
# Copy the example template and customize it
cp envvars.example.sh envvars.sh

# Edit with your credentials
nano envvars.sh  # or vim, code, etc.

# Load the environment variables
source envvars.sh
```

**Option B: Create from scratch**

```bash
# Create your environment variables file
cat > envvars.sh << 'EOF'
#!/bin/bash
# Required: Unique 5-character identifier
export GUID=web01

# AWS Credentials (required for AWS deployments)
export AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_KEY
export AWS_BILLING_ACCOUNT_ID=YOUR_AWS_BILLING_ACCOUNT_ID

# SSH Public Key (for instance access)
export SSH_PUBLIC_KEY="ssh-rsa YOUR_PUBLIC_KEY_HERE your-email@example.com"

# Red Hat OpenShift Token (required for ROSA/OpenShift deployments)
export REDHAT_OPENSHIFT_TOKEN=YOUR_REDHAT_TOKEN

# Add other cloud credentials as needed...
EOF

# Load the environment variables
source envvars.sh
```

### Quick Setup for Testing

For a minimal setup to get started quickly:

```bash
# Minimal environment for testing
export GUID=test1
export AWS_ACCESS_KEY_ID=your_key_here
export AWS_SECRET_ACCESS_KEY=your_secret_here
```

**Valid GUID examples:** `web01`, `app42`, `test1`, `dev99`, `prod1`

**Security Note:** Never commit `envvars.sh` to version control. Add it to `.gitignore`.

## Step 2: Choose an Example

Start with a pre-built example:

```bash
# Single cloud deployment
cp examples/testing/simple_test.yaml my-first-deployment.yaml

# Multi-cloud deployment  
cp examples/multi-cloud/hybrid_rhel_deployment.yaml my-deployment.yaml

# Cost-optimized deployment
cp examples/cost-conscious/cheapest_provider_example.yaml my-deployment.yaml

# OpenShift cluster deployment
cp examples/openshift/aws_openshift_simple_example.yaml my-deployment.yaml
```

## Step 3: Deploy Infrastructure

### Option A: Automated Deployment (Recommended)

```bash
# Generate and deploy everything automatically
python yamlforge.py my-deployment.yaml -d output/ --auto-deploy
```

### Option B: Manual Deployment

```bash
# Generate Terraform configuration
python yamlforge.py my-deployment.yaml -d output/

# Deploy manually
cd output/
terraform init
terraform plan
terraform apply
```

## Step 4: Verify Deployment

```bash
# Check what was created
cd output/
terraform show

# See output values
terraform output
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
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

# Azure Credentials (required for Azure deployments and ARO clusters)
# NOTE: ARO requires full subscription access, not compatible with shared resource groups
# Get from: az ad sp create-for-rbac --role="Contributor" --scopes="/subscriptions/YOUR_SUBSCRIPTION_ID"
export ARM_CLIENT_ID=YOUR_AZURE_CLIENT_ID
export ARM_CLIENT_SECRET=YOUR_AZURE_CLIENT_SECRET
export ARM_SUBSCRIPTION_ID=YOUR_AZURE_SUBSCRIPTION_ID  # Your Azure subscription ID
export ARM_TENANT_ID=YOUR_AZURE_TENANT_ID

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
    description: "Multi-cloud web application deployment"

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
      region: "eastus"
```

### Cost-Optimized Setup

```yaml
guid: "save01"

yamlforge:
  cloud_workspace:
    name: "cost-optimized-deployment"
    description: "Budget-friendly multi-cloud deployment"

  instances:
    - name: "api-server"
      provider: "cheapest"    # Automatically finds lowest cost
      size: "large"
      image: "RHEL9-latest"
      
    - name: "worker-nodes"
      provider: "cheapest"
      size: "medium"
      image: "RHEL9-latest"
```

### GCP Existing Project Setup

```yaml
guid: "gcp01"

yamlforge:
  cloud_workspace:
    name: "existing-project-deployment"
    description: "Deployment using existing GCP project"
  
  # Use existing GCP project instead of creating new one
  gcp:
    use_existing_project: true
    existing_project_id: "my-existing-project-123"

  instances:
    - name: "gcp-server"
      provider: "gcp"
      size: "medium"
      image: "RHEL9-latest"
      region: "us-central1"
```

### Azure Full Subscription Setup (Default)

```yaml
guid: "full01"

yamlforge:
  cloud_workspace:
    name: "full-subscription-deployment"
    description: "Multi-region deployment with full subscription access"

  instances:
    - name: "web-eastus"
      provider: "azure"
      size: "medium"
      image: "RHEL9-latest"
      region: "eastus"
    
    - name: "web-westus"
      provider: "azure"
      size: "medium"
      image: "RHEL9-latest"
      region: "westus2"  # Creates separate resource group automatically
```

### Azure Shared Subscription Setup

**Note:** This model is for Azure VMs only. ARO clusters require full subscription access.

```yaml
guid: "azu01"

yamlforge:
  cloud_workspace:
    name: "shared-subscription-deployment"
    description: "Deployment using existing Azure resource group (VMs only, not ARO)"
  
  # Use existing Azure resource group in shared subscription
  azure:
    use_existing_resource_group: true
    existing_resource_group_name: "rg-shared-dev-001"
    existing_resource_group_location: "eastus"

  instances:
    - name: "azure-server"
      provider: "azure"
      size: "medium"
      image: "RHEL9-latest"
      region: "eastus"
  
  # NOTE: ARO clusters not supported with shared resource groups
  # For ARO, use the "Azure Full Subscription Setup" instead
```

### OpenShift Setup

```yaml
guid: "ocp01"

yamlforge:
  cloud_workspace:
    name: "production-openshift"
    description: "Production OpenShift cluster deployment"

  openshift_clusters:
    - name: "prod-cluster"
      type: "rosa-classic"
      region: "us-east-1"
      version: "latest"
      size: "medium"
      worker_count: 3

  openshift_applications:
    - name: "web-app"
      target_cluster: "prod-cluster"
      namespace: "production"
      deployment:
        replicas: 2
        containers:
          - name: "web"
            image: "nginx:1.21"
            ports: [80]
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
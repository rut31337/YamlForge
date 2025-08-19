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

# Red Hat OpenShift Token (for ROSA/ARO)
export REDHAT_OPENSHIFT_TOKEN=YOUR_REDHAT_TOKEN
export OCP_PULL_SECRET='{"auths":{"fake":{"auth":"fake"}}}'  # Optional but recommended

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

### Option A: Analyze Configuration (Recommended First Step)

```bash
# Analyze configuration without generating Terraform
python yamlforge.py my-deployment.yaml --analyze
```

This shows you:
- Which providers will be selected for `cheapest` and `cheapest-gpu` instances
- Cost analysis for each instance
- Mapped regions, flavors, and images
- Required cloud providers

### Option B: Automated Deployment

```bash
# Generate and deploy everything automatically
python yamlforge.py my-deployment.yaml -d output/ --auto-deploy
```

### Option C: Manual Deployment

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
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east"
      
    - name: "web-azure"
      provider: "azure"
      flavor: "medium"
      image: "RHEL9-latest"
      region: "eastus"
```

### Cost-Optimized Setup

```yaml
guid: "sav01"

yamlforge:
  cloud_workspace:
    name: "cost-optimized-deployment"
    description: "Budget-friendly multi-cloud deployment"

  instances:
    - name: "api-server"
      provider: "cheapest"    # Automatically finds lowest cost
      flavor: "large"
      image: "RHEL9-latest"
      
    - name: "worker-nodes"
      provider: "cheapest"
      flavor: "medium"
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
      flavor: "medium"
      image: "RHEL9-latest"
      region: "us-central1"
```

### Azure Full Subscription Setup (Default)

```yaml
guid: "ful01"

yamlforge:
  cloud_workspace:
    name: "full-subscription-deployment"
    description: "Multi-region deployment with full subscription access"

  instances:
    - name: "web-eastus"
      provider: "azure"
      flavor: "medium"
      image: "RHEL9-latest"
      region: "eastus"
    
    - name: "web-westus"
      provider: "azure"
      flavor: "medium"
      image: "RHEL9-latest"
      region: "westus2"  # Creates separate resource group automatically
```

## Object Storage Quick Start

Deploy object storage buckets across multiple clouds:

```yaml
guid: "stor1"

yamlforge:
  cloud_workspace:
    name: "storage-quickstart-{guid}"
    description: "Multi-cloud object storage"
  
  storage:
    - name: "data-bucket-{guid}"
      provider: "aws"
      location: "us-east"
      public: false
      versioning: true
      encryption: true
      tags:
        Environment: "demo"
    
    - name: "backup-bucket-{guid}"
      provider: "cheapest"  # Auto-select cheapest provider
      location: "us-east"
      public: false
      versioning: false
      encryption: true
```

**Deploy storage:**
```bash
python yamlforge.py storage-config.yaml -d output/ --auto-deploy
```

See [Storage Documentation](storage.md) for detailed configuration options.

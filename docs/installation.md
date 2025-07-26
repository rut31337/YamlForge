# Installation Guide

## Prerequisites

- Python 3.8 or higher
- Git
- Terraform (for deployment - see installation below)

## Installation Options

### Full Installation (All Clouds)
```bash
# Clone the repository
git clone <repository-url>
cd yamlforge

# Install all cloud provider SDKs
pip install -r requirements.txt
```

### Targeted Installation
Choose the installation that matches your cloud usage:

```bash
# Major clouds only (AWS + GCP)
pip install -r requirements-major-clouds.txt

# Minimal installation (Azure, IBM, VMware - no SDKs needed)
pip install -r requirements-minimal.txt

# AWS only
pip install -r requirements-aws.txt

# GCP only  
pip install -r requirements-gcp.txt

# Oracle Cloud only
pip install -r requirements-oci.txt

# Alibaba Cloud only
pip install -r requirements-alibaba.txt
```

## Optional: GCP Dynamic Image Discovery

For advanced GCP features with automatic latest image discovery:

```bash
# Install GCP client library
pip install google-cloud-compute>=1.14.0

# Authenticate with GCP
gcloud auth application-default login

# Or set service account credentials
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

## Environment Setup

### Required: GUID Configuration

YamlForge requires a Global Unique Identifier (GUID) for DNS compliance:

```bash
# Set GUID environment variable (recommended)
export GUID=web01  # 5-char lowercase alphanumeric

# Verify it's set correctly
echo $GUID
```

### Optional: Cloud Provider Credentials

```bash
# AWS credentials (if using AWS features)
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"

# Azure credentials (if using Azure features)  
export ARM_CLIENT_ID="your-client-id"
export ARM_CLIENT_SECRET="your-secret"

# GCP credentials (if using GCP features)
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
```

## Terraform Installation

YamlForge generates Terraform configurations, so you'll need Terraform installed to deploy them:

> **⚠️ IMPORTANT: Terraform v1.12.0+ Required**  
> YamlForge requires **Terraform v1.12.0 or newer** for proper ROSA/OpenShift provider dependency resolution.  
> Older versions have known issues that cause deployment failures.

### Quick Install (Recommended)

```bash
# Linux/macOS (using tfswitch - version manager)
curl -L https://raw.githubusercontent.com/warrensbox/terraform-switcher/release/install.sh | bash
tfswitch  # Choose v1.12.0 or newer

# Alternative: Direct download (Linux)
wget https://releases.hashicorp.com/terraform/1.12.2/terraform_1.12.2_linux_amd64.zip
unzip terraform_1.12.2_linux_amd64.zip
sudo mv terraform /usr/local/bin/

# macOS (using Homebrew)
brew install terraform
# If you have an older version: brew upgrade terraform

# Windows (using Chocolatey)
choco install terraform
```

### Verify Terraform Installation

```bash
terraform version
# Should show: Terraform v1.12.x or higher
# Example output: Terraform v1.12.2
```

### Upgrade from Older Versions

If you have an older Terraform version, upgrade before using YamlForge:

```bash
# Check current version
terraform version

# Upgrade via package managers
# macOS (Homebrew)
brew upgrade terraform

# Linux (Ubuntu/Debian)
sudo apt update && sudo apt upgrade terraform

# Or download latest manually
wget https://releases.hashicorp.com/terraform/1.12.2/terraform_1.12.2_linux_amd64.zip
unzip terraform_1.12.2_linux_amd64.zip
sudo mv terraform /usr/local/bin/terraform

# Verify upgrade
terraform version
```

### Alternative Package Managers

```bash
# Ubuntu/Debian
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform

# RHEL/CentOS/Fedora
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo https://rpm.releases.hashicorp.com/fedora/hashicorp.repo
sudo dnf install terraform
```

## Verification

Test your installation:

```bash
# Test YamlForge with a simple example
export GUID=test1
python yamlforge.py examples/testing/simple_test.yaml -d test-output/

# Check generated files
ls test-output/
# Should show: main.tf, terraform.tfvars

# Test Terraform on generated files
cd test-output/
terraform init
terraform validate
# Should show: Success! The configuration is valid.
```

## Development Installation

For contributors:

```bash
# Clone for development
git clone <repository-url>
cd yamlforge

# Install in development mode
pip install -e .

# Install development dependencies
pip install -r requirements-dev.txt  # if available
```

## Troubleshooting

### Common Issues

**Missing GUID**
```
Error: GUID is required but not found
```
Solution: Set the GUID environment variable or add `guid: "abc12"` to your YAML.

**Python Version**
```
SyntaxError: invalid syntax
```
Solution: Ensure you're using Python 3.8 or higher.

**Missing Dependencies**
```
ModuleNotFoundError: No module named 'yaml'
```
Solution: Run `pip install -r requirements.txt`.

### Next Steps

- [Quick Start Guide](quickstart.md)
- [GUID Configuration](guid-configuration.md)
- [Examples Gallery](examples.md) 
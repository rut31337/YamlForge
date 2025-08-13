# Troubleshooting Guide

## Common Issues and Solutions

### 1. Invalid GUID Format

**Error**: `Invalid GUID format. Must be exactly 5 characters (lowercase alphanumeric)`

**Solution**: Use a 5-character lowercase alphanumeric identifier:

```yaml
# ✅ Correct
guid: "web01"
guid: "app42"
guid: "test1"

# ❌ Incorrect
guid: "web001"    # Too long
guid: "WEB01"     # Uppercase
guid: "web-01"    # Special characters
```

### 2. Missing Required Fields

**Error**: `Missing required field: provider`

**Solution**: Ensure all required fields are present:

```yaml
yamlforge:
  instances:
    - name: "web-server-{guid}"
      provider: "aws"        # ✅ Required
      flavor: "medium"       # ✅ Required (or cores/memory)
      image: "RHEL9-latest"  # ✅ Required
      region: "us-east-1"    # ✅ Required (except for CNV)
```

### 3. Invalid Provider

**Error**: `Invalid provider: 'invalid-provider'`

**Solution**: Use only supported providers:

```yaml
# ✅ Supported providers
provider: "aws"
provider: "azure"
provider: "gcp"
provider: "oci"
provider: "ibm_vpc"
provider: "ibm_classic"
provider: "vmware"
provider: "alibaba"
provider: "cheapest"
provider: "cheapest-gpu"
provider: "cnv"
```

### 4. Invalid Flavor

**Error**: `No mapping found for flavor 'invalid-flavor' on provider 'aws'`

**Solution**: Use valid flavors or custom specifications:

```yaml
# ✅ Valid flavors
flavor: "small"
flavor: "medium"
flavor: "large"
flavor: "xlarge"

# ✅ Custom specifications
cores: 4
memory: 8192  # 8GB in MB

# ✅ Provider-specific flavors
flavor: "t3.medium"      # AWS
flavor: "Standard_D4s_v3" # Azure
flavor: "n1-standard-4"   # GCP
```

### 5. Missing Cloud Credentials

**Error**: `No AWS credentials found`

**Solution**: Set up environment variables:

```bash
# Create envvars.sh
cp envvars.example.sh envvars.sh

# Edit with your credentials
nano envvars.sh

# Load environment variables
source envvars.sh
```

### 6. Invalid Region

**Error**: `Invalid region: 'invalid-region'`

**Solution**: Use valid regions or universal locations:

```yaml
# ✅ Universal locations (recommended)
region: "us-east"    # Maps to us-east-1, eastus, us-east1, etc.
region: "eu-west"    # Maps to eu-west-1, westeurope, europe-west1, etc.

# ✅ Provider-specific regions
region: "us-east-1"  # AWS
region: "eastus"     # Azure
region: "us-east1"   # GCP
```

### 7. GPU Configuration Issues

**Error**: `GPU type 'NVIDIA T4' not available in region 'us-west-2'`

**Solution**: Use available GPU types and regions:

```yaml
# ✅ Available GPU types
gpu_type: "NVIDIA T4"
gpu_type: "NVIDIA V100"
gpu_type: "NVIDIA A100"
gpu_type: "NVIDIA L4"
gpu_type: "NVIDIA L40S"
gpu_type: "NVIDIA K80"
gpu_type: "AMD RADEON PRO V520"

# ✅ Use cheapest-gpu for automatic selection
provider: "cheapest-gpu"
gpu_type: "NVIDIA T4"
```

### 8. OpenShift Cluster Issues

**Error**: `Worker count must be multiple of 3 for ROSA HCP`

**Solution**: Use correct worker counts:

```yaml
openshift_clusters:
  - name: "my-cluster"
    type: "rosa-hcp"
    worker_count: 3    # ✅ Multiple of 3
    worker_count: 6    # ✅ Multiple of 3
    worker_count: 9    # ✅ Multiple of 3
```

### 9. Cost Analysis Issues

**Error**: `No cost data available for provider 'vmware'`

**Solution**: Use providers with cost data or exclude from analysis:

```yaml
# Global provider exclusions
yamlforge:
  exclude_providers: ["vmware", "alibaba"]  # Exclude from cost analysis
  
  instances:
    - name: "web-server-{guid}"
      provider: "cheapest"  # Only considers providers with cost data
      flavor: "medium"
```

### 10. Terraform Generation Issues

**Error**: `Failed to generate Terraform: Invalid configuration`

**Solution**: Validate your configuration:

```bash
# Analyze configuration first
python yamlforge.py my-config.yaml --analyze

# Check for specific errors
python yamlforge.py my-config.yaml --verbose
```

## Debugging Commands

### 1. Configuration Analysis

```bash
# Analyze without generating Terraform
python yamlforge.py my-config.yaml --analyze

# Verbose analysis with detailed output
python yamlforge.py my-config.yaml --analyze --verbose
```

### 2. Schema Validation

```bash
# Validate YAML against schema
python yamlforge.py my-config.yaml --validate
```

### 3. Dry Run

```bash
# Generate Terraform without deploying
python yamlforge.py my-config.yaml -d output/ --no-credentials

# Review generated files
ls -la output/
cat output/main.tf
```

### 4. Provider Testing

```bash
# Test specific provider
python yamlforge.py my-config.yaml --analyze --provider aws

# Test with credentials
source envvars.sh
python yamlforge.py my-config.yaml --analyze
```

## Common Configuration Patterns

### 1. Development Environment

```yaml
guid: "dev01"

yamlforge:
  instances:
    - name: "dev-server-{guid}"
      provider: "cheapest"
      flavor: "small"
      image: "RHEL9-latest"
      region: "us-east-1"
```

### 2. Production Environment

```yaml
guid: "prod1"

yamlforge:
  instances:
    - name: "web-server-{guid}"
      provider: "aws"
      flavor: "large"
      image: "RHEL9-latest"
      region: "us-east-1"
      security_groups: ["web-access-{guid}"]
```

### 3. GPU Workload

```yaml
guid: "gpu01"

yamlforge:
  instances:
    - name: "gpu-training-{guid}"
      provider: "cheapest-gpu"
      flavor: "medium"
      image: "RHEL9-latest"
      region: "us-east-1"
      gpu_type: "NVIDIA T4"
      gpu_count: 1
```

## Environment Variable Checklist

Ensure these environment variables are set for your providers:

### AWS
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
```

### Azure
```bash
export ARM_CLIENT_ID=your_client_id
export ARM_CLIENT_SECRET=your_client_secret
export ARM_SUBSCRIPTION_ID=your_subscription_id
export ARM_TENANT_ID=your_tenant_id
```

### OpenShift
```bash
export REDHAT_OPENSHIFT_TOKEN=your_token
export OCP_PULL_SECRET='{"auths":{"fake":{"auth":"fake"}}}'  # Optional but recommended
```

## Getting Help

1. **Check the logs**: Use `--verbose` flag for detailed output
2. **Validate configuration**: Use `--analyze` to check before deployment
3. **Review examples**: Check the `examples/` directory for working configurations
4. **Check documentation**: Review provider-specific guides in `docs/`
5. **Test incrementally**: Start with simple configurations and add complexity

## Error Reporting

When reporting issues, include:

1. **YAML configuration** (with sensitive data removed)
2. **Error message** (full output)
3. **Environment**: OS, Python version, YamlForge version
4. **Steps to reproduce**
5. **Expected vs actual behavior** 

# Troubleshooting Guide

Common issues and solutions for YamlForge.

## Installation Issues

### Missing GUID Error
```
Error: GUID is required but not found
```

**Solution:**
```bash
# Option 1: Environment variable (recommended)
export GUID=web01

# Option 2: Add to YAML file
echo 'guid: "web01"' >> my-config.yaml
```

### Python Version Error
```
SyntaxError: invalid syntax
```

**Solution:** Ensure Python 3.8+
```bash
python --version  # Check version
python3 --version # Try python3 if python is older
```

### Missing Dependencies
```
ModuleNotFoundError: No module named 'yaml'
```

**Solution:**
```bash
pip install -r requirements.txt
```

## GUID Issues

### Invalid GUID Format
```
ValueError: GUID must be exactly 5 characters, lowercase alphanumeric
```

**Valid GUID Examples:**
- `web01` ✅
- `app42` ✅  
- `test1` ✅

**Invalid GUID Examples:**
- `WEB01` ❌ (uppercase)
- `web-01` ❌ (special characters)
- `web001` ❌ (too long)

## Cloud Provider Issues

### GCP Image Discovery
```
Warning: GCP credentials not configured. Using static image names.
```

**Solution:**
```bash
# Install GCP library
pip install google-cloud-compute>=1.14.0

# Authenticate
gcloud auth application-default login
```

### Missing Image Mappings
```
Warning: No image mapping found for 'CustomImage'
```

**Solution:** Add mapping to `mappings/images.yaml`

### Provider Not Found
```
ValueError: Unsupported provider 'invalid-provider'
```

**Supported Providers:**
- aws, azure, gcp
- ibm_vpc, ibm_classic
- oci, alibaba, vmware
- cheapest, cheapest-gpu

## OpenShift Issues

### Missing Cluster Type
```
ValueError: Cluster type must be specified
```

**Solution:** Add type to cluster config:
```yaml
openshift_clusters:
  - name: "my-cluster"
    type: "rosa-classic"  # Required!
    region: "us-east-1"
```

### Service Account Token Expired
```
Error: Unauthorized (401)
```

**Check Token Expiration:**
```bash
# Get token from Terraform output
ADMIN_TOKEN=$(terraform output -raw my_cluster_admin_token)

# Test token validity
kubectl auth whoami --token=$ADMIN_TOKEN
```

**Rotate Tokens:**
```bash
# Regenerate via Terraform
terraform taint kubernetes_secret.my_cluster_admin_token
terraform apply
```

## GPU Issues

### Invalid GPU Type
```
GPU type 'NVIDIA H100' is not available in any cloud provider
```

**Available GPU Types:**
- NVIDIA: A100, V100, T4, L4, L40S
- AMD: Radeon Pro V520

### GPU Provider Incompatibility
```
AMD GPU flavor 'gpu_amd_small' is only available on AWS
```

**Solution:** Use compatible provider:
```yaml
instances:
  - name: "amd-gpu"
    provider: "aws"  # AMD only on AWS
    size: "gpu_amd_small"
```

## Terraform Issues

### Output Directory Not Found
```
Error: Output directory 'terraform/' does not exist
```

**Solution:**
```bash
mkdir terraform-output
python yamlforge.py config.yaml -d terraform-output/
```

### Terraform Init Fails
```
Error: Failed to initialize Terraform
```

**Solution:**
```bash
cd terraform-output/
terraform version  # Check Terraform is installed (v1.12.0+ required)
terraform init      # Initialize
```

### Terraform Version Too Old
```
Error: Terraform Version Error: Version 1.5.7 is too old
```

**Solution:** Upgrade to Terraform v1.12.0+
```bash
# Check current version
terraform version

# Upgrade via package managers
brew upgrade terraform  # macOS
sudo apt upgrade terraform  # Linux

# Or download latest from https://developer.hashicorp.com/terraform/downloads
```

### Provider Dependency Conflicts
```
Error: Failed to query available provider packages
Could not retrieve the list of available versions for provider hashicorp/aws
```

**Cause:** Older Terraform versions have known issues with ROSA provider dependencies  
**Solution:** Upgrade to Terraform v1.12.0+ (see above)

## Common Validation Errors

### Duplicate Cluster Names
```
ValueError: Duplicate OpenShift cluster name 'prod-cluster'
```

**Solution:** Use unique cluster names:
```yaml
openshift_clusters:
  - name: "prod-rosa"     # Unique
    type: "rosa-classic"
  - name: "prod-aro"      # Unique  
    type: "aro"
```

### Missing Required Fields
```
ValueError: ROSA cluster 'my-cluster' must specify 'region'
```

**Solution:** Add all required fields:
```yaml
openshift_clusters:
  - name: "my-cluster"
    type: "rosa-classic"
    region: "us-east-1"    # Required
    version: "4.14.15"     # Required
    size: "medium"         # Required
```

## Performance Issues

### Slow Provider Detection
- **Cause:** Checking many providers
- **Solution:** Use provider exclusions in `defaults/core.yaml`

### Large Terraform Files
- **Cause:** Many instances/clusters
- **Solution:** Split into multiple YAML files

## Getting Help

### Debug Information
```bash
# Check Python version
python --version

# Check installed packages
pip list | grep -E "(yaml|google-cloud)"

# Test basic functionality
python yamlforge.py examples/simple_test.yaml -d test-output/
```

### Log Output
```bash
# Enable verbose output (if available)
python yamlforge.py config.yaml -d output/ --verbose

# Check Terraform logs
cd terraform-output/
export TF_LOG=DEBUG
terraform plan
```

### File Locations
- **Examples:** `examples/`
- **Mappings:** `mappings/`
- **Environment Variables:** Use `envvars.example.sh` as a template
- **Defaults:** `defaults/`

### Getting Support
1. Check this troubleshooting guide
2. Review [Examples Directory](../examples/)
3. Check [Configuration Guides](configuration/)
4. Create GitHub issue with:
   - YamlForge version
   - Python version
   - Complete error message
   - Minimal YAML that reproduces issue 
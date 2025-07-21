# Credentials Directory

This directory contains credential configuration files that document the required environment variables for each cloud provider. No manual secret creation or Kubernetes resources required - yamlforge automatically reads these configurations and sources credentials from environment variables.

## 📁 Directory Structure

### **Cloud Provider Credentials (Environment Variable Documentation)**
- **`aws.yaml`** - AWS credentials sourced from `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- **`azure.yaml`** - Azure credentials sourced from `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, etc.
- **`gcp.yaml`** - Google Cloud credentials sourced from `GCP_SERVICE_ACCOUNT_KEY`, `GCP_PROJECT_ID`
- **`ibm_classic.yaml`** - IBM Classic credentials sourced from `IBM_CLASSIC_USERNAME`, `IBM_CLASSIC_API_KEY`
- **`ibm_vpc.yaml`** - IBM VPC credentials sourced from `IBM_CLOUD_API_KEY`
- **`oci.yaml`** - Oracle Cloud credentials sourced from `OCI_USER_OCID`, `OCI_PRIVATE_KEY`, etc.
- **`vmware.yaml`** - VMware vSphere credentials sourced from `VSPHERE_SERVER`, `VSPHERE_USER`, etc.
- **`alibaba.yaml`** - Alibaba Cloud credentials sourced from `ALICLOUD_ACCESS_KEY`, `ALICLOUD_SECRET_KEY`

### **OpenShift Credentials**
- **`openshift.yaml`** - OpenShift cluster credentials sourced from `OPENSHIFT_CLUSTER_URL`, `OPENSHIFT_TOKEN`
- **`cert-manager.yaml`** - cert-manager EAB configuration (automatically read by yamlforge) ⭐

## 🚀 **How Credential Configuration Works**

All credential files follow the same simple pattern:

### **1. Set Environment Variables**
```bash
# Example for AWS
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_DEFAULT_REGION="us-east-1"
```

### **2. Run yamlforge (Automatically Uses Environment Variables)**
```bash
# yamlforge automatically detects and uses environment variables
yamlforge convert my-infrastructure.yaml
```

**That's it!** No manual secret creation, no Kubernetes resources to apply, no template substitution required.

## 🔐 **Cloud Provider Setup**

### **AWS Credentials**
```bash
# Set environment variables
export AWS_ACCESS_KEY_ID="AKIA1234567890EXAMPLE"
export AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
export AWS_DEFAULT_REGION="us-east-1"

# Run yamlforge (automatically uses environment variables)
yamlforge convert my-infrastructure.yaml
```

### **Azure Credentials**
```bash
# Create service principal
az ad sp create-for-rbac --name "yamlforge-sp" --role contributor

# Set environment variables from output
export AZURE_CLIENT_ID="12345678-1234-1234-1234-123456789012"
export AZURE_CLIENT_SECRET="your-client-secret"
export AZURE_TENANT_ID="87654321-4321-4321-4321-210987654321"
export AZURE_SUBSCRIPTION_ID="your-subscription-id"

# Run yamlforge (automatically uses environment variables)
yamlforge convert my-infrastructure.yaml
```

### **Google Cloud Credentials**
```bash
# Create service account and key
gcloud iam service-accounts create yamlforge-sa
gcloud iam service-accounts keys create ~/yamlforge-key.json --iam-account=yamlforge-sa@project.iam.gserviceaccount.com

# Set environment variables
export GCP_PROJECT_ID="your-project-id"
export GCP_SERVICE_ACCOUNT_KEY="$(cat ~/yamlforge-key.json)"

# Run yamlforge (automatically uses environment variables)
yamlforge convert my-infrastructure.yaml
```

### **Other Providers**
Each credential file (`oci.yaml`, `vmware.yaml`, `alibaba.yaml`, etc.) contains detailed setup instructions for that specific provider.

## 🚀 **OpenShift cert-manager: Single Source of Truth**

The cert-manager configuration in `credentials/cert-manager.yaml` is automatically read by yamlforge. No manual application required!

### **cert-manager Setup**
```bash
# 1. Set environment variables (only if using EAB providers)
export ZEROSSL_EAB_KID="your_zerossl_eab_kid"
export ZEROSSL_EAB_HMAC="your_zerossl_eab_hmac"

# 2. Enable providers in defaults/openshift_operators/security/cert_manager.yaml
# 3. Deploy cert-manager (yamlforge automatically reads credentials/cert-manager.yaml)
yamlforge convert my-openshift-config.yaml
```

## ✅ **Benefits of Environment Variable Configuration**

- **🔒 Maximum Security**: Credentials never stored in files, only in environment variables
- **⚡ Ultra Simple**: Just set environment variables and run yamlforge
- **🎯 GitOps Ready**: All configuration files are safe to commit (no actual credentials)
- **🔄 Fully Automated**: No manual secret creation or Kubernetes resource application
- **🛡️ Consistent**: Standardized approach across all cloud providers
- **🔧 CI/CD Friendly**: Perfect for automated pipelines and secret management systems

## 🔒 Security Best Practices

### **Environment Variable Security**
- **✅ Use secure storage** (CI/CD secrets, password managers, vault systems)
- **✅ Limit environment access** to necessary personnel
- **✅ Use temporary credentials** where possible
- **✅ Rotate credentials regularly** according to provider policies
- **✅ Never commit credentials** to version control

### **Configuration File Security**
- **✅ Configuration files are safe to commit** (contain no actual credentials)
- **✅ Document required environment variables** for team members
- **✅ Use descriptive variable names** for clarity
- **✅ Include validation commands** to verify setup

### **Production Recommendations**
- **✅ Use External Secrets Operator** to inject from external systems (Vault, AWS Secrets Manager)
- **✅ Use CI/CD secret management** for automated deployments
- **✅ Monitor credential usage** through application logs
- **✅ Use service accounts** instead of personal credentials for automation

## 📋 Quick Reference

### **Environment Variable Patterns**
| **Provider** | **Key Variables** | **Configuration File** |
|--------------|------------------|------------------------|
| **AWS** | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | `aws.yaml` |
| **Azure** | `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID` | `azure.yaml` |
| **GCP** | `GCP_SERVICE_ACCOUNT_KEY`, `GCP_PROJECT_ID` | `gcp.yaml` |
| **OCI** | `OCI_USER_OCID`, `OCI_PRIVATE_KEY`, `OCI_TENANCY_OCID` | `oci.yaml` |
| **VMware** | `VSPHERE_SERVER`, `VSPHERE_USER`, `VSPHERE_PASSWORD` | `vmware.yaml` |
| **Alibaba** | `ALICLOUD_ACCESS_KEY`, `ALICLOUD_SECRET_KEY` | `alibaba.yaml` |
| **IBM Classic** | `IBM_CLASSIC_USERNAME`, `IBM_CLASSIC_API_KEY` | `ibm_classic.yaml` |
| **IBM VPC** | `IBM_CLOUD_API_KEY` | `ibm_vpc.yaml` |
| **OpenShift** | `OPENSHIFT_CLUSTER_URL`, `OPENSHIFT_TOKEN` | `openshift.yaml` |
| **cert-manager** | `ZEROSSL_EAB_*` (auto-read) | `cert-manager.yaml` |

### **Standard Workflow**
```bash
# 1. Set environment variables for your provider(s)
export PROVIDER_KEY="your_value"

# 2. Run yamlforge (automatically detects and uses environment variables)
yamlforge convert my-infrastructure.yaml
```

## 🆘 Troubleshooting

### **Common Issues**

#### **Environment Variables Not Set**
```bash
# Error: required environment variable not set
# Solution: Verify all required variables are exported
env | grep AWS_  # Check AWS variables
env | grep AZURE_  # Check Azure variables
```

#### **Credentials Not Detected**
```bash
# Error: credentials not found
# Solution: Ensure environment variables are properly exported
echo $AWS_ACCESS_KEY_ID  # Verify variable is set
export AWS_ACCESS_KEY_ID="your_value"  # Set if missing
```

#### **Invalid Credentials**
```bash
# Error: authentication failed
# Solution: Verify credentials are correct and have proper permissions
# Test credentials using provider CLI tools before setting environment variables
```

#### **Permission Denied**
```bash
# Error: insufficient permissions
# Solution: Verify credentials have required permissions as documented in configuration files
```

For detailed setup instructions and troubleshooting, see the provider-specific documentation in each configuration file. 
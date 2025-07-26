# Defaults Directory

This directory contains default configuration files for each cloud provider. These files define fallback settings used when specific environment variables or configurations are not available.

## Structure

### **`aws.yaml`**
**AWS Default Configuration**
- **AMI Owners**: Predefined owner IDs for different image types (Red Hat, Fedora, Amazon, Canonical, Microsoft)
- **Features**: AWS-specific feature configurations (assume role duration)
- **Usage**: Always loaded for AMI owner mappings and AWS-specific settings (required regardless of credentials)

### **`azure.yaml`**
**Azure Default Configuration**
- **Features**: Azure-specific feature configurations
- **Usage**: Reserved for future Azure-specific defaults

### **`ibm_classic.yaml`**
**IBM Cloud Classic Infrastructure Defaults**
- **Features**: IBM Classic-specific configurations
- **Usage**: Reserved for IBM Classic infrastructure defaults

### **`ibm_vpc.yaml`**
**IBM Cloud VPC Infrastructure Defaults**
- **Features**: IBM VPC-specific configurations  
- **Usage**: Reserved for IBM VPC infrastructure defaults

### **`openshift.yaml`**
**OpenShift Default Configuration**
- **Default Base Networking**: Default CIDR blocks for service, pod, and machine networks per cluster type (can be overridden in input YAML)
- **Sizing**: Default cluster sizes (micro, small, medium, large, xlarge) with master/worker counts
- **Features**: OpenShift-specific feature defaults (security, auto-scaling, addons)
- **Usage**: Always loaded by OpenShift provider for networking and cluster configuration defaults

## Usage Pattern

Each cloud provider's resolver has different configuration needs:

1. **AWS**: Always loads `defaults/aws.yaml` for AMI owner mappings, then uses environment variables for dynamic API calls
2. **GCP**: Uses environment variables for authentication, uses built-in image discovery settings when credentials unavailable
3. **Azure/IBM**: Uses environment variables for authentication (defaults reserved for future use)

## Example: Configuration Sources

```yaml
# AWS: defaults/aws.yaml (AMI owners) + environment variables (API access)
# GCP: environment variables (API access) → built-in settings (image discovery)
# Azure/IBM: environment variables (API access) only
# OpenShift: defaults/openshift.yaml (networking, sizing) → Always loaded
```

## Benefits

- **Separation of Concerns**: Static configuration (defaults) separate from secrets (credentials)
- **Essential Mappings**: Provider-specific mappings (like AMI owners) externalized from code
- **Maintainability**: Configuration changes don't require code modifications
- **Consistency**: Standardized approach across cloud providers 
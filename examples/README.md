# YamlForge Examples

This directory contains comprehensive examples demonstrating YamlForge's multi-cloud infrastructure capabilities across AWS, Azure, Google Cloud, Oracle Cloud, VMware vSphere, Alibaba Cloud, IBM Cloud, and OpenShift platforms.

## Quick Start

```bash
# Basic multi-cloud example with auto-deploy
python3 ../yamlforge.py testing/simple_test.yaml -d output/ --auto-deploy

# Cost-optimized deployment
python3 ../yamlforge.py cost-conscious/cheapest_provider_example.yaml -d output/

# OpenShift cluster deployment
python3 ../yamlforge.py openshift/aws_openshift_simple_example.yaml -d output/ --auto-deploy
```

## Example Categories

### Testing Examples (`testing/`)
```
testing/
├── simple_test.yaml              # Single cloud deployment
├── multi_provider_example.yaml   # Multi-cloud setup
├── rhel_gold_test.yaml           # RHEL Gold images
├── rhel_latest_test.yaml         # Public RHEL images
├── fedora_example.yaml           # Fedora deployment
├── provider_selection_example.yaml # Provider comparison
├── cloud_workspace_example.yaml  # Development environments
└── tags_example.yaml             # Resource tagging
```

### Cost-Conscious Examples (`cost-conscious/`)
```
cost-conscious/
├── cheapest_provider_example.yaml # Automatic cheapest provider
└── mixed_cheapest_example.yaml    # Mixed cost optimization
```

### Cloud-Specific Examples (`cloud-specific/`)
```
cloud-specific/
├── architecture_example.yaml      # Multi-region architecture
├── gcp_example.yaml              # Google Cloud focused
├── gcp_dynamic_example.yaml      # Dynamic image discovery
├── ibm_classic_example.yaml      # IBM Classic Infrastructure  
├── ibm_modern_example.yaml       # IBM Cloud VPC
└── ibm_vpc_example.yaml          # IBM VPC networking
```

### Multi-Cloud Examples (`multi-cloud/`)
```
multi-cloud/
├── hybrid_rhel_deployment.yaml   # Hybrid cloud setup
├── cloud_access_test.yaml       # Cloud access validation
└── rhel_gold_vs_public_test.yaml # Image comparison
```

### Extended Provider Examples (`extended-providers/`)
```
extended-providers/
├── oci_example.yaml              # Oracle Cloud Infrastructure
├── vmware_example.yaml           # VMware vSphere
├── alibaba_example.yaml          # Alibaba Cloud
└── hybrid_multi_cloud.yaml      # All providers combined
```

### OpenShift Examples (`openshift/`)
```
openshift/
├── rosa_basic_example.yaml       # ROSA cluster
├── aro_basic_example.yaml        # Azure Red Hat OpenShift
├── self_managed_example.yaml     # Self-managed OpenShift
└── operators_example.yaml       # OpenShift operators
```

### Region & Networking (`region-and-networking/`)
```
region-and-networking/
├── region_specification_example.yaml # Multi-region deployment
├── security_groups_example.yaml      # Security configuration
└── subnets_example.yaml             # Custom networking
```

## Example Types by Use Case

### Enterprise Examples
- **Images**: RHEL Gold images with Red Hat Cloud Access
- **Support**: Enterprise support and compliance
- **Networking**: Advanced security groups and VPC configuration

### Development Examples  
- **Images**: Public RHEL versions across all clouds
- **Cost**: Cost-optimized deployments
- **Testing**: Multi-provider validation and testing

### AI/ML Examples
- **GPU Support**: Automatic GPU instance selection
- **Cost Optimization**: GPU-focused cost analysis
- **Performance**: High-performance computing configurations

## Usage Patterns

### Single Cloud Deployment
```yaml
yamlforge:
  providers: ["aws"]
  instances:
    - name: web-server
      provider: aws
      size: "medium"
      image: "RHEL9-latest"
```

### Multi-Cloud Deployment
```yaml
yamlforge:
  providers: ["aws", "azure", "gcp"]
  instances:
    - name: web-east
      provider: aws
      region: "us-east-1"
    - name: web-west  
      provider: azure
      region: "West US 2"
    - name: web-europe
      provider: gcp
      region: "europe-west1"
```

### Cost-Optimized Deployment
```yaml
yamlforge:
  instances:
    - name: cost-optimized
      provider: "cheapest"  # Automatically selects lowest cost
      size: "small"
      image: "RHEL9-latest"
```

## Testing Framework

YamlForge includes a comprehensive testing framework:

#### `simple_test.yaml`
**Basic functionality testing**
- **Clouds**: AWS, Azure, GCP
- **Images**: Standard RHEL 9 images
- **Purpose**: Validate core converter functionality

#### `multi_provider_example.yaml`
**Multi-cloud validation**
- **Clouds**: All supported providers
- **Images**: Consistent RHEL deployment
- **Purpose**: Test provider abstraction and consistency

#### `rhel_latest_test.yaml`
**Public image testing**
- **Images**: RHEL 9 public images
- **Purpose**: Validate public image resolution

#### `rhel_gold_test.yaml`
**Enterprise image testing**  
- **Images**: RHEL Gold with Cloud Access
- **Purpose**: Validate enterprise image resolution

#### `provider_selection_example.yaml`
**Provider comparison testing**
- **Feature**: Automatic provider selection
- **Purpose**: Test cheapest provider logic

### Running Tests

```bash
# Basic functionality test
python3 ../yamlforge.py testing/simple_test.yaml

# Multi-cloud validation
python3 ../yamlforge.py testing/multi_provider_example.yaml

# Public image testing
python3 ../yamlforge.py testing/rhel_latest_test.yaml

# Enterprise image testing
python3 ../yamlforge.py testing/rhel_gold_test.yaml
```

## Infrastructure Patterns

### Development Environment
```bash
# Development setup
python3 ../yamlforge.py testing/cloud_workspace_example.yaml
```

### Production Deployment
```bash  
# Production multi-cloud
python3 ../yamlforge.py multi-cloud/hybrid_rhel_deployment.yaml
```

### Cost-Conscious Deployment
```bash
# Cost optimization
python3 ../yamlforge.py cost-conscious/cheapest_provider_example.yaml
```

## Example Features

- **Multi-Cloud Support**: AWS, Azure, GCP, OCI, VMware, Alibaba, IBM
- **Image Management**: Automatic resolution and validation
- **Cost Optimization**: Intelligent provider selection
- **Public Images**: RHEL versions across all clouds
- **Enterprise Images**: RHEL Gold with Cloud Access support
- **Dynamic Discovery**: Automatic image resolution (GCP)
- **Hybrid Deployments**: Cloud + on-premises integration
- **Resource Tagging**: Consistent labeling across providers

## Learning Path

1. **Start with Testing**: Begin with `testing/rhel_latest_test.yaml` for basic concepts
2. **Explore Multi-Cloud**: Try `multi-cloud/hybrid_rhel_deployment.yaml`
3. **Cost Optimization**: Use `cost-conscious/cheapest_provider_example.yaml`
4. **Advanced Features**: Explore OpenShift and extended providers
5. **Production Ready**: Implement with enterprise images and networking

## Best Practices

- **Use consistent naming** across cloud providers
- **Leverage cost optimization** with `cheapest` provider
- **Implement proper tagging** for resource management
- **Test across multiple clouds** before production deployment
- **Use enterprise images** for production workloads

## Example Structure

Each example follows a consistent structure:

```yaml
yamlforge:
  providers: [...]          # Cloud providers to use
  core:                     # Global configuration
    exclude_providers: [...] # Optional provider exclusions
  instances:               # Virtual machine definitions
    - name: "server-name"
      provider: "aws"       # Specific or "cheapest"
      size: "medium"        # Standard size mapping
      image: "RHEL9-latest"
```

This structure ensures consistency and predictability across all deployment scenarios. 
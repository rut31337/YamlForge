# OpenShift Documentation Overview

Comprehensive documentation for all OpenShift deployment options supported by YamlForge.

## OpenShift Providers

YamlForge supports multiple OpenShift deployment methods across different cloud providers and deployment models:

### Cloud-Managed OpenShift Services

#### **Azure Red Hat OpenShift (ARO)**
- **Provider**: `aro`
- **Documentation**: [ARO Guide](aro-guide.md)
- **Cloud**: Microsoft Azure
- **Management**: Fully managed by Microsoft and Red Hat
- **Features**: Complete Terraform automation, automatic service principal creation, enhanced networking

```yaml
openshift_clusters:
  - name: "prod-aro"
    type: "aro"
    region: "eastus"
    version: "4.18.19"
    size: "medium"
```

#### **Red Hat OpenShift Service on AWS (ROSA)**
- **Provider**: `rosa-classic` | `rosa-hcp`
- **Cloud**: Amazon Web Services
- **Management**: Fully managed by Red Hat on AWS
- **Features**: CLI and Terraform deployment methods, automatic IAM role management

**ROSA Classic:**
```yaml
openshift_clusters:
  - name: "prod-rosa"
    type: "rosa-classic"
    region: "us-east-1"
    version: "4.18.19"
    size: "medium"
```

**ROSA with Hosted Control Planes (HCP):**
```yaml
openshift_clusters:
  - name: "prod-rosa-hcp"
    type: "rosa-hcp"
    region: "us-east-1"
    version: "4.18.19"
    size: "medium"
```

#### **Red Hat OpenShift Dedicated**
- **Provider**: `openshift-dedicated`
- **Cloud**: Multiple (AWS, GCP)
- **Management**: Fully managed by Red Hat
- **Features**: Enterprise-grade managed OpenShift

```yaml
openshift_clusters:
  - name: "dedicated-cluster"
    type: "openshift-dedicated"
    region: "us-east-1"
    version: "4.18.19"
    size: "large"
```

### Self-Managed OpenShift

#### **Self-Managed OpenShift**
- **Provider**: `self-managed`
- **Cloud**: Any supported cloud provider
- **Management**: Customer managed
- **Features**: Full control, custom configurations

```yaml
openshift_clusters:
  - name: "self-managed"
    type: "self-managed"
    region: "us-east-1"
    version: "4.18.19"
    size: "large"
```

### HyperShift Deployments

#### **HyperShift Hosted Clusters**
- **Provider**: `hypershift`
- **Cloud**: AWS (primary), others supported
- **Management**: Hosted control planes
- **Features**: Cost-effective, rapid scaling

```yaml
openshift_clusters:
  - name: "hypershift-cluster"
    type: "hypershift"
    region: "us-east-1"
    version: "4.18.19"
    size: "medium"
```

## Deployment Features

### Multi-Cloud Support
Deploy OpenShift clusters across multiple cloud providers:

```yaml
openshift_clusters:
  # ARO on Azure
  - name: "azure-cluster"
    type: "aro"
    region: "eastus"
    
  # ROSA on AWS
  - name: "aws-cluster"
    type: "rosa-classic"
    region: "us-east-1"
    
  # Self-managed on GCP
  - name: "gcp-cluster"
    type: "self-managed"
    provider: "gcp"
    region: "us-central1"
```

### Application Deployment
Deploy applications across OpenShift clusters:

```yaml
openshift_applications:
  - type: "multi-cluster"
    name: "monitoring-stack"
    clusters: ["azure-cluster", "aws-cluster"]
    applications:
      - name: "prometheus"
        namespace: "monitoring"
        source: "helm"
```

### Operator Management
Install and manage OpenShift operators:

```yaml
openshift_operators:
  - type: "single-cluster"
    cluster: "azure-cluster"
    operators:
      - name: "openshift-gitops"
        namespace: "openshift-gitops"
        channel: "gitops-1.12"
```

## Provider-Specific Documentation

### **Azure Red Hat OpenShift (ARO)**
- **[Complete ARO Guide](aro-guide.md)** - Comprehensive documentation
- **Example**: [ARO Complete Example](../../examples/openshift/aro_complete_example.yaml)
- **Features**: Terraform automation, service principal management, networking

### **Red Hat OpenShift Service on AWS (ROSA)**
- **[ROSA Dynamic Versions](../ROSA_DYNAMIC_VERSIONS.md)** - Version management
- **Examples**: 
  - [ROSA Classic vs HCP](../../examples/openshift/rosa_classic_vs_hcp_example.yaml)
  - [ROSA Automatic Phases](../../examples/openshift/rosa_automatic_phases_example.yaml)

### **Multi-Cloud OpenShift**
- **Examples**:
  - [Multi-Cloud OpenShift](../../examples/openshift/multi_cloud_openshift_example.yaml)
  - [Complete Enterprise Platform](../../examples/openshift/complete_enterprise_platform_example.yaml)

## Getting Started

### Quick Start
1. **Choose your provider** based on your cloud and requirements
2. **Set up credentials** for your chosen cloud provider
3. **Create configuration** using the examples above
4. **Deploy** using YamlForge

```bash
# Set environment variables
export GUID=ocp01

# For ARO (Azure)
export ARM_CLIENT_ID=your_client_id
export ARM_CLIENT_SECRET=your_secret
export ARM_SUBSCRIPTION_ID=your_subscription
export ARM_TENANT_ID=your_tenant

# Deploy ARO cluster
python yamlforge.py aro-config.yaml -d aro-terraform/
cd aro-terraform/
terraform init && terraform apply
```

### Common Configuration Options

#### Cluster Sizes
All OpenShift providers support standardized cluster sizes:

- **Small**: Development and testing (3 workers)
- **Medium**: Small production workloads (4 workers)
- **Large**: High-performance production (6+ workers)

#### Security Options
```yaml
openshift_clusters:
  - name: "secure-cluster"
    type: "aro"  # or rosa-classic, etc.
    private: true           # Private API and ingress
    fips_enabled: true      # FIPS compliance
```

#### Networking Customization
```yaml
openshift_clusters:
  - name: "custom-network"
    type: "aro"
    networking:
      vnet_cidr: "10.1.0.0/16"
      pod_cidr: "10.128.0.0/14"
      service_cidr: "172.30.0.0/16"
```

## Best Practices

### Production Deployments
1. **Use managed services** (ARO, ROSA) for operational simplicity
2. **Enable private clusters** for enhanced security
3. **Implement FIPS validation** for compliance requirements
4. **Use large cluster sizes** for production workloads
5. **Deploy across multiple regions** for high availability

### Development Environments
1. **Use smaller cluster sizes** to reduce costs
2. **Public clusters** for easier access during development
3. **Regular cleanup** of unused clusters and resources

### Multi-Cloud Strategy
1. **Standardize on OpenShift** across all clouds
2. **Use GitOps** for consistent application deployment
3. **Implement monitoring** across all clusters
4. **Plan for data sovereignty** requirements

## Architecture Patterns

### Hub and Spoke Model
```yaml
openshift_clusters:
  # Hub cluster for management
  - name: "hub-cluster"
    type: "rosa-classic"
    region: "us-east-1"
    size: "large"
    
  # Spoke clusters for workloads
  - name: "spoke-azure"
    type: "aro"
    region: "eastus"
    size: "medium"
    
  - name: "spoke-gcp"
    type: "self-managed"
    provider: "gcp"
    region: "us-central1"
    size: "medium"
```

### Regional Distribution
```yaml
openshift_clusters:
  # US East
  - name: "us-east-cluster"
    type: "aro"
    region: "eastus"
    
  # US West
  - name: "us-west-cluster"
    type: "rosa-hcp"
    region: "us-west-2"
    
  # Europe
  - name: "eu-cluster"
    type: "aro"
    region: "northeurope"
```

## Cost Optimization

### Provider Selection
- **ARO**: Often cost-effective for Azure-centric environments
- **ROSA**: Excellent for AWS-native workloads
- **Self-Managed**: Maximum control but higher operational overhead

### Resource Sizing
- Start with **medium** clusters for most workloads
- Scale to **large** for high-performance requirements
- Use **small** only for development and testing

### Regional Considerations
- Choose regions close to users for performance
- Consider data residency requirements
- Factor in regional pricing differences

## Troubleshooting

### Common Issues
1. **Authentication failures** - Verify cloud credentials
2. **Version compatibility** - Use supported OpenShift versions
3. **Network conflicts** - Ensure unique CIDR ranges
4. **Resource limits** - Check cloud provider quotas

### Support Resources
- [Troubleshooting Guide](../troubleshooting.md)
- [Installation Guide](../installation.md)
- [Examples Gallery](../examples.md)

---

**Implementation Locations:**
- **ARO Provider**: `yamlforge/providers/openshift/aro.py`
- **ROSA Provider**: `yamlforge/providers/openshift/rosa.py`
- **Base Provider**: `yamlforge/providers/openshift/base.py`
- **Configuration**: `mappings/flavors_openshift/` 
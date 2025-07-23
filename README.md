# YamlForge - Multi-Cloud Infrastructure as Code and PaaS Management Suite

> **⚠️ ALPHA SOFTWARE WARNING ⚠️**  
> **This is v0.99 ALPHA - Work in Progress**  
> **Use at your own risk. Not recommended for production environments.**

A comprehensive enterprise-grade platform for managing multi-cloud infrastructure and Platform-as-a-Service deployments through unified YAML definitions.

## 🚀 Quick Start

### Installation
```bash
git clone <repository-url>
cd yamlforge
pip install -r requirements.txt

# Verify Terraform v1.12.0+ is installed
terraform version  # Should show v1.12.0 or newer
```

> **⚠️ Requirement:** Terraform v1.12.0+ required for ROSA/OpenShift support

### Basic Usage
```bash
# Set required GUID (5-char lowercase alphanumeric)
export GUID=web01

# Generate Terraform
python yamlforge.py examples/simple_test.yaml -d terraform/
```

## 🌐 Supported Platforms

### **Cloud Providers**
- **AWS** - Native EC2, VPC, Security Groups
- **Azure** - Virtual Machines, VNets, Network Security Groups  
- **GCP** - Compute Engine with dynamic image discovery
- **IBM Cloud** - VPC Gen 2 and Classic Infrastructure
- **Oracle Cloud (OCI)** - Compute instances and networking
- **Alibaba Cloud** - ECS instances and VPC
- **VMware vSphere** - Virtual machines and networking

### **OpenShift Platforms**
- **ROSA** (Classic & HCP) - Red Hat OpenShift Service on AWS
- **ARO** - Azure Red Hat OpenShift
- **OpenShift Dedicated** - Managed OpenShift clusters
- **Self-Managed** - Custom OpenShift deployments
- **HyperShift** - Hosted control planes

## 🎯 Key Features

- **🌍 Multi-Cloud** - Deploy across all major cloud providers
- **💰 Cost Optimization** - Automatic cheapest provider selection
- **🎮 GPU Support** - Complete GPU instance support with cost analysis
- **🔑 GUID-Based** - Unique deployment identification (5-char required)
- **🤖 Auto-Discovery** - Automatic flavor recommendation
- **🔒 Enterprise Security** - Red Hat Cloud Access, service accounts
- **⚡ Smart Detection** - Only includes Terraform providers you use

## 📚 Documentation

### **Getting Started**
- [Installation Guide](installation.md)
- [Quick Start Guide](quickstart.md)
- [GUID Configuration](guid-configuration.md)
- [Examples Gallery](examples.md)

### **Features**
- [Multi-Cloud Support](features/multi-cloud.md)
- [Cost Optimization](features/cost-optimization.md)
- [GPU Support](features/gpu-support.md)
- [Auto Discovery](features/auto-discovery.md)

### **OpenShift**
- [OpenShift Overview](openshift/overview.md)
- [Cluster Management](openshift/clusters.md)
- [Application Deployment](openshift/applications.md)
- [Security & Service Accounts](openshift/security.md)

### **Configuration**
- [Mappings & Flavors](configuration/mappings.md)
- [Credentials Setup](configuration/credentials.md)
- [Networking](configuration/networking.md)

### **Help**
- [Troubleshooting](troubleshooting.md)
- [Examples Directory](../examples/)

## 🔧 Example Configuration

```yaml
guid: "web01"  # Required: 5-char unique identifier

yamlforge:
  cloud_workspace:
    name: "multi-cloud-demo"
    
instances:
  # Multi-cloud deployment
  - name: "web-aws"
    provider: "aws"
    size: "medium"
    image: "RHEL9-latest"
    
  - name: "web-azure"
    provider: "azure"
    size: "medium"
    image: "RHEL9-latest"
    
  # Cost optimization
  - name: "api-cheapest"
    provider: "cheapest"    # Automatically selects lowest cost
    size: "large"
    image: "RHEL9-latest"
```

## 🎮 OpenShift Example

```yaml
guid: "ocp01"

openshift_clusters:
  - name: "prod-rosa"
    type: "rosa-classic"
    region: "us-east-1"
    version: "4.14.15"
    size: "medium"

openshift_applications:
  - name: "frontend"
    type: "deployment"
    cluster: "prod-rosa"
    image: "nginx:1.21"
    replicas: 3
```

## 📊 Output

YamlForge generates production-ready Terraform with:
- **Native cloud resources** (no abstractions)
- **Smart provider detection** (only includes what you use)
- **Complete networking** (VPCs, subnets, security groups)
- **Service accounts** (automatic OpenShift credential management)
- **Cost optimization** (cheapest provider analysis)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add your changes and tests
4. Submit a pull request

## 📄 License

MIT License - see the LICENSE file for details.

---

**Ready to get started?** Check out the [Quick Start Guide](quickstart.md) or explore the [Examples Directory](../examples/)! 
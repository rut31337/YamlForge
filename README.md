# YamlForge - Multi-Cloud Infrastructure as Code and OpenShift Management Suite

**Platform for managing multi-cloud infrastructure and OpenShift deployments through unified YAML definitions.**

A comprehensive tool that generates Terraform configurations from simple YAML specifications, supporting multiple cloud providers and OpenShift platforms with automated deployment capabilities.

## Quick Start

### Installation
```bash
git clone <repository-url>
cd yamlforge
pip install -r requirements.txt

# Verify Terraform v1.12.0+ is installed
terraform version  # Should show v1.12.0 or newer
```

**Requirement:** Terraform v1.12.0+ required for OpenShift/ROSA support

### Basic Usage
```bash
# Set required GUID (5-char lowercase alphanumeric)
export GUID=web01

# Generate and deploy infrastructure
python yamlforge.py examples/simple_test.yaml -d output/ --auto-deploy

# Or generate Terraform only
python yamlforge.py examples/simple_test.yaml -d output/
cd output/
terraform init && terraform apply
```

### AI-Assisted Configuration
Use AI assistants to generate YamlForge configurations from natural language:

```bash
# Ask your AI assistant:
"Create a YamlForge YAML configuration for: 
'Production OpenShift cluster on AWS with monitoring and a sample web application'"

# AI generates valid YAML following our schema
# Save the output and deploy with YamlForge
python yamlforge.py ai-generated-config.yaml -d output/ --auto-deploy
```

See [AI Prompt Engineering Guide](docs/ai-prompts.md) for detailed prompting techniques.

## Supported Platforms

### Cloud Providers
- **AWS** - Native EC2, VPC, Security Groups, ROSA clusters
- **Azure** - Virtual Machines, VNets, Network Security Groups, ARO clusters  
- **GCP** - Compute Engine with dynamic image discovery
- **IBM Cloud** - VPC Gen 2 and Classic Infrastructure
- **Oracle Cloud (OCI)** - Compute instances and networking
- **Alibaba Cloud** - ECS instances and VPC
- **VMware vSphere** - Virtual machines and networking

### OpenShift Platforms
- **ROSA** (Classic & HCP) - Red Hat OpenShift Service on AWS
- **ARO** - Azure Red Hat OpenShift
- **OpenShift Dedicated** - Managed OpenShift clusters
- **Self-Managed** - Custom OpenShift deployments
- **HyperShift** - Hosted control planes

## Key Features

- **Multi-Cloud** - Deploy across all major cloud providers
- **Cost Optimization** - Automatic cheapest provider selection
- **GPU Support** - Complete GPU instance support with cost analysis
- **GUID-Based** - Unique deployment identification (5-char required)
- **Auto-Discovery** - Automatic flavor recommendation
- **Enterprise Security** - Red Hat Cloud Access, service accounts
- **Smart Detection** - Only includes Terraform providers you use
- **Unified Deployment** - Single command deploys infrastructure and OpenShift clusters
- **ROSA Integration** - Automated ROSA account role creation via CLI
- **AI-Friendly** - Generate configurations from natural language using AI assistants

## Documentation

### Getting Started
- [Installation Guide](installation.md)
- [Quick Start Guide](quickstart.md)
- [GUID Configuration](guid-configuration.md)
- [Examples Gallery](examples.md)

### Features
- [Multi-Cloud Support](features/multi-cloud.md)
- [Cost Optimization](features/cost-optimization.md)
- [GPU Support](features/gpu-support.md)
- [Auto Discovery](features/auto-discovery.md)

### OpenShift
- [OpenShift Overview](openshift/overview.md)
- [Cluster Management](openshift/clusters.md)
- [Application Deployment](openshift/applications.md)
- [Security & Service Accounts](openshift/security.md)

### Configuration
- [Mappings & Flavors](configuration/mappings.md)
- [Credentials Setup](configuration/credentials.md)
- [Networking](configuration/networking.md)

### AI Assistance
- [AI Training Guide](docs/ai-training.md) - Comprehensive AI training materials
- [AI Prompt Engineering](docs/ai-prompts.md) - User guide for AI-generated configurations
- [JSON Schema](docs/yamlforge-schema.json) - Complete schema for AI validation

### Help
- [Troubleshooting](troubleshooting.md)
- [Examples Directory](../examples/)

## Example Configuration

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

## OpenShift Example

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

## Output

YamlForge generates production-ready Terraform with:
- **Native cloud resources** (no abstractions)
- **Smart provider detection** (only includes what you use)
- **Complete networking** (VPCs, subnets, security groups)
- **Service accounts** (automatic OpenShift credential management)
- **Cost optimization** (cheapest provider analysis)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your changes and tests
4. Submit a pull request

## License

MIT License - see the LICENSE file for details.

---

**Ready to get started?** Check out the [Quick Start Guide](quickstart.md) or explore the [Examples Directory](../examples/)! 

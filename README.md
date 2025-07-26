# YamlForge

**Universal Infrastructure as Code Across All Clouds**

Write your infrastructure once in elegant YAML syntax and deploy it seamlessly across AWS, Azure, GCP, OCI, Alibaba Cloud, IBM Cloud, and VMware. YamlForge eliminates cloud lock-in by providing a universal interface that generates production-ready Terraform configurations with built-in AI assistance.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Terraform](https://img.shields.io/badge/Terraform-1.0+-blue.svg)](https://www.terraform.io/)

## The Vision

**Universal infrastructure that works everywhere.**

YamlForge breaks down the barriers between cloud providers. Define your infrastructure once using intuitive YAML syntax, and watch it materialize across any cloud environment. Whether you're deploying OpenShift clusters, Kubernetes workloads, or custom applications, YamlForge provides the abstraction layer that makes multi-cloud a reality.

### Why YamlForge?

- **Universal Cloud Support**: Deploy to any major cloud provider with identical syntax
- **Intelligent Assistance**: AI-powered configuration generation from natural language
- **Enterprise Patterns**: Pre-built templates for OpenShift, Kubernetes, and production workloads
- **Zero Lock-in**: Migrate between clouds without rewriting your infrastructure code
- **Production Hardened**: Built-in security, compliance, and operational best practices
- **Developer Experience**: Intuitive YAML syntax that abstracts away cloud complexity

⚠️  ALPHA SOFTWARE WARNING ⚠️

This is v0.99 ALPHA - Work in Progress

This software may not work as expected and could break at any time.

Use at your own risk ($$$). Not yet recommended for production environments.

## Quick Start

### Installation
```bash
git clone https://github.com/rut31337/YamlForge.git
cd YamlForge
pip install -r requirements.txt

# Verify Terraform v1.12.0+ is installed
terraform version  # Should show v1.12.0 or newer
```

**Requirement:** Terraform v1.12.0+ required for OpenShift/ROSA support

### Define Once, Deploy Everywhere
```yaml
# infrastructure.yaml
guid: "demo1"

yamlforge:
  cloud_workspace:
    name: "multi-cloud-demo-{guid}"
    description: "Multi-cloud deployment demonstration"
  
  # Deploy instances across multiple clouds using universal locations
  # us-east maps to: AWS us-east-1, Azure East US, GCP us-east1, IBM VPC us-east
  instances:
    - name: "web-aws-{guid}"
      provider: "aws"
      region: "us-east"
      size: "medium"
      image: "RHEL9-latest"
      
    - name: "web-azure-{guid}"
      provider: "azure"
      region: "us-east"
      size: "medium"
      image: "RHEL9-latest"
      
    - name: "web-gcp-{guid}"
      provider: "gcp"
      region: "us-east"
      size: "medium"
      image: "RHEL9-latest"
  
  # Deploy OpenShift clusters using universal locations
  # us-east maps to: AWS us-east-1, Azure East US, GCP us-east1, IBM VPC us-east
  openshift_clusters:
    - name: "aws-rosa-{guid}"
      type: "rosa-classic"
      region: "us-east"
      version: "4.18.19"
      size: "medium"
      
    - name: "azure-aro-{guid}"
      type: "aro"
      region: "us-east"
      version: "latest"
      size: "medium"
  
  # Security configuration
  security_groups:
    - name: "web-access-{guid}"
      description: "Allow web traffic"
      rules:
        - direction: "ingress"
          protocol: "tcp"
          port_range: "80"
          source: "0.0.0.0/0"
        - direction: "ingress"
          protocol: "tcp"
          port_range: "443"
          source: "0.0.0.0/0"
```

### Deploy with Confidence
```bash
# Set up environment variables (copy and customize the template)
cp envvars.example.sh envvars.sh
# Edit envvars.sh with your credentials, then:
source envvars.sh

# See Command Line Options section for deployment commands
```

## Command Line Options

```bash
# Analyze configuration without generating Terraform
python yamlforge.py config.yaml --analyze

# Generate Terraform files
python yamlforge.py config.yaml -d output/

# Generate and deploy automatically
python yamlforge.py config.yaml -d output/ --auto-deploy

# Generate with verbose output (shows generated files, detailed AMI search info)
python yamlforge.py config.yaml -d output/ --verbose

# Generate without cloud credentials (uses placeholders, skips dynamic lookups, mainly for testing/development)
python yamlforge.py config.yaml -d output/ --no-credentials
```

**Available Flags:**
- `--analyze`: Analyze configuration and show provider selections, cost analysis, and mappings without generating Terraform
- `-d, --output-dir`: Specify output directory for generated Terraform files (required unless using `--analyze`)
- `--auto-deploy`: Automatically deploy infrastructure after generating Terraform (cannot be used with `--analyze`)
- `--verbose`: Show detailed output including generated files and dynamic lookups
- `--no-credentials`: Skip cloud credential validation and use placeholders (mainly for testing/development, may result in unusable Terraform)

## Configuration Analysis

**Explore options without generating Terraform:**
Perfect for AI chatbots and exploring configurations:

```bash
# Analyze what providers would be selected and their costs
python yamlforge.py my-config.yaml --analyze
```

**Example Analysis Output:**
```
================================================================================
  YAMLFORGE CLOUD ANALYSIS
================================================================================
Global provider exclusions: vmware, alibaba (excluded from cost comparison)
Global unexcluded providers: aws, azure, gcp, ibm_vpc, ibm_classic, oci

INSTANCES (2 found):
----------------------------------------

1. web-server-test1:
   Provider: cheapest (gcp)
   Region: us-east (us-east1)
   Size: medium (e2-medium)
   Image: RHEL9-latest (rhel-cloud/rhel-9)
   Cost analysis for instance 'web-server-test1':
     gcp: $0.0335/hour (e2-medium, 1 vCPU, 4GB) ← SELECTED
     aws: $0.0416/hour (t3.medium, 2 vCPU, 4GB)
     azure: $0.0752/hour (Standard_B4ms, 4 vCPU, 16GB)

2. gpu-worker-test1:
   Provider: cheapest-gpu (gcp)
   Region: us-east (us-east1)
   GPU Count: 1
   GPU Type: NVIDIA T4
   GPU Flavor: n1-standard-4-t4
   Image: RHEL9-latest (rhel-cloud/rhel-9)
   GPU-optimized cost analysis for instance 'gpu-worker-test1':
     gcp: $0.3500/hour (n1-standard-4-t4, 4 vCPU, 15GB, 1x NVIDIA T4) ← SELECTED
     aws: $0.5260/hour (g4dn.xlarge, 4 vCPU, 16GB, 1x NVIDIA T4)

REQUIRED PROVIDERS:
----------------------------------------
  • aws
  • gcp
```

**Perfect for AI Chatbots:**
- "What's the cheapest GPU instance?"
- "What would a medium server cost on different clouds?"
- "What providers do I need for this configuration?"
- "Show me the mapped regions and flavors for this configuration"

### AI-Assisted Configuration

**Training AI to Use YamlForge:**
Provide the AI with our JSON schema ([`docs/yamlforge-schema.json`](docs/yamlforge-schema.json)) and real examples from the `examples/` directory. Emphasize the required 5-character GUID, valid provider names, and exact field structure. See [AI Training Guide](docs/ai-training.md) for comprehensive training materials.

Use AI assistants to generate YamlForge configurations from natural language:

```bash
# Ask your AI assistant:
"Create a YamlForge YAML configuration for: 
'Production OpenShift cluster on AWS with monitoring and a sample web application'"

# AI generates valid YAML following our [schema](docs/yamlforge-schema.json)
# Save the output and analyze/deploy with YamlForge
python yamlforge.py ai-generated-config.yaml --analyze  # See what it will do
python yamlforge.py ai-generated-config.yaml -d output/ --auto-deploy  # Deploy it
## Real-World Scenarios

### Multi-Cloud Strategy
Deploy identical infrastructure across multiple clouds for redundancy and compliance:
```yaml
guid: "prod1"

yamlforge:
  cloud_workspace:
    name: "production-multi-cloud-{guid}"
    description: "Production deployment across multiple clouds"
  
  instances:
    - name: "app-aws-{guid}"
      provider: "aws"
      region: "us-east"
      size: "large"
      image: "RHEL9-latest"
    - name: "app-azure-{guid}"
      provider: "azure"
      region: "us-east"
      size: "large"
      image: "RHEL9-latest"
    - name: "app-gcp-{guid}"
      provider: "gcp"
      region: "us-east"
      size: "large"
      image: "RHEL9-latest"
```

### Cloud Migration
Seamlessly migrate workloads between cloud providers:
```yaml
guid: "mig1"

yamlforge:
  cloud_workspace:
    name: "migration-to-aws-{guid}"
    description: "Migrating from Azure to AWS"
  
  instances:
    - name: "migrated-app-{guid}"
      provider: "aws"  # Migrate from Azure to AWS
      region: "us-east"
      size: "medium"
      image: "RHEL9-latest"
```

### Flavor Mapping
No need to memorize provider-specific instance types! YamlForge automatically maps your CPU and memory requirements to the appropriate instance type for each cloud:

```yaml
guid: "flav1"

yamlforge:
  cloud_workspace:
    name: "flavor-mapping-{guid}"
    description: "Demonstrating CPU/memory to flavor mapping"
  
  instances:
    - name: "web-server-{guid}"
      provider: "aws"
      region: "us-east"
      cores: 2
      memory: 4096  # MB - YamlForge selects t3.medium automatically
      image: "RHEL9-latest"
    - name: "app-server-{guid}"
      provider: "azure"
      region: "us-east"
      cores: 4
      memory: 8192  # MB - YamlForge selects Standard_D2s_v3 automatically
      image: "RHEL9-latest"
    - name: "database-{guid}"
      provider: "gcp"
      region: "us-east"
      cores: 8
      memory: 16384  # MB - YamlForge selects e2-standard-8 automatically
      image: "RHEL9-latest"
```

**Instead of learning:**
- AWS: t3.micro, t3.small, t3.medium, m5.large, c5.xlarge...
- Azure: Standard_B1s, Standard_D2s_v3, Standard_E4s_v3...
- GCP: e2-micro, e2-small, e2-standard-8, n2-standard-4...

**Just specify:** `cores: 4, memory: 8192` and YamlForge handles the rest!

**Or use simple t-shirt sizing:**
```yaml
guid: "size1"

yamlforge:
  cloud_workspace:
    name: "t-shirt-sizing-{guid}"
    description: "Using generic small/medium/large sizing"
  
  instances:
    - name: "web-server-{guid}"
      provider: "aws"
      region: "us-east"
      size: "small"  # Generic size - works on all clouds
      image: "RHEL9-latest"
    - name: "app-server-{guid}"
      provider: "azure"
      region: "us-east"
      size: "medium"  # Generic size - works on all clouds
      image: "RHEL9-latest"
    - name: "database-{guid}"
      provider: "gcp"
      region: "us-east"
      size: "large"  # Generic size - works on all clouds
      image: "RHEL9-latest"
```

**Available sizes:** `nano`, `micro`, `small`, `medium`, `large`, `xlarge`, `2xlarge`, `4xlarge`, `8xlarge`, `16xlarge`

### Cost Optimization
YamlForge offers two intelligent cost optimization providers:

**`cheapest`** - General cost optimization for balanced workloads:
```yaml
guid: "cost1"

yamlforge:
  cloud_workspace:
    name: "cost-optimized-{guid}"
    description: "Automatically select cheapest provider"
  
  instances:
    - name: "api-server-{guid}"
      provider: "cheapest"  # Finds cheapest instance meeting CPU/memory requirements
      region: "us-east"
      size: "medium"  # Must specify size or cores/memory
      image: "RHEL9-latest"
    - name: "database-server-{guid}"
      provider: "cheapest"  # CPU/memory only - no GPU needed
      region: "us-east"
      cores: 4
      memory: 8192  # MB
      image: "RHEL9-latest"
    - name: "ml-training-{guid}"
      provider: "cheapest"  # Can also optimize GPU workloads with specs
      region: "us-east"
      cores: 8
      memory: 16384  # MB
      gpu_type: "NVIDIA V100"
      gpu_count: 1
      image: "RHEL9-latest"
    - name: "app-server-{guid}"
      provider: "cheapest"  # Combines t-shirt sizing with cost optimization
      region: "us-east"
      size: "large"  # Generic size - YamlForge finds cheapest "large" across all clouds
      image: "RHEL9-latest"
```

**`cheapest-gpu`** - Specialized GPU cost optimization:
```yaml
guid: "gpu1"

yamlforge:
  cloud_workspace:
    name: "gpu-optimized-{guid}"
    description: "Cheapest GPU instances across all clouds"
  
  instances:
    - name: "gpu-worker-{guid}"
      provider: "cheapest-gpu"  # Focuses purely on GPU cost, ignores CPU/memory
      region: "us-east"
      gpu_type: "NVIDIA T4"  # Only GPU requirements needed
      gpu_count: 1
      image: "RHEL9-latest"
```

**Key Differences:**
- **`cheapest`**: Requires `size` or `cores`/`memory`, optimizes for overall cost
- **`cheapest-gpu`**: Only needs `gpu_type`/`gpu_count`, finds cheapest GPU regardless of CPU/memory

### Enterprise OpenShift
Deploy OpenShift clusters optimized for each cloud's native capabilities:
```yaml
guid: "ocp1"

yamlforge:
  cloud_workspace:
    name: "enterprise-openshift-{guid}"
    description: "Enterprise OpenShift across clouds"
  
  openshift_clusters:
    - name: "aws-rosa-{guid}"
      type: "rosa-classic"
      region: "us-east"
      version: "4.18.19"
      size: "large"
    - name: "azure-aro-{guid}"
      type: "aro"
      region: "us-east"
      version: "latest"
      size: "large"
```

### Generic Images
Use the same image names across all cloud providers:
```yaml
guid: "img1"

yamlforge:
  cloud_workspace:
    name: "multi-os-deployment-{guid}"
    description: "Deploying different operating systems across clouds"
  
  instances:
    - name: "web-server-{guid}"
      provider: "aws"
      region: "us-east"
      size: "medium"
      image: "RHEL9-latest"  # Generic name - maps to provider-specific images
    - name: "app-server-{guid}"
      provider: "azure"
      region: "us-east"
      size: "medium"
      image: "Ubuntu2204-latest"  # Ubuntu 22.04 LTS - works on all clouds
    - name: "db-server-{guid}"
      provider: "gcp"
      region: "us-east"
      size: "medium"
      image: "Fedora-latest"  # Fedora (latest stable) - works on all clouds
    - name: "monitoring-{guid}"
      provider: "oci"
      region: "us-east"
      size: "medium"
      image: "OracleLinux9-latest"  # Oracle Linux 9 - works on all clouds
```

### Generic Locations
Use simple region names that work across all cloud providers:
```yaml
# Instead of learning provider-specific regions:
# AWS: us-east-1, Azure: East US, GCP: us-east1, OCI: us-ashburn-1...

# Just use: "us-east" - YamlForge maps to the correct region for each provider
region: "us-east"  # Works on all clouds
```

## Universal Mappings

YamlForge uses generic names that work across all clouds. All mappings are customizable:

**Customizable Mappings:**
All mappings can be customized in the `mappings/` directory:
- `mappings/images.yaml` - Customize image mappings
- `mappings/locations.yaml` - Customize region mappings  
- `mappings/flavors/` - Customize instance type mappings
- `mappings/flavors_openshift/` - Customize OpenShift-specific mappings

**Unbiased and Transparent:**
YamlForge is not biased toward any specific operating system image or cloud provider. We only use information freely available on the internet to determine costs and make recommendations. Users can add their own operating system images in the `mappings/images.yaml` file to customize the available options for their deployments.

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

- **Universal Cloud Support**: Deploy to any major cloud provider with identical syntax
- **Intelligent Assistance**: AI-powered configuration generation from natural language
- **Enterprise Patterns**: Pre-built templates for OpenShift, Kubernetes, and production workloads
- **Zero Lock-in**: Migrate between clouds without rewriting your infrastructure code
- **Production Hardened**: Built-in security, compliance, and operational best practices
- **Developer Experience**: Intuitive YAML syntax that abstracts away cloud complexity
- **Cost Optimization**: Automatic cheapest provider selection
- **GPU Support**: Complete GPU instance support with cost analysis
- **GUID-Based**: Unique deployment identification (5-char required)
- **Auto-Discovery**: Automatic flavor recommendation
- **Enterprise Security**: Red Hat Cloud Access, service accounts
- **Smart Detection**: Only includes Terraform providers you use
- **Unified Deployment**: Single command deploys infrastructure and OpenShift clusters
- **ROSA Integration**: Automated ROSA account role creation via CLI

## How It Works

```
Your Vision → YAML Definition → Universal Processing → Provider-Specific Terraform → Multi-Cloud Deployment
```

YamlForge acts as the intelligent translation layer between your infrastructure vision and the reality of multi-cloud deployment.

## Documentation

- [Getting Started](docs/quickstart.md)
- [Configuration Reference](docs/configuration/)
- [AI Training Guide](docs/ai-training.md)
- [Multi-Cloud Examples](examples/)
- [OpenShift Deployment](docs/openshift/)

## Contributing

Help us build the future of universal infrastructure. See our [Contributing Guide](CONTRIBUTING.md).

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Author

**Patrick T. Rutledge III**

Project Link: [https://github.com/rut31337/YamlForge](https://github.com/rut31337/YamlForge) 

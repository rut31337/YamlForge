# AWS OpenShift Examples

This directory contains comprehensive examples for deploying OpenShift on AWS using YamlForge. These examples demonstrate both ROSA (Red Hat OpenShift Service on AWS) deployment patterns and supporting infrastructure.

## 🔴 **Available Examples**

### ✅ **aws_openshift_simple_example.yaml** (Ready to Use)
A working, tested example that includes:
- **ROSA HCP** cluster (production-ready, hosted control plane)
- **ROSA Classic** cluster (development, traditional deployment)
- **Jump host** with OpenShift CLI tools pre-installed
- **Basic operators** (monitoring, GitOps)
- **Sample application** deployment
- **Security groups** and networking

### 🚧 **aws_openshift_comprehensive_example.yaml** (Advanced)
A comprehensive example showcasing enterprise features:
- Multiple ROSA clusters (HCP + Classic)
- Complete operator ecosystem
- Day 2 operations
- Security configurations
- Cost optimization
- Multi-cluster management

## 🚀 **Quick Start Guide**

### Prerequisites
1. **AWS Account** with appropriate permissions
2. **ROSA CLI** installed and configured
3. **Terraform** installed (v1.0+)
4. **AWS CLI** configured with credentials

### Step 1: Generate Terraform
```bash
# Generate Terraform configuration
./yamlforge.py examples/openshift/aws_openshift_simple_example.yaml -d my-openshift-deployment/

# Navigate to output directory
cd my-openshift-deployment/
```

### Step 2: Review Generated Files
```bash
# Check generated files
ls -la
# main.tf          - Terraform configuration
# terraform.tfvars  - Variables to customize

# Review the configuration
cat main.tf | head -50
```

### Step 3: Customize Variables
```bash
# Edit terraform.tfvars with your values
vim terraform.tfvars

# Required variables:
# ssh_public_key = "ssh-rsa AAAAB3NzaC1yc2E... your-email@domain.com"
# aws_region = "us-east-1"
```

### Step 4: Deploy Infrastructure
```bash
# Initialize Terraform
terraform init

# Plan deployment
terraform plan

# Apply configuration
terraform apply
```

> 📋 **For detailed post-deployment steps, see [TERRAFORM_NEXT_STEPS.md](TERRAFORM_NEXT_STEPS.md)** - Complete 9-phase workflow from Terraform deployment to production OpenShift clusters with sample applications.

## 🔧 **Configuration Options**

### **Cluster Types**

#### ROSA HCP (Hosted Control Plane) - Recommended
```yaml
- name: "production-cluster"
  type: "rosa-hcp"                 # Managed control plane
  provider: "aws"
  region: "us-east-1"
  version: "4.14.15"
  size: "large"                    # production-ready
  
  worker_count: 3
  min_replicas: 2
  max_replicas: 10
  
  auto_scaling:
    enabled: true
    min_replicas: 2
    max_replicas: 10
```

#### ROSA Classic (Traditional)
```yaml
- name: "development-cluster"
  type: "rosa-classic"             # Traditional deployment
  provider: "aws"
  region: "us-west-2"
  version: "4.14.15"
  size: "medium"                   # development sizing
  
  worker_count: 2
```

### **Supported Operators**

#### Monitoring Stack
```yaml
openshift_operators:
  - type: "monitoring"
    name: "cluster-monitoring"
    target_cluster: "production-cluster"
    
    prometheus:
      retention: "15d"
      storage_size: "20Gi"
      
    grafana:
      enabled: true
```

#### GitOps (ArgoCD)
```yaml
  - type: "gitops"
    name: "openshift-gitops"
    target_cluster: "production-cluster"
    
    repositories:
      - url: "https://github.com/your-org/apps"
        path: "manifests/"
        target_revision: "main"
```

#### Service Mesh (Istio)
```yaml
  - type: "service-mesh"
    name: "istio-system"
    target_cluster: "production-cluster"
    
    control_plane:
      version: "v2.4"
      security:
        data_plane:
          mtls: true
```

### **Application Deployments**

#### Web Application
```yaml
openshift_applications:
  - name: "web-app"
    target_cluster: "production-cluster"
    namespace: "production"
    
    deployment:
      replicas: 2
      containers:
        - name: "web"
          image: "nginx:latest"
          ports: [80]
          
    service:
      type: "ClusterIP"
      ports:
        - port: 80
          target_port: 80
          
    route:
      host: "web.apps.cluster.example.com"
      tls:
        termination: "edge"
```

## 🔐 **Security Configuration**

### **RBAC Example**
```yaml
security:
  rbac:
    - name: "developers"
      kind: "Group"
      permissions: ["get", "list", "watch", "create", "update"]
      resources: ["pods", "services", "deployments"]
      namespaces: ["development", "staging"]
```

### **Network Policies**
```yaml
  network_policies:
    default_deny: true
    allow_dns: true
    custom_policies:
      - name: "allow-web-to-api"
        pod_selector:
          app: "web-frontend"
        ingress:
          - from:
              pod_selector:
                app: "api-backend"
```

## 💰 **Cost Optimization**

### **Cluster Autoscaling**
```yaml
cost_optimization:
  autoscaling:
    enabled: true
    min_nodes: 2
    max_nodes: 10
    scale_down_delay: "10m"
```

### **Spot Instances**
```yaml
  spot_instances:
    enabled: true
    max_price: "0.10"
    instance_types: ["m5.large", "m5.xlarge"]
```

## 🔧 **Day 2 Operations**

### **Automated Upgrades**
```yaml
day2_operations:
  upgrades:
    schedule: "0 2 * * 0"           # Weekly on Sunday
    channel: "stable-4.14"
    auto_approve_patch: true
    
    maintenance_window:
      start: "02:00"
      duration: "4h"
      timezone: "UTC"
```

### **Backup Configuration**
```yaml
  backup:
    schedule: "0 1 * * *"           # Daily at 1 AM
    retention: "30d"
    include_resources:
      - "persistentvolumes"
      - "secrets"
      - "configmaps"
```

## 🏗️ **Infrastructure Components**

### **Jump Host Configuration**
The examples include a pre-configured jump host with:
- **OpenShift CLI** (`oc`)
- **ROSA CLI** 
- **AWS CLI v2**
- **kubectl**
- **Helm**
- **Tekton CLI** (`tkn`)

### **Networking**
- **VPC** with proper CIDR blocks
- **Security groups** for management access
- **Multi-AZ** deployment for high availability

## 📚 **Additional Resources**

### **Prerequisites Setup**

#### Install ROSA CLI
```bash
# Download and install ROSA CLI
curl -L https://mirror.openshift.com/pub/openshift-v4/clients/rosa/latest/rosa-linux.tar.gz | tar -xz
sudo mv rosa /usr/local/bin/
rosa version
```

#### Configure AWS CLI
```bash
# Configure AWS credentials
aws configure
# AWS Access Key ID: [Your Access Key]
# AWS Secret Access Key: [Your Secret Key]
# Default region name: us-east-1
# Default output format: json
```

#### Verify ROSA Prerequisites
```bash
# Check ROSA prerequisites
rosa verify permissions
rosa verify quota
```

### **Cluster Access**
```bash
# After deployment, get cluster credentials
rosa describe cluster production-rosa-hcp
rosa logs install production-rosa-hcp

# Login to cluster
rosa get-admin-password --cluster=production-rosa-hcp
oc login https://api.production-rosa-hcp.xxxxx.p1.openshiftapps.com:6443 \\
  --username cluster-admin --password <password>
```

### **Monitoring Access**
```bash
# Access Grafana dashboard
oc get route grafana -n openshift-monitoring
# Navigate to the route URL

# Access Prometheus
oc get route prometheus-k8s -n openshift-monitoring
```

## 🎯 **Best Practices**

1. **Start Simple**: Use `aws_openshift_simple_example.yaml` first
2. **Customize Gradually**: Add operators and applications as needed
3. **Use HCP for Production**: ROSA HCP offers better cost and management
4. **Enable Monitoring**: Always include monitoring and logging
5. **Plan for Scale**: Configure autoscaling from the start
6. **Secure by Default**: Implement RBAC and network policies
7. **Backup Strategy**: Configure automated backups for critical data

## 🐛 **Troubleshooting**

### **Common Issues**

#### ROSA Quota Limits
```bash
# Check current quotas
rosa verify quota

# Request quota increase if needed
```

#### Network Connectivity
```bash
# Verify VPC and subnet configuration
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=*openshift*"
aws ec2 describe-subnets --filters "Name=tag:Name,Values=*openshift*"
```

#### Cluster Creation Failures
```bash
# Check ROSA cluster status
rosa describe cluster <cluster-name>
rosa logs install <cluster-name>
```

## 📞 **Support**

- **YamlForge Issues**: [GitHub Issues](https://github.com/your-org/yamlforge/issues)
- **ROSA Documentation**: [Red Hat OpenShift Service on AWS](https://docs.openshift.com/rosa/)
- **AWS Documentation**: [AWS Documentation](https://docs.aws.amazon.com/)

---

**Ready to deploy OpenShift on AWS? Start with the simple example and expand from there!** 🚀 
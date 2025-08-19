# IBM VPC Configuration Guide

This guide covers IBM VPC-specific configuration options and best practices for YamlForge.

## Quick Start

### Basic IBM VPC Instance

```yaml
guid: "ibm01"

yamlforge:
  cloud_workspace:
    name: "ibm-vpc-demo-{guid}"
    description: "Basic IBM VPC instance deployment"
  
  instances:
    - name: "ibm-vpc-vm-{guid}"
      provider: "ibm_vpc"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-south"
```

### Multi-Region IBM VPC Deployment

```yaml
guid: "ibm02"

yamlforge:
  cloud_workspace:
    name: "multi-region-ibm-{guid}"
    description: "Multi-region IBM VPC deployment"
  
  instances:
    - name: "vpc-east-{guid}"
      provider: "ibm_vpc"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-east"
      
    - name: "vpc-south-{guid}"
      provider: "ibm_vpc"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-south"
```

## Environment Variables

### Required IBM VPC Credentials

```bash
# IBM Cloud API Key
export IBMCLOUD_API_KEY=your_ibm_cloud_api_key

# IBM Cloud Region
export IBMCLOUD_REGION=us-south

# SSH Public Key
export SSH_PUBLIC_KEY="ssh-rsa your_public_key_here"
```

### Getting IBM Cloud API Key

1. **Log into IBM Cloud Console**: https://cloud.ibm.com
2. **Go to Manage → Access (IAM) → API Keys**
3. **Create API Key**: Click "Create an IBM Cloud API key"
4. **Copy the key**: Save it securely

## Available Regions

IBM VPC supports these regions:

```yaml
# ✅ Supported regions
location: "us-south"      # Dallas
location: "us-east"       # Washington DC
location: "eu-gb"         # London
location: "eu-de"         # Frankfurt
location: "jp-tok"        # Tokyo
location: "au-syd"        # Sydney
location: "ca-tor"        # Toronto
location: "br-sao"        # São Paulo
```

## Instance Flavors

IBM VPC supports these instance profiles:

```yaml
# ✅ Available flavors
flavor: "small"         # 2 vCPU, 4GB RAM
flavor: "medium"        # 4 vCPU, 8GB RAM
flavor: "large"         # 8 vCPU, 16GB RAM
flavor: "xlarge"        # 16 vCPU, 32GB RAM

# ✅ Custom specifications
cores: 4
memory: 8192  # 8GB in MB
```

## Advanced Configuration

### Security Groups

```yaml
guid: "ibm03"

yamlforge:
  cloud_workspace:
    name: "ibm-security-demo-{guid}"
    description: "IBM VPC with security groups"
  
  security_groups:
    - name: "web-access-{guid}"
      description: "Web server access"
      rules:
        - direction: "ingress"
          protocol: "tcp"
          port_range: "80"
          source: "0.0.0.0/0"
        - direction: "ingress"
          protocol: "tcp"
          port_range: "443"
          source: "0.0.0.0/0"
        - direction: "ingress"
          protocol: "tcp"
          port_range: "22"
          source: "0.0.0.0/0"

  instances:
    - name: "web-server-{guid}"
      provider: "ibm_vpc"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-south"
      security_groups: ["web-access-{guid}"]
```

### Tags and Labels

```yaml
guid: "ibm04"

yamlforge:
  cloud_workspace:
    name: "ibm-tagged-demo-{guid}"
    description: "IBM VPC with tags and labels"
  
  instances:
    - name: "tagged-vm-{guid}"
      provider: "ibm_vpc"
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-south"
      tags:
        environment: "production"
        team: "development"
        cost_center: "it-ops"
```

## Cost Optimization

### Using Cheapest Provider

```yaml
guid: "ibm05"

yamlforge:
  cloud_workspace:
    name: "ibm-cost-optimized-{guid}"
    description: "Cost-optimized IBM VPC deployment"
  
  instances:
    - name: "cost-optimized-{guid}"
      provider: "cheapest"  # IBM VPC may be selected if cheapest
      flavor: "medium"
      image: "RHEL9-latest"
      location: "us-south"
```

### Custom Specifications

```yaml
guid: "ibm06"

yamlforge:
  cloud_workspace:
    name: "ibm-custom-specs-{guid}"
    description: "IBM VPC with custom specifications"
  
  instances:
    - name: "custom-specs-{guid}"
      provider: "ibm_vpc"
      cores: 6
      memory: 12288  # 12GB in MB
      image: "RHEL9-latest"
      location: "us-south"
```

## Troubleshooting

### Common Issues

1. **API Key Issues**
   ```bash
   # Verify API key
   curl -H "Authorization: Bearer $IBMCLOUD_API_KEY" \
        https://us-south.iaas.cloud.ibm.com/v1/instances
   ```

2. **Region Availability**
   ```bash
   # Check available regions
   ibmcloud regions
   ```

3. **Instance Profile Issues**
   ```bash
   # List available profiles
   ibmcloud is instance-profiles
   ```

### Best Practices

1. **Use Universal Locations**: `location: "us-east"` maps to IBM VPC regions
2. **Tag Resources**: Use tags for cost tracking and organization
3. **Security Groups**: Always use security groups for network access control
4. **Backup Strategy**: Consider IBM Cloud Backup for data protection

## Integration with OpenShift

IBM VPC can be used with OpenShift clusters:

```yaml
guid: "ibm07"

yamlforge:
  cloud_workspace:
    name: "ibm-openshift-{guid}"
    description: "IBM VPC with OpenShift cluster"
  
  openshift_clusters:
    - name: "ibm-openshift-{guid}"
      type: "self-managed"
      provider: "ibm_vpc"
      location: "us-south"
      version: "latest"
      flavor: "medium"  # Cluster size (not instance size)
      worker_count: 3
```

## Next Steps

- [Multi-Cloud Configuration](multi-cloud.md)
- [Cost Optimization](features/cost-optimization.md)
- [Troubleshooting Guide](troubleshooting.md) 

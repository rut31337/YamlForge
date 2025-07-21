# Multi-Cloud Examples

This directory contains examples that demonstrate deploying infrastructure across multiple cloud providers, showcasing hybrid and multi-cloud strategies.

## Available Examples

### **Hybrid Deployments**
- **`hybrid_rhel_deployment.yaml`** - Comprehensive multi-cloud RHEL deployment
  - Infrastructure across AWS, Azure, GCP, and IBM Cloud
  - Both public and Red Hat Gold images
  - Demonstrates native multi-cloud infrastructure patterns
  - Production-ready enterprise hybrid cloud setup

### **Cloud Access & Licensing**
- **`cloud_access_test.yaml`** - Red Hat Cloud Access testing across providers
  - RHEL Gold image deployment on multiple clouds
  - BYOS (Bring Your Own Subscription) examples
  - Red Hat subscription compliance demonstration
  - Licensing model comparison

- **`rhel_gold_vs_public_test.yaml`** - RHEL Gold vs Public image comparison
  - Side-by-side comparison of licensing models
  - Public RHEL (community support) vs Gold (Red Hat support)
  - Cost and support model evaluation
  - Deployment strategy comparison

## Usage

```bash
# Deploy comprehensive multi-cloud infrastructure
python yamlforge.py examples/multi-cloud/hybrid_rhel_deployment.yaml -d terraform-hybrid/

# Test Cloud Access across providers
python yamlforge.py examples/multi-cloud/cloud_access_test.yaml -d terraform-cloud-access/

# Compare licensing models
python yamlforge.py examples/multi-cloud/rhel_gold_vs_public_test.yaml -d terraform-licensing/
```

## Key Features Demonstrated

- **Multi-cloud deployment patterns** across AWS, Azure, GCP, IBM Cloud
- **Unified configuration** for consistent infrastructure
- **Red Hat Cloud Access** (BYOS) implementation
- **Licensing strategy comparison** (Public vs Gold images)
- **Cross-cloud networking** and security groups
- **Enterprise hybrid cloud** best practices
- **Subscription management** across cloud providers

## Use Cases

### **Enterprise Hybrid Cloud**
- **Disaster recovery** across multiple providers
- **Geographic distribution** for compliance
- **Risk mitigation** through provider diversification
- **Cost optimization** through provider competition

### **Red Hat Ecosystem**
- **Cloud Access deployment** strategies
- **RHEL licensing** across cloud providers
- **Support model evaluation** (community vs enterprise)
- **Subscription compliance** in multi-cloud environments

## Learning Path

1. **Start with `rhel_gold_vs_public_test.yaml`** to understand licensing models
2. **Try `cloud_access_test.yaml`** for Red Hat Cloud Access implementation  
3. **Deploy `hybrid_rhel_deployment.yaml`** for comprehensive multi-cloud setup
4. **Compare costs and features** across different cloud providers
5. **Adapt patterns** for your specific enterprise requirements

## Benefits

- **Vendor independence** - avoid cloud provider lock-in
- **Risk mitigation** - distribute infrastructure across providers
- **Cost optimization** - leverage competitive pricing
- **Compliance flexibility** - meet geographic and regulatory requirements
- **Technology diversity** - use best-of-breed services from each provider 
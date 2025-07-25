# AI Training Guide for YamlForge

This document provides comprehensive training materials for AI systems to understand and generate YamlForge YAML configurations from natural language inputs.

## Core YamlForge Structure

YamlForge uses a structured YAML format with the `yamlforge:` wrapper containing all configuration:

```yaml
# Optional: Unique 5-character identifier  
guid: "web01"

# Required: Main configuration wrapper
yamlforge:
  cloud_workspace:
    name: "workspace-name"
    description: "Workspace description"
  
  instances: []
  openshift_clusters: []
  openshift_operators: []
  openshift_applications: []
  security_groups: []
  tags: {}
```

## JSON Schema Definition

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "YamlForge Configuration Schema",
  "type": "object",
  "required": ["yamlforge"],
  "properties": {
    "guid": {
      "type": "string",
      "pattern": "^[a-z0-9]{5}$",
      "description": "Unique 5-character identifier (lowercase alphanumeric)"
    },
    "yamlforge": {
      "type": "object",
      "description": "Main configuration wrapper (required)",
      "properties": {
        "cloud_workspace": {"$ref": "#/definitions/cloud_workspace"},
        "instances": {"$ref": "#/definitions/instances"},
        "openshift_clusters": {"$ref": "#/definitions/openshift_clusters"},
        "openshift_operators": {"$ref": "#/definitions/openshift_operators"},
        "openshift_applications": {"$ref": "#/definitions/openshift_applications"}
      }
    }
  }
}
```

## Natural Language to YAML Patterns

### Pattern 1: Simple Infrastructure
**User Input**: "Create 3 AWS instances running RHEL 9 in us-east-1"
**Generated YAML**:
```yaml
guid: "web01"
yamlforge:
  cloud_workspace:
    name: "aws-infrastructure"
    description: "Simple AWS infrastructure deployment"
  
  instances:
    - name: "aws-instance-1"
      provider: "aws"
      region: "us-east-1"
      size: "medium"
      image: "RHEL9-latest"
    - name: "aws-instance-2"
      provider: "aws"
      region: "us-east-1"
      size: "medium"
      image: "RHEL9-latest"
    - name: "aws-instance-3"
      provider: "aws"
      region: "us-east-1"
      size: "medium"
      image: "RHEL9-latest"
```

### Pattern 2: Multi-Cloud Deployment
**User Input**: "Deploy web servers on AWS and Azure, with database on the cheapest provider"
**Generated YAML**:
```yaml
guid: "web01"
yamlforge:
  cloud_workspace:
    name: "multi-cloud-web"
    description: "Multi-cloud web deployment with cost optimization"
  
  instances:
    - name: "web-aws"
      provider: "aws"
      size: "medium"
      image: "RHEL9-latest"
      tags:
        role: "web"
    - name: "web-azure"
      provider: "azure"
      size: "medium"
      image: "RHEL9-latest"
      tags:
        role: "web"
    - name: "database"
      provider: "cheapest"
      size: "large"
      memory: 16384
      image: "RHEL9-latest"
      tags:
        role: "database"
```

### Pattern 3: ROSA Cluster
**User Input**: "Create a production ROSA HCP cluster with monitoring"
**Generated YAML**:
```yaml
guid: "prod1"
yamlforge:
  cloud_workspace:
    name: "production-openshift"
    description: "Production ROSA HCP deployment"
  
  openshift_clusters:
    - name: "production-rosa"
      type: "rosa-hcp"
      region: "us-east-1"
      version: "latest"
      size: "large"
      worker_count: 6
      auto_scaling:
        enabled: true
        min_replicas: 3
        max_replicas: 10

  openshift_operators:
    - type: "monitoring"
      name: "cluster-monitoring"
      target_cluster: "production-rosa"
      enabled: true
```

### Pattern 4: GPU Workload
**User Input**: "I need GPU instances for AI training across multiple clouds"
**Generated YAML**:
```yaml
guid: "ai001"
yamlforge:
  cloud_workspace:
    name: "ai-training"
    description: "Multi-cloud AI training infrastructure"
  
  instances:
    - name: "gpu-aws"
      provider: "aws"
      size: "gpu_large"
      gpu_type: "NVIDIA V100"
      gpu_count: 4
      image: "RHEL9-latest"
    - name: "gpu-azure"
      provider: "azure"
      size: "gpu_large"
      gpu_type: "NVIDIA V100"
      gpu_count: 4
      image: "RHEL9-latest"
    - name: "gpu-cheapest"
      provider: "cheapest"
      gpu_type: "NVIDIA V100"
      gpu_count: 2
      image: "RHEL9-latest"
```

## Common Translation Rules

### Size Mapping
- "small/development" → `size: "small"`
- "medium/standard/production" → `size: "medium"`
- "large/enterprise/high-performance" → `size: "large"`
- "micro/minimal/testing" → `size: "micro"`

### Provider Mapping
- "cheapest/cost-effective/budget" → `provider: "cheapest"`
- "AWS/Amazon" → `provider: "aws"`
- "Azure/Microsoft" → `provider: "azure"`
- "GCP/Google Cloud/Google" → `provider: "gcp"`
- "Oracle Cloud/OCI" → `provider: "oci"`

### OpenShift Type Mapping
- "ROSA HCP/hosted control plane" → `type: "rosa-hcp"`
- "ROSA Classic/traditional ROSA" → `type: "rosa-classic"`
- "Azure Red Hat OpenShift/ARO" → `type: "aro"`
- "self-managed/DIY OpenShift" → `type: "self-managed"`

### Operator Mapping
- "monitoring/Prometheus/Grafana" → `type: "monitoring"`
- "logging/ElasticSearch/Fluentd" → `type: "logging"`
- "GitOps/ArgoCD/continuous deployment" → `type: "gitops"`
- "service mesh/Istio" → `type: "service-mesh"`
- "certificates/cert-manager/TLS" → `type: "cert-manager"`

## AI Prompt Templates

### Template 1: Infrastructure Focus
```
Generate a YamlForge YAML configuration for the following infrastructure request:
"{user_natural_language_input}"

Requirements:
1. Use a 5-character GUID based on the use case
2. Wrap everything in yamlforge: block
3. Include cloud_workspace with name and description
4. Select appropriate cloud providers
5. Choose suitable instance sizes
6. Include necessary tags for organization
7. Use RHEL9-latest as default image unless specified

Output only valid YAML matching the YamlForge schema.
```

### Template 2: OpenShift Focus
```
Create a YamlForge YAML configuration for OpenShift deployment:
"{user_natural_language_input}"

Requirements:
1. Generate appropriate GUID
2. Wrap everything in yamlforge: block
3. Include cloud_workspace with name and description
4. Choose correct OpenShift cluster type (rosa-hcp for production, rosa-classic for development)
5. Include monitoring and logging operators by default
6. Set worker_count to multiples of 3 for ROSA HCP
7. Use latest stable OpenShift version (latest)

Output only valid YAML.
```

## Example AI Conversations

### Conversation 1: Simple Request
**User**: "I need a development environment with 2 servers on AWS"
**AI Response**:
```yaml
guid: "dev01"
yamlforge:
  cloud_workspace:
    name: "development-environment"
    description: "Development environment with AWS servers"
  
  instances:
    - name: "dev-server-1"
      provider: "aws"
      region: "us-east-1"
      size: "small"
      image: "RHEL9-latest"
      tags:
        environment: "development"
    - name: "dev-server-2"
      provider: "aws"
      region: "us-east-1"
      size: "small"
      image: "RHEL9-latest"
      tags:
        environment: "development"
```

### Conversation 2: Complex Request
**User**: "Set up a production OpenShift cluster on AWS with monitoring, logging, and a sample web application"
**AI Response**:
```yaml
guid: "prod1"
yamlforge:
  cloud_workspace:
    name: "production-openshift"
    description: "Production OpenShift cluster with full stack"
  
  openshift_clusters:
    - name: "production-cluster"
      type: "rosa-hcp"
      region: "us-east-1"
      version: "latest"
      size: "large"
      worker_count: 6
      auto_scaling:
        enabled: true
        min_replicas: 3
        max_replicas: 12

  openshift_operators:
    - type: "monitoring"
      name: "cluster-monitoring"
      target_cluster: "production-cluster"
      enabled: true
    - type: "logging"
      name: "cluster-logging"
      target_cluster: "production-cluster"
      enabled: true

  openshift_applications:
    - name: "sample-web-app"
      target_cluster: "production-cluster"
      namespace: "production"
      deployment:
        replicas: 3
        containers:
          - name: "web"
            image: "nginx:latest"
            ports: [80]
```

## Validation Rules for AI

1. **GUID**: Always exactly 5 characters, lowercase alphanumeric
2. **Wrapper**: Everything must be under `yamlforge:` block
3. **Workspace**: Always include `cloud_workspace` with name and description
4. **Provider Validation**: Only use supported providers
5. **OpenShift Versions**: Use current versions (4.18, 4.19, latest)
6. **Worker Counts**: ROSA HCP requires multiples of 3
7. **Regional Consistency**: Keep resources in same region unless specified
8. **Resource Naming**: Use descriptive, consistent naming patterns
9. **Defaults**: Apply sensible defaults for unspecified parameters

## Error Prevention

- Always validate provider names against the enum
- Check that target_cluster references exist
- Ensure GUID format compliance
- Verify OpenShift cluster types are correct
- Validate that worker counts are appropriate
- Always wrap configuration in `yamlforge:` block
- Include `cloud_workspace` section

## Advanced Features

### Cost Optimization
When users mention "cheapest" or "budget":
```yaml
guid: "cost1"
yamlforge:
  cloud_workspace:
    name: "cost-optimized"
    description: "Cost-optimized deployment"
  
  instances:
    - name: "cost-optimized-server"
      provider: "cheapest"
      size: "small"
      image: "RHEL9-latest"
```

### GPU Workloads
When users mention "AI", "ML", "GPU", "training":
```yaml
guid: "gpu01"
yamlforge:
  cloud_workspace:
    name: "gpu-workload"
    description: "GPU-enabled AI/ML workload"
  
  instances:
    - name: "gpu-workload"
      provider: "cheapest"
      gpu_type: "NVIDIA V100"
      gpu_count: 1
      size: "gpu_medium"
      image: "RHEL9-latest"
```

### Multi-Region Deployment
When users mention "high availability", "disaster recovery", "multi-region":
```yaml
guid: "ha001"
yamlforge:
  cloud_workspace:
    name: "high-availability"
    description: "Multi-region high availability deployment"
  
  instances:
    - name: "primary-server"
      provider: "aws"
      region: "us-east-1"
      size: "medium"
      image: "RHEL9-latest"
    - name: "backup-server"
      provider: "aws"
      region: "us-west-2"
      size: "medium"
      image: "RHEL9-latest"
```

This training guide enables AI systems to quickly understand YamlForge's structure and generate appropriate configurations from natural language inputs. 

# AI Training Guide for YamlForge

This document provides comprehensive training materials for AI systems to understand and generate YamlForge YAML configurations from natural language inputs.

## Core YamlForge Structure

YamlForge uses a structured YAML format with specific top-level sections:

```yaml
# Required: Unique 5-character identifier
guid: "web01"

# Optional: Legacy wrapper (still supported)
yamlforge:
  # Infrastructure and cluster definitions go here

# Direct top-level definitions (modern approach)
instances: []
openshift_clusters: []
openshift_operators: []
openshift_applications: []
```

## JSON Schema Definition

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "YamlForge Configuration Schema",
  "type": "object",
  "required": ["guid"],
  "properties": {
    "guid": {
      "type": "string",
      "pattern": "^[a-z0-9]{5}$",
      "description": "Unique 5-character identifier (lowercase alphanumeric)"
    },
    "yamlforge": {
      "type": "object",
      "description": "Legacy wrapper for configuration (optional)",
      "properties": {
        "cloud_workspace": {"$ref": "#/definitions/cloud_workspace"},
        "instances": {"$ref": "#/definitions/instances"},
        "openshift_clusters": {"$ref": "#/definitions/openshift_clusters"},
        "openshift_operators": {"$ref": "#/definitions/openshift_operators"},
        "openshift_applications": {"$ref": "#/definitions/openshift_applications"}
      }
    },
    "cloud_workspace": {"$ref": "#/definitions/cloud_workspace"},
    "instances": {"$ref": "#/definitions/instances"},
    "openshift_clusters": {"$ref": "#/definitions/openshift_clusters"},
    "openshift_operators": {"$ref": "#/definitions/openshift_operators"},
    "openshift_applications": {"$ref": "#/definitions/openshift_applications"}
  },
  "definitions": {
    "cloud_workspace": {
      "type": "object",
      "properties": {
        "name": {"type": "string"},
        "description": {"type": "string"}
      }
    },
    "instances": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "provider"],
        "properties": {
          "name": {"type": "string"},
          "provider": {
            "type": "string",
            "enum": ["aws", "azure", "gcp", "oci", "ibm_vpc", "ibm_classic", "vmware", "alibaba", "cheapest"]
          },
          "region": {"type": "string"},
          "size": {"type": "string"},
          "flavor": {"type": "string"},
          "image": {"type": "string"},
          "cores": {"type": "integer"},
          "memory": {"type": "integer"},
          "gpu_type": {"type": "string"},
          "gpu_count": {"type": "integer"},
          "ssh_key": {"type": "string"},
          "security_groups": {"type": "array", "items": {"type": "string"}},
          "tags": {"type": "object"}
        }
      }
    },
    "openshift_clusters": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "type", "provider"],
        "properties": {
          "name": {"type": "string"},
          "type": {
            "type": "string",
            "enum": ["rosa-classic", "rosa-hcp", "aro", "openshift-dedicated", "self-managed", "hypershift-mgmt", "hypershift-hosted"]
          },
          "provider": {
            "type": "string",
            "enum": ["aws", "azure", "gcp", "oci", "ibm_vpc", "vmware"]
          },
          "region": {"type": "string"},
          "version": {"type": "string"},
          "size": {"type": "string"},
          "worker_count": {"type": "integer"},
          "min_replicas": {"type": "integer"},
          "max_replicas": {"type": "integer"},
          "billing_account": {"type": "string"},
          "auto_scaling": {
            "type": "object",
            "properties": {
              "enabled": {"type": "boolean"},
              "min_replicas": {"type": "integer"},
              "max_replicas": {"type": "integer"}
            }
          },
          "networking": {
            "type": "object",
            "properties": {
              "machine_cidr": {"type": "string"},
              "pod_cidr": {"type": "string"},
              "service_cidr": {"type": "string"}
            }
          }
        }
      }
    },
    "openshift_operators": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["type", "name"],
        "properties": {
          "type": {
            "type": "string",
            "enum": ["monitoring", "logging", "gitops", "pipelines", "serverless", "service-mesh", "cert-manager", "storage", "backup"]
          },
          "name": {"type": "string"},
          "target_cluster": {"type": "string"},
          "enabled": {"type": "boolean"}
        }
      }
    },
    "openshift_applications": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name"],
        "properties": {
          "name": {"type": "string"},
          "target_cluster": {"type": "string"},
          "namespace": {"type": "string"},
          "deployment": {
            "type": "object",
            "properties": {
              "replicas": {"type": "integer"},
              "containers": {"type": "array"}
            }
          }
        }
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
openshift_clusters:
  - name: "production-rosa"
    type: "rosa-hcp"
    provider: "aws"
    region: "us-east-1"
    version: "4.19"
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
instances:
  - name: "gpu-aws"
    provider: "aws"
    size: "gpu_large"
    gpu_type: "nvidia-tesla-v100"
    gpu_count: 4
    image: "RHEL9-latest"
  - name: "gpu-azure"
    provider: "azure"
    size: "gpu_large"
    gpu_type: "nvidia-tesla-v100"
    gpu_count: 4
    image: "RHEL9-latest"
  - name: "gpu-cheapest"
    provider: "cheapest"
    gpu_type: "nvidia-tesla-v100"
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
2. Select appropriate cloud providers
3. Choose suitable instance sizes
4. Include necessary tags for organization
5. Use RHEL9-latest as default image unless specified

Output only valid YAML matching the YamlForge schema.
```

### Template 2: OpenShift Focus
```
Create a YamlForge YAML configuration for OpenShift deployment:
"{user_natural_language_input}"

Requirements:
1. Generate appropriate GUID
2. Choose correct OpenShift cluster type (rosa-hcp for production, rosa-classic for development)
3. Include monitoring and logging operators by default
4. Set worker_count to multiples of 3 for ROSA HCP
5. Use latest stable OpenShift version (4.19)

Output only valid YAML.
```

## Example AI Conversations

### Conversation 1: Simple Request
**User**: "I need a development environment with 2 servers on AWS"
**AI Response**:
```yaml
guid: "dev01"
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
openshift_clusters:
  - name: "production-cluster"
    type: "rosa-hcp"
    provider: "aws"
    region: "us-east-1"
    version: "4.19"
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
2. **Provider Validation**: Only use supported providers
3. **OpenShift Versions**: Use current versions (4.18, 4.19)
4. **Worker Counts**: ROSA HCP requires multiples of 3
5. **Regional Consistency**: Keep resources in same region unless specified
6. **Resource Naming**: Use descriptive, consistent naming patterns
7. **Defaults**: Apply sensible defaults for unspecified parameters

## Error Prevention

- Always validate provider names against the enum
- Check that target_cluster references exist
- Ensure GUID format compliance
- Verify OpenShift cluster types are correct
- Validate that worker counts are appropriate

## Advanced Features

### Cost Optimization
When users mention "cheapest" or "budget":
```yaml
instances:
  - name: "cost-optimized-server"
    provider: "cheapest"
    size: "small"  # Start with smallest viable size
    image: "RHEL9-latest"
```

### GPU Workloads
When users mention "AI", "ML", "GPU", "training":
```yaml
instances:
  - name: "gpu-workload"
    provider: "cheapest"
    gpu_type: "nvidia-tesla-v100"
    gpu_count: 1
    size: "gpu_medium"
    image: "RHEL9-latest"
```

### Multi-Region Deployment
When users mention "high availability", "disaster recovery", "multi-region":
```yaml
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
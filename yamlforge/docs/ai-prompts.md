# AI Prompt Engineering Guide for YamlForge

This guide helps users leverage AI assistants to generate YamlForge YAML configurations from natural language descriptions.

## Quick Setup for AI Assistants

### Essential Context to Provide AI

```
You are helping create YamlForge YAML configurations. YamlForge generates Terraform from YAML for multi-cloud infrastructure and OpenShift clusters.

Key constraints:
1. Everything must be wrapped in yamlforge: block
2. Always include cloud_workspace with name and description
3. GUID must be exactly 5 lowercase alphanumeric characters
4. ROSA HCP worker_count must be multiple of 3
5. Use current OpenShift versions: 4.18, 4.19, latest
6. Default image: RHEL9-latest
7. Supported providers: aws, azure, gcp, oci, ibm_vpc, ibm_classic, vmware, alibaba, cheapest

Schema reference: See docs/yamlforge-schema.json
Training guide: See docs/ai-training.md
```

## User Prompt Templates

### Template 1: Infrastructure Request
```
Create a YamlForge YAML configuration for:
"[Your infrastructure description]"

Please:
- Use an appropriate 5-character GUID
- Wrap everything in yamlforge: block
- Include cloud_workspace with name and description
- Choose suitable instance sizes
- Include tags for organization
- Use RHEL9-latest unless specified otherwise
```

**Example**: 
"Create a YamlForge YAML configuration for: 'I need 3 development servers on AWS and 2 production servers on the cheapest provider'"

### Template 2: OpenShift Request
```
Generate YamlForge YAML for OpenShift deployment:
"[Your OpenShift requirements]"

Requirements:
- Use ROSA HCP for production, ROSA Classic for development
- Include monitoring and logging operators
- Set worker_count to multiples of 3 for HCP
- Use OpenShift latest version
- Wrap everything in yamlforge: block
- Include cloud_workspace section
```

**Example**:
"Generate YamlForge YAML for OpenShift deployment: 'Production ROSA cluster with GitOps and a sample web application'"

### Template 3: Complex Multi-Component
```
Create a comprehensive YamlForge configuration:
"[Your complete infrastructure needs]"

Include:
- Appropriate cloud providers
- OpenShift clusters if needed
- Operators and applications
- Cost optimization where mentioned
- Proper inter-component references
- yamlforge: wrapper with cloud_workspace
```

**Example**:
"Create a comprehensive YamlForge configuration: 'E-commerce platform with web servers on AWS, database on cheapest provider, ROSA cluster for microservices, and monitoring'"

## Common User Intents and AI Responses

### Intent: Development Environment
**User**: "I need a development environment"
**AI Should Generate**:
```yaml
guid: "dev01"
yamlforge:
  cloud_workspace:
    name: "development-environment"
    description: "Development environment for testing"
  
  instances:
    - name: "dev-server"
      provider: "cheapest"
      flavor: "small"
      image: "RHEL9-latest"
      tags:
        environment: "development"
```

### Intent: Production OpenShift
**User**: "Production OpenShift cluster"
**AI Should Generate**:
```yaml
guid: "prod1"
yamlforge:
  cloud_workspace:
    name: "production-openshift"
    description: "Production OpenShift cluster deployment"
  
  openshift_clusters:
    - name: "production-cluster"
      type: "rosa-hcp"
      location: "us-east-1"
      version: "latest"
      flavor: "large"
      worker_count: 6
      auto_scaling:
        enabled: true
        min_replicas: 3
        max_replicas: 12

  openshift_operators:
    - type: "monitoring"
      name: "cluster-monitoring"
      target_cluster: "production-cluster"
    - type: "logging"
      name: "cluster-logging"
      target_cluster: "production-cluster"
```

### Intent: GPU Workload
**User**: "AI training infrastructure"
**AI Should Generate**:
```yaml
guid: "ai001"
yamlforge:
  cloud_workspace:
    name: "ai-training"
    description: "AI training infrastructure with GPU support"
  
  instances:
    - name: "gpu-trainer"
      provider: "cheapest"
      gpu_type: "NVIDIA V100"
      gpu_count: 2
      flavor: "gpu_large"
      image: "RHEL9-latest"
      tags:
        workload: "ai-training"
```

## Advanced Prompting Techniques

### Iterative Refinement
1. **Start Simple**: "Basic AWS infrastructure for web application"
2. **Add Details**: "Add monitoring and load balancing"
3. **Optimize**: "Make it cost-effective across multiple clouds"

### Constraint-Based Prompting
```
Create YamlForge YAML with these constraints:
- Budget-conscious (use cheapest providers)
- High availability (multiple regions)
- GPU support for AI workloads
- OpenShift for container orchestration
- Must include monitoring and logging
```

### Role-Based Prompting
```
As a DevOps engineer, I need YamlForge configuration for:
- Development environment (cost-effective)
- Staging environment (AWS, production-like)
- Production environment (multi-cloud, highly available)
Each environment needs OpenShift with GitOps.
```

## Validation Prompts

### After AI Generates Configuration
```
Please validate this YamlForge YAML:
1. Is everything wrapped in yamlforge: block?
2. Is there a cloud_workspace section with name and description?
3. Is the GUID exactly 5 lowercase alphanumeric characters?
4. Are all provider names valid?
5. Do ROSA HCP worker_counts use multiples of 3?
6. Do target_cluster references match cluster names?
7. Are OpenShift versions current (4.18, 4.19, latest)?
```

### Schema Compliance Check
```
Check this YamlForge YAML against the schema at docs/yamlforge-schema.json:
[paste generated YAML]

Fix any issues and provide the corrected version.
```

## Best Practices for Users

### Be Specific About Requirements
- **Good**: "3 web servers on AWS, 1 database on cheapest provider, production OpenShift with monitoring"
- **Poor**: "Some servers and OpenShift"

### Mention Cost Preferences
- "budget-friendly" → AI uses `provider: "cheapest"`
- "production-grade" → AI uses specific reliable providers
- "development" → AI uses smaller sizes

### Specify Environment Type
- "development/dev/test" → Small sizes, basic features
- "staging" → Medium sizes, production-like
- "production/prod" → Large sizes, full features, monitoring

### Include Integration Needs
- "with monitoring" → Adds monitoring operators
- "with GitOps" → Adds gitops operators
- "with applications" → Includes sample applications

## Common Issues and Solutions

### Issue: Missing yamlforge wrapper
**Problem**: AI generates configuration without yamlforge: block
**Solution**: Specifically request "wrap everything in yamlforge: block"

### Issue: Missing cloud_workspace
**Problem**: AI omits cloud_workspace section
**Solution**: Ask AI to "include cloud_workspace with name and description"

### Issue: Invalid GUID
**Problem**: AI generates 6-character or mixed-case GUID
**Solution**: Specifically request "exactly 5 lowercase alphanumeric characters"

### Issue: Wrong Worker Count
**Problem**: ROSA HCP gets worker_count not divisible by 3
**Solution**: Mention "ROSA HCP requires worker count multiples of 3"

### Issue: Missing Target Cluster
**Problem**: Operators/applications without target_cluster
**Solution**: Ask AI to "ensure all operators reference valid cluster names"

### Issue: Outdated Versions
**Problem**: AI uses old OpenShift versions
**Solution**: Specify "use current OpenShift version latest"

## Example Conversations

### Complete Infrastructure Request
**User**: "I need a comprehensive e-commerce platform: web servers on AWS, database on cheapest provider, ROSA cluster for microservices with monitoring and GitOps, plus a sample application"

**AI Response**:
```yaml
guid: "shop1"
yamlforge:
  cloud_workspace:
    name: "ecommerce-platform"
    description: "Comprehensive e-commerce platform with multi-cloud infrastructure"

  instances:
    - name: "web-server-1"
      provider: "aws"
      location: "us-east-1"
      flavor: "medium"
      image: "RHEL9-latest"
      tags:
        role: "web"
        tier: "frontend"
    - name: "web-server-2"
      provider: "aws"
      location: "us-east-1"
      flavor: "medium"
      image: "RHEL9-latest"
      tags:
        role: "web"
        tier: "frontend"
    - name: "database-server"
      provider: "cheapest"
      flavor: "large"
      memory: 16384
      image: "RHEL9-latest"
      tags:
        role: "database"
        tier: "backend"

  openshift_clusters:
    - name: "microservices-cluster"
      type: "rosa-hcp"
      location: "us-east-1"
      version: "latest"
      flavor: "large"
      worker_count: 6
      auto_scaling:
        enabled: true
        min_replicas: 3
        max_replicas: 12

  openshift_operators:
    - type: "monitoring"
      name: "cluster-monitoring"
      target_cluster: "microservices-cluster"
    - type: "gitops"
      name: "cluster-gitops"
      target_cluster: "microservices-cluster"

  openshift_applications:
    - name: "sample-ecommerce-app"
      target_cluster: "microservices-cluster"
      namespace: "ecommerce"
      deployment:
        replicas: 3
        containers:
          - name: "app"
            image: "nginx:latest"
            ports: [80]
```

This guide enables users to effectively communicate with AI assistants to generate proper YamlForge configurations from natural language descriptions. 

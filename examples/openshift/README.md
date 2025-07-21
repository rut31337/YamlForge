# OpenShift Examples

This directory contains examples and documentation for deploying OpenShift clusters using YamlForge's comprehensive OpenShift provider.

## 🔴 **OpenShift Provider Overview**

YamlForge supports **complete OpenShift deployments** across multiple cloud providers, including:

- **ROSA (Red Hat OpenShift Service on AWS)** - Classic and HCP variants
- **ARO (Azure Red Hat OpenShift)** - Managed OpenShift on Azure  
- **OpenShift Dedicated** - Managed service across clouds
- **Self-Managed OpenShift** - Customer-managed clusters
- **HyperShift** - Hosted control planes for all providers

## 📁 **Example Structure**

```
openshift/
├── rosa_basic_example.yaml        # ROSA cluster deployment
├── aro_basic_example.yaml         # Azure Red Hat OpenShift
├── self_managed_example.yaml      # Self-managed cluster
├── operators_example.yaml         # OpenShift operators
├── applications_example.yaml      # Application deployments
└── advanced_features_example.yaml # Advanced configurations
```

## 🚀 **Quick Start Examples**

### **ROSA (Red Hat OpenShift Service on AWS)**
```yaml
yamlforge:
  openshift_clusters:
    - name: production-rosa
      type: rosa-classic
      provider: aws
      region: us-east-1
      version: "4.14"
      compute:
        instance_type: m5.xlarge
        replicas: 3
      networking:
        machine_cidr: "10.0.0.0/16"
```

### **ARO (Azure Red Hat OpenShift)**
```yaml
yamlforge:
  openshift_clusters:
    - name: production-aro
      type: aro
      provider: azure
      region: eastus
      version: "4.14"
      compute:
        instance_type: Standard_D4s_v3
        replicas: 3
```

### **Self-Managed OpenShift**
```yaml
yamlforge:
  openshift_clusters:
    - name: self-managed-cluster
      type: self-managed
      provider: aws
      region: us-west-2
      control_plane:
        instance_type: m5.xlarge
        replicas: 3
      compute:
        instance_type: m5.large
        replicas: 5
```

## 🛠️ **OpenShift Operators**

YamlForge supports automated deployment of OpenShift operators:

```yaml
yamlforge:
  openshift_operators:
    # Monitoring Stack
    - type: monitoring
      name: cluster-monitoring
      prometheus:
        retention: "30d"
        storage_class: "gp3"
      grafana:
        enabled: true

    # Logging Stack  
    - type: logging
      name: cluster-logging
      elasticsearch:
        storage_class: "gp3"
        storage_size: "200Gi"

    # Service Mesh
    - type: service-mesh
      name: istio-system
      gateways:
        - name: main-gateway
          hosts: ["*.apps.cluster.com"]

    # Certificate Management
    - type: cert-manager
      name: automated-certificates
      default_issuer_email: "admin@company.com"
      enabled_acme_providers:
        - "letsencrypt-prod"
        - "zerossl"

    # Backup & Disaster Recovery
    - type: oadp
      name: cluster-backup
      backup_locations:
        - name: aws-backup
          provider: aws
          bucket: "cluster-backups"
```

## 🏗️ **Application Deployments**

Deploy applications alongside OpenShift clusters:

```yaml
yamlforge:
  openshift_applications:
    # Web Application
    - name: frontend-app
      namespace: production
      deployment:
        replicas: 3
        containers:
          - name: web
            image: "nginx:latest"
            ports: [80]
        
    # Database  
    - name: database
      namespace: production
      deployment:
        replicas: 1
        containers:
          - name: postgres
            image: "postgres:15"
            env:
              POSTGRES_DB: "appdb"
        storage:
          size: "50Gi"
          class: "gp3"

    # Monitoring
    - name: monitoring-stack
      namespace: monitoring
      monitoring:
        metrics: true
        alerts: true
        dashboards: true
```

## 🌐 **Multi-Cloud OpenShift**

Deploy OpenShift across multiple cloud providers:

```yaml
yamlforge:
  openshift_clusters:
    # Primary cluster on AWS
    - name: primary-cluster
      type: rosa-hcp
      provider: aws
      region: us-east-1
      
    # DR cluster on Azure
    - name: dr-cluster  
      type: aro
      provider: azure
      region: eastus2
      
    # Development cluster (self-managed)
    - name: dev-cluster
      type: self-managed
      provider: gcp
      region: us-central1

  # Cross-cluster networking
  cluster_networking:
    submariner:
      enabled: true
      cable_driver: "libreswan"
```

## 🔧 **Advanced Features**

### **Day 2 Operations**
```yaml
yamlforge:
  day2_operations:
    # Cluster Upgrades
    upgrades:
      schedule: "0 2 * * 0"  # Weekly on Sunday
      channel: "stable-4.14"
      
    # Backup Policies  
    backup:
      schedule: "0 1 * * *"   # Daily at 1 AM
      retention: "30d"
      
    # Monitoring & Alerting
    monitoring:
      alert_manager:
        slack_webhook: "https://hooks.slack.com/..."
      prometheus:
        retention: "15d"
```

### **Security & Compliance**
```yaml
yamlforge:
  security:
    # Pod Security Standards
    pod_security:
      enforce: "restricted"
      audit: "restricted"
      warn: "restricted"
      
    # Network Policies
    network_policies:
      default_deny: true
      allow_dns: true
      
    # RBAC Configuration
    rbac:
      - name: developers
        kind: Group
        permissions: ["get", "list", "watch"]
        resources: ["pods", "services"]
```

## 📊 **Supported OpenShift Versions**

- **OpenShift 4.12** - Stable LTS version
- **OpenShift 4.13** - Previous stable  
- **OpenShift 4.14** - Current stable
- **OpenShift 4.15** - Latest release

## 🔗 **Integration Examples**

### **CI/CD Pipeline Integration**
```yaml
yamlforge:
  openshift_operators:
    - type: pipelines  # Tekton
      name: ci-cd-pipelines
      
    - type: gitops     # ArgoCD
      name: gitops-deployment
      repositories:
        - url: "https://github.com/company/apps"
          path: "manifests/"
```

### **Storage Integration**
```yaml
yamlforge:
  openshift_operators:
    - type: storage    # OpenShift Data Foundation
      name: cluster-storage
      storage_classes:
        - name: "ocs-storagecluster-ceph-rbd"
          provisioner: "openshift-storage.rbd.csi.ceph.com"
```

## 📚 **Documentation Links**

- **ROSA Documentation**: Red Hat OpenShift Service on AWS
- **ARO Documentation**: Azure Red Hat OpenShift  
- **OpenShift Documentation**: Self-managed deployment guides
- **Operator Hub**: Available operators and their configurations

## 🎯 **Best Practices**

1. **Use managed services** (ROSA, ARO) for production workloads
2. **Implement proper RBAC** for multi-tenant environments
3. **Configure monitoring** and alerting from day one
4. **Plan for disaster recovery** with backup strategies
5. **Use GitOps** for application deployment and configuration management

This comprehensive OpenShift support makes YamlForge the ideal choice for enterprise Kubernetes deployments across any infrastructure platform. 
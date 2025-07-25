"""
OpenShift Application Provider for yamlforge
Handles deployment of applications across OpenShift clusters including:
- Kubernetes Deployments/Services
- Helm Chart deployments 
- ArgoCD Applications
- Multi-cluster application orchestration
"""

import json
from typing import Dict, List, Any, Optional


class ApplicationProvider:
    """Provider for OpenShift application deployments and management."""
    
    def __init__(self, converter=None):
        """Initialize the ApplicationProvider."""
        self.converter = converter
        
    def clean_name(self, name: str) -> str:
        """Clean a name for use as a Terraform/Kubernetes resource identifier."""
        if not name:
            return "unnamed"
        return name.replace("-", "_").replace(".", "_").replace(" ", "_")
    
    def generate_applications_terraform(self, config: Dict[str, Any], cluster_configs: List[Dict[str, Any]]) -> str:
        """Generate Terraform configuration for all OpenShift applications."""
        applications = config.get('openshift_applications', [])
        
        if not applications:
            return ""
            
        terraform_config = '''
# =============================================================================
# OPENSHIFT APPLICATIONS
# =============================================================================

'''
        
        # Group applications by type for better organization
        deployments = [app for app in applications if app.get('type') == 'deployment']
        helm_apps = [app for app in applications if app.get('type') == 'helm']
        argocd_apps = [app for app in applications if app.get('type') == 'argocd']
        multi_cluster_apps = [app for app in applications if app.get('type') == 'multi-cluster']
        
        # Generate deployments
        if deployments:
            terraform_config += self._generate_deployment_applications(deployments, cluster_configs)
            
        # Generate Helm applications
        if helm_apps:
            terraform_config += self._generate_helm_applications(helm_apps, cluster_configs)
            
        # Generate ArgoCD applications
        if argocd_apps:
            terraform_config += self._generate_argocd_applications(argocd_apps, cluster_configs)
            
        # Generate multi-cluster applications
        if multi_cluster_apps:
            terraform_config += self._generate_multicluster_applications(multi_cluster_apps, cluster_configs)
        
        return terraform_config
    
    def _generate_deployment_applications(self, deployments: List[Dict[str, Any]], cluster_configs: List[Dict[str, Any]]) -> str:
        """Generate Terraform for Kubernetes deployment applications."""
        terraform_config = '''
# -----------------------------------------------------------------------------
# KUBERNETES DEPLOYMENT APPLICATIONS
# -----------------------------------------------------------------------------

'''
        
        for app in deployments:
            app_name = app.get('name', 'unnamed-app')
            clean_app_name = self.clean_name(app_name)
            cluster_name = app.get('cluster')
            
            if not cluster_name:
                continue
                
            # Find cluster configuration
            cluster_config = next((c for c in cluster_configs if c.get('name') == cluster_name), None)
            if not cluster_config:
                continue
                
            clean_cluster_name = self.clean_name(cluster_name)
            
            # Application configuration
            image = app.get('image', 'nginx:latest')
            replicas = app.get('replicas', 1)
            port = app.get('port', 80)
            namespace = app.get('namespace', 'default')
            hostname = app.get('hostname')
            
            # Resource specifications
            resources = app.get('resources', {})
            requests = resources.get('requests', {})
            limits = resources.get('limits', {})
            
            # Environment variables
            env_vars = app.get('env', {})
            env_config = ""
            if env_vars:
                for key, value in env_vars.items():
                    env_config += f'''
        env {{
          name  = "{key}"
          value = "{value}"
        }}'''
            
            # Resource configuration
            resource_config = ""
            if requests or limits:
                resource_config = f'''
        resources {{'''
                if requests:
                    resource_config += f'''
          requests = {{
            cpu    = "{requests.get('cpu', '100m')}"
            memory = "{requests.get('memory', '128Mi')}"
          }}'''
                if limits:
                    resource_config += f'''
          limits = {{
            cpu    = "{limits.get('cpu', '500m')}"
            memory = "{limits.get('memory', '512Mi')}"
          }}'''
                resource_config += '''
        }}'''
            
            terraform_config += f'''
# Application: {app_name} on {cluster_name}
resource "kubernetes_namespace" "{clean_app_name}_{clean_cluster_name}_namespace" {{
  provider = kubernetes.{clean_cluster_name}_app_deployer
  
  metadata {{
    name = "{namespace}"
  }}
  
  depends_on = [kubernetes_service_account.{clean_cluster_name}_app_deployer]
}}

resource "kubernetes_deployment" "{clean_app_name}_{clean_cluster_name}_deployment" {{
  provider = kubernetes.{clean_cluster_name}_app_deployer
  
  metadata {{
    name      = "{app_name}"
    namespace = "{namespace}"
    labels = {{
      app = "{app_name}"
    }}
  }}

  spec {{
    replicas = {replicas}
    
    selector {{
      match_labels = {{
        app = "{app_name}"
      }}
    }}

    template {{
      metadata {{
        labels = {{
          app = "{app_name}"
        }}
      }}

      spec {{
        container {{
          name  = "{app_name}"
          image = "{image}"
          
          port {{
            container_port = {port}
          }}{env_config}{resource_config}
        }}
      }}
    }}
  }}
  
  depends_on = [
    kubernetes_namespace.{clean_app_name}_{clean_cluster_name}_namespace,
    kubernetes_service_account.{clean_cluster_name}_app_deployer
  ]
}}

resource "kubernetes_service" "{clean_app_name}_{clean_cluster_name}_service" {{
  provider = kubernetes.{clean_cluster_name}_app_deployer
  
  metadata {{
    name      = "{app_name}-service"
    namespace = "{namespace}"
  }}

  spec {{
    selector = {{
      app = "{app_name}"
    }}

    port {{
      port        = {port}
      target_port = {port}
    }}

    type = "ClusterIP"
  }}
  
  depends_on = [kubernetes_deployment.{clean_app_name}_{clean_cluster_name}_deployment]
}}'''

            # Add Route/Ingress if hostname is specified
            if hostname:
                terraform_config += f'''

resource "kubernetes_manifest" "{clean_app_name}_{clean_cluster_name}_route" {{
  provider = kubernetes.{clean_cluster_name}_app_deployer
  
  manifest = {{
    apiVersion = "route.openshift.io/v1"
    kind       = "Route"
    metadata = {{
      name      = "{app_name}-route"
      namespace = "{namespace}"
    }}
    spec = {{
      host = "{hostname}"
      to = {{
        kind = "Service"
        name = "{app_name}-service"
      }}
      port = {{
        targetPort = {port}
      }}
    }}
  }}
  
  depends_on = [kubernetes_service.{clean_app_name}_{clean_cluster_name}_service]
}}'''

        return terraform_config
    
    def _generate_helm_applications(self, helm_apps: List[Dict[str, Any]], cluster_configs: List[Dict[str, Any]]) -> str:
        """Generate Terraform for Helm chart applications."""
        terraform_config = '''

# -----------------------------------------------------------------------------
# HELM CHART APPLICATIONS
# -----------------------------------------------------------------------------

'''
        
        for app in helm_apps:
            app_name = app.get('name', 'unnamed-helm-app')
            clean_app_name = self.clean_name(app_name)
            cluster_name = app.get('cluster')
            
            if not cluster_name:
                continue
                
            clean_cluster_name = self.clean_name(cluster_name)
            
            # Helm configuration
            chart = app.get('chart', 'nginx')
            repository = app.get('repository', 'https://charts.bitnami.com/bitnami')
            version = app.get('version', 'latest')
            namespace = app.get('namespace', 'default')
            values = app.get('values', {})
            
            # Convert values to YAML
            values_yaml = json.dumps(values, indent=2) if values else "{}"
            
            terraform_config += f'''
# Helm Application: {app_name} on {cluster_name}
resource "kubernetes_namespace" "{clean_app_name}_{clean_cluster_name}_helm_namespace" {{
  provider = kubernetes.{clean_cluster_name}_app_deployer
  
  metadata {{
    name = "{namespace}"
  }}
  
  depends_on = [kubernetes_service_account.{clean_cluster_name}_app_deployer]
}}

resource "helm_release" "{clean_app_name}_{clean_cluster_name}_helm" {{
  provider = helm.{clean_cluster_name}
  
  name       = "{app_name}"
  repository = "{repository}"
  chart      = "{chart}"
  version    = "{version}"
  namespace  = "{namespace}"
  
  values = [
    jsonencode({values_yaml})
  ]
  
  depends_on = [
    kubernetes_namespace.{clean_app_name}_{clean_cluster_name}_helm_namespace,
    kubernetes_service_account.{clean_cluster_name}_app_deployer
  ]
}}'''

        return terraform_config
    
    def _generate_argocd_applications(self, argocd_apps: List[Dict[str, Any]], cluster_configs: List[Dict[str, Any]]) -> str:
        """Generate Terraform for ArgoCD applications."""
        terraform_config = '''

# -----------------------------------------------------------------------------
# ARGOCD GITOPS APPLICATIONS
# -----------------------------------------------------------------------------

'''
        
        for app in argocd_apps:
            app_name = app.get('name', 'unnamed-argocd-app')
            clean_app_name = self.clean_name(app_name)
            cluster_name = app.get('cluster')
            
            if not cluster_name:
                continue
                
            clean_cluster_name = self.clean_name(cluster_name)
            
            # ArgoCD configuration
            git_repo = app.get('git_repo', '')
            path = app.get('path', '.')
            branch = app.get('branch', 'main')
            namespace = app.get('namespace', 'default')
            project = app.get('project', 'default')
            sync_policy = app.get('sync_policy', {})
            
            terraform_config += f'''
# ArgoCD Application: {app_name} on {cluster_name}
resource "kubernetes_namespace" "{clean_app_name}_{clean_cluster_name}_argocd_namespace" {{
  provider = kubernetes.{clean_cluster_name}_app_deployer
  
  metadata {{
    name = "{namespace}"
  }}
  
  depends_on = [kubernetes_service_account.{clean_cluster_name}_app_deployer]
}}

resource "kubernetes_manifest" "{clean_app_name}_{clean_cluster_name}_argocd_app" {{
  provider = kubernetes.{clean_cluster_name}_app_deployer
  
  manifest = {{
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata = {{
      name      = "{app_name}"
      namespace = "openshift-gitops"
    }}
    spec = {{
      destination = {{
        namespace = "{namespace}"
        server    = "https://kubernetes.default.svc"
      }}
      project = "{project}"
      source = {{
        path           = "{path}"
        repoURL        = "{git_repo}"
        targetRevision = "{branch}"
      }}'''
      
            # Add sync policy if specified
            if sync_policy:
                sync_config = json.dumps(sync_policy, indent=6)
                terraform_config += f'''
      syncPolicy = {sync_config}'''
                
            terraform_config += f'''
    }}
  }}
  
  depends_on = [
    kubernetes_namespace.{clean_app_name}_{clean_cluster_name}_argocd_namespace,
    kubernetes_service_account.{clean_cluster_name}_app_deployer
  ]
}}'''

        return terraform_config
    
    def _generate_multicluster_applications(self, multi_apps: List[Dict[str, Any]], cluster_configs: List[Dict[str, Any]]) -> str:
        """Generate Terraform for multi-cluster applications."""
        terraform_config = '''

# -----------------------------------------------------------------------------
# MULTI-CLUSTER APPLICATIONS
# -----------------------------------------------------------------------------

'''
        
        for app in multi_apps:
            app_name = app.get('name', 'unnamed-multi-app')
            clean_app_name = self.clean_name(app_name)
            
            # Multi-cluster configuration
            target_clusters = app.get('clusters', [])
            if not target_clusters:
                # Deploy to all clusters if none specified
                target_clusters = [cluster.get('name') for cluster in cluster_configs]
            
            deployment_type = app.get('deployment_type', 'deployment')
            
            # Generate application on each target cluster
            for cluster_name in target_clusters:
                if not cluster_name:
                    continue
                    
                cluster_config = next((c for c in cluster_configs if c.get('name') == cluster_name), None)
                if not cluster_config:
                    continue
                    
                clean_cluster_name = self.clean_name(cluster_name)
                
                # Create a deployment-type application for each cluster
                if deployment_type == 'deployment':
                    terraform_config += self._generate_multicluster_deployment(app, cluster_name, clean_app_name, clean_cluster_name)
                elif deployment_type == 'argocd':
                    terraform_config += self._generate_multicluster_argocd(app, cluster_name, clean_app_name, clean_cluster_name)

        return terraform_config
    
    def _generate_multicluster_deployment(self, app: Dict[str, Any], cluster_name: str, clean_app_name: str, clean_cluster_name: str) -> str:
        """Generate a deployment for multi-cluster application."""
        app_name = app.get('name', 'unnamed-multi-app')
        image = app.get('image', 'nginx:latest')
        replicas = app.get('replicas', 1)
        port = app.get('port', 80)
        namespace = app.get('namespace', 'default')
        
        # Cluster-specific overrides
        cluster_overrides = app.get('cluster_overrides', {}).get(cluster_name, {})
        image = cluster_overrides.get('image', image)
        replicas = cluster_overrides.get('replicas', replicas)
        
        return f'''
# Multi-Cluster Application: {app_name} on {cluster_name}
resource "kubernetes_namespace" "{clean_app_name}_{clean_cluster_name}_multi_namespace" {{
  provider = kubernetes.{clean_cluster_name}_app_deployer
  
  metadata {{
    name = "{namespace}"
  }}
  
  depends_on = [kubernetes_service_account.{clean_cluster_name}_app_deployer]
}}

resource "kubernetes_deployment" "{clean_app_name}_{clean_cluster_name}_multi_deployment" {{
  provider = kubernetes.{clean_cluster_name}_app_deployer
  
  metadata {{
    name      = "{app_name}"
    namespace = "{namespace}"
    labels = {{
      app     = "{app_name}"
      cluster = "{cluster_name}"
    }}
  }}

  spec {{
    replicas = {replicas}
    
    selector {{
      match_labels = {{
        app = "{app_name}"
      }}
    }}

    template {{
      metadata {{
        labels = {{
          app     = "{app_name}"
          cluster = "{cluster_name}"
        }}
      }}

      spec {{
        container {{
          name  = "{app_name}"
          image = "{image}"
          
          port {{
            container_port = {port}
          }}
        }}
      }}
    }}
  }}
  
  depends_on = [
    kubernetes_namespace.{clean_app_name}_{clean_cluster_name}_multi_namespace,
    kubernetes_service_account.{clean_cluster_name}_app_deployer
  ]
}}

resource "kubernetes_service" "{clean_app_name}_{clean_cluster_name}_multi_service" {{
  provider = kubernetes.{clean_cluster_name}_app_deployer
  
  metadata {{
    name      = "{app_name}-service"
    namespace = "{namespace}"
  }}

  spec {{
    selector = {{
      app = "{app_name}"
    }}

    port {{
      port        = {port}
      target_port = {port}
    }}

    type = "ClusterIP"
  }}
  
  depends_on = [kubernetes_deployment.{clean_app_name}_{clean_cluster_name}_multi_deployment]
}}'''

    def _generate_multicluster_argocd(self, app: Dict[str, Any], cluster_name: str, clean_app_name: str, clean_cluster_name: str) -> str:
        """Generate ArgoCD application for multi-cluster deployment."""
        app_name = app.get('name', 'unnamed-multi-app')
        git_repo = app.get('git_repo', '')
        path = app.get('path', '.')
        branch = app.get('branch', 'main')
        namespace = app.get('namespace', 'default')
        
        return f'''
# Multi-Cluster ArgoCD Application: {app_name} on {cluster_name}
resource "kubernetes_manifest" "{clean_app_name}_{clean_cluster_name}_multi_argocd" {{
  provider = kubernetes.{clean_cluster_name}_app_deployer
  
  manifest = {{
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata = {{
      name      = "{app_name}-{cluster_name}"
      namespace = "openshift-gitops"
    }}
    spec = {{
      destination = {{
        namespace = "{namespace}"
        server    = "https://kubernetes.default.svc"
      }}
      project = "default"
      source = {{
        path           = "{path}"
        repoURL        = "{git_repo}"
        targetRevision = "{branch}"
      }}
      syncPolicy = {{
        automated = {{
          prune    = true
          selfHeal = true
        }}
      }}
    }}
  }}
  
  depends_on = [kubernetes_service_account.{clean_cluster_name}_app_deployer]
}}'''

 
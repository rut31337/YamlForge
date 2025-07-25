"""
OpenShift GitOps Operator for yamlforge
Supports ArgoCD configuration
"""

from typing import Dict, List
from ....base import BaseOpenShiftProvider


class GitOpsOperator(BaseOpenShiftProvider):
    """OpenShift GitOps operator for continuous deployment"""
    
    def __init__(self, converter):
        super().__init__(converter)
        self.operator_config = self.load_operator_config('core/gitops')
    
    def generate_gitops_operator(self, operator_config: Dict, target_clusters: List[str]) -> str:
        """Generate OpenShift GitOps (ArgoCD) operator"""
        
        # Load defaults from YAML configuration
        defaults = self.operator_config.get('defaults', {})
        subscription_config = self.operator_config.get('subscription', {})

        controller_config = self.operator_config.get('controller', {})
        repo_server_config = self.operator_config.get('repoServer', {})
        redis_config = self.operator_config.get('redis', {})

        
        operator_name = operator_config.get('name', defaults.get('name', 'openshift-gitops'))
        clean_name = self.clean_name(operator_name)
        
        # Configuration options with YAML defaults



        server_route_enabled = operator_config.get('server_route_enabled', defaults.get('server_route_enabled', True))
        server_insecure = operator_config.get('server_insecure', defaults.get('server_insecure', False))

        
        terraform_config = f'''
# =============================================================================
# OPENSHIFT GITOPS OPERATOR: {operator_name}
# =============================================================================
# Clusters: {', '.join(target_clusters) if target_clusters else 'All clusters'}

'''
        
        # Generate operator for each target cluster
        for cluster_name in target_clusters:
            clean_cluster_name = self.clean_name(cluster_name)
            
            terraform_config += f'''
# OpenShift GitOps Subscription for {cluster_name}
resource "kubernetes_manifest" "{clean_name}_{clean_cluster_name}_subscription" {{
  count    = var.deploy_day2_operations ? 1 : 0
  provider = kubernetes.{clean_cluster_name}_cluster_admin_limited
  
  manifest = {{
    apiVersion = "operators.coreos.com/v1alpha1"
    kind       = "Subscription"
    metadata = {{
      name      = "{subscription_config.get('name', 'openshift-gitops-operator')}"
      namespace = "openshift-operators"
    }}
    spec = {{
      channel = "{subscription_config.get('channel', 'latest')}"
      name    = "{subscription_config.get('name', 'openshift-gitops-operator')}"
      source  = "{subscription_config.get('source', 'redhat-operators')}"
      sourceNamespace = "{subscription_config.get('sourceNamespace', 'openshift-marketplace')}"
      installPlanApproval = "{subscription_config.get('installPlanApproval', 'Automatic')}"
    }}
  }}
  
  depends_on = [kubernetes_service_account.{clean_cluster_name}_cluster_admin_limited]
}}

# ArgoCD Instance for {cluster_name}
resource "kubernetes_manifest" "{clean_name}_{clean_cluster_name}_argocd" {{
  count    = var.deploy_day2_operations ? 1 : 0
  provider = kubernetes.{clean_cluster_name}_cluster_admin_limited
  
  manifest = {{
    apiVersion = "argoproj.io/v1beta1"
    kind       = "ArgoCD"
    metadata = {{
      name      = "openshift-gitops"
      namespace = "openshift-gitops"
    }}
    spec = {{
      server = {{
        route = {{
          enabled = {str(server_route_enabled).lower()}
        }}
        insecure = {str(server_insecure).lower()}
        grpc = {{
          web = true
        }}
      }}
      
      controller = {{
        resources = {{
          requests = {{
            cpu = "{controller_config.get('resources', {}).get('requests', {}).get('cpu', '250m')}"
            memory = "{controller_config.get('resources', {}).get('requests', {}).get('memory', '1Gi')}"
          }}
          limits = {{
            cpu = "{controller_config.get('resources', {}).get('limits', {}).get('cpu', '2')}"
            memory = "{controller_config.get('resources', {}).get('limits', {}).get('memory', '2Gi')}"
          }}
        }}
      }}
      
      redis = {{
        resources = {{
          requests = {{
            cpu = "{redis_config.get('resources', {}).get('requests', {}).get('cpu', '250m')}"
            memory = "{redis_config.get('resources', {}).get('requests', {}).get('memory', '128Mi')}"
          }}
          limits = {{
            cpu = "{redis_config.get('resources', {}).get('limits', {}).get('cpu', '500m')}"
            memory = "{redis_config.get('resources', {}).get('limits', {}).get('memory', '256Mi')}"
          }}
        }}
      }}
      
      repoServer = {{
        resources = {{
          requests = {{
            cpu = "{repo_server_config.get('resources', {}).get('requests', {}).get('cpu', '250m')}"
            memory = "{repo_server_config.get('resources', {}).get('requests', {}).get('memory', '256Mi')}"
          }}
          limits = {{
            cpu = "{repo_server_config.get('resources', {}).get('limits', {}).get('cpu', '1')}"
            memory = "{repo_server_config.get('resources', {}).get('limits', {}).get('memory', '1Gi')}"
          }}
        }}
      }}
    }}
  }}
  
  depends_on = [
    kubernetes_manifest.{clean_name}_{clean_cluster_name}_subscription,
    kubernetes_service_account.{clean_cluster_name}_cluster_admin_limited
  ]
}}

'''

        # Add ArgoCD Applications if configured
        applications = operator_config.get('applications', defaults.get('applications', []))
        for application in applications:
            app_name = self.clean_name(application.get('name', 'argocd-app'))
            terraform_config += f'''# ArgoCD Application: {application.get('name')}
resource "kubernetes_manifest" "{clean_name}_application_{app_name}" {{
  manifest = {{
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "Application"
    metadata = {{
      name      = "{app_name}"
      namespace = "{application.get('namespace', 'openshift-gitops')}"
    }}
    spec = {{
      destination = {{
        namespace = "{application.get('destination', {}).get('namespace', 'default')}"
        server = "{application.get('destination', {}).get('server', 'https://kubernetes.default.svc')}"
      }}
      project = "{application.get('project', 'default')}"
      source = {{
        path = "{application.get('source', {}).get('path', '.')}"
        repoURL = "{application.get('source', {}).get('repoURL', '')}"
        targetRevision = "{application.get('source', {}).get('targetRevision', 'HEAD')}"
      }}
      syncPolicy = {application.get('syncPolicy', {})}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_argocd]
}}

'''

        # Add ArgoCD ApplicationSets if configured
        application_sets = operator_config.get('application_sets', defaults.get('application_sets', []))
        for app_set in application_sets:
            app_set_name = self.clean_name(app_set.get('name', 'argocd-appset'))
            terraform_config += f'''# ArgoCD ApplicationSet: {app_set.get('name')}
resource "kubernetes_manifest" "{clean_name}_applicationset_{app_set_name}" {{
  manifest = {{
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "ApplicationSet"
    metadata = {{
      name      = "{app_set_name}"
      namespace = "{app_set.get('namespace', 'openshift-gitops')}"
    }}
    spec = {{
      generators = {app_set.get('generators', [])}
      template = {{
        metadata = {{
          name = "{app_set.get('template', {}).get('metadata', {}).get('name', '{{name}}')}"
        }}
        spec = {app_set.get('template', {}).get('spec', {})}
      }}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_argocd]
}}

'''

        # Add ArgoCD Projects if configured
        projects = operator_config.get('projects', defaults.get('projects', []))
        for project in projects:
            project_name = self.clean_name(project.get('name', 'argocd-project'))
            terraform_config += f'''# ArgoCD Project: {project.get('name')}
resource "kubernetes_manifest" "{clean_name}_project_{project_name}" {{
  manifest = {{
    apiVersion = "argoproj.io/v1alpha1"
    kind       = "AppProject"
    metadata = {{
      name      = "{project_name}"
      namespace = "{project.get('namespace', 'openshift-gitops')}"
    }}
    spec = {{
      description = "{project.get('description', 'ArgoCD Project')}"
      sourceRepos = {project.get('sourceRepos', ['*'])}
      destinations = {project.get('destinations', [])}
      clusterResourceWhitelist = {project.get('clusterResourceWhitelist', [])}
      namespaceResourceWhitelist = {project.get('namespaceResourceWhitelist', [])}
      roles = {project.get('roles', [])}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_argocd]
}}

'''

        return terraform_config 
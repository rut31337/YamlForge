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
        server_config = self.operator_config.get('server', {})
        controller_config = self.operator_config.get('controller', {})
        repo_server_config = self.operator_config.get('repoServer', {})
        redis_config = self.operator_config.get('redis', {})
        application_set_config = self.operator_config.get('applicationSet', {})
        
        operator_name = operator_config.get('name', defaults.get('name', 'openshift-gitops'))
        clean_name = self.clean_name(operator_name)
        
        # Configuration options with YAML defaults
        enable_cluster_admin = operator_config.get('enable_cluster_admin', defaults.get('enable_cluster_admin', False))
        enable_dex = operator_config.get('enable_dex', defaults.get('enable_dex', True))
        enable_rbac = operator_config.get('enable_rbac', defaults.get('enable_rbac', True))
        server_route_enabled = operator_config.get('server_route_enabled', defaults.get('server_route_enabled', True))
        server_insecure = operator_config.get('server_insecure', defaults.get('server_insecure', False))
        default_rbac_policy = operator_config.get('default_rbac_policy', defaults.get('default_rbac_policy', ''))
        
        terraform_config = f'''
# =============================================================================
# OPENSHIFT GITOPS OPERATOR: {operator_name}
# =============================================================================
# Clusters: {', '.join(target_clusters) if target_clusters else 'All clusters'}

# OpenShift GitOps Subscription
resource "kubernetes_manifest" "{clean_name}_subscription" {{
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
}}

# ArgoCD Instance
resource "kubernetes_manifest" "{clean_name}_argocd" {{
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
          enabled = {str(server_config.get('route', {}).get('enabled', server_route_enabled)).lower()}
          tls = {{
            termination = "{server_config.get('route', {}).get('tls', {}).get('termination', 'reencrypt')}"
            insecureEdgeTerminationPolicy = "{server_config.get('route', {}).get('tls', {}).get('insecureEdgeTerminationPolicy', 'Redirect')}"
          }}
        }}
        service = {{
          type = "{server_config.get('service', {}).get('type', 'ClusterIP')}"
        }}
        insecure = {str(server_insecure).lower()}
      }}
      
      controller = {{
        env = {controller_config.get('env', [])}
        resources = {{
          limits = {{
            cpu = "{controller_config.get('resources', {}).get('limits', {}).get('cpu', '2000m')}"
            memory = "{controller_config.get('resources', {}).get('limits', {}).get('memory', '2Gi')}"
          }}
          requests = {{
            cpu = "{controller_config.get('resources', {}).get('requests', {}).get('cpu', '250m')}"
            memory = "{controller_config.get('resources', {}).get('requests', {}).get('memory', '1Gi')}"
          }}
        }}
      }}
      
      repoServer = {{
        autoscaling = {{
          enabled = {str(repo_server_config.get('autoscaling', {}).get('enabled', False)).lower()}
        }}
        resources = {{
          limits = {{
            cpu = "{repo_server_config.get('resources', {}).get('limits', {}).get('cpu', '1000m')}"
            memory = "{repo_server_config.get('resources', {}).get('limits', {}).get('memory', '1Gi')}"
          }}
          requests = {{
            cpu = "{repo_server_config.get('resources', {}).get('requests', {}).get('cpu', '250m')}"
            memory = "{repo_server_config.get('resources', {}).get('requests', {}).get('memory', '256Mi')}"
          }}
        }}
      }}
      
      redis = {{
        resources = {{
          limits = {{
            cpu = "{redis_config.get('resources', {}).get('limits', {}).get('cpu', '500m')}"
            memory = "{redis_config.get('resources', {}).get('limits', {}).get('memory', '256Mi')}"
          }}
          requests = {{
            cpu = "{redis_config.get('resources', {}).get('requests', {}).get('cpu', '250m')}"
            memory = "{redis_config.get('resources', {}).get('requests', {}).get('memory', '128Mi')}"
          }}
        }}
      }}
      
      applicationSet = {{
        resources = {{
          limits = {{
            cpu = "{application_set_config.get('resources', {}).get('limits', {}).get('cpu', '2')}"
            memory = "{application_set_config.get('resources', {}).get('limits', {}).get('memory', '1Gi')}"
          }}
          requests = {{
            cpu = "{application_set_config.get('resources', {}).get('requests', {}).get('cpu', '250m')}"
            memory = "{application_set_config.get('resources', {}).get('requests', {}).get('memory', '512Mi')}"
          }}
        }}
      }}'''

        # Add RBAC configuration if enabled
        if enable_rbac:
            terraform_config += f'''
      
      rbac = {{
        defaultPolicy = "{default_rbac_policy}"
        policy = |
          g, system:cluster-admins, role:admin
          g, cluster-admins, role:admin'''
            
            if enable_cluster_admin:
                terraform_config += '''
          g, argocd-admins, role:admin'''
            
        terraform_config += '''
        scopes = "[groups]"
      }'''

        # Add Dex configuration if enabled
        if enable_dex:
            terraform_config += '''
      
      dex = {
        openShiftOAuth = true
        resources = {
          limits = {
            cpu = "500m"
            memory = "256Mi"
          }
          requests = {
            cpu = "250m"
            memory = "128Mi"
          }
        }
      }'''

        terraform_config += '''
    }
  }
  
  depends_on = [kubernetes_manifest.''' + clean_name + '''_subscription]
}

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
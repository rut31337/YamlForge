"""
OpenShift Pipelines Operator for yamlforge
Supports Tekton Pipelines, Triggers, and CI/CD automation
"""

from typing import Dict, List
from ....base import BaseOpenShiftProvider


class PipelinesOperator(BaseOpenShiftProvider):
    """OpenShift Pipelines operator for CI/CD and automation"""
    
    def __init__(self, converter):
        super().__init__(converter)
        self.operator_config = self.load_operator_config('core/pipelines')
    
    def generate_pipelines_operator(self, operator_config: Dict, target_clusters: List[str]) -> str:
        """Generate OpenShift Pipelines (Tekton) operator"""
        
        # Load defaults from YAML configuration
        defaults = self.operator_config.get('defaults', {})
        subscription_config = self.operator_config.get('subscription', {})
        performance_config = self.operator_config.get('performance', {})
        
        operator_name = operator_config.get('name', defaults.get('name', 'openshift-pipelines'))
        clean_name = self.clean_name(operator_name)
        
        # Configuration options with YAML defaults
        enable_tekton_config = operator_config.get('enable_tekton_config', defaults.get('enable_tekton_config', True))
        enable_performance_config = operator_config.get('enable_performance_config', defaults.get('enable_performance_config', True))



        default_timeout_minutes = operator_config.get('default_timeout_minutes', defaults.get('default_timeout_minutes', 60))
        
        terraform_config = f'''
# =============================================================================
# OPENSHIFT PIPELINES OPERATOR: {operator_name}
# =============================================================================
# Clusters: {', '.join(target_clusters) if target_clusters else 'All clusters'}

# OpenShift Pipelines Subscription
resource "kubernetes_manifest" "{clean_name}_subscription" {{
  manifest = {{
    apiVersion = "operators.coreos.com/v1alpha1"
    kind       = "Subscription"
    metadata = {{
      name      = "{subscription_config.get('name', 'openshift-pipelines-operator-rh')}"
      namespace = "openshift-operators"
    }}
    spec = {{
      channel = "{subscription_config.get('channel', 'latest')}"
      name    = "{subscription_config.get('name', 'openshift-pipelines-operator-rh')}"
      source  = "{subscription_config.get('source', 'redhat-operators')}"
      sourceNamespace = "{subscription_config.get('sourceNamespace', 'openshift-marketplace')}"
      installPlanApproval = "{subscription_config.get('installPlanApproval', 'Automatic')}"
    }}
  }}
}}

'''

        # Add TektonConfig if configuration is enabled
        if enable_tekton_config:
            terraform_config += f'''# TektonConfig for global pipeline configuration
resource "kubernetes_manifest" "{clean_name}_tekton_config" {{
  manifest = {{
    apiVersion = "operator.tekton.dev/v1alpha1"
    kind       = "TektonConfig"
    metadata = {{
      name = "config"
    }}
    spec = {{
      profile = "all"
      targetNamespace = "openshift-pipelines"
      config = {{
        defaults = {{
          default-timeout-minutes = "{default_timeout_minutes}"
          default-service-account = "pipeline"
          default-managed-by-label-value = "tekton-pipelines"
        }}'''

            # Add performance configuration if enabled
            if enable_performance_config:
                terraform_config += f'''
        performance = {{
          buckets = {performance_config.get('buckets', 10)}
          threads-per-controller = {performance_config.get('threads-per-controller', 2)}
          kube-api-qps = {performance_config.get('kube-api-qps', 100)}
          kube-api-burst = {performance_config.get('kube-api-burst', 200)}
        }}'''

            terraform_config += '''
      }
    }
  }
  
  depends_on = [kubernetes_manifest.''' + clean_name + '''_subscription]
}

'''

        # Add default cluster tasks
        cluster_tasks = operator_config.get('cluster_tasks', self.operator_config.get('cluster_tasks', []))
        for task in cluster_tasks:
            task_name = self.clean_name(task.get('name', 'cluster-task'))
            terraform_config += f'''# Cluster Task: {task.get('name')}
resource "kubernetes_manifest" "{clean_name}_cluster_task_{task_name}" {{
  manifest = {{
    apiVersion = "tekton.dev/v1beta1"
    kind       = "ClusterTask"
    metadata = {{
      name = "{task.get('name')}"
      labels = {{
        "app.kubernetes.io/version" = "{task.get('version', '0.1')}"
      }}
    }}
    spec = {{
      description = "Default {task.get('name')} cluster task"
      params = []
      results = []
      steps = [
        {{
          name = "{task.get('name')}-step"
          image = "registry.redhat.io/ubi8/ubi-minimal:latest"
          script = |
            #!/usr/bin/env bash
            echo "Running {task.get('name')} task"
        }}
      ]
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_tekton_config]
}}

'''

        # Add pipeline templates if configured
        pipeline_templates = operator_config.get('pipeline_templates', defaults.get('pipeline_templates', []))
        for template in pipeline_templates:
            template_name = self.clean_name(template.get('name', 'pipeline-template'))
            terraform_config += f'''# Pipeline Template: {template.get('name')}
resource "kubernetes_manifest" "{clean_name}_pipeline_{template_name}" {{
  manifest = {{
    apiVersion = "tekton.dev/v1beta1"
    kind       = "Pipeline"
    metadata = {{
      name      = "{template_name}"
      namespace = "{template.get('namespace', 'openshift-pipelines')}"
    }}
    spec = {{
      description = "{template.get('description', 'Pipeline template')}"
      params = {template.get('params', [])}
      tasks = {template.get('tasks', [])}
      workspaces = {template.get('workspaces', [])}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_tekton_config]
}}

'''

        # Add event listeners if configured
        event_listeners = operator_config.get('event_listeners', defaults.get('event_listeners', []))
        for listener in event_listeners:
            listener_name = self.clean_name(listener.get('name', 'event-listener'))
            terraform_config += f'''# Event Listener: {listener.get('name')}
resource "kubernetes_manifest" "{clean_name}_event_listener_{listener_name}" {{
  manifest = {{
    apiVersion = "triggers.tekton.dev/v1beta1"
    kind       = "EventListener"
    metadata = {{
      name      = "{listener_name}"
      namespace = "{listener.get('namespace', 'openshift-pipelines')}"
    }}
    spec = {{
      serviceAccountName = "{listener.get('service_account', 'pipeline')}"
      triggers = {listener.get('triggers', [])}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_tekton_config]
}}

'''

        return terraform_config 
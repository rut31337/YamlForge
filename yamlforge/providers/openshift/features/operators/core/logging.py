"""
OpenShift Logging Operator for yamlforge
Supports ELK/EFK stack configuration
"""

from typing import Dict, List
from ....base import BaseOpenShiftProvider


class LoggingOperator(BaseOpenShiftProvider):
    """OpenShift Logging operator for log aggregation and analysis"""
    
    def __init__(self, converter):
        super().__init__(converter)
        self.operator_config = self.load_operator_config('core/logging')
    
    def generate_logging_operator(self, operator_config: Dict, target_clusters: List[str]) -> str:
        """Generate OpenShift Logging (ELK/EFK) operator"""
        
        # Load defaults from YAML configuration
        defaults = self.operator_config.get('defaults', {})
        subscription_config = self.operator_config.get('subscription', {})
        elasticsearch_subscription_config = self.operator_config.get('elasticsearch_subscription', {})
        storage_config = self.operator_config.get('storage', {})
        
        operator_name = operator_config.get('name', defaults.get('name', 'cluster-logging'))
        clean_name = self.clean_name(operator_name)
        
        # Configuration options with YAML defaults
        log_retention = operator_config.get('log_retention', defaults.get('log_retention', '7d'))
        storage_size = operator_config.get('storage_size', defaults.get('storage_size', '200Gi'))
        elasticsearch_node_count = operator_config.get('elasticsearch_node_count', defaults.get('elasticsearch_node_count', 3))
        redundancy_policy = operator_config.get('redundancy_policy', defaults.get('redundancy_policy', 'SingleRedundancy'))
        collection_type = operator_config.get('collection_type', defaults.get('collection_type', 'fluentd'))
        
        # Storage class from YAML config
        storage_class = storage_config.get('storageClassName', 'gp3')
        
        terraform_config = f'''
# =============================================================================
# OPENSHIFT LOGGING OPERATOR: {operator_name}
# =============================================================================
# Clusters: {', '.join(target_clusters) if target_clusters else 'All clusters'}

# Create openshift-logging namespace
resource "kubernetes_manifest" "{clean_name}_namespace" {{
  manifest = {{
    apiVersion = "v1"
    kind       = "Namespace"
    metadata = {{
      name = "openshift-logging"
      labels = {{
        "openshift.io/cluster-monitoring" = "true"
      }}
    }}
  }}
}}

# ElasticSearch Operator Subscription
resource "kubernetes_manifest" "{clean_name}_elasticsearch_subscription" {{
  manifest = {{
    apiVersion = "operators.coreos.com/v1alpha1"
    kind       = "Subscription"
    metadata = {{
      name      = "{elasticsearch_subscription_config.get('name', 'elasticsearch-operator')}"
      namespace = "openshift-operators-redhat"
    }}
    spec = {{
      channel = "{elasticsearch_subscription_config.get('channel', 'stable')}"
      name    = "{elasticsearch_subscription_config.get('name', 'elasticsearch-operator')}"
      source  = "{elasticsearch_subscription_config.get('source', 'redhat-operators')}"
      sourceNamespace = "{elasticsearch_subscription_config.get('sourceNamespace', 'openshift-marketplace')}"
      installPlanApproval = "Automatic"
    }}
  }}
}}

# Cluster Logging Subscription
resource "kubernetes_manifest" "{clean_name}_subscription" {{
  manifest = {{
    apiVersion = "operators.coreos.com/v1alpha1"
    kind       = "Subscription"
    metadata = {{
      name      = "{subscription_config.get('name', 'cluster-logging')}"
      namespace = "openshift-logging"
    }}
    spec = {{
      channel = "{subscription_config.get('channel', 'stable')}"
      name    = "{subscription_config.get('name', 'cluster-logging')}"
      source  = "{subscription_config.get('source', 'redhat-operators')}"
      sourceNamespace = "{subscription_config.get('sourceNamespace', 'openshift-marketplace')}"
      installPlanApproval = "{subscription_config.get('installPlanApproval', 'Automatic')}"
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_namespace]
}}

# Cluster Logging Instance
resource "kubernetes_manifest" "{clean_name}_instance" {{
  count    = var.deploy_day2_operations ? 1 : 0
  manifest = {{
    apiVersion = "logging.coreos.com/v1"
    kind       = "ClusterLogging"
    metadata = {{
      name      = "instance"
      namespace = "openshift-logging"
    }}
    spec = {{
      managementState = "Managed"
      logStore = {{
        type = "elasticsearch"
        elasticsearch = {{
          nodeCount = {elasticsearch_node_count}
          storage = {{
            storageClassName = "{storage_class}"
            size = "{storage_size}"
          }}
          redundancyPolicy = "{redundancy_policy}"
        }}
        retentionPolicy = {{
          application = {{
            maxAge = "{log_retention}"
          }}
          infra = {{
            maxAge = "{log_retention}"
          }}
          audit = {{
            maxAge = "{log_retention}"
          }}
        }}
      }}
      visualization = {{
        type = "kibana"
        kibana = {{
          replicas = 1
        }}
      }}
      collection = {{
        logs = {{
          type = "{collection_type}"
          {collection_type} = {{}}
        }}
      }}
    }}
  }}
  
  depends_on = [
    kubernetes_manifest.{clean_name}_subscription,
    kubernetes_manifest.{clean_name}_elasticsearch_subscription
  ]
}}

'''

        # Add log forwarders if configured
        log_forwarders = operator_config.get('log_forwarders', defaults.get('log_forwarders', []))
        for forwarder in log_forwarders:
            forwarder_name = self.clean_name(forwarder.get('name', 'log-forwarder'))
            terraform_config += f'''# Log Forwarder: {forwarder.get('name')}
resource "kubernetes_manifest" "{clean_name}_forwarder_{forwarder_name}" {{
  manifest = {{
    apiVersion = "logging.coreos.com/v1"
    kind       = "ClusterLogForwarder"
    metadata = {{
      name      = "{forwarder_name}"
      namespace = "openshift-logging"
    }}
    spec = {{
      outputs = {forwarder.get('outputs', [])}
      pipelines = {forwarder.get('pipelines', [])}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_instance]
}}

'''

        return terraform_config 
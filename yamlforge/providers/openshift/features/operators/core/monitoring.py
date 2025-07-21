"""
OpenShift Monitoring Operator for yamlforge
Supports Prometheus, Grafana, and AlertManager configuration
"""

from typing import Dict, List
from ....base import BaseOpenShiftProvider


class MonitoringOperator(BaseOpenShiftProvider):
    """OpenShift Monitoring operator for observability"""
    
    def __init__(self, converter):
        super().__init__(converter)
        self.operator_config = self.load_operator_config('core/monitoring')
    
    def generate_monitoring_operator(self, operator_config: Dict, target_clusters: List[str]) -> str:
        """Generate OpenShift Monitoring (Prometheus/Grafana) operator"""
        
        # Load defaults from YAML configuration
        defaults = self.operator_config.get('defaults', {})
        
        operator_name = operator_config.get('name', defaults.get('name', 'cluster-monitoring'))
        clean_name = self.clean_name(operator_name)
        
        # Configuration options with YAML defaults
        retention_days = operator_config.get('retention_days', defaults.get('retention_days', 15))
        storage_size = operator_config.get('storage_size', defaults.get('storage_size', '50Gi'))
        enable_user_workload_monitoring = operator_config.get('enable_user_workload_monitoring', defaults.get('enable_user_workload_monitoring', True))
        alertmanager_storage = operator_config.get('alertmanager_storage_size', defaults.get('alertmanager_storage_size', '10Gi'))
        node_selector = operator_config.get('node_selector', defaults.get('node_selector', {"node-role.kubernetes.io/infra": ""}))
        
        # Storage configuration from YAML
        storage_config = self.operator_config.get('storage', {})
        storage_class = storage_config.get('storageClassName', 'gp3')
        
        # Tolerations from YAML
        tolerations = self.operator_config.get('tolerations', [])
        
        terraform_config = f'''
# =============================================================================
# OPENSHIFT MONITORING OPERATOR: {operator_name}
# =============================================================================
# Clusters: {', '.join(target_clusters) if target_clusters else 'All clusters'}

# Cluster Monitoring Configuration
resource "kubernetes_manifest" "{clean_name}_cluster_monitoring" {{
  manifest = {{
    apiVersion = "v1"
    kind       = "ConfigMap"
    metadata = {{
      name      = "cluster-monitoring-config"
      namespace = "openshift-monitoring"
    }}
    data = {{
      "config.yaml" = yamlencode({{
        prometheusK8s = {{
          retention = "{retention_days}d"
          volumeClaimTemplate = {{
            spec = {{
              storageClassName = "{storage_class}"
              resources = {{
                requests = {{
                  storage = "{storage_size}"
                }}
              }}
            }}
          }}'''

        # Add node selector if configured
        if node_selector:
            terraform_config += f'''
          nodeSelector = {{{', '.join(f'"{k}" = "{v}"' for k, v in node_selector.items())}}}'''

        # Add tolerations if configured
        if tolerations:
            terraform_config += '''
          tolerations = ['''
            for toleration in tolerations:
                terraform_config += f'''
            {{
              key    = "{toleration.get('key', '')}"
              effect = "{toleration.get('effect', '')}"
            }}'''
            terraform_config += '''
          ]'''

        terraform_config += f'''
        }}
        
        alertmanagerMain = {{
          volumeClaimTemplate = {{
            spec = {{
              storageClassName = "{storage_class}"
              resources = {{
                requests = {{
                  storage = "{alertmanager_storage}"
                }}
              }}
            }}
          }}
        }}
        
        enableUserWorkloadMonitoring = {str(enable_user_workload_monitoring).lower()}
      }})
    }}
  }}
}}

'''

        # Add user workload monitoring configuration if enabled
        if enable_user_workload_monitoring:
            user_retention_days = operator_config.get('user_retention_days', defaults.get('user_retention_days', 7))
            user_storage_size = operator_config.get('user_storage_size', defaults.get('user_storage_size', '20Gi'))
            
            terraform_config += f'''# User Workload Monitoring Configuration
resource "kubernetes_manifest" "{clean_name}_user_workload_monitoring" {{
  manifest = {{
    apiVersion = "v1"
    kind       = "ConfigMap"
    metadata = {{
      name      = "user-workload-monitoring-config"
      namespace = "openshift-user-workload-monitoring"
    }}
    data = {{
      "config.yaml" = yamlencode({{
        prometheus = {{
          retention = "{user_retention_days}d"
          volumeClaimTemplate = {{
            spec = {{
              storageClassName = "{storage_class}"
              resources = {{
                requests = {{
                  storage = "{user_storage_size}"
                }}
              }}
            }}
          }}
        }}
        
        thanosRuler = {{
          retention = "{user_retention_days}d"
          volumeClaimTemplate = {{
            spec = {{
              storageClassName = "{storage_class}"
              resources = {{
                requests = {{
                  storage = "{user_storage_size}"
                }}
              }}
            }}
          }}
        }}
      }})
    }}
  }}
}}

'''

        # Add custom prometheus rules if configured
        custom_rules = operator_config.get('custom_rules', defaults.get('custom_rules', []))
        for rule in custom_rules:
            rule_name = self.clean_name(rule.get('name', 'custom-rule'))
            terraform_config += f'''# Custom Prometheus Rule: {rule.get('name')}
resource "kubernetes_manifest" "{clean_name}_custom_rule_{rule_name}" {{
  manifest = {{
    apiVersion = "monitoring.coreos.com/v1"
    kind       = "PrometheusRule"
    metadata = {{
      name      = "{rule_name}"
      namespace = "{rule.get('namespace', 'openshift-monitoring')}"
      labels = {{
        prometheus = "kube-prometheus"
        role       = "alert-rules"
      }}
    }}
    spec = {{
      groups = {rule.get('groups', [])}
    }}
  }}
}}

'''

        return terraform_config 
        return terraform_config 
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
        """Generate OpenShift monitoring operator"""
        
        # Load defaults from YAML configuration
        defaults = self.operator_config.get('defaults', {})
        monitoring_config = operator_config.get('monitoring', defaults.get('monitoring', {}))
        alertmanager_config = operator_config.get('alertmanager', defaults.get('alertmanager', {}))
        
        operator_name = operator_config.get('name', defaults.get('name', 'monitoring-operator'))
        clean_name = self.clean_name(operator_name)
        
        # Configuration options with YAML defaults
        enable_alertmanager = operator_config.get('enable_alertmanager', defaults.get('enable_alertmanager', True))
        
        terraform_config = f'''
# =============================================================================
# MONITORING OPERATOR: {operator_name}
# =============================================================================
# Clusters: {', '.join(target_clusters) if target_clusters else 'All clusters'}

'''
        
        # Generate operator for each target cluster
        for cluster_name in target_clusters:
            clean_cluster_name = self.clean_name(cluster_name)
            
            terraform_config += f'''
# User Workload Monitoring ConfigMap for {cluster_name}
resource "kubernetes_manifest" "{clean_name}_{clean_cluster_name}_user_workload_monitoring" {{
  count    = var.deploy_day2_operations ? 1 : 0
  provider = kubernetes.{clean_cluster_name}_cluster_admin_limited
  
  manifest = {{
    apiVersion = "v1"
    kind       = "ConfigMap"
    metadata = {{
      name      = "user-workload-monitoring-config"
      namespace = "openshift-user-workload-monitoring"
    }}
    data = {{
      "config.yaml" = <<-EOT
        prometheus:
          retention: {monitoring_config.get('retention', '15d')}
          resources:
            requests:
              cpu: {monitoring_config.get('resources', {}).get('requests', {}).get('cpu', '200m')}
              memory: {monitoring_config.get('resources', {}).get('requests', {}).get('memory', '2Gi')}
          volumeClaimTemplate:
            spec:
              storageClassName: {monitoring_config.get('storageClass', 'gp2')}
              resources:
                requests:
                  storage: {monitoring_config.get('storage', '40Gi')}
        alertmanager:
          enabled: {str(enable_alertmanager).lower()}
          resources:
            requests:
              cpu: {alertmanager_config.get('resources', {}).get('requests', {}).get('cpu', '100m')}
              memory: {alertmanager_config.get('resources', {}).get('requests', {}).get('memory', '200Mi')}
          volumeClaimTemplate:
            spec:
              storageClassName: {alertmanager_config.get('storageClass', 'gp2')}
              resources:
                requests:
                  storage: {alertmanager_config.get('storage', '20Gi')}
      EOT
    }}
  }}
  
  depends_on = [kubernetes_service_account.{clean_cluster_name}_cluster_admin_limited]
}}

'''
        
        return terraform_config 
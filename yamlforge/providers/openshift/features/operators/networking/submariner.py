"""
OpenShift Submariner Operator for yamlforge
Supports cross-cluster connectivity and multi-cluster networking
"""

from typing import Dict, List
from ....base import BaseOpenShiftProvider


class SubmarinerOperator(BaseOpenShiftProvider):
    """OpenShift Submariner operator for cross-cluster connectivity"""
    
    def __init__(self, converter):
        super().__init__(converter)
        self.operator_config = self.load_operator_config('networking/submariner')
    
    def generate_submariner_operator(self, operator_config: Dict, target_clusters: List[str]) -> str:
        """Generate Submariner operator for cross-cluster connectivity"""
        
        # Load defaults from YAML configuration
        defaults = self.operator_config.get('defaults', {})
        subscription_config = self.operator_config.get('subscription', {})
        broker_config = self.operator_config.get('broker', {})
        
        operator_name = operator_config.get('name', defaults.get('name', 'submariner'))
        clean_name = self.clean_name(operator_name)
        
        # Configuration options with YAML defaults
        enable_broker = operator_config.get('enable_broker', defaults.get('enable_broker', True))
        cluster_id = operator_config.get('cluster_id', defaults.get('cluster_id', 'cluster1'))
        service_cidr = operator_config.get('service_cidr', defaults.get('service_cidr', '10.96.0.0/16'))
        cluster_cidr = operator_config.get('cluster_cidr', defaults.get('cluster_cidr', '10.244.0.0/16'))
        
        terraform_config = f'''
# =============================================================================
# SUBMARINER OPERATOR: {operator_name}
# =============================================================================
# Clusters: {', '.join(target_clusters) if target_clusters else 'All clusters'}

# Create submariner-operator namespace
resource "kubernetes_manifest" "{clean_name}_namespace" {{
  manifest = {{
    apiVersion = "v1"
    kind       = "Namespace"
    metadata = {{
      name = "submariner-operator"
      labels = {{
        "openshift.io/cluster-monitoring" = "true"
      }}
    }}
  }}
}}

# Submariner Operator Subscription
resource "kubernetes_manifest" "{clean_name}_subscription" {{
  manifest = {{
    apiVersion = "operators.coreos.com/v1alpha1"
    kind       = "Subscription"
    metadata = {{
      name      = "{subscription_config.get('name', 'submariner')}"
      namespace = "submariner-operator"
    }}
    spec = {{
      channel = "{subscription_config.get('channel', 'stable-0.16')}"
      name    = "{subscription_config.get('name', 'submariner')}"
      source  = "{subscription_config.get('source', 'redhat-operators')}"
      sourceNamespace = "{subscription_config.get('sourceNamespace', 'openshift-marketplace')}"
      installPlanApproval = "{subscription_config.get('installPlanApproval', 'Automatic')}"
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_namespace]
}}

'''

        # Add Broker if enabled
        if enable_broker:
            terraform_config += f'''# Submariner Broker
resource "kubernetes_manifest" "{clean_name}_broker" {{
  manifest = {{
    apiVersion = "submariner.io/v1alpha1"
    kind       = "Broker"
    metadata = {{
      name      = "submariner-broker"
      namespace = "submariner-operator"
    }}
    spec = {{
      globalnetEnabled = {str(broker_config.get('globalnet_enabled', False)).lower()}
      defaultGlobalnetClusterSize = {broker_config.get('default_globalnet_cluster_size', 8192)}
      globalnetCIDR = "{broker_config.get('globalnet_cidr', '242.0.0.0/8')}"
      defaultCustomDomains = {broker_config.get('default_custom_domains', [])}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_subscription]
}}

'''

        # Add Submariner configuration
        terraform_config += f'''# Submariner Configuration
resource "kubernetes_manifest" "{clean_name}_submariner" {{
  manifest = {{
    apiVersion = "submariner.io/v1alpha1"
    kind       = "Submariner"
    metadata = {{
      name      = "submariner"
      namespace = "submariner-operator"
    }}
    spec = {{
      clusterID = "{cluster_id}"
      serviceCIDR = "{service_cidr}"
      clusterCIDR = "{cluster_cidr}"
      repository = "{defaults.get('repository', 'quay.io/submariner')}"
      version = "{defaults.get('version', 'release-0.16')}"
      ceIPSecNATTPort = {defaults.get('ce_ipsec_natt_port', 4500)}
      ceIPSecIKEPort = {defaults.get('ce_ipsec_ike_port', 500)}
      ceIPSecDebug = {str(defaults.get('ce_ipsec_debug', False)).lower()}
      natEnabled = {str(defaults.get('nat_enabled', True)).lower()}
      debug = {str(defaults.get('debug', False)).lower()}
      loadBalancerEnabled = {str(defaults.get('load_balancer_enabled', False)).lower()}
      colorCodes = "{defaults.get('color_codes', 'blue')}"
      connectionHealthCheck = {{
        enabled = {str(defaults.get('health_check_enabled', True)).lower()}
        intervalSeconds = {defaults.get('health_check_interval', 1)}
        maxPacketLossCount = {defaults.get('max_packet_loss_count', 5)}
      }}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_broker]
}}

'''

        # Add ServiceExports if configured
        service_exports = operator_config.get('service_exports', defaults.get('service_exports', []))
        for service_export in service_exports:
            export_name = self.clean_name(service_export.get('name', 'service-export'))
            terraform_config += f'''# Service Export: {service_export.get('name')}
resource "kubernetes_manifest" "{clean_name}_export_{export_name}" {{
  manifest = {{
    apiVersion = "multicluster.x-k8s.io/v1alpha1"
    kind       = "ServiceExport"
    metadata = {{
      name      = "{service_export.get('service_name', 'my-service')}"
      namespace = "{service_export.get('namespace', 'default')}"
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_submariner]
}}

'''

        # Add Gateways if configured
        gateways = operator_config.get('gateways', defaults.get('gateways', []))
        for gateway in gateways:
            gateway_name = self.clean_name(gateway.get('name', 'gateway'))
            terraform_config += f'''# Gateway: {gateway.get('name')}
resource "kubernetes_manifest" "{clean_name}_gateway_{gateway_name}" {{
  manifest = {{
    apiVersion = "submariner.io/v1alpha1"
    kind       = "Gateway"
    metadata = {{
      name      = "{gateway_name}"
      namespace = "submariner-operator"
    }}
    spec = {{
      ha = {{
        enabled = {str(gateway.get('ha_enabled', False)).lower()}
      }}
      connections = {gateway.get('connections', [])}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_submariner]
}}

'''

        return terraform_config 
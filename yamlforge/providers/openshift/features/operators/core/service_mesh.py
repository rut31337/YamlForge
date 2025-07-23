"""
OpenShift Service Mesh Operator for yamlforge
Supports Istio/Maistra configuration
"""

from typing import Dict, List
from ....base import BaseOpenShiftProvider


class ServiceMeshOperator(BaseOpenShiftProvider):
    """OpenShift Service Mesh operator for microservices communication"""
    
    def __init__(self, converter):
        super().__init__(converter)
        self.operator_config = self.load_operator_config('core/service_mesh')
    
    def generate_service_mesh_operator(self, operator_config: Dict, target_clusters: List[str]) -> str:
        """Generate OpenShift Service Mesh (Istio/Maistra) operator"""
        
        # Load defaults from YAML configuration
        defaults = self.operator_config.get('defaults', {})
        subscription_config = self.operator_config.get('subscription', {})
        kiali_subscription_config = self.operator_config.get('kiali_subscription', {})
        jaeger_subscription_config = self.operator_config.get('jaeger_subscription', {})
        control_plane_config = self.operator_config.get('control_plane', {})
        tracing_config = self.operator_config.get('tracing', {})
        addons_config = self.operator_config.get('addons', {})
        
        operator_name = operator_config.get('name', defaults.get('name', 'service-mesh'))
        clean_name = self.clean_name(operator_name)
        
        # Configuration options with YAML defaults
        version = operator_config.get('version', defaults.get('version', 'v2.5'))
        jaeger_storage_type = operator_config.get('jaeger_storage_type', defaults.get('jaeger_storage_type', 'Memory'))
        tracing_sampling = operator_config.get('tracing_sampling', defaults.get('tracing_sampling', 1000))
        enable_kiali = operator_config.get('enable_kiali', defaults.get('enable_kiali', True))
        enable_grafana = operator_config.get('enable_grafana', defaults.get('enable_grafana', True))
        control_plane_namespace = operator_config.get('control_plane_namespace', defaults.get('control_plane_namespace', 'istio-system'))
        
        terraform_config = f'''
# =============================================================================
# OPENSHIFT SERVICE MESH OPERATOR: {operator_name}
# =============================================================================
# Clusters: {', '.join(target_clusters) if target_clusters else 'All clusters'}

# Create istio-system namespace
resource "kubernetes_manifest" "{clean_name}_namespace" {{
  manifest = {{
    apiVersion = "v1"
    kind       = "Namespace"
    metadata = {{
      name = "{control_plane_namespace}"
      labels = {{
        "maistra.io/member-of" = "{control_plane_namespace}"
      }}
    }}
  }}
}}

# Service Mesh Subscription
resource "kubernetes_manifest" "{clean_name}_subscription" {{
  manifest = {{
    apiVersion = "operators.coreos.com/v1alpha1"
    kind       = "Subscription"
    metadata = {{
      name      = "{subscription_config.get('name', 'servicemeshoperator')}"
      namespace = "openshift-operators"
    }}
    spec = {{
      channel = "{subscription_config.get('channel', 'stable')}"
      name    = "{subscription_config.get('name', 'servicemeshoperator')}"
      source  = "{subscription_config.get('source', 'redhat-operators')}"
      sourceNamespace = "{subscription_config.get('sourceNamespace', 'openshift-marketplace')}"
    }}
  }}
}}

# Kiali Subscription
resource "kubernetes_manifest" "{clean_name}_kiali_subscription" {{
  manifest = {{
    apiVersion = "operators.coreos.com/v1alpha1"
    kind       = "Subscription"
    metadata = {{
      name      = "{kiali_subscription_config.get('name', 'kiali-ossm')}"
      namespace = "openshift-operators"
    }}
    spec = {{
      channel = "{kiali_subscription_config.get('channel', 'stable')}"
      name    = "{kiali_subscription_config.get('name', 'kiali-ossm')}"
      source  = "{kiali_subscription_config.get('source', 'redhat-operators')}"
      sourceNamespace = "{kiali_subscription_config.get('sourceNamespace', 'openshift-marketplace')}"
    }}
  }}
}}

# Jaeger Subscription
resource "kubernetes_manifest" "{clean_name}_jaeger_subscription" {{
  manifest = {{
    apiVersion = "operators.coreos.com/v1alpha1"
    kind       = "Subscription"
    metadata = {{
      name      = "{jaeger_subscription_config.get('name', 'jaeger-product')}"
      namespace = "openshift-operators"
    }}
    spec = {{
      channel = "{jaeger_subscription_config.get('channel', 'stable')}"
      name    = "{jaeger_subscription_config.get('name', 'jaeger-product')}"
      source  = "{jaeger_subscription_config.get('source', 'redhat-operators')}"
      sourceNamespace = "{jaeger_subscription_config.get('sourceNamespace', 'openshift-marketplace')}"
    }}
  }}
}}

# Service Mesh Control Plane
resource "kubernetes_manifest" "{clean_name}_control_plane" {{
  manifest = {{
    apiVersion = "maistra.io/v2"
    kind       = "ServiceMeshControlPlane"
    metadata = {{
      name      = "basic"
      namespace = "{control_plane_namespace}"
    }}
    spec = {{
      version = "{control_plane_config.get('version', version)}"
      tracing = {{
        type = "{tracing_config.get('type', 'Jaeger')}"
        sampling = {tracing_config.get('sampling', tracing_sampling)}
      }}
      addons = {{
        jaeger = {{
          install = {{
            storage = {{
              type = "{addons_config.get('jaeger', {}).get('install', {}).get('storage', {}).get('type', jaeger_storage_type)}"
            }}
          }}
        }}
        kiali = {{
          enabled = {str(addons_config.get('kiali', {}).get('enabled', enable_kiali)).lower()}
        }}
        grafana = {{
          enabled = {str(addons_config.get('grafana', {}).get('enabled', enable_grafana)).lower()}
        }}
      }}
    }}
  }}
  
  depends_on = [
    kubernetes_manifest.{clean_name}_subscription,
    kubernetes_manifest.{clean_name}_kiali_subscription,
    kubernetes_manifest.{clean_name}_jaeger_subscription,
    kubernetes_manifest.{clean_name}_namespace
  ]
}}

'''

        # Add Elasticsearch configuration for Jaeger if specified
        elasticsearch_config = operator_config.get('elasticsearch_config', defaults.get('elasticsearch_config', {}))
        if elasticsearch_config and jaeger_storage_type == 'Elasticsearch':
            elasticsearch_name = self.clean_name(elasticsearch_config.get('name', 'jaeger-elasticsearch'))
            terraform_config += f'''# Elasticsearch for Jaeger
resource "kubernetes_manifest" "{clean_name}_jaeger_elasticsearch" {{
  manifest = {{
    apiVersion = "logging.coreos.com/v1"
    kind       = "Elasticsearch"
    metadata = {{
      name      = "{elasticsearch_name}"
      namespace = "{control_plane_namespace}"
    }}
    spec = {{
      managementState = "Managed"
      nodes = [
        {{
          nodeCount = {elasticsearch_config.get('node_count', 3)}
          storage = {{
            storageClassName = "{elasticsearch_config.get('storage_class', 'gp3')}"
            size = "{elasticsearch_config.get('storage_size', '200Gi')}"
          }}
          roles = ["client", "data", "master"]
        }}
      ]
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_control_plane]
}}

'''

        # Add Service Mesh Member Roll for member namespaces
        member_namespaces = operator_config.get('member_namespaces', defaults.get('member_namespaces', []))
        if member_namespaces:
            terraform_config += f'''# Service Mesh Member Roll
resource "kubernetes_manifest" "{clean_name}_member_roll" {{
  manifest = {{
    apiVersion = "maistra.io/v1"
    kind       = "ServiceMeshMemberRoll"
    metadata = {{
      name      = "default"
      namespace = "{control_plane_namespace}"
    }}
    spec = {{
      members = {member_namespaces}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_control_plane]
}}

'''

        # Add PeerAuthentication for mTLS if configured
        mtls_mode = operator_config.get('mtls_mode', defaults.get('mtls_mode', 'PERMISSIVE'))
        terraform_config += f'''# Default PeerAuthentication for mTLS
resource "kubernetes_manifest" "{clean_name}_peer_authentication" {{
  manifest = {{
    apiVersion = "security.istio.io/v1beta1"
    kind       = "PeerAuthentication"
    metadata = {{
      name      = "default"
      namespace = "{control_plane_namespace}"
    }}
    spec = {{
      mtls = {{
        mode = "{mtls_mode}"
      }}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_control_plane]
}}

'''

        return terraform_config 
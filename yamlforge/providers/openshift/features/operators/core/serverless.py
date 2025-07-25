"""
OpenShift Serverless Operator for yamlforge
Supports Knative Serving and Eventing configuration
"""

from typing import Dict, List
from ....base import BaseOpenShiftProvider


class ServerlessOperator(BaseOpenShiftProvider):
    """OpenShift Serverless operator for event-driven applications"""
    
    def __init__(self, converter):
        super().__init__(converter)
        self.operator_config = self.load_operator_config('core/serverless')
    
    def generate_serverless_operator(self, operator_config: Dict, target_clusters: List[str]) -> str:
        """Generate OpenShift Serverless (Knative) operator"""
        
        # Load defaults from YAML configuration
        defaults = self.operator_config.get('defaults', {})
        subscription_config = self.operator_config.get('subscription', {})
        serving_config = self.operator_config.get('serving', {})
        eventing_config = self.operator_config.get('eventing', {})
        kafka_config = self.operator_config.get('kafka', {})
        
        operator_name = operator_config.get('name', defaults.get('name', 'openshift-serverless'))
        clean_name = self.clean_name(operator_name)
        
        # Configuration options with YAML defaults
        enable_serving = operator_config.get('enable_serving', defaults.get('enable_serving', True))
        enable_eventing = operator_config.get('enable_eventing', defaults.get('enable_eventing', True))
        enable_kafka = operator_config.get('enable_kafka', defaults.get('enable_kafka', False))
        serving_namespace = operator_config.get('serving_namespace', defaults.get('serving_namespace', 'knative-serving'))
        eventing_namespace = operator_config.get('eventing_namespace', defaults.get('eventing_namespace', 'knative-eventing'))
        
        terraform_config = f'''
# =============================================================================
# OPENSHIFT SERVERLESS OPERATOR: {operator_name}
# =============================================================================
# Clusters: {', '.join(target_clusters) if target_clusters else 'All clusters'}

# OpenShift Serverless Subscription
resource "kubernetes_manifest" "{clean_name}_subscription" {{
  manifest = {{
    apiVersion = "operators.coreos.com/v1alpha1"
    kind       = "Subscription"
    metadata = {{
      name      = "{subscription_config.get('name', 'serverless-operator')}"
      namespace = "openshift-operators"
    }}
    spec = {{
      channel = "{subscription_config.get('channel', 'stable')}"
      name    = "{subscription_config.get('name', 'serverless-operator')}"
      source  = "{subscription_config.get('source', 'redhat-operators')}"
      sourceNamespace = "{subscription_config.get('sourceNamespace', 'openshift-marketplace')}"
      installPlanApproval = "{subscription_config.get('installPlanApproval', 'Automatic')}"
    }}
  }}
}}

'''

        # Add Knative Serving if enabled
        if enable_serving:
            # Knative Serving configuration options with YAML defaults




            
            terraform_config += f'''# Knative Serving Namespace
resource "kubernetes_manifest" "{clean_name}_serving_namespace" {{
  manifest = {{
    apiVersion = "v1"
    kind       = "Namespace"
    metadata = {{
      name = "{serving_namespace}"
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_subscription]
}}

# Knative Serving
resource "kubernetes_manifest" "{clean_name}_serving" {{
  manifest = {{
    apiVersion = "operator.knative.dev/v1beta1"
    kind       = "KnativeServing"
    metadata = {{
      name      = "knative-serving"
      namespace = "{serving_namespace}"
    }}
    spec = {{
      config = {serving_config.get('config', {})}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_serving_namespace]
}}

'''

        # Add Knative Eventing if enabled
        if enable_eventing:
            terraform_config += f'''# Knative Eventing Namespace
resource "kubernetes_manifest" "{clean_name}_eventing_namespace" {{
  manifest = {{
    apiVersion = "v1"
    kind       = "Namespace"
    metadata = {{
      name = "{eventing_namespace}"
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_subscription]
}}

# Knative Eventing
resource "kubernetes_manifest" "{clean_name}_eventing" {{
  manifest = {{
    apiVersion = "operator.knative.dev/v1beta1"
    kind       = "KnativeEventing"
    metadata = {{
      name      = "knative-eventing"
      namespace = "{eventing_namespace}"
    }}
    spec = {{
      config = {eventing_config.get('config', {})}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_eventing_namespace]
}}

'''

        # Add Kafka configuration if enabled
        if enable_kafka:
            kafka_bootstrap_servers = operator_config.get('kafka_bootstrap_servers', kafka_config.get('bootstrap_servers', 'my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092'))
            terraform_config += f'''# Knative Kafka
resource "kubernetes_manifest" "{clean_name}_kafka" {{
  manifest = {{
    apiVersion = "operator.knative.dev/v1beta1"
    kind       = "KnativeKafka"
    metadata = {{
      name      = "knative-kafka"
      namespace = "{eventing_namespace}"
    }}
    spec = {{
      channel = {{
        enabled = true
        bootstrapServers = "{kafka_bootstrap_servers}"
      }}
      source = {{
        enabled = true
      }}
      broker = {{
        enabled = true
        defaultConfig = {{
          bootstrapServers = "{kafka_bootstrap_servers}"
          numPartitions = "10"
          replicationFactor = "3"
        }}
      }}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_eventing]
}}

'''

        # Add example services if configured
        example_services = operator_config.get('example_services', defaults.get('example_services', []))
        for service in example_services:
            service_name = self.clean_name(service.get('name', 'example-service'))
            terraform_config += f'''# Example Knative Service: {service.get('name')}
resource "kubernetes_manifest" "{clean_name}_service_{service_name}" {{
  manifest = {{
    apiVersion = "serving.knative.dev/v1"
    kind       = "Service"
    metadata = {{
      name      = "{service_name}"
      namespace = "{service.get('namespace', 'default')}"
    }}
    spec = {{
      template = {{
        metadata = {{
          annotations = {{
            "autoscaling.knative.dev/minScale" = "{service.get('min_scale', '0')}"
            "autoscaling.knative.dev/maxScale" = "{service.get('max_scale', '10')}"
          }}
        }}
        spec = {{
          containers = [
            {{
              image = "{service.get('image', 'quay.io/openshift/hello-openshift:latest')}"
              ports = [
                {{
                  containerPort = {service.get('port', 8080)}
                }}
              ]
              env = {service.get('env', [])}
            }}
          ]
        }}
      }}
      traffic = [
        {{
          percent = 100
          latestRevision = true
        }}
      ]
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_serving]
}}

'''

        return terraform_config 
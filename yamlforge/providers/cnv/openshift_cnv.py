"""
OpenShift CNV Provider for yamlforge
Handles Red Hat Container Native Virtualization (CNV) operations
"""

from typing import Dict, List, Optional
from .base import BaseCNVProvider
import re


class OpenShiftCNVProvider(BaseCNVProvider):
    """OpenShift-specific CNV provider with Red Hat optimizations"""
    
    def generate_openshift_cnv_vm(self, instance, index, clean_name, flavor, available_subnets=None, yaml_data=None, has_guid_placeholder=False):
        """Generate OpenShift CNV VM configuration for OpenShift clusters"""
        
        # Get VM specifications
        cores = instance.get('cores')
        memory = instance.get('memory')
        
        # Determine size configuration
        if cores and memory:
            # Use cores and memory directly
            size_config = self.get_cnv_specs_config(cores, memory)
        else:
            # Use flavor mapping
            size_config = self.get_cnv_size_config(flavor)
        
        # Parse instance details
        vm_name = instance.get('name', f'cnv-vm-{index}')
        
        # Replace GUID placeholders if converter is available
        if self.converter:
            vm_name = self.converter.replace_guid_placeholders(vm_name)
        
        # Use cloud_workspace.name as the namespace (required for all YamlForge configs)
        yamlforge_data = yaml_data.get('yamlforge', {}) if yaml_data else {}
        cloud_workspace = yamlforge_data.get('cloud_workspace', {})
        workspace_name = cloud_workspace.get('name', 'yamlforge-workspace')
        
        # Clean the workspace name for use as a Kubernetes namespace
        # Kubernetes namespaces must be lowercase, alphanumeric, and hyphens only
        namespace = re.sub(r'[^a-z0-9-]', '-', workspace_name.lower())
        namespace = re.sub(r'-+', '-', namespace)  # Replace multiple hyphens with single
        namespace = namespace.strip('-')  # Remove leading/trailing hyphens
        
        # Ensure namespace is not empty and has valid length
        if not namespace:
            namespace = 'yamlforge-workspace'
        elif len(namespace) > 63:  # Kubernetes namespace length limit
            namespace = namespace[:63].rstrip('-')
        
        image = instance.get('image', self.cnv_defaults.get('default_image', 'kubevirt/fedora-cloud-container-disk-demo:latest'))
        
        # Generate namespace (only for first instance to avoid duplicates)
        terraform_config = ""
        if index == 1:
            terraform_config += self.generate_cnv_namespace(namespace)
        
        # Generate VirtualMachine resource
        terraform_config += f'''
# OpenShift CNV VirtualMachine: {vm_name}
resource "kubectl_manifest" "{clean_name}_vm" {{
  depends_on = [kubernetes_namespace.{namespace}]
  
  yaml_body = yamlencode({{
    apiVersion = "kubevirt.io/v1"
    kind       = "VirtualMachine"
    metadata = {{
      name      = "{vm_name}"
      namespace = "{namespace}"
      labels = {{
        "managed-by" = "yamlforge"
        "cnv-provider" = "openshift"
      }}
    }}
    spec = {{
      running = true
      template = {{
        metadata = {{
          labels = {{
            kubevirt.io/vm = "{vm_name}"
            "managed-by" = "yamlforge"
          }}
        }}
        spec = {{
          domain = {{
            devices = {{
              disks = [{{
                name = "containerdisk"
                disk = {{}}
              }}]
              interfaces = [{{
                name = "default"
                bridge = {{}}
              }}]
            }}
            resources = {{
              requests = {{
                memory = "{size_config['memory']}"
                cpu    = "{size_config['cpu']}"
              }}
              limits = {{
                memory = "{size_config['memory']}"
                cpu    = "{size_config['cpu']}"
              }}
            }}
            features = {{
              acpi = {{}}
              apic = {{}}
              hyperv = {{
                relaxed = {{}}
                vapic = {{}}
                spinlocks = {{
                  spinlocks = 8191
                }}
              }}
            }}
          }}
          networks = [{{
            name = "default"
            pod = {{}}
          }}]
          volumes = [{{
            name = "containerdisk"
            containerDisk = {{
              image = "{image}"
            }}
          }}]
          terminationGracePeriodSeconds = 0
        }}
      }}
    }}
  }})
}}

# SSH Service for VM: {vm_name} (agnosticd-style)
resource "kubernetes_service" "{clean_name}_ssh_service" {{
  depends_on = [kubectl_manifest.{clean_name}_vm]
  
  metadata {{
    name      = "{vm_name}-ssh"
    namespace = "{namespace}"
    labels = {{
      "managed-by" = "yamlforge"
      "cnv-provider" = "openshift"
      "vm-name" = "{vm_name}"
    }}
    annotations = {{
      "yamlforge.io/ssh-service" = "true"
      "yamlforge.io/vm-name" = "{vm_name}"
    }}
  }}
  
  spec {{
    type = "NodePort"
    selector = {{
      "kubevirt.io/vm" = "{vm_name}"
    }}
    port {{
      name        = "ssh"
      port        = 22
      target_port = 22
      protocol    = "TCP"
      node_port   = 0  # Let Kubernetes allocate a random port
    }}
  }}
}}



# SSH access information output
output "{clean_name}_ssh_access" {{
  description = "SSH access details for {vm_name}"
  value = {{
    vm_name = "{vm_name}"
    namespace = "{namespace}"
    service_name = "{vm_name}-ssh"
    service_type = "NodePort"
    node_port = kubernetes_service.{clean_name}_ssh_service.spec[0].port[0].node_port
    node_ip = "NODE_IP"
    ssh_command = "ssh cloud-user@NODE_IP -p ${{kubernetes_service.{clean_name}_ssh_service.spec[0].port[0].node_port}}"
  }}
}}




'''
        return terraform_config
    
    def generate_cnv_operator_installation(self, yaml_data):
        """Generate OpenShift CNV operator installation"""
        
        terraform_config = '''
# OpenShift CNV Operator Installation

# Create CNV namespace
resource "kubernetes_namespace" "openshift_cnv" {
  metadata {
    name = "openshift-cnv"
    labels = {
      "managed-by" = "yamlforge"
      "cnv-provider" = "openshift"
    }
  }
}

# Create CNV Operator Group
resource "kubectl_manifest" "cnv_operator_group" {
  depends_on = [kubernetes_namespace.openshift_cnv]
  
  yaml_body = yamlencode({
    apiVersion = "operators.coreos.com/v1"
    kind       = "OperatorGroup"
    metadata = {
      name      = "openshift-cnv"
      namespace = "openshift-cnv"
    }
    spec = {
      targetNamespaces = ["openshift-cnv"]
    }
  })
}

# Create CNV Subscription
resource "kubectl_manifest" "cnv_subscription" {
  depends_on = [kubectl_manifest.cnv_operator_group]
  
  yaml_body = yamlencode({
    apiVersion = "operators.coreos.com/v1alpha1"
    kind       = "Subscription"
    metadata = {
      name      = "hco-operatorhub"
      namespace = "openshift-cnv"
    }
    spec = {
      channel     = "stable"
      name        = "hco-operatorhub"
      source      = "redhat-operators"
      sourceNamespace = "openshift-marketplace"
      installPlanApproval = "Automatic"
    }
  })
}

# Create HyperConverged CR to deploy CNV
resource "kubectl_manifest" "hyperconverged" {
  depends_on = [kubectl_manifest.cnv_subscription]
  
  yaml_body = yamlencode({
    apiVersion = "hco.kubevirt.io/v1beta1"
    kind       = "HyperConverged"
    metadata = {
      name      = "kubevirt-hyperconverged"
      namespace = "openshift-cnv"
    }
    spec = {
      localStorageClassName = "local-path"
      infra = {
        nodePlacement = {
          tolerations = [{
            key = "node-role.kubernetes.io/master"
            operator = "Exists"
            effect = "NoSchedule"
          }]
        }
      }
      workloads = {
        nodePlacement = {
          tolerations = [{
            key = "node-role.kubernetes.io/master"
            operator = "Exists"
            effect = "NoSchedule"
          }]
        }
      }
    }
  })
}
'''
        return terraform_config

"""
CNV Networks Feature Provider for yamlforge
Handles network operations and configurations for CNV
"""

from typing import Dict, List, Optional
from ..base import BaseCNVProvider


class CNVNetworkProvider(BaseCNVProvider):
    """Network management for CNV"""
    
    def generate_multus_network(self, network_config):
        """Generate a Multus network attachment for CNV"""
        
        network_name = network_config.get('name')
        namespace = network_config.get('namespace', 'default')
        network_type = network_config.get('type', 'bridge')
        subnet = network_config.get('subnet', '10.244.0.0/16')
        
        terraform_config = f'''
# Multus Network Attachment: {network_name}
resource "kubectl_manifest" "{network_name}_network_attachment" {{
  yaml_body = yamlencode({{
    apiVersion = "k8s.cni.cncf.io/v1"
    kind       = "NetworkAttachmentDefinition"
    metadata = {{
      name      = "{network_name}"
      namespace = "{namespace}"
      labels = {{
        "managed-by" = "yamlforge"
        "cnv-feature" = "multus-network"
      }}
    }}
    spec = {{
      config = jsonencode({{
        cniVersion = "0.3.1"
        type       = "{network_type}"
        bridge     = "{network_name}"
        ipam = {{
          type = "host-local"
          subnet = "{subnet}"
        }}
      }})
    }}
  }})
}}
'''
        return terraform_config
    
    def generate_vm_with_multus_network(self, vm_config):
        """Generate a VM that uses Multus networking"""
        
        vm_name = vm_config.get('name')
        namespace = vm_config.get('namespace', 'default')
        network_name = vm_config.get('network_name', 'default-network')
        size_config = self.get_cnv_size_config(vm_config.get('size', 'medium'))
        
        terraform_config = f'''
# VirtualMachine with Multus Network: {vm_name}
resource "kubectl_manifest" "{vm_name}_vm" {{
  depends_on = [kubectl_manifest.{network_name}_network_attachment]
  
  yaml_body = yamlencode({{
    apiVersion = "kubevirt.io/v1"
    kind       = "VirtualMachine"
    metadata = {{
      name      = "{vm_name}"
      namespace = "{namespace}"
      labels = {{
        "managed-by" = "yamlforge"
        "cnv-feature" = "vm-with-multus"
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
          annotations = {{
            "k8s.v1.cni.cncf.io/networks" = "{network_name}"
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
              }}, {{
                name = "multus"
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
            }}
          }}
          networks = [{{
            name = "default"
            pod = {{}}
          }}, {{
            name = "multus"
            multus = {{
              networkName = "{network_name}"
            }}
          }}]
          volumes = [{{
            name = "containerdisk"
            containerDisk = {{
              image = "kubevirt/fedora-cloud-container-disk-demo:latest"
            }}
          }}]
          terminationGracePeriodSeconds = 0
        }}
      }}
    }}
  }})
}}
'''
        return terraform_config
    
    def generate_service_network(self, network_config):
        """Generate a service network for CNV VMs (agnosticd-style SSH access)"""
        
        vm_name = network_config.get('name')
        namespace = network_config.get('namespace', 'default')
        service_type = network_config.get('service_type', 'NodePort')  # Default to NodePort for SSH access
        port = network_config.get('port', 22)
        target_port = network_config.get('target_port', 22)
        
        # Generate a unique service name
        service_name = f"{vm_name}-ssh"
        
        terraform_config = f'''
# SSH Service for VM: {vm_name} (agnosticd-style)
resource "kubernetes_service" "{service_name}_service" {{
  metadata {{
    name      = "{service_name}"
    namespace = "{namespace}"
    labels = {{
      "managed-by" = "yamlforge"
      "cnv-feature" = "ssh-service"
      "vm-name" = "{vm_name}"
    }}
    annotations = {{
      "yamlforge.io/ssh-service" = "true"
      "yamlforge.io/vm-name" = "{vm_name}"
    }}
  }}
  
  spec {{
    type = "{service_type}"
    selector = {{
      "kubevirt.io/vm" = "{vm_name}"
    }}
    port {{
      name        = "ssh"
      port        = {port}
      target_port = {target_port}
      protocol    = "TCP"
      node_port   = 0  # Let Kubernetes allocate a random port
    }}
  }}
}}

# Service output for SSH access information
output "{vm_name}_ssh_info" {{
  description = "SSH access information for {vm_name}"
  value = {{
    vm_name = "{vm_name}"
    namespace = "{namespace}"
    service_name = "{service_name}"
    service_type = "{service_type}"
    ssh_port = kubernetes_service.{service_name}_service.spec[0].port[0].node_port
    ssh_command = "ssh cloud-user@NODE_IP -p ${{kubernetes_service.{service_name}_service.spec[0].port[0].node_port}}"
    node_port = kubernetes_service.{service_name}_service.spec[0].port[0].node_port
    load_balancer_ip = kubernetes_service.{service_name}_service.status[0].load_balancer[0].ingress[0].ip
  }}
}}
'''
        return terraform_config

    def generate_ssh_service_for_vm(self, vm_name, namespace, service_type='NodePort'):
        """Generate SSH service for a specific VM (agnosticd-style)"""
        
        service_name = f"{vm_name}-ssh"
        
        terraform_config = f'''
# SSH Service for VM: {vm_name}
resource "kubernetes_service" "{service_name}_service" {{
  metadata {{
    name      = "{service_name}"
    namespace = "{namespace}"
    labels = {{
      "managed-by" = "yamlforge"
      "cnv-feature" = "ssh-service"
      "vm-name" = "{vm_name}"
    }}
    annotations = {{
      "yamlforge.io/ssh-service" = "true"
      "yamlforge.io/vm-name" = "{vm_name}"
    }}
  }}
  
  spec {{
    type = "{service_type}"
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
output "{vm_name}_ssh_access" {{
  description = "SSH access details for {vm_name}"
  value = {{
    vm_name = "{vm_name}"
    namespace = "{namespace}"
    service_name = "{service_name}"
    service_type = "{service_type}"
    node_port = kubernetes_service.{service_name}_service.spec[0].port[0].node_port
    load_balancer_ip = try(kubernetes_service.{service_name}_service.status[0].load_balancer[0].ingress[0].ip, null)
    ssh_command = "ssh cloud-user@NODE_IP -p ${{kubernetes_service.{service_name}_service.spec[0].port[0].node_port}}"
  }}
}}
'''
        return terraform_config

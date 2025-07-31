"""
Kubernetes KubeVirt Provider for yamlforge
Handles upstream KubeVirt operations on Kubernetes clusters
"""

from typing import Dict, List, Optional
from .base import BaseCNVProvider


class KubernetesKubeVirtProvider(BaseCNVProvider):
    """Kubernetes-specific KubeVirt provider for upstream deployments"""
    
    def generate_kubevirt_vm(self, instance, index, clean_name, flavor, available_subnets=None, yaml_data=None, has_guid_placeholder=False):
        """Generate Kubernetes KubeVirt virtual machine configuration"""
        
        # Get CNV configuration from yamlforge section
        yamlforge_data = yaml_data.get('yamlforge', {}) if yaml_data else {}
        cnv_config = yamlforge_data.get('cnv', {})
        datavolume_namespace = cnv_config.get('datavolume_namespace', self.cnv_defaults.get('default_datavolume_namespace', 'cnv-images'))
        validate_operator = cnv_config.get('validate_operator', True)
        
        # Validate CNV operator is installed (if enabled)
        if validate_operator:
            if not self.validate_cnv_operator():
                raise ValueError("CNV/KubeVirt operator is not installed or not working. Please install OpenShift Virtualization or KubeVirt operator.")
        
        # Get VM specifications
        cores = instance.get('cores')
        memory = instance.get('memory')
        
        # Validate that both flavor and cores/memory are not specified together
        has_flavor = bool(flavor)
        has_cores_memory = bool(cores and memory)
        
        if has_flavor and has_cores_memory:
            instance_name = instance.get('name', 'unnamed')
            raise ValueError(
                f"CNV instance '{instance_name}' cannot specify both 'flavor' and 'cores'/'memory'. "
                f"Choose one:\n"
                f"  • Use 'flavor': small, medium, large, xlarge\n"
                f"  • Use 'cores' and 'memory': cores: 2, memory: 2048"
            )
        
        if not has_flavor and not has_cores_memory:
            instance_name = instance.get('name', 'unnamed')
            raise ValueError(
                f"CNV instance '{instance_name}' must specify either 'flavor' OR both 'cores' and 'memory'.\n"
                f"Examples:\n"
                f"  • flavor: small\n"
                f"  • cores: 2, memory: 2048"
            )
        
        # Determine size configuration
        if has_cores_memory:
            # Use cores and memory directly
            size_config = self.get_cnv_specs_config(cores, memory)
        else:
            # Use flavor mapping
            size_config = self.get_cnv_size_config(flavor)
        
        # Parse instance details
        vm_name = instance.get('name', f'kubevirt-vm-{index}')
        
        # Replace GUID placeholders if converter is available
        if self.converter:
            vm_name = self.converter.replace_guid_placeholders(vm_name)
        
        # Use cloud_workspace.name as the namespace (required for all YamlForge configs)
        cloud_workspace = yamlforge_data.get('cloud_workspace', {})
        workspace_name = cloud_workspace.get('name', 'yamlforge-workspace')
        
        # Clean the workspace name for use as a Kubernetes namespace
        # Kubernetes namespaces must be lowercase, alphanumeric, and hyphens only
        import re
        namespace = re.sub(r'[^a-z0-9-]', '-', workspace_name.lower())
        namespace = re.sub(r'-+', '-', namespace)  # Replace multiple hyphens with single
        namespace = namespace.strip('-')  # Remove leading/trailing hyphens
        
        # Ensure namespace is not empty and has valid length
        if not namespace:
            namespace = 'yamlforge-workspace'
        elif len(namespace) > 63:  # Kubernetes namespace length limit
            namespace = namespace[:63].rstrip('-')
        
        # Get image configuration using dynamic discovery
        image_name = instance.get('image', self.cnv_defaults.get('default_image', 'kubevirt/fedora-cloud-container-disk-demo:latest'))
        image_config = self.get_cnv_image_config(image_name, datavolume_namespace)
        
        # Generate namespace (only for first instance to avoid duplicates)
        terraform_config = ""
        if index == 1:
            terraform_config += self.generate_cnv_namespace(namespace)
        
        # Generate VirtualMachine resource
        depends_on_clause = f'depends_on = [kubernetes_namespace.{namespace}]'
        
        terraform_config += f'''
# Kubernetes KubeVirt VirtualMachine: {vm_name}
resource "kubectl_manifest" "{clean_name}_vm" {{
  {depends_on_clause}

  yaml_body = yamlencode({{
    apiVersion = "kubevirt.io/v1"
    kind       = "VirtualMachine"
    metadata = {{
      name      = "{vm_name}"
      namespace = "{namespace}"
      labels = {{
        "managed-by" = "yamlforge"
        "cnv-provider" = "kubernetes"
      }}
    }}
    spec = {{
      running = true
      template = {{
        metadata = {{
          labels = {{
            "kubevirt.io/vm" = "{vm_name}"
            "managed-by" = "yamlforge"
          }}
        }}
        spec = {{
          domain = {{
            devices = {{
              disks = [{{
                name = "rootdisk"
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
            }}
          }}
          networks = [{{
            name = "default"
            pod = {{}}
          }}]
          volumes = [{{
            name = "rootdisk"
            persistentVolumeClaim = {{
              claimName = "{image_config['pvc_name']}"
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
      "cnv-provider" = "kubernetes"
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
    
    def generate_kubevirt_installation(self, yaml_data):
        """Generate Kubernetes KubeVirt installation"""
        
        terraform_config = '''
# Kubernetes KubeVirt Installation

# Create KubeVirt namespace
resource "kubernetes_namespace" "kubevirt" {
  metadata {
    name = "kubevirt"
    labels = {
      "managed-by" = "yamlforge"
      "cnv-provider" = "kubernetes"
    }
  }
}

# Install KubeVirt using Helm
resource "helm_release" "kubevirt" {
  depends_on = [kubernetes_namespace.kubevirt]
  
  name       = "kubevirt"
  repository = "https://kubevirt.io/charts"
  chart      = "kubevirt"
  namespace  = "kubevirt"
  
  set {
    name  = "certRotateStrategy.signer.ca.duration"
    value = "48h"
  }
  
  set {
    name  = "certRotateStrategy.signer.server.duration"
    value = "24h"
  }
  
  set {
    name  = "certRotateStrategy.signer.client.duration"
    value = "24h"
  }
  
  set {
    name  = "certRotateStrategy.signer.bundle.duration"
    value = "24h"
  }
}

# Install Containerized Data Importer (CDI) for DataVolumes
resource "helm_release" "cdi" {
  depends_on = [helm_release.kubevirt]
  
  name       = "cdi"
  repository = "https://kubevirt.io/charts"
  chart      = "cdi"
  namespace  = "kubevirt"
  
  set {
    name  = "cdi.cr.spec.config.uploadProxyURLOverride"
    value = ""
  }
  
  set {
    name  = "cdi.cr.spec.config.dataVolumeTTLSeconds"
    value = "0"
  }
}

# Create default StorageClass for local storage
resource "kubectl_manifest" "local_path_storage_class" {
  yaml_body = yamlencode({
    apiVersion = "storage.k8s.io/v1"
    kind       = "StorageClass"
    metadata = {
      name = "local-path"
      annotations = {
        "storageclass.kubernetes.io/is-default-class" = "true"
      }
    }
    provisioner = "rancher.io/local-path"
    volumeBindingMode = "WaitForFirstConsumer"
  })
}
'''
        return terraform_config

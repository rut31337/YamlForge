"""
CNV Storage Feature Provider for yamlforge
Handles storage operations and configurations for CNV
"""

from typing import Dict, List, Optional
from ..base import BaseCNVProvider


class CNVStorageProvider(BaseCNVProvider):
    """Storage management for CNV"""
    
    def generate_storage_class(self, storage_config):
        """Generate a StorageClass for CNV"""
        
        storage_name = storage_config.get('name')
        provisioner = storage_config.get('provisioner', 'rancher.io/local-path')
        volume_binding_mode = storage_config.get('volume_binding_mode', 'WaitForFirstConsumer')
        is_default = storage_config.get('is_default', False)
        
        terraform_config = f'''
# StorageClass: {storage_name}
resource "kubectl_manifest" "{storage_name}_storage_class" {{
  yaml_body = yamlencode({{
    apiVersion = "storage.k8s.io/v1"
    kind       = "StorageClass"
    metadata = {{
      name = "{storage_name}"
      annotations = {{
        "storageclass.kubernetes.io/is-default-class" = "{str(is_default).lower()}"
      }}
      labels = {{
        "managed-by" = "yamlforge"
        "cnv-feature" = "storage-class"
      }}
    }}
    provisioner = "{provisioner}"
    volumeBindingMode = "{volume_binding_mode}"
  }})
}}
'''
        return terraform_config
    
    def generate_persistent_volume(self, volume_config):
        """Generate a PersistentVolume for CNV"""
        
        volume_name = volume_config.get('name')
        storage_class = volume_config.get('storage_class', 'local-path')
        size = volume_config.get('size', '10Gi')
        access_mode = volume_config.get('access_mode', 'ReadWriteOnce')
        host_path = volume_config.get('host_path', '/tmp/cnv-storage')
        
        terraform_config = f'''
# PersistentVolume: {volume_name}
resource "kubectl_manifest" "{volume_name}_persistent_volume" {{
  yaml_body = yamlencode({{
    apiVersion = "v1"
    kind       = "PersistentVolume"
    metadata = {{
      name = "{volume_name}"
      labels = {{
        "managed-by" = "yamlforge"
        "cnv-feature" = "persistent-volume"
      }}
    }}
    spec = {{
      capacity = {{
        storage = "{size}"
      }}
      accessModes = ["{access_mode}"]
      persistentVolumeReclaimPolicy = "Retain"
      storageClassName = "{storage_class}"
      hostPath = {{
        path = "{host_path}"
        type = "DirectoryOrCreate"
      }}
    }}
  }})
}}
'''
        return terraform_config
    
    def generate_vm_with_persistent_storage(self, vm_config):
        """Generate a VM with persistent storage"""
        
        vm_name = vm_config.get('name')
        namespace = vm_config.get('namespace', 'default')
        storage_size = vm_config.get('storage_size', '10Gi')
        storage_class = vm_config.get('storage_class', 'local-path')
        size_config = self.get_cnv_size_config(vm_config.get('size', 'medium'))
        
        terraform_config = f'''
# VirtualMachine with Persistent Storage: {vm_name}
resource "kubectl_manifest" "{vm_name}_vm" {{
  depends_on = [kubectl_manifest.{vm_name}_pvc]
  
  yaml_body = yamlencode({{
    apiVersion = "kubevirt.io/v1"
    kind       = "VirtualMachine"
    metadata = {{
      name      = "{vm_name}"
      namespace = "{namespace}"
      labels = {{
        "managed-by" = "yamlforge"
        "cnv-feature" = "vm-with-persistent-storage"
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
                name = "persistentdisk"
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
            name = "persistentdisk"
            persistentVolumeClaim = {{
              claimName = "{vm_name}-pvc"
            }}
          }}]
          terminationGracePeriodSeconds = 0
        }}
      }}
    }}
  }})
}}

# Persistent Volume Claim for VM storage
resource "kubectl_manifest" "{vm_name}_pvc" {{
  yaml_body = yamlencode({{
    apiVersion = "v1"
    kind       = "PersistentVolumeClaim"
    metadata = {{
      name      = "{vm_name}-pvc"
      namespace = "{namespace}"
      labels = {{
        "managed-by" = "yamlforge"
        "cnv-feature" = "persistent-storage"
      }}
    }}
    spec = {{
      accessModes = ["ReadWriteOnce"]
      resources = {{
        requests = {{
          storage = "{storage_size}"
        }}
      }}
      storageClassName = "{storage_class}"
    }}
  }})
}}
'''
        return terraform_config

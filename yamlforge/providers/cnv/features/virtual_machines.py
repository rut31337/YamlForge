"""
CNV Virtual Machines Feature Provider for yamlforge
Handles advanced virtual machine operations and configurations
"""

from typing import Dict, List, Optional
from ..base import BaseCNVProvider


class CNVVirtualMachineProvider(BaseCNVProvider):
    """Advanced virtual machine management for CNV"""
    
    def generate_persistent_vm(self, vm_config):
        """Generate a persistent virtual machine with DataVolumes"""
        
        vm_name = vm_config.get('name')
        namespace = vm_config.get('namespace', 'default')
        size_config = self.get_cnv_size_config(vm_config.get('size', 'medium'))
        
        terraform_config = f'''
# Persistent VirtualMachine: {vm_name}
resource "kubectl_manifest" "{vm_name}_vm" {{
  yaml_body = yamlencode({{
    apiVersion = "kubevirt.io/v1"
    kind       = "VirtualMachine"
    metadata = {{
      name      = "{vm_name}"
      namespace = "{namespace}"
      labels = {{
        "managed-by" = "yamlforge"
        "cnv-feature" = "persistent-vm"
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
                name = "bootdisk"
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
            name = "bootdisk"
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
    }}
    spec = {{
      accessModes = ["ReadWriteOnce"]
      resources = {{
        requests = {{
          storage = "{vm_config.get('storage_size', '10Gi')}"
        }}
      }}
      storageClassName = "{vm_config.get('storage_class', 'local-path')}"
    }}
  }})
}}
'''
        return terraform_config
    
    def generate_multi_disk_vm(self, vm_config):
        """Generate a virtual machine with multiple disks"""
        
        vm_name = vm_config.get('name')
        namespace = vm_config.get('namespace', 'default')
        disks = vm_config.get('disks', [])
        size_config = self.get_cnv_size_config(vm_config.get('size', 'medium'))
        
        # Generate disk configurations
        disk_configs = []
        volume_configs = []
        
        for i, disk in enumerate(disks):
            disk_name = disk.get('name', f'disk-{i}')
            disk_size = disk.get('size', '10Gi')
            
            disk_configs.append(f'''
              {{
                name = "{disk_name}"
                disk = {{}}
              }}''')
            
            volume_configs.append(f'''
              {{
                name = "{disk_name}"
                persistentVolumeClaim = {{
                  claimName = "{vm_name}-{disk_name}-pvc"
                }}
              }}''')
        
        disk_config_str = ','.join(disk_configs)
        volume_config_str = ','.join(volume_configs)
        
        terraform_config = f'''
# Multi-Disk VirtualMachine: {vm_name}
resource "kubectl_manifest" "{vm_name}_vm" {{
  yaml_body = yamlencode({{
    apiVersion = "kubevirt.io/v1"
    kind       = "VirtualMachine"
    metadata = {{
      name      = "{vm_name}"
      namespace = "{namespace}"
      labels = {{
        "managed-by" = "yamlforge"
        "cnv-feature" = "multi-disk-vm"
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
              disks = [{disk_config_str}]
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
          volumes = [{volume_config_str}]
          terminationGracePeriodSeconds = 0
        }}
      }}
    }}
  }})
}}
'''
        
        # Generate PVCs for each disk
        for i, disk in enumerate(disks):
            disk_name = disk.get('name', f'disk-{i}')
            disk_size = disk.get('size', '10Gi')
            
            terraform_config += f'''

# PVC for disk: {disk_name}
resource "kubectl_manifest" "{vm_name}_{disk_name}_pvc" {{
  yaml_body = yamlencode({{
    apiVersion = "v1"
    kind       = "PersistentVolumeClaim"
    metadata = {{
      name      = "{vm_name}-{disk_name}-pvc"
      namespace = "{namespace}"
    }}
    spec = {{
      accessModes = ["ReadWriteOnce"]
      resources = {{
        requests = {{
          storage = "{disk_size}"
        }}
      }}
      storageClassName = "{vm_config.get('storage_class', 'local-path')}"
    }}
  }})
}}
'''
        
        return terraform_config

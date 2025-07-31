"""
CNV Data Volumes Feature Provider for yamlforge
Handles DataVolume operations and configurations
"""

from typing import Dict, List, Optional
from ..base import BaseCNVProvider


class CNVDataVolumeProvider(BaseCNVProvider):
    """DataVolume management for CNV"""
    
    def generate_data_volume(self, volume_config):
        """Generate a DataVolume for CNV"""
        
        volume_name = volume_config.get('name')
        namespace = volume_config.get('namespace', 'default')
        size = volume_config.get('size', '10Gi')
        url = volume_config.get('url')
        storage_class = volume_config.get('storage_class', 'local-path')
        
        terraform_config = f'''
# DataVolume: {volume_name}
resource "kubectl_manifest" "{volume_name}_datavolume" {{
  yaml_body = yamlencode({{
    apiVersion = "cdi.kubevirt.io/v1beta1"
    kind       = "DataVolume"
    metadata = {{
      name      = "{volume_name}"
      namespace = "{namespace}"
      labels = {{
        "managed-by" = "yamlforge"
        "cnv-feature" = "datavolume"
      }}
    }}
    spec = {{
      source = {{
        http = {{
          url = "{url}"
        }}
      }}
      pvc = {{
        accessModes = ["ReadWriteOnce"]
        resources = {{
          requests = {{
            storage = "{size}"
          }}
        }}
        storageClassName = "{storage_class}"
      }}
    }}
  }})
}}
'''
        return terraform_config
    
    def generate_blank_data_volume(self, volume_config):
        """Generate a blank DataVolume for CNV"""
        
        volume_name = volume_config.get('name')
        namespace = volume_config.get('namespace', 'default')
        size = volume_config.get('size', '10Gi')
        storage_class = volume_config.get('storage_class', 'local-path')
        
        terraform_config = f'''
# Blank DataVolume: {volume_name}
resource "kubectl_manifest" "{volume_name}_blank_datavolume" {{
  yaml_body = yamlencode({{
    apiVersion = "cdi.kubevirt.io/v1beta1"
    kind       = "DataVolume"
    metadata = {{
      name      = "{volume_name}"
      namespace = "{namespace}"
      labels = {{
        "managed-by" = "yamlforge"
        "cnv-feature" = "blank-datavolume"
      }}
    }}
    spec = {{
      source = {{
        blank = {{}}
      }}
      pvc = {{
        accessModes = ["ReadWriteOnce"]
        resources = {{
          requests = {{
            storage = "{size}"
          }}
        }}
        storageClassName = "{storage_class}"
      }}
    }}
  }})
}}
'''
        return terraform_config
    
    def generate_registry_data_volume(self, volume_config):
        """Generate a DataVolume from container registry"""
        
        volume_name = volume_config.get('name')
        namespace = volume_config.get('namespace', 'default')
        size = volume_config.get('size', '10Gi')
        image = volume_config.get('image')
        storage_class = volume_config.get('storage_class', 'local-path')
        
        terraform_config = f'''
# Registry DataVolume: {volume_name}
resource "kubectl_manifest" "{volume_name}_registry_datavolume" {{
  yaml_body = yamlencode({{
    apiVersion = "cdi.kubevirt.io/v1beta1"
    kind       = "DataVolume"
    metadata = {{
      name      = "{volume_name}"
      namespace = "{namespace}"
      labels = {{
        "managed-by" = "yamlforge"
        "cnv-feature" = "registry-datavolume"
      }}
    }}
    spec = {{
      source = {{
        registry = {{
          url = "{image}"
        }}
      }}
      pvc = {{
        accessModes = ["ReadWriteOnce"]
        resources = {{
          requests = {{
            storage = "{size}"
          }}
        }}
        storageClassName = "{storage_class}"
      }}
    }}
  }})
}}
'''
        return terraform_config
    
    def generate_vm_with_datavolume(self, vm_config):
        """Generate a VM that uses a DataVolume"""
        
        vm_name = vm_config.get('name')
        namespace = vm_config.get('namespace', 'default')
        datavolume_name = vm_config.get('datavolume_name', f'{vm_name}-dv')
        size_config = self.get_cnv_size_config(vm_config.get('size', 'medium'))
        
        terraform_config = f'''
# VirtualMachine with DataVolume: {vm_name}
resource "kubectl_manifest" "{vm_name}_vm" {{
  depends_on = [kubectl_manifest.{datavolume_name}_datavolume]
  
  yaml_body = yamlencode({{
    apiVersion = "kubevirt.io/v1"
    kind       = "VirtualMachine"
    metadata = {{
      name      = "{vm_name}"
      namespace = "{namespace}"
      labels = {{
        "managed-by" = "yamlforge"
        "cnv-feature" = "vm-with-datavolume"
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
                name = "datavolumedisk"
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
            name = "datavolumedisk"
            dataVolume = {{
              name = "{datavolume_name}"
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

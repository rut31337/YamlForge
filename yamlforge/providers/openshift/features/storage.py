"""
OpenShift Storage Provider for yamlforge
Supports CSI drivers and storage configurations
"""

from typing import Dict, List
from ..base import BaseOpenShiftProvider


class OpenShiftStorageProvider(BaseOpenShiftProvider):
    """OpenShift Storage provider for persistent storage features"""
    
    def generate_storage_features(self, yaml_data: Dict, clusters: List[Dict]) -> str:
        """Generate OpenShift storage features for clusters"""
        
        storage_config = yaml_data.get('openshift_storage', {})
        if not storage_config:
            return ""
        
        terraform_config = ""
        
        # Generate CSI drivers
        if storage_config.get('csi_drivers'):
            terraform_config += self.generate_csi_drivers(storage_config['csi_drivers'])
        
        # Generate storage classes
        if storage_config.get('storage_classes'):
            terraform_config += self.generate_storage_classes(storage_config['storage_classes'])
        
        return terraform_config
    
    def generate_csi_drivers(self, csi_drivers_config: List[Dict]) -> str:
        """Generate CSI driver configurations"""
        
        terraform_config = '''
# =============================================================================
# CSI DRIVERS
# =============================================================================

'''
        
        for driver in csi_drivers_config:
            driver_name = driver.get('name')
            clean_name = self.clean_name(driver_name)
            
            terraform_config += f'''
# CSI Driver: {driver_name}
resource "kubernetes_manifest" "{clean_name}_csi_driver" {{
  manifest = {{
    apiVersion = "storage.k8s.io/v1"
    kind       = "CSIDriver"
    metadata = {{
      name = "{driver_name}"
    }}
    spec = {{
      attachRequired = {str(driver.get('attach_required', True)).lower()}
      podInfoOnMount = {str(driver.get('pod_info_on_mount', False)).lower()}
      volumeLifecycleModes = {driver.get('volume_lifecycle_modes', ['Persistent'])}
    }}
  }}
}}

'''
        
        return terraform_config
    
    def generate_storage_classes(self, storage_classes_config: List[Dict]) -> str:
        """Generate StorageClass configurations"""
        
        terraform_config = '''
# =============================================================================
# STORAGE CLASSES
# =============================================================================

'''
        
        for storage_class in storage_classes_config:
            class_name = storage_class.get('name')
            clean_name = self.clean_name(class_name)
            
            terraform_config += f'''
# Storage Class: {class_name}
resource "kubernetes_manifest" "{clean_name}_storage_class" {{
  manifest = {{
    apiVersion = "storage.k8s.io/v1"
    kind       = "StorageClass"
    metadata = {{
      name = "{class_name}"
      annotations = {storage_class.get('annotations', {})}
    }}
    provisioner = "{storage_class.get('provisioner', 'kubernetes.io/no-provisioner')}"
    parameters = {storage_class.get('parameters', {})}
    volumeBindingMode = "{storage_class.get('volume_binding_mode', 'Immediate')}"
    allowVolumeExpansion = {str(storage_class.get('allow_volume_expansion', False)).lower()}
    reclaimPolicy = "{storage_class.get('reclaim_policy', 'Delete')}"
  }}
}}

'''
        
        return terraform_config 
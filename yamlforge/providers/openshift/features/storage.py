"""
OpenShift Storage Provider for yamlforge
Supports CSI drivers and storage configurations
"""

from typing import Dict, List
from ..base import BaseOpenShiftProvider


class OpenShiftStorageProvider(BaseOpenShiftProvider):
    """OpenShift Storage provider for persistent storage features"""
    
    def generate_storage_features(self, yaml_data: Dict, clusters: List[Dict]) -> str:
        """Generate OpenShift storage features"""
        
        storage_config = yaml_data.get('storage_features', {})
        if not storage_config:
            return ""
        
        cluster_names = [cluster.get('name') for cluster in clusters if cluster.get('name')]
        
        terraform_config = '''
# =============================================================================
# STORAGE FEATURES
# =============================================================================

'''
        
        # Generate storage features for each cluster
        for cluster_name in cluster_names:
            clean_cluster_name = self.clean_name(cluster_name)
            
            # CSI Drivers
            csi_drivers_config = storage_config.get('csi_drivers', [])
            if csi_drivers_config:
                terraform_config += self.generate_csi_drivers(csi_drivers_config, cluster_name, clean_cluster_name)
            
            # Storage Classes
            storage_classes_config = storage_config.get('storage_classes', [])
            if storage_classes_config:
                terraform_config += self.generate_storage_classes(storage_classes_config, cluster_name, clean_cluster_name)
        
        return terraform_config
    
    def generate_csi_drivers(self, csi_drivers_config: List[Dict], cluster_name: str, clean_cluster_name: str) -> str:
        """Generate CSI driver configurations"""
        
        terraform_config = ""
        
        for i, driver in enumerate(csi_drivers_config):
            driver_name = driver.get('name', f'csi-driver-{i+1}')
            clean_driver_name = self.clean_name(driver_name)
            
            terraform_config += f'''
# CSI Driver: {driver_name} for {cluster_name}
resource "kubernetes_manifest" "csi_driver_{clean_driver_name}_{clean_cluster_name}" {{
  provider = kubernetes.{clean_cluster_name}_admin
  
  manifest = {{
    apiVersion = "storage.k8s.io/v1"
    kind       = "CSIDriver"
    metadata = {{
      name = "{driver.get('driverName', driver_name)}"
    }}
    spec = {{
      attachRequired = {str(driver.get('attachRequired', True)).lower()}
      podInfoOnMount = {str(driver.get('podInfoOnMount', False)).lower()}
      volumeLifecycleModes = {driver.get('volumeLifecycleModes', ['Persistent'])}
    }}
  }}
  
  depends_on = [kubernetes_service_account.{clean_cluster_name}_admin]
}}

'''
        
        return terraform_config
    
    def generate_storage_classes(self, storage_classes_config: List[Dict], cluster_name: str, clean_cluster_name: str) -> str:
        """Generate StorageClass configurations"""
        
        terraform_config = ""
        
        for i, storage_class in enumerate(storage_classes_config):
            class_name = storage_class.get('name', f'storage-class-{i+1}')
            clean_class_name = self.clean_name(class_name)
            
            terraform_config += f'''
# Storage Class: {class_name} for {cluster_name}
resource "kubernetes_manifest" "storage_class_{clean_class_name}_{clean_cluster_name}" {{
  provider = kubernetes.{clean_cluster_name}_admin
  
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
  
  depends_on = [kubernetes_service_account.{clean_cluster_name}_admin]
}}

'''
        
        return terraform_config 
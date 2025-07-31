"""
CNV Provider for yamlforge
Main orchestrator that combines all CNV provider components
"""

from typing import Dict, List, Set, Any
from .base import BaseCNVProvider
from .openshift_cnv import OpenShiftCNVProvider
from .kubernetes_kubevirt import KubernetesKubeVirtProvider
from .features import (
    CNVVirtualMachineProvider,
    CNVDataVolumeProvider,
    CNVNetworkProvider,
    CNVStorageProvider
)


class CNVProvider(BaseCNVProvider):
    """Main CNV provider orchestrator"""
    
    def __init__(self, converter=None):
        """Initialize the CNV provider with all sub-providers."""
        super().__init__(converter)
        
        # Initialize sub-providers
        self.openshift_cnv_provider = OpenShiftCNVProvider(converter)
        self.kubernetes_kubevirt_provider = KubernetesKubeVirtProvider(converter)
        
        # Initialize feature providers
        self.vm_provider = CNVVirtualMachineProvider(converter)
        self.datavolume_provider = CNVDataVolumeProvider(converter)
        self.network_provider = CNVNetworkProvider(converter)
        self.storage_provider = CNVStorageProvider(converter)
    
    def generate_cnv_vm(self, instance, index, clean_name, flavor, available_subnets=None, yaml_data=None, has_guid_placeholder=False):
        """Generate CNV virtual machine configuration"""
        
        # Determine if this is OpenShift or Kubernetes
        cluster_type = self._get_cluster_type(yaml_data)
        
        if cluster_type == 'openshift':
            return self.openshift_cnv_provider.generate_openshift_cnv_vm(instance, index, clean_name, flavor, available_subnets, yaml_data, has_guid_placeholder)
        else:
            return self.kubernetes_kubevirt_provider.generate_kubevirt_vm(instance, index, clean_name, flavor, available_subnets, yaml_data, has_guid_placeholder)
    
    def generate_cnv_operator_installation(self, yaml_data):
        """Generate CNV/KubeVirt operator installation"""
        
        cluster_type = self._get_cluster_type(yaml_data)
        
        if cluster_type == 'openshift':
            return self.openshift_cnv_provider.generate_cnv_operator_installation(yaml_data)
        else:
            return self.kubernetes_kubevirt_provider.generate_kubevirt_installation(yaml_data)
    
    def _get_cluster_type(self, yaml_data):
        """Determine if this is an OpenShift or Kubernetes deployment"""
        openshift_clusters = yaml_data.get('openshift_clusters', [])
        if openshift_clusters:
            return 'openshift'
        return 'kubernetes'

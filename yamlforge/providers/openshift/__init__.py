"""
OpenShift Provider for yamlforge
Main orchestrator that combines all OpenShift provider components
"""

from typing import Dict, List, Set, Any
from .base import BaseOpenShiftProvider
from .rosa import ROSAProvider
from .aro import AROProvider
from .self_managed import SelfManagedOpenShiftProvider
from .hypershift import HyperShiftProvider
from .dedicated import OpenShiftDedicatedProvider
from .features import (
    OpenShiftOperatorProvider,
    OpenShiftSecurityProvider,
    OpenShiftStorageProvider,
    OpenShiftNetworkingProvider,
    Day2OperationsProvider
)


class OpenShiftProvider(BaseOpenShiftProvider):
    """Main OpenShift provider orchestrator"""
    
    # Mapping of OpenShift types to provider classes
    OPENSHIFT_PROVIDER_MAP = {
        'rosa-classic': 'aws',
        'rosa-hcp': 'aws', 
        'aro': 'azure',
        'openshift-dedicated': None,
        'self-managed': None,
        'hypershift': None,
    }
    
    def __init__(self, converter):
        super().__init__(converter)
        
        # Initialize cluster providers
        self.rosa_provider = ROSAProvider(converter)
        self.aro_provider = AROProvider(converter)
        self.self_managed_provider = SelfManagedOpenShiftProvider(converter)
        self.hypershift_provider = HyperShiftProvider(converter)
        self.dedicated_provider = OpenShiftDedicatedProvider(converter)
        
        # Initialize feature providers
        self.operator_provider = OpenShiftOperatorProvider(converter)
        self.security_provider = OpenShiftSecurityProvider(converter)
        self.storage_provider = OpenShiftStorageProvider(converter)
        self.networking_provider = OpenShiftNetworkingProvider(converter)
        self.day2_provider = Day2OperationsProvider(converter)
    
    def generate_openshift_clusters(self, yaml_data: Dict) -> str:
        """Generate OpenShift clusters configuration"""
        
        clusters = yaml_data.get('openshift_clusters', [])
        if not clusters:
            return ""
        
        terraform_config = ""
        
        # Generate Terraform providers block
        terraform_config += self.generate_terraform_providers(clusters)
        
        # Generate variables
        terraform_config += self.generate_openshift_variables(clusters)
        
        # Generate clusters
        for cluster in clusters:
            cluster_type = cluster.get('type')
            
            # Validate cluster type is specified
            if not cluster_type:
                raise ValueError(f"OpenShift cluster '{cluster.get('name', 'unnamed')}' must specify a 'type' field")
            
            # Check for deprecated 'rosa' type
            if cluster_type == 'rosa':
                raise ValueError(f"OpenShift cluster '{cluster.get('name', 'unnamed')}' uses deprecated type 'rosa'. Use 'rosa-classic' or 'rosa-hcp' instead.")
            
            # Validate cluster type is supported
            if cluster_type not in self.OPENSHIFT_PROVIDER_MAP:
                supported_types = list(self.OPENSHIFT_PROVIDER_MAP.keys())
                raise ValueError(f"Unsupported OpenShift cluster type '{cluster_type}' for cluster '{cluster.get('name', 'unnamed')}'. Supported types: {supported_types}")
            
            # Generate cluster based on type
            if cluster_type == 'rosa-classic':
                terraform_config += self.rosa_provider.generate_rosa_classic_cluster(cluster)
            elif cluster_type == 'rosa-hcp':
                terraform_config += self.rosa_provider.generate_rosa_hcp_cluster(cluster)
            elif cluster_type == 'aro':
                terraform_config += self.aro_provider.generate_aro_cluster(cluster)
            elif cluster_type == 'openshift-dedicated':
                terraform_config += self.dedicated_provider.generate_dedicated_cluster(cluster)
            elif cluster_type == 'self-managed':
                terraform_config += self.self_managed_provider.generate_self_managed_cluster(cluster)
            elif cluster_type == 'hypershift':
                terraform_config += self.hypershift_provider.generate_hypershift_cluster(cluster, clusters)
        
        # Generate operators
        terraform_config += self.operator_provider.generate_operators(yaml_data, clusters)
        
        # Generate security resources
        terraform_config += self.security_provider.generate_security_resources(yaml_data, clusters)
        
        # Generate storage resources
        terraform_config += self.storage_provider.generate_storage_resources(yaml_data, clusters)
        
        # Generate networking resources
        terraform_config += self.networking_provider.generate_networking_resources(yaml_data, clusters)
        
        # Generate Day 2 operations
        terraform_config += self.day2_provider.generate_day2_operations(yaml_data, clusters)
        
        return terraform_config
    
    def detect_required_providers(self, yaml_data: Dict) -> Set[str]:
        """Detect which cloud providers are required for OpenShift clusters"""
        
        required_providers = set()
        clusters = yaml_data.get('openshift_clusters', [])
        
        for cluster in clusters:
            cluster_type = cluster.get('type')
            
            # Get cloud provider for cluster type
            cloud_provider = self.OPENSHIFT_PROVIDER_MAP.get(cluster_type)
            if cloud_provider:
                required_providers.add(cloud_provider)
            
            # Handle cluster types that can use multiple providers
            if cluster_type == 'openshift-dedicated':
                dedicated_cloud = cluster.get('cloud_provider', 'aws')
                required_providers.add(dedicated_cloud)
            elif cluster_type == 'self-managed':
                self_managed_provider = cluster.get('provider', 'aws')
                required_providers.add(self_managed_provider)
            elif cluster_type == 'hypershift':
                hypershift_provider = cluster.get('provider', 'aws')
                required_providers.add(hypershift_provider)
        
        return required_providers
    
    def validate_openshift_configuration(self, yaml_data: Dict) -> List[str]:
        """Validate OpenShift configuration and return list of validation errors"""
        
        errors = []
        clusters = yaml_data.get('openshift_clusters', [])
        
        if not clusters:
            return errors  # No clusters is valid
        
        cluster_names = []
        
        for cluster in clusters:
            cluster_name = cluster.get('name')
            
            # Check for required fields
            if not cluster_name:
                errors.append("OpenShift cluster missing required 'name' field")
                continue
            
            # Check for duplicate cluster names
            if cluster_name in cluster_names:
                errors.append(f"Duplicate OpenShift cluster name: {cluster_name}")
            cluster_names.append(cluster_name)
            
            cluster_type = cluster.get('type')
            if not cluster_type:
                errors.append(f"OpenShift cluster '{cluster_name}' missing required 'type' field")
                continue
            
            # Validate cluster type
            if cluster_type not in self.OPENSHIFT_PROVIDER_MAP:
                supported_types = list(self.OPENSHIFT_PROVIDER_MAP.keys())
                errors.append(f"Unsupported OpenShift cluster type '{cluster_type}' for cluster '{cluster_name}'. Supported: {supported_types}")
                continue
            
            # Type-specific validations
            if cluster_type == 'hypershift':
                management_cluster = cluster.get('management_cluster')
                if not management_cluster:
                    errors.append(f"HyperShift cluster '{cluster_name}' must specify 'management_cluster'")
                elif management_cluster not in cluster_names:
                    # Check if management cluster exists in the list
                    management_exists = any(c.get('name') == management_cluster for c in clusters)
                    if not management_exists:
                        errors.append(f"HyperShift cluster '{cluster_name}' references non-existent management cluster '{management_cluster}'")
            
            elif cluster_type == 'self-managed':
                provider = cluster.get('provider')
                if not provider:
                    errors.append(f"Self-managed OpenShift cluster '{cluster_name}' must specify 'provider'")
                elif provider not in ['aws', 'azure', 'gcp', 'ibm_vpc', 'ibm_classic', 'oci', 'vmware', 'alibaba']:
                    errors.append(f"Self-managed OpenShift cluster '{cluster_name}' has unsupported provider '{provider}'")
        
        return errors


# Export the main provider
__all__ = ['OpenShiftProvider'] 
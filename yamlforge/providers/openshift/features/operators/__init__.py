"""
OpenShift Operators Orchestrator for yamlforge
Manages all OpenShift operator installations and configurations
"""

from typing import Dict, List
from ...base import BaseOpenShiftProvider

# Import core operators
from .core import (
    MonitoringOperator,
    LoggingOperator,
    ServiceMeshOperator,
    StorageOperator,
    PipelinesOperator,
    ServerlessOperator,
    GitOpsOperator
)

# Import security operators
from .security import CertManagerOperator

# Import networking operators
from .networking import SubmarinerOperator, MetalLBOperator

# Import backup operators
from .backup import OADPOperator


class OpenShiftOperatorProvider(BaseOpenShiftProvider):
    """Main OpenShift Operators provider orchestrator"""
    
    def __init__(self, converter):
        super().__init__(converter)
        
        # Initialize core operator providers
        self.monitoring_operator = MonitoringOperator(converter)
        self.logging_operator = LoggingOperator(converter)
        self.service_mesh_operator = ServiceMeshOperator(converter)
        self.storage_operator = StorageOperator(converter)
        self.pipelines_operator = PipelinesOperator(converter)
        self.serverless_operator = ServerlessOperator(converter)
        self.gitops_operator = GitOpsOperator(converter)
        
        # Initialize security operator providers
        self.cert_manager_operator = CertManagerOperator(converter)
        
        # Initialize networking operator providers
        self.submariner_operator = SubmarinerOperator(converter)
        self.metallb_operator = MetalLBOperator(converter)
        
        # Initialize backup operator providers
        self.oadp_operator = OADPOperator(converter)
    
    def generate_operators(self, yaml_data: Dict, clusters: List[Dict]) -> str:
        """Generate OpenShift operators for clusters"""
        
        operators_config = yaml_data.get('openshift_operators', [])
        if not operators_config:
            return ""
        
        terraform_config = ""
        
        # Get list of cluster names for operators that don't specify target clusters
        cluster_names = [cluster.get('name') for cluster in clusters if cluster.get('name')]
        
        for operator in operators_config:
            operator_name = operator.get('name')
            operator_type = operator.get('type')
            target_clusters = operator.get('clusters', cluster_names)  # Default to all clusters
            
            # Ensure target_clusters is a list
            if not target_clusters:
                target_clusters = cluster_names
            
            # Core operators - all require admin permissions
            if operator_type == 'monitoring':
                terraform_config += self.monitoring_operator.generate_monitoring_operator(operator, target_clusters)
            elif operator_type == 'logging':
                terraform_config += self.logging_operator.generate_logging_operator(operator, target_clusters)
            elif operator_type == 'service-mesh':
                terraform_config += self.service_mesh_operator.generate_service_mesh_operator(operator, target_clusters)
            elif operator_type == 'storage':
                terraform_config += self.storage_operator.generate_storage_operator(operator, target_clusters)
            elif operator_type == 'pipelines':
                terraform_config += self.pipelines_operator.generate_pipelines_operator(operator, target_clusters)
            elif operator_type == 'serverless':
                terraform_config += self.serverless_operator.generate_serverless_operator(operator, target_clusters)
            elif operator_type == 'gitops':
                terraform_config += self.gitops_operator.generate_gitops_operator(operator, target_clusters)
            
            # Security operators - require admin permissions
            elif operator_type == 'cert-manager':
                terraform_config += self.cert_manager_operator.generate_cert_manager_operator(operator, clusters)
            
            # Networking operators - require admin permissions
            elif operator_type == 'metallb':
                terraform_config += self.metallb_operator.generate_metallb_operator(operator, target_clusters)
            elif operator_type == 'submariner':
                terraform_config += self.submariner_operator.generate_submariner_operator(operator, target_clusters)
            
            # Backup operators - require admin permissions
            elif operator_type == 'oadp':
                terraform_config += self.oadp_operator.generate_oadp_operator(operator, target_clusters)
            
            else:
                print(f"Warning: Unknown operator type '{operator_type}' for operator '{operator_name}'")
        
        return terraform_config


# Export the main provider
__all__ = ['OpenShiftOperatorProvider'] 
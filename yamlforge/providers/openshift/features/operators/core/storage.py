"""
OpenShift Storage Operator for yamlforge
Supports OpenShift Data Foundation (ODF/OCS) and related storage services
"""

from typing import Dict, List
from ....base import BaseOpenShiftProvider


class StorageOperator(BaseOpenShiftProvider):
    """OpenShift Storage operator for persistent storage and data services"""
    
    def __init__(self, converter):
        super().__init__(converter)
        self.operator_config = self.load_operator_config('core/storage')
    
    def generate_storage_operator(self, operator_config: Dict, target_clusters: List[str]) -> str:
        """Generate OpenShift Data Foundation (ODF/OCS) operator"""
        
        # Load defaults from YAML configuration
        defaults = self.operator_config.get('defaults', {})
        local_storage_subscription_config = self.operator_config.get('local_storage_subscription', {})
        odf_subscription_config = self.operator_config.get('odf_subscription', {})
        storage_system_config = self.operator_config.get('storage_system', {})
        storage_cluster_config = self.operator_config.get('storage_cluster', {})
        multi_cloud_gateway_config = self.operator_config.get('multi_cloud_gateway', {})
        
        operator_name = operator_config.get('name', defaults.get('name', 'openshift-data-foundation'))
        clean_name = self.clean_name(operator_name)
        
        # Configuration options with YAML defaults
        storage_class = operator_config.get('storage_class', defaults.get('storage_class', 'gp3'))
        device_sets = operator_config.get('device_sets', defaults.get('device_sets', 3))
        device_size = operator_config.get('device_size', defaults.get('device_size', '2Ti'))
        enable_ceph_tools = operator_config.get('enable_ceph_tools', defaults.get('enable_ceph_tools', True))
        enable_noobaa = operator_config.get('enable_noobaa', defaults.get('enable_noobaa', True))
        replica_count = operator_config.get('replica_count', defaults.get('replica_count', 3))
        
        terraform_config = f'''
# =============================================================================
# OPENSHIFT DATA FOUNDATION OPERATOR: {operator_name}
# =============================================================================
# Clusters: {', '.join(target_clusters) if target_clusters else 'All clusters'}

# Create OpenShift Storage namespace
resource "kubernetes_manifest" "{clean_name}_namespace" {{
  manifest = {{
    apiVersion = "v1"
    kind       = "Namespace"
    metadata = {{
      name = "openshift-storage"
      labels = {{
        "openshift.io/cluster-monitoring" = "true"
      }}
    }}
  }}
}}

# Local Storage Operator Subscription (for bare metal/on-prem)
resource "kubernetes_manifest" "{clean_name}_local_storage_subscription" {{
  manifest = {{
    apiVersion = "operators.coreos.com/v1alpha1"
    kind       = "Subscription"
    metadata = {{
      name      = "{local_storage_subscription_config.get('name', 'local-storage-operator')}"
      namespace = "openshift-local-storage"
    }}
    spec = {{
      channel = "{local_storage_subscription_config.get('channel', 'stable')}"
      name    = "{local_storage_subscription_config.get('name', 'local-storage-operator')}"
      source  = "{local_storage_subscription_config.get('source', 'redhat-operators')}"
      sourceNamespace = "{local_storage_subscription_config.get('sourceNamespace', 'openshift-marketplace')}"
      installPlanApproval = "Automatic"
    }}
  }}
}}

# OpenShift Data Foundation Operator Subscription
resource "kubernetes_manifest" "{clean_name}_odf_subscription" {{
  manifest = {{
    apiVersion = "operators.coreos.com/v1alpha1"
    kind       = "Subscription"
    metadata = {{
      name      = "{odf_subscription_config.get('name', 'odf-operator')}"
      namespace = "openshift-storage"
    }}
    spec = {{
      channel = "{odf_subscription_config.get('channel', 'stable-4.14')}"
      name    = "{odf_subscription_config.get('name', 'odf-operator')}"
      source  = "{odf_subscription_config.get('source', 'redhat-operators')}"
      sourceNamespace = "{odf_subscription_config.get('sourceNamespace', 'openshift-marketplace')}"
      installPlanApproval = "Automatic"
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_namespace]
}}

# Storage System
resource "kubernetes_manifest" "{clean_name}_storage_system" {{
  manifest = {{
    apiVersion = "odf.openshift.io/v1alpha1"
    kind       = "StorageSystem"
    metadata = {{
      name      = "ocs-storagecluster-storagesystem"
      namespace = "openshift-storage"
    }}
    spec = {{
      kind = "{storage_system_config.get('kind', 'StorageSystem')}"
      name = "ocs-storagecluster"
      namespace = "openshift-storage"
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_odf_subscription]
}}

# Storage Cluster
resource "kubernetes_manifest" "{clean_name}_storage_cluster" {{
  manifest = {{
    apiVersion = "ocs.openshift.io/v1"
    kind       = "StorageCluster"
    metadata = {{
      name      = "ocs-storagecluster"
      namespace = "openshift-storage"
    }}
    spec = {{
      managementState = "{storage_cluster_config.get('managementState') or 'Managed'}"
      monDataDirHostPath = "{storage_cluster_config.get('monDataDirHostPath') or '/var/lib/rook'}"
      storageDeviceSets = [
        {{
          name = "ocs-deviceset-{storage_class}"
          count = {device_sets}
          replica = {replica_count}
          resources = {{}}
          placement = {{}}
          portable = true
          dataPVCTemplate = {{
            spec = {{
              storageClassName = "{storage_class}"
              accessModes = ["ReadWriteOnce"]
              resources = {{
                requests = {{
                  storage = "{device_size}"
                }}
              }}
              volumeMode = "Block"
            }}
          }}
        }}
      ]'''

        # Add Multi-Cloud Gateway (NooBaa) if enabled
        if enable_noobaa:
            terraform_config += f'''
      multiCloudGateway = {{
        reconcileStrategy = "{multi_cloud_gateway_config.get('reconcileStrategy', 'standalone')}"
        dbStorageClass = "{multi_cloud_gateway_config.get('dbStorageClass', storage_class)}"
        cacheVolumeStorageClass = "{multi_cloud_gateway_config.get('cacheVolumeStorageClass', storage_class)}"
      }}'''

        terraform_config += '''
    }
  }
  
  depends_on = [kubernetes_manifest.''' + clean_name + '''_storage_system]
}

'''

        # Add Ceph Tools if enabled
        if enable_ceph_tools:
            terraform_config += f'''# Ceph Tools for debugging and management
resource "kubernetes_manifest" "{clean_name}_ceph_tools" {{
  manifest = {{
    apiVersion = "ocs.openshift.io/v1"
    kind       = "OCSInitialization"
    metadata = {{
      name      = "ocsinit"
      namespace = "openshift-storage"
    }}
    spec = {{
      enableCephTools = true
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_storage_cluster]
}}

'''

        # Add backup configuration if specified
        backup_config = operator_config.get('backup_config', defaults.get('backup_config', {}))
        if backup_config:
            backup_name = self.clean_name(backup_config.get('name', 'storage-backup'))
            terraform_config += f'''# Storage Backup Configuration
resource "kubernetes_manifest" "{clean_name}_backup_{backup_name}" {{
  manifest = {{
    apiVersion = "volsync.backube/v1alpha1"
    kind       = "ReplicationSource"
    metadata = {{
      name      = "{backup_name}"
      namespace = "openshift-storage"
    }}
    spec = {{
      sourcePVC = "{backup_config.get('source_pvc', 'ocs-storagecluster-cephfs')}"
      trigger = {{
        schedule = "{backup_config.get('schedule', '0 0 * * *')}"  # Daily at midnight
      }}
      restic = {{
        repository = "{backup_config.get('repository', 'restic-secret')}"
        copyMethod = "{backup_config.get('copy_method', 'Snapshot')}"
        pruneIntervalDays = {backup_config.get('prune_interval_days', 7)}
        retain = {{
          daily = {backup_config.get('retain_daily', 7)}
          weekly = {backup_config.get('retain_weekly', 4)}
          monthly = {backup_config.get('retain_monthly', 12)}
        }}
      }}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_storage_cluster]
}}

'''

        return terraform_config 
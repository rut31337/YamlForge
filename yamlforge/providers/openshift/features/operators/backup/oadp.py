"""
OpenShift OADP Operator for yamlforge
Supports OpenShift API for Data Protection (backup/restore)
"""

from typing import Dict, List
from ....base import BaseOpenShiftProvider


class OADPOperator(BaseOpenShiftProvider):
    """OpenShift OADP operator for backup and restore operations"""
    
    def __init__(self, converter):
        super().__init__(converter)
        self.operator_config = self.load_operator_config('backup/oadp')
    
    def generate_oadp_operator(self, operator_config: Dict, target_clusters: List[str]) -> str:
        """Generate OADP operator for backup and restore"""
        
        # Load defaults from YAML configuration
        defaults = self.operator_config.get('defaults', {})
        subscription_config = self.operator_config.get('subscription', {})
        
        operator_name = operator_config.get('name', defaults.get('name', 'redhat-oadp-operator'))
        clean_name = self.clean_name(operator_name)
        
        # Configuration options with YAML defaults
        default_backup_ttl = operator_config.get('default_backup_ttl', defaults.get('default_backup_ttl', '720h'))
        default_backup_provider = operator_config.get('default_backup_provider', defaults.get('default_backup_provider', 'aws'))
        enable_restic = operator_config.get('enable_restic', defaults.get('enable_restic', True))
        
        terraform_config = f'''
# =============================================================================
# OADP OPERATOR: {operator_name}
# =============================================================================
# Clusters: {', '.join(target_clusters) if target_clusters else 'All clusters'}

# Create openshift-adp namespace
resource "kubernetes_manifest" "{clean_name}_namespace" {{
  manifest = {{
    apiVersion = "v1"
    kind       = "Namespace"
    metadata = {{
      name = "openshift-adp"
      labels = {{
        "openshift.io/cluster-monitoring" = "true"
      }}
    }}
  }}
}}

# OADP Operator Subscription
resource "kubernetes_manifest" "{clean_name}_subscription" {{
  manifest = {{
    apiVersion = "operators.coreos.com/v1alpha1"
    kind       = "Subscription"
    metadata = {{
      name      = "{subscription_config.get('name', 'redhat-oadp-operator')}"
      namespace = "openshift-adp"
    }}
    spec = {{
      channel = "{subscription_config.get('channel', 'stable-1.2')}"
      name    = "{subscription_config.get('name', 'redhat-oadp-operator')}"
      source  = "{subscription_config.get('source', 'redhat-operators')}"
      sourceNamespace = "{subscription_config.get('sourceNamespace', 'openshift-marketplace')}"
      installPlanApproval = "{subscription_config.get('installPlanApproval', 'Automatic')}"
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_namespace]
}}

# Data Protection Application
resource "kubernetes_manifest" "{clean_name}_dpa" {{
  manifest = {{
    apiVersion = "oadp.openshift.io/v1alpha1"
    kind       = "DataProtectionApplication"
    metadata = {{
      name      = "dpa-sample"
      namespace = "openshift-adp"
    }}
    spec = {{
      configuration = {{
        velero = {{
          defaultPlugins = [
            "openshift",
            "{default_backup_provider}"
          ]
          resourceTimeout = "{defaults.get('resource_timeout', '10m')}"
        }}
        restic = {{
          enable = {str(enable_restic).lower()}
          podConfig = {{
            resourceAllocations = {{
              limits = {{
                cpu = "{defaults.get('restic_cpu_limit', '1')}"
                memory = "{defaults.get('restic_memory_limit', '512Mi')}"
              }}
              requests = {{
                cpu = "{defaults.get('restic_cpu_request', '500m')}"
                memory = "{defaults.get('restic_memory_request', '256Mi')}"
              }}
            }}
          }}
        }}
      }}
      backupLocations = []
      snapshotLocations = []
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_subscription]
}}

'''

        # Generate backup storage locations
        backup_storage_locations = operator_config.get('backup_storage_locations', defaults.get('backup_storage_locations', []))
        for backup_location in backup_storage_locations:
            location_name = self.clean_name(backup_location.get('name', 'backup-location'))
            terraform_config += f'''# Backup Storage Location: {backup_location.get('name')}
resource "kubernetes_manifest" "{clean_name}_backup_location_{location_name}" {{
  manifest = {{
    apiVersion = "velero.io/v1"
    kind       = "BackupStorageLocation"
    metadata = {{
      name      = "{location_name}"
      namespace = "openshift-adp"
    }}
    spec = {{
      provider = "{backup_location.get('provider', default_backup_provider)}"
      default  = {str(backup_location.get('default', False)).lower()}
      objectStorage = {{
        bucket = "{backup_location.get('bucket', 'openshift-backups')}"
        prefix = "{backup_location.get('prefix', 'cluster-backups')}"
      }}
      config = {{
        region = "{backup_location.get('region', 'us-east-1')}"
      }}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_dpa]
}}

'''

        # Generate volume snapshot locations
        volume_snapshot_locations = operator_config.get('volume_snapshot_locations', defaults.get('volume_snapshot_locations', []))
        for snapshot_location in volume_snapshot_locations:
            location_name = self.clean_name(snapshot_location.get('name', 'snapshot-location'))
            terraform_config += f'''# Volume Snapshot Location: {snapshot_location.get('name')}
resource "kubernetes_manifest" "{clean_name}_snapshot_location_{location_name}" {{
  manifest = {{
    apiVersion = "velero.io/v1"
    kind       = "VolumeSnapshotLocation"
    metadata = {{
      name      = "{location_name}"
      namespace = "openshift-adp"
    }}
    spec = {{
      provider = "{snapshot_location.get('provider', default_backup_provider)}"
      config = {{
        region = "{snapshot_location.get('region', 'us-east-1')}"
      }}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_dpa]
}}

'''

        # Generate backup schedules
        backup_schedules = operator_config.get('backup_schedules', defaults.get('backup_schedules', []))
        for schedule in backup_schedules:
            schedule_name = self.clean_name(schedule.get('name', 'backup-schedule'))
            terraform_config += f'''# Backup Schedule: {schedule.get('name')}
resource "kubernetes_manifest" "{clean_name}_schedule_{schedule_name}" {{
  manifest = {{
    apiVersion = "velero.io/v1"
    kind       = "Schedule"
    metadata = {{
      name      = "{schedule_name}"
      namespace = "openshift-adp"
    }}
    spec = {{
      schedule = "{schedule.get('schedule', '0 2 * * *')}"  # Daily at 2 AM
      template = {{
        ttl = "{schedule.get('ttl', default_backup_ttl)}"
        includedNamespaces = {schedule.get('included_namespaces', [])}
        excludedNamespaces = {schedule.get('excluded_namespaces', [])}
        includedResources = {schedule.get('included_resources', [])}
        excludedResources = {schedule.get('excluded_resources', [])}
        labelSelector = {{
          matchLabels = {schedule.get('label_selector', {})}
        }}
        storageLocation = "{schedule.get('storage_location', 'default')}"
        snapshotVolumes = {str(schedule.get('snapshot_volumes', True)).lower()}
        defaultVolumesToRestic = {str(schedule.get('default_volumes_to_restic', False)).lower()}
      }}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_dpa]
}}

'''

        return terraform_config 
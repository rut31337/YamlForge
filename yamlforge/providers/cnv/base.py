"""
Base CNV Provider for yamlforge
Contains common functionality shared by all CNV deployment types
"""

import os
import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import subprocess
import json
from ...utils import find_yamlforge_file

# Import kubernetes client for direct API access
try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException
    import urllib3
    # Suppress SSL warnings for development clusters
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False


class BaseCNVProvider:
    """Base class for CNV providers with common functionality"""
    
    def __init__(self, converter=None):
        self.converter = converter
        self.cnv_defaults = self._load_cnv_defaults()
        self.cnv_images_cache = None
        self.cnv_images_cache_timestamp = None
    
    def _load_cnv_defaults(self):
        """Load CNV defaults from configuration file"""
        try:
            defaults_path = find_yamlforge_file("mappings/cnv/defaults.yaml")
            with open(defaults_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise Exception("CNV defaults file not found: mappings/cnv/defaults.yaml")
        except Exception as e:
            raise Exception(f"Could not load CNV defaults: {e}")
    
    def validate_cnv_operator(self) -> bool:
        """Validate that CNV/KubeVirt operator is installed and working using Kubernetes client"""
        if not KUBERNETES_AVAILABLE:
            print("Warning: kubernetes Python client not available, skipping CNV operator validation")
            return True  # Skip validation if client not available
        
        try:
            # Get OpenShift cluster credentials from environment variables
            cluster_url = os.getenv('OPENSHIFT_CLUSTER_URL')
            cluster_token = os.getenv('OPENSHIFT_CLUSTER_TOKEN')
            
            if not cluster_url or not cluster_token:
                print("Warning: OPENSHIFT_CLUSTER_URL or OPENSHIFT_CLUSTER_TOKEN not set, skipping CNV operator validation")
                return True  # Skip validation if credentials not available
            
            # Configure Kubernetes client with OpenShift credentials
            configuration = client.Configuration()
            configuration.host = cluster_url
            configuration.api_key = {"authorization": f"Bearer {cluster_token}"}
            
            # SSL verification - can be disabled for development clusters
            cluster_ca_cert = os.getenv('OPENSHIFT_CLUSTER_CA_CERT')
            if cluster_ca_cert:
                configuration.verify_ssl = True
                configuration.ssl_ca_cert = cluster_ca_cert
            else:
                configuration.verify_ssl = False  # For development clusters without CA cert
            
            # Create API client
            api_client = client.ApiClient(configuration)
            
            # Check for KubeVirt CRDs
            try:
                apiextensions_v1 = client.ApiextensionsV1Api(api_client)
                apiextensions_v1.read_custom_resource_definition("virtualmachines.kubevirt.io")
            except ApiException as e:
                if e.status == 404:
                    print("Warning: KubeVirt CRD 'virtualmachines.kubevirt.io' not found")
                    return False
                else:
                    print(f"Warning: Error checking KubeVirt CRD: {e}")
                    return False
            
            # Check for DataVolume CRDs
            try:
                apiextensions_v1.read_custom_resource_definition("datavolumes.cdi.kubevirt.io")
            except ApiException as e:
                if e.status == 404:
                    print("Warning: CDI CRD 'datavolumes.cdi.kubevirt.io' not found")
                    return False
                else:
                    print(f"Warning: Error checking CDI CRD: {e}")
                    return False
            
            # Check for KubeVirt operator pods in multiple possible namespaces
            possible_namespaces = ['kubevirt', 'openshift-ovirt-infra', 'openshift-virtualization', 'openshift-cnv']
            operator_found = False
            
            core_v1 = client.CoreV1Api(api_client)
            
            for namespace in possible_namespaces:
                try:
                    pods = core_v1.list_namespaced_pod(namespace=namespace)
                    for pod in pods.items:
                        if pod.status.phase == 'Running':
                            # Check if it's a KubeVirt-related pod
                            if any(keyword in pod.metadata.name.lower() for keyword in ['kubevirt', 'virt', 'cnv', 'hyperconverged']):
                                operator_found = True
                                # Only show this message in verbose mode
                                if hasattr(self, 'converter') and self.converter and hasattr(self.converter, 'verbose') and self.converter.verbose:
                                    print(f"Found running CNV/KubeVirt operator pod: {pod.metadata.name} in namespace {namespace}")
                                break
                    if operator_found:
                        break
                except ApiException as e:
                    if e.status != 404:  # 404 means namespace doesn't exist, which is fine
                        print(f"Warning: Error checking namespace {namespace}: {e}")
                    continue
            
            if not operator_found:
                print("Warning: No running CNV/KubeVirt operator pods found in expected namespaces")
                return False
            
            return True
            
        except Exception as e:
            print(f"Warning: Could not validate CNV operator: {e}")
            return False
    
    def discover_cnv_images(self, datavolume_namespace: str = None) -> Dict:
        """Dynamically discover available CNV images from DataVolumes in the cluster"""
        if not datavolume_namespace:
            datavolume_namespace = self.cnv_defaults.get('default_datavolume_namespace', 'cnv-images')
        
        # Check cache first (cache for 5 minutes)
        import time
        current_time = time.time()
        if (self.cnv_images_cache and self.cnv_images_cache_timestamp and 
            (current_time - self.cnv_images_cache_timestamp) < 300):
            return self.cnv_images_cache
        
        # For now, return mock data to test pattern matching without kubectl
        # TODO: Re-enable kubectl discovery once timeout issues are resolved
        mock_images = {
            'rhel-9.1': {
                'datavolume_name': 'rhel-9.1',
                'datavolume_namespace': datavolume_namespace,
                'description': 'Red Hat Enterprise Linux 9.1',
                'os_family': 'rhel',
                'os_version': '9.1',
                'phase': 'Succeeded'
            },
            'rhel-9.6': {
                'datavolume_name': 'rhel-9.6',
                'datavolume_namespace': datavolume_namespace,
                'description': 'Red Hat Enterprise Linux 9.6',
                'os_family': 'rhel',
                'os_version': '9.6',
                'phase': 'Succeeded'
            },
            'rhel-10.0': {
                'datavolume_name': 'rhel-10.0',
                'datavolume_namespace': datavolume_namespace,
                'description': 'Red Hat Enterprise Linux 10.0',
                'os_family': 'rhel',
                'os_version': '10.0',
                'phase': 'Succeeded'
            }
        }
        
        # Cache the results
        self.cnv_images_cache = mock_images
        self.cnv_images_cache_timestamp = current_time
        
        return mock_images
        
        # TODO: Re-enable kubectl discovery
        # try:
        #     # Get DataVolumes from the specified namespace
        #     result = subprocess.run(
        #         ['kubectl', 'get', 'datavolumes', '-n', datavolume_namespace, '-o', 'json'],
        #         capture_output=True, text=True, timeout=30
        #     )
        #     
        #     if result.returncode != 0:
        #         print(f"Warning: Could not discover CNV images from namespace {datavolume_namespace}")
        #         return {}
        #     
        #     datavolumes = json.loads(result.stdout)
        #     discovered_images = {}
        #     
        #     for dv in datavolumes.get('items', []):
        #         metadata = dv.get('metadata', {})
        #         name = metadata.get('name', '')
        #         phase = dv.get('status', {}).get('phase', '')
        #         
        #         # Only include successful DataVolumes
        #         if phase == 'Succeeded':
        #             # Parse RHEL version from name
        #             os_family, os_version = self._parse_rhel_version(name)
        #             
        #             discovered_images[name] = {
        #                 'datavolume_name': name,
        #                 'datavolume_namespace': datavolume_namespace,
        #                 'description': f"Red Hat Enterprise Linux {os_version}",
        #                 'os_family': os_family,
        #                 'os_version': os_version,
        #                 'phase': phase
        #             }
        #             
        #             # Also add legacy mappings for backward compatibility
        #             if os_family == 'rhel':
        #                 if os_version.startswith('9'):
        #                     discovered_images[f'RHEL9-latest'] = discovered_images[name].copy()
        #                 elif os_version.startswith('8'):
        #                     discovered_images[f'RHEL8-latest'] = discovered_images[name].copy()
        #                 elif os_version.startswith('10'):
        #                     discovered_images[f'RHEL10-latest'] = discovered_images[name].copy()
        #     
        #     # Cache the results
        #     self.cnv_images_cache = discovered_images
        #     self.cnv_images_cache_timestamp = os.path.getmtime(__file__)
        #     
        #     return discovered_images
        #     
        # except Exception as e:
        #     print(f"Warning: Error discovering CNV images: {e}")
        #     return {}

    def discover_cnv_pvcs(self, namespace: str = None) -> Dict:
        """Discover available PVCs in the specified namespace (for cross-namespace references)"""
        if not namespace:
            namespace = self.cnv_defaults.get('default_datavolume_namespace', 'cnv-images')
        
        discovered_pvcs = {}
        
        if not KUBERNETES_AVAILABLE:
            print("Warning: kubernetes Python client not available, using placeholder data")
            return {
                'rhel-9.6': {
                    'pvc_name': 'rhel-9.6',
                    'pvc_namespace': namespace,
                    'status': 'Bound',
                    'description': 'Red Hat Enterprise Linux 9.6 PVC (placeholder)',
                    'os_family': 'rhel',
                    'os_version': '9.6'
                }
            }
        
        cluster_url = os.getenv('OPENSHIFT_CLUSTER_URL')
        cluster_token = os.getenv('OPENSHIFT_CLUSTER_TOKEN')
        
        if not cluster_url or not cluster_token:
            print("Warning: OPENSHIFT_CLUSTER_URL or OPENSHIFT_CLUSTER_TOKEN not set, using placeholder data")
            return {
                'rhel-9.6': {
                    'pvc_name': 'rhel-9.6',
                    'pvc_namespace': namespace,
                    'status': 'Bound',
                    'description': 'Red Hat Enterprise Linux 9.6 PVC (placeholder)',
                    'os_family': 'rhel',
                    'os_version': '9.6'
                }
            }
        
        configuration = client.Configuration()
        configuration.host = cluster_url
        configuration.api_key = {"authorization": f"Bearer {cluster_token}"}
        
        cluster_ca_cert = os.getenv('OPENSHIFT_CLUSTER_CA_CERT')
        if cluster_ca_cert:
            configuration.verify_ssl = True
            configuration.ssl_ca_cert = cluster_ca_cert
        else:
            configuration.verify_ssl = False
        
        api_client = client.ApiClient(configuration)
        
        try:
            # Use CoreV1Api to query PVCs
            core_v1 = client.CoreV1Api(api_client)
            
            # Query PVCs in the specified namespace
            pvcs = core_v1.list_namespaced_persistent_volume_claim(namespace=namespace)
            
            for pvc in pvcs.items:
                pvc_name = pvc.metadata.name
                pvc_status = pvc.status.phase if pvc.status else 'Unknown'
                
                # Only include PVCs that are bound (ready to use)
                if pvc_status == 'Bound':
                    # Parse RHEL version from name if possible
                    os_family, os_version = self._parse_rhel_version(pvc_name)
                    
                    discovered_pvcs[pvc_name] = {
                        'pvc_name': pvc_name,
                        'pvc_namespace': namespace,
                        'status': pvc_status,
                        'description': f"PVC: {pvc_name} (Status: {pvc_status})",
                        'os_family': os_family,
                        'os_version': os_version,
                        'storage_class': pvc.spec.storage_class_name if pvc.spec else 'unknown',
                        'capacity': pvc.status.capacity.get('storage', 'unknown') if pvc.status and pvc.status.capacity else 'unknown'
                    }
            
            if hasattr(self, 'converter') and self.converter and hasattr(self.converter, 'verbose') and self.converter.verbose:
                print(f"Discovered {len(discovered_pvcs)} bound PVCs in namespace '{namespace}'")
            
            return discovered_pvcs
            
        except Exception as e:
            print(f"Warning: Could not discover PVCs in namespace '{namespace}': {e}")
            return {}
    
    def _parse_rhel_version(self, datavolume_name: str) -> Tuple[str, str]:
        """Parse RHEL version from DataVolume name"""
        # Common patterns for RHEL DataVolume names
        patterns = [
            r'rhel-(\d+)\.(\d+)',  # rhel-9.6, rhel-8.10
            r'rhel(\d+)-beta',     # rhel10-beta
            r'rhel-(\d+)-(\d+)-(\d+)-(\d+)',  # rhel-10-0-07-09-25
        ]
        
        for pattern in patterns:
            match = re.match(pattern, datavolume_name)
            if match:
                if 'beta' in datavolume_name:
                    return 'rhel', f"{match.group(1)}-beta"
                elif len(match.groups()) == 2:
                    return 'rhel', f"{match.group(1)}.{match.group(2)}"
                elif len(match.groups()) == 4:
                    return 'rhel', f"{match.group(1)}.{match.group(2)}"
        
        # Default fallback
        return 'unknown', 'unknown'
    
    def get_cnv_image_config(self, image_name: str, datavolume_namespace: str = None) -> Dict:
        """Get CNV image configuration from discovered images or pattern matching"""
        if not datavolume_namespace:
            datavolume_namespace = self.cnv_defaults.get('default_datavolume_namespace', 'cnv-images')
        
        # Handle GOLD images by removing "GOLD" from the name (CNV doesn't support GOLD)
        original_image_name = image_name
        if 'GOLD' in image_name.upper():
            # Simply remove "GOLD" from the image name and continue
            image_name = image_name.upper().replace('GOLD', '').replace('--', '-').strip('-')
            
            # Convert dash format to mapping file format: RHEL-9-latest -> RHEL9-latest
            if image_name.startswith('RHEL-'):
                image_name = image_name.replace('RHEL-', 'RHEL')
            
            # Convert to proper case for mapping file entries
            if image_name.endswith('-LATEST'):
                image_name = image_name.replace('-LATEST', '-latest')
            elif image_name.endswith('LATEST'):
                image_name = image_name.replace('LATEST', '-latest')
            
            print(f"Note: GOLD images are not supported in CNV. Converting '{original_image_name}' to '{image_name}'")
        
        # First, try to load static mappings from the mapping file
        static_mappings = self._load_cnv_image_patterns()
        
        # Check if the requested image is a static mapping
        if image_name in static_mappings:
            static_config = static_mappings[image_name]
            if 'cnv' in static_config:
                cnv_config = static_config['cnv']
                if cnv_config.get('static', False):
                    # Static image mapping - return PVC reference
                    return {
                        'pvc_name': cnv_config['datavolume_name'],  # PVC name is same as DataVolume name
                        'pvc_namespace': cnv_config.get('datavolume_namespace', datavolume_namespace),
                        'description': static_config.get('description', f"Static image: {image_name}"),
                        'os_family': cnv_config.get('os_family', 'unknown'),
                        'os_version': cnv_config.get('os_version', 'unknown'),
                        'volume_type': 'pvc'  # Indicate this is a PVC reference
                    }
                else:
                    # Dynamic discovery mapping
                    name_pattern = cnv_config.get('name_pattern')
                    if name_pattern:
                        return self._resolve_dynamic_image(name_pattern, datavolume_namespace, static_config)
        
        # Check for RHEL-<VERSION> patterns (handled in code like AWS AMI patterns)
        rhel_match = self._match_rhel_pattern(image_name)
        if rhel_match:
            pattern, version_major = rhel_match
            return self._resolve_dynamic_image(pattern, datavolume_namespace, {
                'description': f"Red Hat Enterprise Linux {version_major}.x (latest available)",
                'os_family': 'rhel'
            })
        
        # Check for direct PVC name (cross-namespace reference)
        discovered_pvcs = self.discover_cnv_pvcs(datavolume_namespace)
        
        if image_name in discovered_pvcs:
            pvc_config = discovered_pvcs[image_name]
            return {
                'pvc_name': pvc_config['pvc_name'],
                'pvc_namespace': pvc_config['pvc_namespace'],
                'description': pvc_config['description'],
                'os_family': pvc_config['os_family'],
                'os_version': pvc_config['os_version'],
                'volume_type': 'pvc'  # Indicate this is a PVC reference
            }
        
        # No fallback - fail clearly if no matching PVC is found
        available_pvcs = list(discovered_pvcs.keys())
        raise ValueError(
            f"CNV Image Error: No matching PVC found for image '{original_image_name}' (converted to '{image_name}') in namespace '{datavolume_namespace}'.\n\n"
            f"Available PVCs: {', '.join(available_pvcs) if available_pvcs else 'None found'}\n\n"
            f"Supported patterns:\n"
            f"  • RHEL9-latest, RHEL8-latest, RHEL10-latest (from mapping file)\n"
            f"  • RHEL-8.*, RHEL-9.*, RHEL-10.* (pattern matching)\n"
            f"  • Exact PVC names (e.g., rhel-9.6, rhel-10.0)\n"
            f"  • Static images (e.g., fedora-demo)\n"
            f"  • GOLD images (automatically converted to regular RHEL)\n\n"
            f"Note: GOLD images are automatically converted to regular RHEL images in CNV."
        )
    
    def _resolve_dynamic_image(self, name_pattern: str, datavolume_namespace: str, config: Dict) -> Dict:
        """Resolve dynamic image using name pattern"""
        # Discover available PVCs
        discovered_pvcs = self.discover_cnv_pvcs(datavolume_namespace)
        
        # Find PVCs that match the pattern
        matching_pvcs = []
        import re
        pattern_regex = re.compile(name_pattern)
        
        for pvc_name, pvc_config in discovered_pvcs.items():
            if pattern_regex.match(pvc_name):
                matching_pvcs.append((pvc_name, pvc_config))
        
        if matching_pvcs:
            # Sort by version and select the latest
            matching_pvcs.sort(key=lambda x: self._extract_version_number(x[0]), reverse=True)
            
            # Return the latest matching PVC
            selected_pvc_name, selected_pvc_config = matching_pvcs[0]
            return {
                'pvc_name': selected_pvc_name,
                'pvc_namespace': datavolume_namespace,
                'description': config.get('description', f"Pattern-matched: {name_pattern}"),
                'os_family': config.get('os_family', 'unknown'),
                'os_version': selected_pvc_config.get('os_version', 'unknown'),
                'volume_type': 'pvc'  # Indicate this is a PVC reference
            }
        
        # No fallback - fail clearly if no matching DataVolume is found
        available_images = list(discovered_images.keys())
        raise ValueError(
            f"CNV Image Error: No DataVolume found matching pattern '{name_pattern}' in namespace '{datavolume_namespace}'.\n\n"
            f"Available DataVolumes: {', '.join(available_images) if available_images else 'None found'}\n\n"
            f"Pattern '{name_pattern}' did not match any available DataVolumes.\n"
            f"Make sure the DataVolume exists and is in 'Succeeded' state."
        )
    
    def _load_cnv_image_patterns(self) -> Dict:
        """Load CNV image patterns from the main mappings file"""
        try:
            # Use centralized path resolution
            from ...utils import find_yamlforge_file
            mappings_file = find_yamlforge_file('mappings/images.yaml')
            
            with open(mappings_file, 'r') as f:
                mappings = yaml.safe_load(f)
            
            # Extract CNV-specific mappings from the main images file
            cnv_mappings = {}
            for image_name, image_config in mappings.get('images', {}).items():
                if 'cnv' in image_config:
                    cnv_mappings[image_name] = image_config
            
            return cnv_mappings
        except FileNotFoundError:
            print(f"Warning: CNV image mappings file not found: {mappings_file}")
            return {}
        except yaml.YAMLError as e:
            print(f"Error parsing CNV image mappings: {e}")
            return {}
    
    def _extract_version_number(self, datavolume_name: str) -> str:
        """Extract version number from DataVolume name for sorting"""
        import re
        
        # Try to extract version numbers like 9.6, 10.0, etc.
        version_match = re.search(r'(\d+)\.(\d+)', datavolume_name)
        if version_match:
            major = int(version_match.group(1))
            minor = int(version_match.group(2))
            return f"{major:03d}.{minor:03d}"
        
        # Fallback: return the original name for sorting
        return datavolume_name
    
    def _match_rhel_pattern(self, image_name: str) -> tuple:
        """Match RHEL pattern and return (pattern, version_major) if matched"""
        import re
        
        # RHEL pattern matching (similar to AWS AMI patterns)
        # These patterns are handled in code, not in the mapping file
        rhel_patterns = [
            (r'^RHEL-9(\.\*)?$', '9'),      # RHEL-9, RHEL-9.*
            (r'^RHEL-10(\.\*)?$', '10'),    # RHEL-10, RHEL-10.*
            (r'^RHEL-8(\.\*)?$', '8'),      # RHEL-8, RHEL-8.*
            (r'^rhel-9(\.\*)?$', '9'),      # rhel-9, rhel-9.*
            (r'^rhel-10(\.\*)?$', '10'),    # rhel-10, rhel-10.*
            (r'^rhel-8(\.\*)?$', '8'),      # rhel-8, rhel-8.*
        ]
        
        for pattern_str, version_major in rhel_patterns:
            pattern = re.compile(pattern_str)
            if pattern.match(image_name):
                # Convert the input pattern to a regex pattern for DataVolume matching
                # RHEL-9.* -> rhel-9.*, RHEL-9 -> rhel-9.*
                if image_name.endswith('.*'):
                    dv_pattern = image_name.lower().replace('RHEL-', 'rhel-')
                else:
                    dv_pattern = image_name.lower().replace('RHEL-', 'rhel-') + '.*'
                return (dv_pattern, version_major)
        
        return None
    
    def clean_name(self, name):
        """Clean name for Terraform resource naming"""
        if not name:
            return "cnv-vm"
        
        # Remove special characters and convert to lowercase
        clean_name = re.sub(r'[^a-zA-Z0-9-]', '-', name.lower())
        clean_name = re.sub(r'-+', '-', clean_name)
        clean_name = clean_name.strip('-')
        
        # Check for GUID placeholder
        has_guid_placeholder = '{guid}' in name
        
        return clean_name, has_guid_placeholder
    
    def get_cnv_size_config(self, flavor_name):
        """Get CNV size configuration from mappings file"""
        if not flavor_name:
            raise ValueError("CNV instance must specify a flavor or cores/memory")
            
        # Load CNV flavors from mappings file
        try:
            flavors_path = find_yamlforge_file("mappings/flavors/cnv.yaml")
            if flavors_path.exists():
                with open(flavors_path, 'r') as f:
                    flavors = yaml.safe_load(f)
                flavor_mappings = flavors.get('flavor_mappings', {})
                
                if flavor_name in flavor_mappings:
                    # Get the first (and usually only) flavor for this size
                    size_flavors = flavor_mappings[flavor_name]
                    if size_flavors:
                        # Get the first flavor (e.g., 'cnv-small' for 'small')
                        flavor_name = next(iter(size_flavors.keys()))
                        flavor_config = size_flavors[flavor_name]
                        
                        return {
                            'cpu': str(flavor_config.get('vcpus', 1)),
                            'memory': f"{flavor_config.get('memory_gb', 1)}Gi"
                        }
                
                # Size not found in mappings
                available_sizes = list(flavor_mappings.keys())
                raise ValueError(
                    f"CNV flavor '{flavor_name}' not found in mappings. "
                    f"Available flavors: {', '.join(available_sizes)}"
                )
            else:
                raise ValueError("CNV flavors file not found: mappings/flavors/cnv.yaml")
        except Exception as e:
            if isinstance(e, ValueError):
                raise e
            else:
                raise ValueError(f"Error loading CNV flavors: {e}")
    
    def get_cnv_specs_config(self, cores, memory_gb):
        """Get CNV configuration from cores and memory specifications"""
        if not cores or not memory_gb:
            raise ValueError("CNV instance must specify both 'cores' and 'memory' when not using 'flavor'")
        
        # Memory is already in GB, ensure minimum of 1Gi
        memory_gi = max(1, memory_gb)
        
        return {
            'cpu': str(cores),
            'memory': f'{memory_gi}Gi'
        }
    
    def generate_cnv_namespace(self, namespace_name):
        """Generate Kubernetes namespace for CNV resources with CNV enablement"""
        
        terraform_config = f'''
# CNV Namespace: {namespace_name}
resource "kubernetes_namespace" "{namespace_name}" {{
  metadata {{
    name = "{namespace_name}"
    labels = {{
      "managed-by" = "yamlforge"
      "cnv-enabled" = "true"
    }}
  }}
}}

# Enable CNV for the namespace
resource "kubectl_manifest" "{namespace_name}_cnv_enablement" {{
  depends_on = [kubernetes_namespace.{namespace_name}]
  
  yaml_body = yamlencode({{
    apiVersion = "v1"
    kind = "Namespace"
    metadata = {{
      name = "{namespace_name}"
      labels = {{
        "managed-by" = "yamlforge"
        "cnv-enabled" = "true"
        "openshift.io/cluster-monitoring" = "true"
      }}
      annotations = {{
        "openshift.io/node-selector" = ""
      }}
    }}
  }})
}}


'''
        return terraform_config
    
    def generate_cnv_network_attachment(self, network_config):
        """Generate NetworkAttachmentDefinition for CNV networking"""
        
        network_name = network_config.get('name', 'default-network')
        network_type = network_config.get('type', 'pod')
        
        terraform_config = f'''
# CNV Network Attachment: {network_name}
resource "kubectl_manifest" "{network_name}_network_attachment" {{
  yaml_body = yamlencode({{
    apiVersion = "k8s.cni.cncf.io/v1"
    kind       = "NetworkAttachmentDefinition"
    metadata = {{
      name      = "{network_name}"
      namespace = "{network_config.get('namespace', 'default')}"
    }}
    spec = {{
      config = jsonencode({{
        cniVersion = "0.3.1"
        type       = "{network_type}"
        bridge     = "{network_name}"
        ipam = {{
          type = "host-local"
          subnet = "{network_config.get('subnet', '10.244.0.0/16')}"
        }}
      }})
    }}
  }})
}}
'''
        return terraform_config
    
    def validate_cnv_instance(self, instance):
        """Validate CNV instance configuration"""
        required_fields = ['name']
        for field in required_fields:
            if not instance.get(field):
                raise ValueError(f"CNV instance must specify '{field}'")
        
        # Size validation is handled by get_cnv_size_config method
        # which will raise appropriate errors for invalid sizes
        
        return True

"""
OpenShift MetalLB Operator for yamlforge
Supports advanced load balancing and networking
"""

from typing import Dict, List
from ....base import BaseOpenShiftProvider


class MetalLBOperator(BaseOpenShiftProvider):
    """OpenShift MetalLB operator for advanced load balancing"""
    
    def __init__(self, converter):
        super().__init__(converter)
        self.operator_config = self.load_operator_config('networking/metallb')
    
    def generate_metallb_operator(self, operator_config: Dict, target_clusters: List[str]) -> str:
        """Generate MetalLB operator for advanced load balancing"""
        
        # Load defaults from YAML configuration
        defaults = self.operator_config.get('defaults', {})
        subscription_config = self.operator_config.get('subscription', {})
        
        operator_name = operator_config.get('name', defaults.get('name', 'metallb-operator'))
        clean_name = self.clean_name(operator_name)
        
        # Configuration options with YAML defaults
        enable_bgp = operator_config.get('enable_bgp', defaults.get('enable_bgp', False))
        enable_layer2 = operator_config.get('enable_layer2', defaults.get('enable_layer2', True))
        log_level = operator_config.get('log_level', defaults.get('log_level', 'info'))
        
        terraform_config = f'''
# =============================================================================
# METALLB OPERATOR: {operator_name}
# =============================================================================
# Clusters: {', '.join(target_clusters) if target_clusters else 'All clusters'}

# Create metallb-system namespace
resource "kubernetes_manifest" "{clean_name}_namespace" {{
  manifest = {{
    apiVersion = "v1"
    kind       = "Namespace"
    metadata = {{
      name = "metallb-system"
      labels = {{
        "openshift.io/cluster-monitoring" = "true"
      }}
    }}
  }}
}}

# MetalLB Operator Subscription
resource "kubernetes_manifest" "{clean_name}_subscription" {{
  manifest = {{
    apiVersion = "operators.coreos.com/v1alpha1"
    kind       = "Subscription"
    metadata = {{
      name      = "{subscription_config.get('name', 'metallb-operator')}"
      namespace = "metallb-system"
    }}
    spec = {{
      channel = "{subscription_config.get('channel', 'stable')}"
      name    = "{subscription_config.get('name', 'metallb-operator')}"
      source  = "{subscription_config.get('source', 'redhat-operators')}"
      sourceNamespace = "{subscription_config.get('sourceNamespace', 'openshift-marketplace')}"
      installPlanApproval = "{subscription_config.get('installPlanApproval', 'Automatic')}"
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_namespace]
}}

# MetalLB Instance
resource "kubernetes_manifest" "{clean_name}_instance" {{
  manifest = {{
    apiVersion = "metallb.io/v1beta1"
    kind       = "MetalLB"
    metadata = {{
      name      = "metallb"
      namespace = "metallb-system"
    }}
    spec = {{
      logLevel = "{log_level}"
      nodeSelector = {defaults.get('node_selector', {})}
      tolerations = {defaults.get('tolerations', [])}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_subscription]
}}

'''

        # Generate IP address pools
        address_pools = operator_config.get('address_pools', defaults.get('address_pools', []))
        for pool in address_pools:
            pool_name = self.clean_name(pool.get('name', 'address-pool'))
            terraform_config += f'''# MetalLB IP Address Pool: {pool.get('name')}
resource "kubernetes_manifest" "{clean_name}_pool_{pool_name}" {{
  manifest = {{
    apiVersion = "metallb.io/v1beta1"
    kind       = "IPAddressPool"
    metadata = {{
      name      = "{pool_name}"
      namespace = "metallb-system"
    }}
    spec = {{
      addresses = {pool.get('addresses', [])}
      autoAssign = {str(pool.get('auto_assign', True)).lower()}
      avoidBuggyIPs = {str(pool.get('avoid_buggy_ips', False)).lower()}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_instance]
}}

'''

        # Generate L2 Advertisements if layer2 is enabled
        if enable_layer2:
            l2_advertisements = operator_config.get('l2_advertisements', defaults.get('l2_advertisements', []))
            for l2_ad in l2_advertisements:
                l2_name = self.clean_name(l2_ad.get('name', 'l2-advertisement'))
                terraform_config += f'''# MetalLB L2 Advertisement: {l2_ad.get('name')}
resource "kubernetes_manifest" "{clean_name}_l2_ad_{l2_name}" {{
  manifest = {{
    apiVersion = "metallb.io/v1beta1"
    kind       = "L2Advertisement"
    metadata = {{
      name      = "{l2_name}"
      namespace = "metallb-system"
    }}
    spec = {{
      ipAddressPools = {l2_ad.get('ip_address_pools', [])}
      nodeSelectors = {l2_ad.get('node_selectors', [])}
      interfaces = {l2_ad.get('interfaces', [])}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_instance]
}}

'''

        # Generate BGP Advertisements if BGP is enabled
        if enable_bgp:
            bgp_advertisements = operator_config.get('bgp_advertisements', defaults.get('bgp_advertisements', []))
            for bgp_ad in bgp_advertisements:
                bgp_name = self.clean_name(bgp_ad.get('name', 'bgp-advertisement'))
                terraform_config += f'''# MetalLB BGP Advertisement: {bgp_ad.get('name')}
resource "kubernetes_manifest" "{clean_name}_bgp_ad_{bgp_name}" {{
  manifest = {{
    apiVersion = "metallb.io/v1beta1"
    kind       = "BGPAdvertisement"
    metadata = {{
      name      = "{bgp_name}"
      namespace = "metallb-system"
    }}
    spec = {{
      ipAddressPools = {bgp_ad.get('ip_address_pools', [])}
      aggregationLength = {bgp_ad.get('aggregation_length', 32)}
      localPref = {bgp_ad.get('local_pref', 0)}
      communities = {bgp_ad.get('communities', [])}
      peers = {bgp_ad.get('peers', [])}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_instance]
}}

'''

            # Generate BGP Peers
            bgp_peers = operator_config.get('bgp_peers', defaults.get('bgp_peers', []))
            for peer in bgp_peers:
                peer_name = self.clean_name(peer.get('name', 'bgp-peer'))
                terraform_config += f'''# MetalLB BGP Peer: {peer.get('name')}
resource "kubernetes_manifest" "{clean_name}_bgp_peer_{peer_name}" {{
  manifest = {{
    apiVersion = "metallb.io/v1beta2"
    kind       = "BGPPeer"
    metadata = {{
      name      = "{peer_name}"
      namespace = "metallb-system"
    }}
    spec = {{
      myASN = {peer.get('my_asn', 64512)}
      peerASN = {peer.get('peer_asn', 64512)}
      peerAddress = "{peer.get('peer_address', '192.168.1.1')}"
      sourceAddress = "{peer.get('source_address', '192.168.1.2')}"
      peerPort = {peer.get('peer_port', 179)}
      holdTime = "{peer.get('hold_time', '90s')}"
      keepaliveTime = "{peer.get('keepalive_time', '30s')}"
      routerID = "{peer.get('router_id', '192.168.1.2')}"
      password = "{peer.get('password', '')}"
      bfdProfile = "{peer.get('bfd_profile', '')}"
      ebgpMultiHop = {str(peer.get('ebgp_multi_hop', False)).lower()}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_instance]
}}

'''

        return terraform_config 
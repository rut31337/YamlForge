"""
OpenShift cert-manager Operator for yamlforge
Supports certificate management and TLS automation with multiple ACME providers including EAB and automatic fallback
EAB credentials automatically sourced from environment variables
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List
from ....base import BaseOpenShiftProvider


class CertManagerOperator(BaseOpenShiftProvider):
    """OpenShift cert-manager operator for certificate management"""
    
    def __init__(self, converter):
        super().__init__(converter)
        self.operator_config = self.load_operator_config('security/cert_manager')
        self.eab_config = self._load_eab_template()
    
    def _load_eab_template(self) -> Dict:
        """Load EAB configuration from environment variables - no more file loading"""
        # All EAB configuration now comes from environment variables
        # Return static configuration for environment variable mappings
        return {
            'auto_generate_secrets': True,
            'environment_variables': {
                'zerossl': {
                    'eab_kid_env': 'ZEROSSL_EAB_KID',
                    'eab_hmac_env': 'ZEROSSL_EAB_HMAC',
                    'fallback_kid': 'demo-kid-zerossl',
                    'fallback_hmac': 'demo-hmac-key-zerossl'
                },
                'sslcom': {
                    'eab_kid_env': 'SSLCOM_EAB_KID',
                    'eab_hmac_env': 'SSLCOM_EAB_HMAC',
                    'fallback_kid': 'demo-kid-sslcom',
                    'fallback_hmac': 'demo-hmac-key-sslcom'
                }
            }
        }
    
    def generate_cert_manager_operator(self, operator_config: Dict, target_clusters: List[Dict]) -> str:
        """Generate cert-manager operator for certificate management"""
        
        # Load defaults from YAML configuration
        defaults = self.operator_config.get('defaults', {})
        subscription_config = self.operator_config.get('subscription', {})
        acme_providers = self.operator_config.get('acme_providers', {})
        fallback_chains = self.operator_config.get('fallback_chains', {})
        fallback_triggers = self.operator_config.get('fallback_triggers', {})
        
        operator_name = operator_config.get('name', defaults.get('name', 'cert-manager'))
        clean_name = self.clean_name(operator_name)
        
        # Configuration options with YAML defaults
        enable_cluster_issuers = operator_config.get('enable_cluster_issuers', defaults.get('enable_cluster_issuers', True))
        default_issuer_email = operator_config.get('default_issuer_email', defaults.get('default_issuer_email', 'admin@example.com'))
        enable_fallback = operator_config.get('enable_fallback', defaults.get('enable_fallback', True))
        fallback_chain = operator_config.get('fallback_chain', 'default')
        
        # EAB automation comes from credential template only - single source of truth
        auto_generate_secrets = self.eab_config.get('auto_generate_secrets', True)
        
        terraform_config = f'''
# =============================================================================
# CERT-MANAGER OPERATOR: {operator_name} (TEMPLATE-AUTOMATED)
# =============================================================================
# Clusters: {', '.join(target_clusters) if target_clusters else 'All clusters'}
# Supports multiple ACME providers: Let's Encrypt, ZeroSSL (EAB), SSL.com (EAB), Buypass, Google
        # EAB (External Account Binding) credentials automatically sourced from environment variables
# Automatic fallback between providers on failures (rate limits, outages, etc.)
# SINGLE SOURCE OF TRUTH - EAB configuration read from credential template only

# Create cert-manager namespace
resource "kubernetes_manifest" "{clean_name}_namespace" {{
  manifest = {{
    apiVersion = "v1"
    kind       = "Namespace"
    metadata = {{
      name = "{defaults.get('namespace', 'cert-manager-operator')}"
      labels = {{
        "openshift.io/cluster-monitoring" = "true"
        "cert-manager.io/disable-validation" = "true"
        "yamlforge.io/operator" = "cert-manager"
        "yamlforge.io/automated" = "true"
      }}
      annotations = {{
        "yamlforge.io/generated-by" = "yamlforge"
        "yamlforge.io/config-source" = "defaults/openshift_operators/security/cert_manager.yaml"
                        "yamlforge.io/eab-source" = "environment-variables"
        "yamlforge.io/single-source-of-truth" = "true"
      }}
    }}
  }}
}}

# cert-manager Subscription
resource "kubernetes_manifest" "{clean_name}_subscription" {{
  manifest = {{
    apiVersion = "operators.coreos.com/v1alpha1"
    kind       = "Subscription"
    metadata = {{
      name      = "{subscription_config.get('name', 'cert-manager')}"
      namespace = "{defaults.get('namespace', 'cert-manager-operator')}"
      annotations = {{
        "yamlforge.io/operator" = "cert-manager"
        "yamlforge.io/version" = "{subscription_config.get('channel', 'stable-v1')}"
      }}
    }}
    spec = {{
      channel = "{subscription_config.get('channel', 'stable-v1')}"
      name    = "{subscription_config.get('name', 'cert-manager')}"
      source  = "{subscription_config.get('source', 'redhat-operators')}"
      sourceNamespace = "{subscription_config.get('sourceNamespace', 'openshift-marketplace')}"
      installPlanApproval = "{subscription_config.get('installPlanApproval', 'Automatic')}"
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_namespace]
}}

'''

        # Auto-generate EAB secrets from environment variables if template configured
        if auto_generate_secrets and 'environment_variables' in self.eab_config:
            terraform_config += self._generate_eab_secrets(clean_name, acme_providers)

        # Generate ClusterIssuers for each enabled ACME provider
        if enable_cluster_issuers:
            enabled_providers = operator_config.get('enabled_acme_providers', [])
            
            # If no specific providers configured, use defaults from YAML
            if not enabled_providers:
                cluster_issuers_config = self.operator_config.get('cluster_issuers', {})
                enabled_providers = cluster_issuers_config.get('enabled_issuers', ['letsencrypt-prod', 'letsencrypt-staging'])
            
            terraform_config += self._generate_cluster_issuers(clean_name, enabled_providers, acme_providers, default_issuer_email)

        # Generate fallback configuration if enabled
        if enable_fallback and fallback_chain in fallback_chains:
            terraform_config += self._generate_fallback_config(clean_name, fallback_chains[fallback_chain], fallback_triggers)

        # Generate example certificates if provided
        example_certificates = operator_config.get('example_certificates', [])
        if example_certificates:
            terraform_config += self._generate_example_certificates(clean_name, example_certificates)

        return terraform_config
    
    def _generate_eab_secrets(self, clean_name: str, acme_providers: Dict) -> str:
        """Generate EAB secrets automatically from environment variables based on template configuration"""
        
        env_mappings = self.eab_config.get('environment_variables', {})
        terraform_config = '''
# =============================================================================
# AUTO-GENERATED EAB SECRETS (From Credential Template - Single Source)
# =============================================================================
# EAB credentials are automatically sourced from environment variables
        # as configured in environment variables:
# - No manual secret creation required
# - No configuration copying required
# - Credentials are securely injected from environment
# - Fallback values provided for testing/demo purposes

'''
        
        for provider_name, provider_config in acme_providers.items():
            if provider_config.get('requires_eab', False) and provider_config.get('enabled', False):
                
                if provider_name in env_mappings:
                    env_config = env_mappings[provider_name]
                    secret_name = provider_config.get('secret_name', f'{provider_name}-eab-credentials')
                    
                    # Get environment variable names from template configuration
                    kid_env = env_config.get('eab_kid_env')
                    hmac_env = env_config.get('eab_hmac_env')
                    fallback_kid = env_config.get('fallback_kid', 'demo-kid')
                    fallback_hmac = env_config.get('fallback_hmac', 'demo-hmac-key')
                    
                    terraform_config += f'''
# {provider_name.upper()} EAB Credentials (Auto-Generated from Template)
# Environment Variables: {kid_env}, {hmac_env}
        # Configuration Source: environment variables
resource "kubernetes_manifest" "{clean_name}_eab_secret_{self.clean_name(provider_name)}" {{
  manifest = {{
    apiVersion = "v1"
    kind       = "Secret"
    metadata = {{
      name      = "{secret_name}"
      namespace = "cert-manager-operator"
      labels = {{
        "app.kubernetes.io/name" = "cert-manager"
        "app.kubernetes.io/component" = "eab-credentials"
        "app.kubernetes.io/provider" = "{provider_name}"
        "yamlforge.io/automated" = "true"
      }}
      annotations = {{
        "yamlforge.io/credential-type" = "eab"
        "yamlforge.io/provider" = "{provider_name}"
        "yamlforge.io/env-source" = "{kid_env}, {hmac_env}"
        "yamlforge.io/generated-by" = "yamlforge"
        "yamlforge.io/config-source" = "environment-variables"
        "yamlforge.io/single-source-of-truth" = "true"
      }}
    }}
    type = "Opaque"
    data = {{
      # EAB Key ID - automatically sourced from environment variable {kid_env}
      "eab-key-id" = "${{base64encode(coalesce(var.{kid_env.lower()}, "{fallback_kid}"))}}"
      
      # EAB HMAC Key - automatically sourced from environment variable {hmac_env}  
      "eab-hmac-key" = "${{base64encode(coalesce(var.{hmac_env.lower()}, "{fallback_hmac}"))}}"
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_namespace]
}}

# Terraform variable for {provider_name.upper()} EAB Key ID
variable "{kid_env.lower()}" {{
  description = "{provider_name.upper()} EAB Key ID for ACME certificate issuance"
  type        = string
  default     = "{fallback_kid}"
  sensitive   = true
}}

# Terraform variable for {provider_name.upper()} EAB HMAC Key
variable "{hmac_env.lower()}" {{
  description = "{provider_name.upper()} EAB HMAC Key for ACME certificate issuance"
  type        = string
  default     = "{fallback_hmac}"
  sensitive   = true
}}

'''
        
        return terraform_config
    
    def _generate_cluster_issuers(self, clean_name: str, enabled_providers: List[str], acme_providers: Dict, default_issuer_email: str) -> str:
        """Generate ClusterIssuer resources for enabled ACME providers"""
        
        env_mappings = self.eab_config.get('environment_variables', {})
        
        terraform_config = '''
# =============================================================================
# CLUSTER ISSUERS (Auto-Generated from Template Configuration)
# =============================================================================
# ClusterIssuers are automatically configured based on enabled providers
# EAB providers automatically reference auto-generated secrets from template configuration
        # Single source of truth: environment variables

'''
        
        for provider_name in enabled_providers:
            if provider_name in acme_providers:
                provider_config = acme_providers[provider_name]
                
                # Skip if provider is explicitly disabled
                if not provider_config.get('enabled', True):
                    continue
                    
                provider_clean_name = self.clean_name(provider_name)
                acme_server = provider_config.get('server')
                description = provider_config.get('description', f'{provider_name} ACME provider')
                requires_eab = provider_config.get('requires_eab', False)
                fallback_priority = provider_config.get('fallback_priority', 5)
                
                # Generate ClusterIssuer with or without EAB
                if requires_eab and provider_name in env_mappings:
                    secret_name = provider_config.get('secret_name', f'{provider_name}-eab-credentials')
                    
                    terraform_config += f'''# {description} (with Auto-Generated EAB from Template) - Fallback Priority: {fallback_priority}
resource "kubernetes_manifest" "{clean_name}_issuer_{provider_clean_name}" {{
  manifest = {{
    apiVersion = "cert-manager.io/v1"
    kind       = "ClusterIssuer"
    metadata = {{
      name = "{provider_name}"
      annotations = {{
        "cert-manager.io/acme-server" = "{acme_server}"
        "cert-manager.io/description" = "{description}"
        "cert-manager.io/rate-limits" = "{provider_config.get('rate_limits', 'Check provider documentation')}"
        "cert-manager.io/requires-eab" = "true"
        "cert-manager.io/fallback-priority" = "{fallback_priority}"
        "cert-manager.io/fallback-enabled" = "true"
        "yamlforge.io/eab-automated" = "true"
        "yamlforge.io/secret-name" = "{secret_name}"
        "yamlforge.io/config-source" = "environment-variables"
        "yamlforge.io/single-source-of-truth" = "true"
      }}
    }}
    spec = {{
      acme = {{
        server = "{acme_server}"
        email = "{default_issuer_email}"
        externalAccountBinding = {{
          keyID = "${{data.kubernetes_secret.{provider_clean_name}_eab.data["eab-key-id"]}}"
          keySecretRef = {{
            name = "{secret_name}"
            key = "eab-hmac-key"
          }}
          keyAlgorithm = "HS256"
        }}
        privateKeySecretRef = {{
          name = "{provider_name}-account-key"
        }}
        solvers = [
          {{
            http01 = {{
              ingress = {{
                class = "openshift-default"
              }}
            }}
          }}
        ]
      }}
    }}
  }}
  
  depends_on = [
    kubernetes_manifest.{clean_name}_subscription,
    kubernetes_manifest.{clean_name}_eab_secret_{provider_clean_name}
  ]
}}

# Data source to read EAB secret for {provider_name}
data "kubernetes_secret" "{provider_clean_name}_eab" {{
  metadata {{
    name      = "{secret_name}"
    namespace = "cert-manager-operator"
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_eab_secret_{provider_clean_name}]
}}

'''
                else:
                    # Standard ClusterIssuer (no EAB)
                    terraform_config += f'''# {description} - Fallback Priority: {fallback_priority}
resource "kubernetes_manifest" "{clean_name}_issuer_{provider_clean_name}" {{
  manifest = {{
    apiVersion = "cert-manager.io/v1"
    kind       = "ClusterIssuer"
    metadata = {{
      name = "{provider_name}"
      annotations = {{
        "cert-manager.io/acme-server" = "{acme_server}"
        "cert-manager.io/description" = "{description}"
        "cert-manager.io/rate-limits" = "{provider_config.get('rate_limits', 'Check provider documentation')}"
        "cert-manager.io/requires-eab" = "false"
        "cert-manager.io/fallback-priority" = "{fallback_priority}"
        "cert-manager.io/fallback-enabled" = "true"
        "yamlforge.io/eab-automated" = "false"
      }}
    }}
    spec = {{
      acme = {{
        server = "{acme_server}"
        email = "{default_issuer_email}"
        privateKeySecretRef = {{
          name = "{provider_name}-account-key"
        }}
        solvers = [
          {{
            http01 = {{
              ingress = {{
                class = "openshift-default"
              }}
            }}
          }}
        ]
      }}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_subscription]
}}

'''
        
        return terraform_config
    
    def _generate_fallback_config(self, clean_name: str, fallback_chain: Dict, fallback_triggers: Dict) -> str:
        """Generate fallback configuration for automatic provider switching"""
        
        chain_name = fallback_chain.get('name', 'Default Fallback')
        chain_description = fallback_chain.get('description', 'Automatic provider fallback')
        steps = fallback_chain.get('steps', [])
        
        terraform_config = f'''
# =============================================================================
# FALLBACK CONFIGURATION: {chain_name}
# =============================================================================
# {chain_description}
# Automatic switching between providers on failures

# Fallback Controller ConfigMap
resource "kubernetes_manifest" "{clean_name}_fallback_config" {{
  manifest = {{
    apiVersion = "v1"
    kind       = "ConfigMap"
    metadata = {{
      name      = "cert-manager-fallback-config"
      namespace = "cert-manager-operator"
      labels = {{
        "app.kubernetes.io/name" = "cert-manager"
        "app.kubernetes.io/component" = "fallback-controller"
        "yamlforge.io/automated" = "true"
      }}
      annotations = {{
        "yamlforge.io/fallback-chain" = "{chain_name}"
        "yamlforge.io/generated-by" = "yamlforge"
      }}
    }}
    data = {{
      "fallback-config.yaml" = yamlencode({{
        fallback_chain = {{
          name = "{chain_name}"
          description = "{chain_description}"
          steps = {steps}
        }}
        fallback_triggers = {dict(fallback_triggers)}
      }})
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_namespace]
}}

'''
        
        return terraform_config
    
    def _generate_example_certificates(self, clean_name: str, example_certificates: List[Dict]) -> str:
        """Generate example certificate resources"""
        
        terraform_config = '''
# =============================================================================
# EXAMPLE CERTIFICATES  
# =============================================================================
# Auto-generated certificate examples for testing and validation

'''
        
        for cert in example_certificates:
            cert_name = cert.get('name')
            cert_clean_name = self.clean_name(cert_name)
            dns_names = cert.get('dns_names', [])
            issuer_ref = cert.get('issuer_ref', 'letsencrypt-staging')
            
            terraform_config += f'''
# Example Certificate: {cert_name}
resource "kubernetes_manifest" "{clean_name}_cert_{cert_clean_name}" {{
  manifest = {{
    apiVersion = "cert-manager.io/v1"
    kind       = "Certificate"
    metadata = {{
      name      = "{cert_name}"
      namespace = "cert-manager-operator"
      annotations = {{
        "yamlforge.io/certificate-type" = "example"
        "yamlforge.io/issuer" = "{issuer_ref}"
        "yamlforge.io/fallback-enabled" = "true"
      }}
    }}
    spec = {{
      secretName = "{cert_name}-tls"
      issuerRef = {{
        name = "{issuer_ref}"
        kind = "ClusterIssuer"
      }}
      dnsNames = {dns_names}
    }}
  }}
  
  depends_on = [kubernetes_manifest.{clean_name}_issuer_{self.clean_name(issuer_ref)}]
}}

'''
        
        return terraform_config 
"""
YamlForge - Multi-Cloud Infrastructure as Code and PaaS Management Suite

A comprehensive platform for managing multi-cloud infrastructure
and Platform-as-a-Service deployments through unified YAML definitions.

Supports all major cloud providers: AWS, Azure, GCP, IBM Cloud, Oracle Cloud,
Alibaba Cloud, and VMware with advanced OpenShift/Kubernetes PaaS management.

Currently Tested And Working:
* AWS
* GCP

Main Components:
- Core: Shared functionality and base classes  
- Providers: Cloud-specific implementations for all major cloud platforms
- OpenShift: Complete PaaS management with operator and application lifecycle
"""

from .core.credentials import CredentialsManager
from .core.converter import YamlForgeConverter
from .providers.aws import AWSProvider
from .providers.azure import AzureProvider
from .providers.gcp import GCPProvider
from .providers.ibm_classic import IBMClassicProvider
from .providers.ibm_vpc import IBMVPCProvider
from .providers.oci import OCIProvider
from .providers.vmware import VMwareProvider
from .providers.alibaba import AlibabaProvider

__version__ = "1.0.0b4"
__author__ = "Patrick T. Rutledge III"
__copyright__ = "Copyright 2025 Patrick T. Rutledge III"

__all__ = [
    'CredentialsManager',
    'YamlForgeConverter',
    'AWSProvider',
    'AzureProvider',
    'GCPProvider',
    'IBMClassicProvider',
    'IBMVPCProvider',
    'OCIProvider',
    'VMwareProvider',
    'AlibabaProvider'
]

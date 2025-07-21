"""
YamlForge - Enterprise Multi-Cloud Infrastructure Converter

A powerful enterprise-grade tool for converting YAML infrastructure definitions
to native cloud provider Terraform configurations, supporting AWS, Azure, GCP,
and IBM Cloud with advanced enterprise features.

Main Components:
- Core: Shared functionality and base classes
- Providers: Cloud-specific implementations for AWS, Azure, GCP, and IBM
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

__version__ = "0.99.0a1"
__author__ = "YamlForge Team"

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
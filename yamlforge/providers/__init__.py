"""
Provider modules for different cloud platforms.
"""

# Core providers
from .aws import AWSProvider, AWSImageResolver
from .azure import AzureProvider
from .gcp import GCPProvider, GCPImageResolver
from .ibm_classic import IBMClassicProvider
from .ibm_vpc import IBMVPCProvider

# New cloud providers
from .oci import OCIProvider, OCIImageResolver
from .vmware import VMwareProvider
from .alibaba import AlibabaProvider, AlibabaImageResolver

# OpenShift providers
from .openshift import (
    OpenShiftProvider,
    BaseOpenShiftProvider,
    ROSAProvider,
    AROProvider,
    SelfManagedOpenShiftProvider,
    OpenShiftDedicatedProvider,
    HyperShiftProvider,
    ApplicationProvider
)

__all__ = [
    'AWSProvider', 'AWSImageResolver',
    'AzureProvider',
    'GCPProvider', 'GCPImageResolver', 
    'IBMClassicProvider',
    'IBMVPCProvider',
    'OCIProvider', 'OCIImageResolver',
    'VMwareProvider',
    'AlibabaProvider', 'AlibabaImageResolver',
    'OpenShiftProvider',
    'BaseOpenShiftProvider',
    'ROSAProvider',
    'AROProvider',
    'SelfManagedOpenShiftProvider',
    'OpenShiftDedicatedProvider',
    'HyperShiftProvider',
    'ApplicationProvider'
]
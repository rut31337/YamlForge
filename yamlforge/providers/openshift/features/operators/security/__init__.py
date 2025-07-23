"""
OpenShift Security Operators Package
Contains security-focused operators (cert-manager, etc.)
"""

from .cert_manager import CertManagerOperator

__all__ = [
    'CertManagerOperator'
] 
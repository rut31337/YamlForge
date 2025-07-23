"""
OpenShift Backup Operators Package
Contains backup and data protection operators (OADP, etc.)
"""

from .oadp import OADPOperator

__all__ = [
    'OADPOperator'
] 
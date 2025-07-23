"""
OpenShift Networking Operators Package
Contains networking-focused operators (Submariner, MetalLB, etc.)
"""

from .submariner import SubmarinerOperator
from .metallb import MetalLBOperator

__all__ = [
    'SubmarinerOperator',
    'MetalLBOperator'
] 
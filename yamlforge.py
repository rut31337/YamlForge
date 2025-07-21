#!/usr/bin/env python3
"""
YamlForge - Enterprise Multi-Cloud Infrastructure Converter
Main command-line interface for the yamlforge tool.
"""

import sys
import os

# Add the yamlforge package to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from yamlforge.main import main

if __name__ == "__main__":
    main()

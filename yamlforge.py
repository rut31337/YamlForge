#!/usr/bin/env python3
"""
YamlForge - Multi-Cloud Infrastructure as Code and OpenShift Management Suite

Copyright 2025 Patrick T. Rutledge III

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import sys
import os

# Add the yamlforge package to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the main function from the proper module
from yamlforge.main import main

if __name__ == "__main__":
    main()

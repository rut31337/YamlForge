#!/usr/bin/env python3

import sys
import os

# Add the yamlforge package to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the main function from the proper module
from yamlforge.main import main

if __name__ == "__main__":
    main()

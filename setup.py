#!/usr/bin/env python3
"""
Setup script for YamlForge - Enterprise Multi-Cloud Infrastructure Converter

YamlForge converts unified YAML infrastructure definitions into 
provider-specific Terraform configurations with intelligent optimization.
"""

from setuptools import setup, find_packages
import os

# Read the requirements file
def read_requirements():
    requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    with open(requirements_path, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

# Read the README file for long description
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "YamlForge - Enterprise Multi-Cloud Infrastructure Converter"

setup(
    name="yamlforge",
    version="0.99.0a1",
    description="Multi-Cloud Infrastructure as Code and PaaS Management Suite (ALPHA - Work in Progress)",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="Patrick T. Rutledge III",
    author_email="",
    url="https://github.com/rut31337/YamlForge",
    license="Apache-2.0",
    
    # Package configuration
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.8",
    
    # Dependencies
    install_requires=read_requirements(),
    
    # Optional dependencies
    extras_require={
        'dev': [
            'pytest>=6.0',
            'black>=21.0',
            'flake8>=3.8',
            'mypy>=0.800',
        ],
        'docs': [
            'sphinx>=4.0',
            'sphinx-rtd-theme>=0.5',
        ],
    },
    
    # Entry points for command-line tools
    entry_points={
        'console_scripts': [
            'yamlforge=yamlforge.main:main',
        ],
    },
    
    # Package data
    package_data={
        "yamlforge": [
            "defaults/*.yaml",
            "defaults/**/*.yaml", 
            "mappings/*.yaml",
            "mappings/**/*.yaml",
        ]
    },
    
    # Classifiers for PyPI
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators", 
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9", 
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Code Generators",
        "Topic :: System :: Systems Administration",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
    ],
    
    # Keywords for discovery
    keywords="terraform multi-cloud infrastructure-as-code paas management yaml aws azure gcp openshift kubernetes",
) 

#!/usr/bin/env python3
"""
Setup script for YamlForge - Enterprise Multi-Cloud Infrastructure Converter

YamlForge converts unified YAML infrastructure definitions into 
provider-specific Terraform configurations with intelligent optimization.
"""

from setuptools import setup, find_packages
import os

# Define requirements directly (avoiding external file dependency in package builds)
def get_requirements():
    return [
        "PyYAML>=6.0.2",
        "boto3>=1.39.0",
        "google-cloud-compute>=1.32.0",
        "google-cloud-dns>=0.35.0",
        "oci>=2.155.0",
        "alibabacloud-ecs20140526>=7.0.0",
        "alibabacloud-tea-openapi>=0.3.0",
        "ibm-cloud-sdk-core>=3.16.7",
        "ibm-vpc>=0.10.0",
        "requests>=2.32.0",
    ]

# Read the README file for long description
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "YamlForge - Enterprise Multi-Cloud Infrastructure Converter"

setup(
    name="yamlforge-infra",
    version="1.0.0b2",
    description="Multi-Cloud Infrastructure as Code and PaaS Management Suite (BETA - Feature Complete)",
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
    install_requires=get_requirements(),
    
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

# AgnosticC - Cloud-Agnostic Infrastructure Configuration

A YAML-to-Multy wrapper that provides a simple, declarative interface for multi-cloud infrastructure deployment using Terraform.

## Overview

AgnosticC allows you to define infrastructure in a simple YAML format (inspired by RedHat's AgnosticD) and generates Terraform plans for multiple cloud providers using Multy.

## Key Features

- **Pure YAML Input**: No Terraform knowledge required
- **Multi-Cloud Support**: Deploy to AWS, Azure, GCP, and more
- **Intelligent Instance Sizing**: Handles differences between cloud providers (flavors vs custom CPU/memory)
- **Security Group Abstraction**: Unified firewall rule definitions
- **Best-Fit Algorithms**: Automatically selects appropriate instance types per cloud

## Project Status

🚧 **In Development** - This project is in early planning/development phase.

## Architecture

1. **YAML Parser**: Reads and validates infrastructure definitions
2. **Cloud Abstraction Layer**: Handles provider-specific differences
3. **Multy Integration**: Generates appropriate Multy Terraform configurations
4. **Terraform Generation**: Outputs ready-to-use Terraform plans

## Contributing

This project is just getting started! Feel free to contribute ideas, code, or documentation.

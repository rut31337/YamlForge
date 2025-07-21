# Testing Examples

This directory contains comprehensive examples for testing and validating YamlForge functionality across different scenarios.

### Files Overview

#### **Core Testing Examples**
- **`tags_example.yaml`** - Comprehensive tagging system demonstration
- **`provider_selection_example.yaml`** - Selective provider configuration (AWS-only)
- **`multi_provider_example.yaml`** - Multi-cloud provider detection (AWS+GCP+IBM, Azure excluded)
- **`cloud_workspace_example.yaml`** - Cloud-agnostic workspace organization

#### **Usage Instructions**

Each example demonstrates different aspects of YamlForge functionality:

1. **Tagging System**
   ```bash
   python yamlforge.py examples/testing/tags_example.yaml -d test_output
   ```

2. **Provider Selection**
   ```bash  
   python yamlforge.py examples/testing/provider_selection_example.yaml -d test_output
   ```

3. **Multi-Provider Detection**
   ```bash
   python yamlforge.py examples/testing/multi_provider_example.yaml -d test_output
   ```

4. **Cloud Workspace Organization**
   ```bash
   python yamlforge.py examples/testing/cloud_workspace_example.yaml -d test_output
   ```

#### **Key Features Demonstrated**

- **Smart Provider Detection**: Only configures Terraform providers that are actually used
- **Unified Tagging**: Consistent tag application across all cloud providers
- **Cloud-Agnostic Workspaces**: Unified resource organization mapping to each cloud's native concepts
- **Multi-Cloud Support**: Seamless resource provisioning across AWS, Azure, GCP, and IBM Cloud 
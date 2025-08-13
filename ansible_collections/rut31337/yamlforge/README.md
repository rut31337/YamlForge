# YamlForge Infrastructure Ansible Collection

This collection provides Ansible modules and roles for managing multi-cloud infrastructure using YamlForge - a universal YAML to Terraform converter with intelligent optimization.

## Features

- **Multi-Cloud Support**: AWS, Azure, GCP, IBM, OCI, Alibaba, VMware, OpenShift
- **Cost Optimization**: Intelligent provider selection for cheapest deployment
- **Ansible Integration**: Native Ansible modules and roles
- **Terraform Generation**: Produces provider-specific Terraform code
- **Auto-Deployment**: Optional automatic infrastructure deployment

## Installation

### From Ansible Galaxy

```bash
ansible-galaxy collection install rut31337.yamlforge
```

### From Source

```bash
git clone https://github.com/rut31337/YamlForge.git
cd YamlForge
ansible-galaxy collection install ansible_collections/rut31337/yamlforge/
```

## Requirements

- Python >= 3.8
- Ansible >= 2.10
- Terraform >= 1.12.0 (for OpenShift/ROSA support)
- yamlforge-infra >= 1.0.0b4 (`pip install yamlforge-infra`)

## Quick Start

### Using the Module

```yaml
- name: Generate multi-cloud infrastructure
  rut31337.yamlforge.infrastructure:
    config_file: /path/to/config.yaml
    output_dir: /tmp/terraform-output
    verbose: true
```

### Using the Role

```yaml
- name: Deploy infrastructure with YamlForge
  hosts: localhost
  roles:
    - role: rut31337.yamlforge.yamlforge
      vars:
        yamlforge_config_file: /path/to/config.yaml
        yamlforge_output_dir: /tmp/terraform-output
        yamlforge_auto_deploy: true
```

## Module Reference

### rut31337.yamlforge.infrastructure

Main module for executing YamlForge operations.

#### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `config_file` | path | yes | - | Path to YamlForge YAML configuration |
| `output_dir` | path | yes | - | Directory for generated Terraform files |
| `auto_deploy` | bool | no | false | Automatically deploy infrastructure |
| `no_credentials` | bool | no | false | Generate without cloud credentials |
| `verbose` | bool | no | false | Enable verbose output |
| `exclude_providers` | list | no | [] | Providers to exclude from cost analysis |
| `guid` | str | no | - | 5-character GUID for resource identification |

#### Examples

```yaml
# Analyze configuration only
- rut31337.yamlforge.infrastructure:
    config_file: /path/to/config.yaml
    output_dir: /tmp/output
    auto_deploy: false

# Generate and deploy with cost optimization
- rut31337.yamlforge.infrastructure:
    config_file: /path/to/config.yaml
    output_dir: /tmp/output
    auto_deploy: true
    exclude_providers: [aws, azure]
    guid: "abc12"
```

## Role Reference

### rut31337.yamlforge.yamlforge

Complete role for YamlForge installation and execution.

#### Role Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `yamlforge_config_file` | str | "" | YamlForge configuration file path |
| `yamlforge_output_dir` | str | "/tmp/yamlforge-output" | Output directory |
| `yamlforge_auto_deploy` | bool | false | Auto-deploy infrastructure |
| `yamlforge_verbose` | bool | false | Verbose output |
| `yamlforge_install_package` | bool | true | Install yamlforge-infra package |
| `terraform_install` | bool | true | Install Terraform |
| `terraform_version` | str | "1.12.0" | Terraform version |
| `install_cloud_clis` | bool | false | Install cloud CLI tools |

#### Example Playbook

```yaml
---
- name: Setup and run YamlForge
  hosts: localhost
  connection: local
  vars:
    yamlforge_config_file: "{{ playbook_dir }}/infrastructure.yaml"
    yamlforge_output_dir: "{{ playbook_dir }}/terraform-output"
    yamlforge_auto_deploy: true
    yamlforge_verbose: true
    
    # Cloud credentials (use vault for production)
    yamlforge_env_vars:
      AWS_ACCESS_KEY_ID: "{{ aws_access_key }}"
      AWS_SECRET_ACCESS_KEY: "{{ aws_secret_key }}"
      AZURE_SUBSCRIPTION_ID: "{{ azure_subscription_id }}"
      AZURE_CLIENT_ID: "{{ azure_client_id }}"
      AZURE_CLIENT_SECRET: "{{ azure_client_secret }}"
      AZURE_TENANT_ID: "{{ azure_tenant_id }}"
    
    # Optional: Install cloud CLI tools
    install_cloud_clis: true
    cloud_cli_tools:
      aws_cli: true
      azure_cli: true
      gcloud_cli: true

  roles:
    - rut31337.yamlforge.yamlforge
```

## Configuration

### Cloud Credentials

Set cloud provider credentials via environment variables:

```yaml
yamlforge_env_vars:
  # AWS
  AWS_ACCESS_KEY_ID: "{{ vault_aws_access_key }}"
  AWS_SECRET_ACCESS_KEY: "{{ vault_aws_secret_key }}"
  
  # Azure
  AZURE_SUBSCRIPTION_ID: "{{ vault_azure_subscription_id }}"
  AZURE_CLIENT_ID: "{{ vault_azure_client_id }}"
  AZURE_CLIENT_SECRET: "{{ vault_azure_client_secret }}"
  AZURE_TENANT_ID: "{{ vault_azure_tenant_id }}"
  
  # GCP
  GOOGLE_APPLICATION_CREDENTIALS: "/path/to/service-account.json"
  
  # IBM Cloud
  IBMCLOUD_API_KEY: "{{ vault_ibm_api_key }}"
```

### YamlForge Configuration

Create a YamlForge YAML configuration file:

```yaml
# infrastructure.yaml
guid: "demo1"
core:
  organization: "My Company"
  project_name: "demo-infrastructure"

instances:
  web-servers:
    provider: aws
    count: 2
    flavor: "t3.medium"
    image: "RHEL9-latest"
    location: "us-east"

openshift:
  clusters:
    development:
      provider: rosa
      version: "4.14"
      node_count: 3
      instance_type: "m5.large"
      location: "us-east"
```

## Advanced Usage

### Multi-Cloud with Cost Optimization

```yaml
- name: Deploy to cheapest provider
  rut31337.yamlforge.infrastructure:
    config_file: /path/to/config.yaml
    output_dir: /tmp/output
    auto_deploy: true
    exclude_providers: [alibaba, vmware]  # Exclude specific providers
```

### Testing Mode

```yaml
- name: Test configuration generation
  rut31337.yamlforge.infrastructure:
    config_file: /path/to/config.yaml
    output_dir: /tmp/output
    no_credentials: true  # Skip credential validation
    auto_deploy: false    # Don't generate files
```

## Support

- **Documentation**: [YamlForge Docs](https://github.com/rut31337/YamlForge/tree/master/docs)
- **Issues**: [GitHub Issues](https://github.com/rut31337/YamlForge/issues)
- **Repository**: [GitHub](https://github.com/rut31337/YamlForge)

## License

Apache License 2.0 - see [LICENSE](https://github.com/rut31337/YamlForge/blob/master/LICENSE)
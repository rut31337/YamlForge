# YamlForge Ansible Playbook Examples

This document provides comprehensive examples for using the YamlForge Ansible collection.

## Basic Examples

### Simple Infrastructure Generation

```yaml
---
- name: Generate Terraform for AWS infrastructure
  hosts: localhost
  connection: local
  tasks:
    - name: Generate Terraform files
      rut31337.yamlforge.infrastructure:
        config_file: "{{ playbook_dir }}/aws-config.yaml"
        output_dir: "{{ playbook_dir }}/terraform-aws"
        verbose: true
```

### Analysis Mode (No Deployment)

```yaml
---
- name: Analyze YamlForge configuration
  hosts: localhost
  connection: local
  tasks:
    - name: Generate Terraform without deployment
      rut31337.yamlforge.infrastructure:
        config_file: "{{ playbook_dir }}/multi-cloud-config.yaml"
        output_dir: "/tmp/analysis"
        auto_deploy: false
        no_credentials: true
        verbose: true
      register: analysis_result
    
    - name: Display detected providers
      debug:
        msg: "Detected providers: {{ analysis_result.providers_detected }}"
```

## Role-Based Examples

### Complete Infrastructure Setup

```yaml
---
- name: Setup complete infrastructure environment
  hosts: localhost
  connection: local
  vars:
    # YamlForge configuration
    yamlforge_config_file: "{{ playbook_dir }}/enterprise-config.yaml"
    yamlforge_output_dir: "{{ playbook_dir }}/terraform-output"
    yamlforge_auto_deploy: true
    yamlforge_verbose: true
    yamlforge_guid: "ent01"
    
    # Installation options
    terraform_install: true
    terraform_version: "1.12.0"
    install_cloud_clis: true
    cloud_cli_tools:
      aws_cli: true
      azure_cli: true
      gcloud_cli: true
      ibmcloud_cli: true
    
    # Credentials (use Ansible Vault in production)
    yamlforge_env_vars:
      AWS_ACCESS_KEY_ID: "{{ vault_aws_access_key }}"
      AWS_SECRET_ACCESS_KEY: "{{ vault_aws_secret_key }}"
      AZURE_SUBSCRIPTION_ID: "{{ vault_azure_subscription_id }}"
      AZURE_CLIENT_ID: "{{ vault_azure_client_id }}"
      AZURE_CLIENT_SECRET: "{{ vault_azure_client_secret }}"
      AZURE_TENANT_ID: "{{ vault_azure_tenant_id }}"
      GOOGLE_APPLICATION_CREDENTIALS: "{{ vault_gcp_service_account_path }}"
      IBMCLOUD_API_KEY: "{{ vault_ibm_api_key }}"

  roles:
    - rut31337.yamlforge.yamlforge
```

### Development Environment

```yaml
---
- name: Setup development environment
  hosts: localhost
  connection: local
  vars:
    yamlforge_config_file: "{{ playbook_dir }}/dev-environment.yaml"
    yamlforge_output_dir: "{{ playbook_dir }}/dev-terraform"
    yamlforge_auto_deploy: false
    yamlforge_verbose: true
    
    # Use cheapest provider for development
    yamlforge_exclude_providers: []  # Allow all providers for cost optimization
    
    terraform_install: true
    install_prerequisites: true

  roles:
    - rut31337.yamlforge.yamlforge
  
  post_tasks:
    - name: Display generated files
      find:
        paths: "{{ yamlforge_output_dir }}"
        patterns: "*.tf"
        recurse: true
      register: terraform_files
    
    - name: Show Terraform files
      debug:
        msg: "Generated: {{ item.path }}"
      loop: "{{ terraform_files.files }}"
```

## Advanced Examples

### Multi-Environment Deployment

```yaml
---
- name: Deploy multiple environments
  hosts: localhost
  connection: local
  vars:
    environments:
      - name: development
        config: dev-config.yaml
        auto_deploy: true
        exclude_providers: [vmware, alibaba]
      - name: staging
        config: staging-config.yaml
        auto_deploy: false
        exclude_providers: [vmware]
      - name: production
        config: prod-config.yaml
        auto_deploy: false
        exclude_providers: []
    
    base_output_dir: "{{ playbook_dir }}/environments"

  tasks:
    - name: Create environment directories
      file:
        path: "{{ base_output_dir }}/{{ item.name }}"
        state: directory
        mode: '0755'
      loop: "{{ environments }}"
    
    - name: Deploy each environment
      rut31337.yamlforge.infrastructure:
        config_file: "{{ playbook_dir }}/{{ item.config }}"
        output_dir: "{{ base_output_dir }}/{{ item.name }}"
        auto_deploy: "{{ item.auto_deploy }}"
        exclude_providers: "{{ item.exclude_providers }}"
        guid: "{{ item.name[:5] }}"
        verbose: true
      loop: "{{ environments }}"
      register: deployment_results
    
    - name: Summary of deployments
      debug:
        msg: |
          Environment: {{ item.item.name }}
          Providers: {{ item.providers_detected }}
          Status: {{ 'Deployed' if item.item.auto_deploy else 'Generated' }}
      loop: "{{ deployment_results.results }}"
```

### OpenShift-Focused Deployment

```yaml
---
- name: Deploy OpenShift clusters across clouds
  hosts: localhost
  connection: local
  vars:
    yamlforge_config_file: "{{ playbook_dir }}/openshift-multi-cloud.yaml"
    yamlforge_output_dir: "{{ playbook_dir }}/openshift-terraform"
    yamlforge_auto_deploy: true
    yamlforge_verbose: true
    
    # OpenShift-specific settings
    terraform_version: "1.12.0"  # Required for ROSA
    install_cloud_clis: true
    cloud_cli_tools:
      aws_cli: true      # For ROSA
      azure_cli: true    # For ARO
      gcloud_cli: true   # For GCP OpenShift
    
    yamlforge_env_vars:
      # AWS for ROSA
      AWS_ACCESS_KEY_ID: "{{ vault_aws_access_key }}"
      AWS_SECRET_ACCESS_KEY: "{{ vault_aws_secret_key }}"
      # Azure for ARO
      AZURE_SUBSCRIPTION_ID: "{{ vault_azure_subscription_id }}"
      AZURE_CLIENT_ID: "{{ vault_azure_client_id }}"
      AZURE_CLIENT_SECRET: "{{ vault_azure_client_secret }}"
      AZURE_TENANT_ID: "{{ vault_azure_tenant_id }}"
      # Red Hat credentials
      REDHAT_USERNAME: "{{ vault_redhat_username }}"
      REDHAT_PASSWORD: "{{ vault_redhat_password }}"

  roles:
    - rut31337.yamlforge.yamlforge
  
  post_tasks:
    - name: Install OpenShift CLI
      get_url:
        url: "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/stable/openshift-client-linux.tar.gz"
        dest: "/tmp/oc-client.tar.gz"
      
    - name: Extract OpenShift CLI
      unarchive:
        src: "/tmp/oc-client.tar.gz"
        dest: "/usr/local/bin"
        remote_src: true
        mode: '0755'
      become: true
```

### Cost-Optimized Deployment

```yaml
---
- name: Deploy with cost optimization
  hosts: localhost
  connection: local
  vars:
    yamlforge_config_file: "{{ playbook_dir }}/cost-optimized-config.yaml"
    yamlforge_output_dir: "{{ playbook_dir }}/cheapest-terraform"
    yamlforge_auto_deploy: false  # Review costs first
    yamlforge_verbose: true
    
    # Exclude expensive providers from cost analysis
    yamlforge_exclude_providers:
      - vmware      # Usually more expensive
      - dedicated   # Dedicated OpenShift instances

  tasks:
    - name: Generate cost-optimized infrastructure
      rut31337.yamlforge.infrastructure:
        config_file: "{{ yamlforge_config_file }}"
        output_dir: "{{ yamlforge_output_dir }}"
        auto_deploy: "{{ yamlforge_auto_deploy }}"
        exclude_providers: "{{ yamlforge_exclude_providers }}"
        verbose: "{{ yamlforge_verbose }}"
      register: cost_result
    
    - name: Display cost analysis
      debug:
        msg: |
          Selected Provider: {{ cost_result.cost_analysis.selected_provider | default('N/A') }}
          Estimated Cost: {{ cost_result.cost_analysis.estimated_monthly_cost | default('N/A') }}
          Detected Providers: {{ cost_result.providers_detected }}
    
    - name: Prompt for deployment approval
      pause:
        prompt: "Review the cost analysis above. Deploy infrastructure? (yes/no)"
      register: deploy_approval
      when: not yamlforge_auto_deploy
    
    - name: Deploy if approved
      rut31337.yamlforge.infrastructure:
        config_file: "{{ yamlforge_config_file }}"
        output_dir: "{{ yamlforge_output_dir }}"
        auto_deploy: true
        exclude_providers: "{{ yamlforge_exclude_providers }}"
        verbose: "{{ yamlforge_verbose }}"
      when: 
        - not yamlforge_auto_deploy
        - deploy_approval.user_input | lower == 'yes'
```

### Testing and Validation

```yaml
---
- name: Test YamlForge configurations
  hosts: localhost
  connection: local
  vars:
    test_configs:
      - name: "AWS Simple"
        file: "test-aws-simple.yaml"
      - name: "Azure Multi-tier"
        file: "test-azure-multitier.yaml"
      - name: "GCP with OpenShift"
        file: "test-gcp-openshift.yaml"
      - name: "Multi-cloud"
        file: "test-multicloud.yaml"
    
    test_output_base: "{{ playbook_dir }}/test-outputs"

  tasks:
    - name: Create test output directory
      file:
        path: "{{ test_output_base }}"
        state: directory
        mode: '0755'
    
    - name: Validate each configuration
      rut31337.yamlforge.infrastructure:
        config_file: "{{ playbook_dir }}/test-configs/{{ item.file }}"
        output_dir: "{{ test_output_base }}/{{ item.name | lower | replace(' ', '-') }}"
        auto_deploy: false  # Generate only, don't deploy
        no_credentials: true  # Skip credential validation for testing
        verbose: true
      loop: "{{ test_configs }}"
      register: validation_results
      ignore_errors: true
    
    - name: Test results summary
      debug:
        msg: |
          Configuration: {{ item.item.name }}
          Status: {{ 'PASS' if item.failed == false else 'FAIL' }}
          Providers: {{ item.providers_detected | default([]) }}
          {% if item.failed %}
          Error: {{ item.msg | default('Unknown error') }}
          {% endif %}
      loop: "{{ validation_results.results }}"
```

## Inventory Integration

### Dynamic Infrastructure with Inventory

```yaml
---
- name: Deploy infrastructure and update inventory
  hosts: localhost
  connection: local
  vars:
    yamlforge_config_file: "{{ playbook_dir }}/dynamic-config.yaml"
    yamlforge_output_dir: "{{ playbook_dir }}/dynamic-terraform"
    yamlforge_auto_deploy: true
    inventory_file: "{{ playbook_dir }}/dynamic_inventory.yml"

  tasks:
    - name: Deploy infrastructure
      rut31337.yamlforge.infrastructure:
        config_file: "{{ yamlforge_config_file }}"
        output_dir: "{{ yamlforge_output_dir }}"
        auto_deploy: "{{ yamlforge_auto_deploy }}"
        verbose: true
      register: deploy_result
    
    - name: Extract Terraform outputs
      command: terraform output -json
      args:
        chdir: "{{ yamlforge_output_dir }}/{{ deploy_result.providers_detected[0] }}"
      register: terraform_outputs
      when: deploy_result.deployment_status == 'deployed'
    
    - name: Parse Terraform outputs
      set_fact:
        infrastructure_outputs: "{{ terraform_outputs.stdout | from_json }}"
      when: terraform_outputs is defined
    
    - name: Generate dynamic inventory
      template:
        src: dynamic_inventory.yml.j2
        dest: "{{ inventory_file }}"
      when: infrastructure_outputs is defined

# Follow-up playbook using the generated inventory
- name: Configure deployed infrastructure
  hosts: web_servers
  remote_user: ec2-user
  tasks:
    - name: Install web server
      yum:
        name: nginx
        state: present
      become: true
```

## Error Handling

### Robust Deployment with Rollback

```yaml
---
- name: Deploy with error handling and rollback
  hosts: localhost
  connection: local
  vars:
    yamlforge_config_file: "{{ playbook_dir }}/production-config.yaml"
    yamlforge_output_dir: "{{ playbook_dir }}/production-terraform"
    backup_dir: "{{ playbook_dir }}/backups/{{ ansible_date_time.epoch }}"

  tasks:
    - name: Create backup directory
      file:
        path: "{{ backup_dir }}"
        state: directory
        mode: '0755'
    
    - name: Backup existing Terraform state
      copy:
        src: "{{ yamlforge_output_dir }}"
        dest: "{{ backup_dir }}/terraform-backup"
        remote_src: true
      ignore_errors: true
    
    - name: Deploy infrastructure
      block:
        - name: Generate and deploy
          rut31337.yamlforge.infrastructure:
            config_file: "{{ yamlforge_config_file }}"
            output_dir: "{{ yamlforge_output_dir }}"
            auto_deploy: true
            verbose: true
          register: deploy_result
        
        - name: Verify deployment
          command: terraform show
          args:
            chdir: "{{ yamlforge_output_dir }}/{{ deploy_result.providers_detected[0] }}"
          register: tf_show
          
      rescue:
        - name: Deployment failed - attempting rollback
          debug:
            msg: "Deployment failed: {{ ansible_failed_result.msg }}"
        
        - name: Restore from backup
          copy:
            src: "{{ backup_dir }}/terraform-backup/"
            dest: "{{ yamlforge_output_dir }}"
            remote_src: true
          when: backup_dir is defined
        
        - name: Attempt Terraform destroy on failed deployment
          command: terraform destroy -auto-approve
          args:
            chdir: "{{ yamlforge_output_dir }}/{{ deploy_result.providers_detected[0] }}"
          ignore_errors: true
          when: deploy_result is defined
        
        - fail:
            msg: "Deployment failed and rollback attempted"
```

These examples demonstrate the flexibility and power of the YamlForge Ansible collection for managing multi-cloud infrastructure deployments.
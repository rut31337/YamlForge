# YamlForge Tools

This directory contains utility tools for YamlForge development and maintenance.

## Available Tools

### `run_vulture.sh` - Static Analysis Tool
Convenient script for running Vulture static analysis with proper ignore patterns.

```bash
# Run Vulture analysis
./tools/run_vulture.sh

# Run with higher confidence
vulture yamlforge/ --min-confidence 80
```

### `install_git_hooks.sh` - Git Integration
Installs Git hooks to automatically run Vulture before and after commits.

```bash
# Install Git hooks
./tools/install_git_hooks.sh

# After installation, Vulture runs automatically on:
#   • git commit (pre-commit hook)
#   • After commit (post-commit hook)
```

### ROSA Version Management
**Note:** ROSA version management has been integrated into the YamlForge codebase as `yamlforge.core.rosa_versions.ROSAVersionManager`. The external tool has been removed to improve maintainability and reduce dependencies.

## Vulture Static Analysis

### Overview
Vulture is a static analysis tool that finds dead code in Python projects. We use it to maintain code quality and identify unused methods, variables, and imports.

### Setup

1. **Install Vulture:**
   ```bash
   pip install vulture
   ```

2. **Run Analysis:**
   ```bash
   ./tools/run_vulture.sh
   ```

### Configuration

The Vulture setup includes:

- **`.vulture`** - Configuration file with ignore patterns for false positives
- **`tools/run_vulture.sh`** - Convenient script for running Vulture with proper ignore patterns

### Ignore Patterns

The following types of code are ignored as they are dynamically called or are stubs for future features:

#### Core Provider Methods
- `generate_aws_vm`, `generate_aws_security_group`, `generate_aws_networking`
- `generate_azure_vm`, `generate_azure_security_group`, `generate_azure_networking`
- `generate_gcp_vm`, `generate_gcp_firewall_rules`
- `generate_ibm_vpc_vm`, `generate_ibm_security_group`, `generate_ibm_classic_vm`
- `generate_oci_vm`, `generate_oci_security_group`
- `generate_alibaba_vm`, `generate_alibaba_security_group`, `generate_alibaba_networking`
- `generate_vmware_vm`

#### Credential Methods
- `get_aws_credentials`, `get_azure_credentials`, `get_gcp_credentials`
- `get_ibm_vpc_credentials`, `get_ibm_classic_credentials`
- `get_oci_credentials`, `get_alibaba_credentials`, `get_vmware_credentials`
- `get_cert_manager_credentials`

#### Property Decorators
- `oci_config`, `alibaba_config`

#### OpenShift Methods
- `validate_openshift_version`
- `create_rosa_account_roles_via_cli`, `generate_rosa_operator_roles`
- `generate_rosa_oidc_config`, `generate_rosa_sts_data_sources`

#### Future Feature Stubs
- `generate_lifecycle_management`, `generate_blue_green_automation`
- `generate_upgrade_automation`, `generate_ingress_resources`
- `generate_external_dns`

#### Operator Stubs
- `generate_gitops_operator`, `generate_pipelines_operator`
- `generate_serverless_operator`, `generate_logging_operator`
- `generate_monitoring_operator`, `generate_storage_operator`
- `generate_service_mesh_operator`, `generate_metallb_operator`
- `generate_submariner_operator`, `generate_cert_manager_operator`
- `generate_oadp_operator`

### Usage Examples

```bash
# Run with default settings (60% confidence)
./tools/run_vulture.sh

# Run with higher confidence (80%)
vulture yamlforge/ --min-confidence 80

# Run with custom ignore patterns
vulture yamlforge/ --ignore-names 'method1,method2'

# Run on specific files
vulture yamlforge/providers/aws.py yamlforge/providers/azure.py
```

### Adding New Ignore Patterns

When Vulture finds false positives, add them to the ignore list in `tools/run_vulture.sh`:

```bash
# Edit the IGNORE_LIST variable in tools/run_vulture.sh
IGNORE_LIST="existing,patterns,new_method_name"
```

### Best Practices

1. **Review Findings Manually** - Don't automatically remove code flagged by Vulture
2. **Verify Dynamic Calls** - Check if methods are called via reflection or dynamic dispatch
3. **Keep Future Stubs** - Don't remove methods that are stubs for planned features
4. **Test After Removal** - Always test the codebase after removing unused code
5. **Update Ignore Patterns** - Add new false positives to the ignore list

### Troubleshooting

#### Common Issues

1. **False Positives** - Methods called dynamically via `getattr()` or similar
2. **Plugin Methods** - Methods that are hooks or callbacks
3. **Configuration Methods** - Methods used in configuration files
4. **Test Fixtures** - Methods used only in tests

#### Solutions

1. Add the method name to the ignore list
2. Use `# noqa: vulture` comments for specific lines
3. Refactor to make the call more explicit
4. Document why the method is kept despite being "unused"

### Git Integration

The Vulture setup is integrated into the Git workflow:

#### **Pre-commit Hook**
- **Automatic** - Runs Vulture on staged Python files before each commit
- **Blocking** - Prevents commits if unused code is found
- **Configurable** - Uses the same ignore patterns as manual runs
- **Bypass** - Use `git commit --no-verify` to skip (not recommended)

#### **Post-commit Hook**
- **Monitoring** - Runs Vulture on entire codebase after each commit
- **Non-blocking** - Runs in background, doesn't affect commit
- **Informational** - Provides feedback on overall code quality

#### **Installation**
```bash
# Install Git hooks
./tools/install_git_hooks.sh

# Verify installation
ls -la .git/hooks/pre-commit .git/hooks/post-commit
```

### CI/CD Integration

The Vulture setup can be integrated into automated testing:

- **GitHub Actions** - Add Vulture to CI pipeline
- **GitLab CI** - Include in build stages
- **Jenkins** - Add as quality gate
- **Code Reviews** - Use Vulture findings to guide reviews

### Maintenance

Regular maintenance tasks:

1. **Update Ignore Patterns** - Add new false positives as they're discovered
2. **Review Findings** - Periodically review Vulture output for real unused code
3. **Clean Up** - Remove truly unused code to maintain code quality
4. **Document Changes** - Update this README when patterns change 
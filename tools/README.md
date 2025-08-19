# YamlForge Tools

This directory contains utility tools for YamlForge development and maintenance.

## Available Tools

### `validate_schema.py` - Schema Validation Tool
Validates YAML files and documentation examples against the YamlForge schema.

```bash
# Validate all YAML files in examples/
python tools/validate_schema.py

# Validate specific files
python tools/validate_schema.py examples/simple.yaml examples/3tier.yaml

# Check documentation YAML examples
python tools/validate_schema.py --check-docs

# Auto-fix common schema violations
python tools/validate_schema.py --fix

# Verbose output for debugging
python tools/validate_schema.py --verbose
```

**Features:**
- ✅ Validates all YAML files against YamlForge schema
- ✅ Checks YAML code blocks in documentation files
- ✅ Auto-fixes common violations (missing cloud_workspace, GUID format, etc.)
- ✅ Educational example support (skip validation with `# yamlforge-validation: skip-schema-errors`)
- ✅ Line-number reporting for precise error location
- ✅ Integrated with Git commit hooks

**Educational Examples:**
For documentation with intentional errors:
```yaml
# yamlforge-validation: skip-schema-errors
# This example shows what NOT to do
guid: "bad01"
yamlforge:
  instances:
    - name: "example"
      # Missing required fields intentionally
```

### `run_vulture.sh` - Static Analysis Tool
Optimized script for running Vulture static analysis with smart configuration and multiple output modes.

```bash
# Run Vulture analysis (default 70% confidence)
./tools/run_vulture.sh

# Run with higher confidence
./tools/run_vulture.sh --confidence 80

# Sort results by code size
./tools/run_vulture.sh --sort-by-size

# Generate whitelist format
./tools/run_vulture.sh --make-whitelist

# Verbose output
./tools/run_vulture.sh --verbose
```

### `install_git_hooks.sh` - Git Integration
Installs Git hooks for automated quality checks including schema validation and Vulture analysis.

```bash
# Install Git hooks
./tools/install_git_hooks.sh

# After installation, quality checks run automatically:
#   • Pre-commit: Schema validation + Vulture + functionality tests
#   • Post-commit: Background schema validation + Vulture analysis
```

### `extract_resourceclaim_vars.py` - ResourceClaim Variable Extractor
Extracts cloud provider credentials from Babylon ResourceClaim objects and outputs them as bash export statements.

```bash
# Basic usage (clean output for sourcing)
./tools/extract_resourceclaim_vars.py \
  --resource-claim azure-resource-claim-name \
  --namespace my-namespace \
  --kubeconfig ~/.kube/config

# Verbose output (with source comments)
./tools/extract_resourceclaim_vars.py \
  --resource-claim gcp-resource-claim-name \
  --namespace my-namespace \
  --kubeconfig ~/.kube/config \
  --verbose

# Source directly into environment
source <(./tools/extract_resourceclaim_vars.py -r azure-claim -n my-namespace -k ~/.kube/config)
```

**Features:**
- Multi-cloud support (AWS, Azure, GCP, IBM Cloud, OCI, VMware, Alibaba Cloud)
- Maps ResourceClaim variables to standard cloud provider credential formats
- Extracts DNS zones and domain information
- Optional verbose mode with source variable comments
- Perfect for integration with YamlForge environment variables


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
- **`tools/run_vulture.sh`** - Optimized script with configurable confidence levels, sorting, and output formats
- **`pyproject.toml`** - Alternative configuration for direct vulture usage

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
# Run with default settings (70% confidence)
./tools/run_vulture.sh

# Run with higher confidence
./tools/run_vulture.sh --confidence 80

# Sort results by code size (largest first)
./tools/run_vulture.sh --sort-by-size

# Generate whitelist format for adding to ignore patterns
./tools/run_vulture.sh --make-whitelist

# Verbose output with detailed analysis
./tools/run_vulture.sh --verbose

# Combined options
./tools/run_vulture.sh --confidence 80 --sort-by-size --verbose
```

### Adding New Ignore Patterns

When Vulture finds false positives, add them to the `.vulture` configuration file:

```bash
# Add to .vulture file in the project root
new_method_name
another_false_positive
```

Alternatively, use the whitelist generation feature:

```bash
# Generate whitelist format from current findings
./tools/run_vulture.sh --make-whitelist
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
- **Schema Validation** - Validates all YAML files and documentation examples
- **Vulture Analysis** - Runs on staged Python files before each commit  
- **Functionality Tests** - Validates provider initialization and Terraform generation
- **Blocking** - Prevents commits if any checks fail
- **Bypass** - Use `git commit --no-verify` to skip (not recommended)

#### **Post-commit Hook**
- **Schema Monitoring** - Quick background check of schema compliance
- **Vulture Monitoring** - Runs Vulture on entire codebase after each commit
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

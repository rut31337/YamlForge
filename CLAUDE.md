# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Commands

### Core Development
```bash
# Run the main tool - analyze configuration
python yamlforge.py config.yaml --analyze

# Generate Terraform files (pre-create output directory first)
mkdir -p /tmp/yamlforge-test-$(date +%s)
python yamlforge.py config.yaml -d /tmp/yamlforge-test-$(date +%s)/

# Generate and auto-deploy
python yamlforge.py config.yaml -d output/ --auto-deploy

# Generate with verbose output (debugging)
python yamlforge.py config.yaml -d output/ --verbose

# Generate without credentials (testing/development)
python yamlforge.py config.yaml -d output/ --no-credentials

# Check for unused code (optimized)
./tools/run_vulture.sh                    # Standard analysis (70% confidence)
./tools/run_vulture.sh --confidence 80    # Stricter analysis
./tools/run_vulture.sh --sort-by-size     # Sort by code size
./tools/run_vulture.sh --make-whitelist   # Generate whitelist format
./tools/run_vulture.sh --verbose          # Detailed analysis output

# Alternative: Use vulture directly with pyproject.toml
vulture --config pyproject.toml

# Install dependencies
pip install -r requirements.txt

# Install with development extras
pip install -e .[dev]
```

### Testing Requirements
- Terraform v1.12.0+ is required for OpenShift/ROSA support
- Verify with: `terraform version`
- **Always use /tmp subdirectories for test files**: `mkdir -p /tmp/yamlforge-test-{timestamp}`
- Source environment variables if cloud credentials needed: `source ~/.envvars.sh`

### DemoBuilder Deployment (OpenShift S2I)
```bash
# Deploy DemoBuilder chatbot to OpenShift
export ANTHROPIC_API_KEY="your-api-key"
./demobuilder/deployment/openshift/deploy-s2i.sh

# Check deployment status
oc get pods -n demobuilder
oc get routes -n demobuilder

# Application URL
echo "https://$(oc get route demobuilder -n demobuilder -o jsonpath='{.spec.host}')"

# View logs
oc logs deployment/demobuilder -n demobuilder
```

## Architecture Overview

YamlForge is a multi-cloud infrastructure converter that translates universal YAML configurations into provider-specific Terraform code. The architecture follows a modular provider pattern:

### Core Components

**Main Entry Point**: `yamlforge/main.py` - CLI interface with analyze mode, Terraform generation, and auto-deploy functionality

**Core Converter**: `yamlforge/core/converter.py` - Central orchestrator that:
- Loads YAML configurations and mappings
- Manages provider instances (AWS, Azure, GCP, IBM, OCI, Alibaba, VMware, CNV)
- Coordinates Terraform generation across multiple clouds
- Handles cost optimization via `cheapest` and `cheapest-gpu` providers

**Provider Architecture**: Each cloud provider implements infrastructure generation:
- `yamlforge/providers/aws.py` - EC2, VPC, security groups, S3 buckets, ROSA clusters
- `yamlforge/providers/azure.py` - VMs, VNets, NSGs, Storage Accounts, ARO clusters
- `yamlforge/providers/gcp.py` - Compute Engine, Cloud Storage with dynamic image discovery
- `yamlforge/providers/ibm_*.py` - VPC Gen 2 and Classic Infrastructure, Cloud Object Storage
- `yamlforge/providers/oci.py` - Compute instances, networking, Object Storage
- `yamlforge/providers/alibaba.py` - ECS instances, VPC, OSS buckets
- `yamlforge/providers/vmware.py` - vSphere VMs and networking
- `yamlforge/providers/cnv/` - Container Native Virtualization (KubeVirt/OpenShift CNV)

**OpenShift Specialization**: `yamlforge/providers/openshift/` contains:
- `base.py` - Common OpenShift functionality
- `rosa.py`, `aro.py` - Cloud-specific managed OpenShift
- `self_managed.py`, `dedicated.py`, `hypershift.py` - Deployment types
- `features/` - Day-2 operations, operators, networking, security

### Key Design Patterns

**Universal Mappings**: The `mappings/` directory provides cloud-agnostic abstractions:
- `images.yaml` - OS images across all providers (e.g., "RHEL9-latest")
- `locations.yaml` - Geographic regions (e.g., "us-east" → aws:us-east-1, azure:East US)
- `flavors/` - Instance types via t-shirt sizing or CPU/memory specs

**Provider Discovery**: The converter automatically determines required providers from YAML config and only generates relevant Terraform modules.

**Cost Optimization**: Special providers `cheapest` and `cheapest-gpu` analyze pricing across clouds and select the most cost-effective option meeting specifications.

**GUID-based Deployment**: All resources require a 5-character GUID for unique identification and safe multi-deployment scenarios.

## Configuration Structure

**Core Configuration**: `defaults/core.yaml` contains organization-wide settings like default usernames, security policies, and provider defaults.

**Provider Defaults**: Individual YAML files in `defaults/` define provider-specific settings (AWS AMI filters, Azure VM configurations, etc.).

**Environment Variables**: `envvars.example.sh` template shows required cloud credentials and configuration options.

## Development Workflow

1. **Configuration Analysis**: Always use `--analyze` first to understand provider selections and cost implications without generating Terraform
2. **Incremental Development**: Test single-provider configs before multi-cloud deployments
3. **Credential Management**: The `CredentialsManager` class handles cloud authentication uniformly
4. **Dynamic Image Resolution**: GCP, OCI, and Alibaba providers include intelligent image discovery for latest OS versions

## Development Guidelines

### Code Quality and Style
- **No emoji characters** in code, comments, or output messages - use clear descriptive text
- Follow PEP 8 Python formatting and meaningful variable/function names
- Run Vulture static analysis before making changes: `./tools/run_vulture.sh`
- Remove unused code when identified, but keep clearly marked future feature stubs

### File and Repository Management
- **Never create test files or output directories inside the repository**
- Use `/tmp/yamlforge-test-{timestamp}` for all testing and output
- Clean up test artifacts after completion: `rm -rf /tmp/yamlforge-test-*`
- Use LF line endings for all files (Unix format, not CRLF)

### YAML Configuration Development
- **Study existing examples** in `examples/` directory before creating new YAML
- **Review schema documentation** in `docs/yamlforge-schema.json`
- Understand the complete YamlForge schema before creating any YAML files
- Ask before adding test YAML to examples directory if it might be useful

### Testing Protocol - CRITICAL REQUIREMENTS
- **ALWAYS read the complete schema FIRST**: `docs/yamlforge-schema.json` is THE AUTHORITY
- Study provider-specific sections and required vs optional fields
- Examples are secondary reference only - schema is authoritative
- Create unique test directories: `mkdir -p /tmp/yamlforge-test-$(date +%s)`
- Use unique GUIDs for all test configurations
- Pre-create output directories before running yamlforge.py
- Use `--auto-deploy` for automated testing, `--verbose` for debugging

### Terraform Operations - MANDATORY PROCEDURES
- **Background terminals required**: All Terraform commands MUST use background terminals
- **terraform plan**: MUST use tee: `terraform plan | tee terraform-plan.log`
- **terraform init/apply/destroy**: Run directly in background terminal
- **Always review plan logs**: `cat terraform-plan.log` before applying
- **Ask permission before apply**: Summarize what will be created
- **Monitor background terminal output** for real-time errors

### Infrastructure Cleanup - CRITICAL
- **NEVER delete test directories without running `terraform destroy` first**
- **ALWAYS destroy infrastructure before directory deletion**
- **Ask user permission before deleting any cloud resources**
- Check for `.terraform` directories or `terraform.tfstate` files
- Use `terraform state list` to verify existing resources

## Important Implementation Details

**Terraform Module Generation**: Each provider generates self-contained Terraform modules with proper variable definitions and outputs.

**OpenShift Integration**: ROSA deployments include automatic account role creation via CLI and support for both Classic and HCP deployment modes.

**CNV Support**: The CNV provider validates Kubernetes/OpenShift cluster connectivity and automatically enables required operators.

**Security Best Practices**: All providers implement secure defaults for networking, SSH access, and cloud-specific security groups.

## Provider-Specific Implementation Notes

### IBM Classic Security Groups
- Use `security_group_id` not `group` in rules
- Use `protocol` as string, not protocol blocks
- No `tags` support in security groups
- No `security_group_ids` in VM instances
- Handle security through VM's `private_network_only` flag

### IBM Cloud CLI Requirements
- **Region targeting required** for zone discovery: `ibmcloud target -r <REGION_NAME>`
- Set target before listing zones: `ibmcloud is zones`
- Common regions: `us-east`, `us-south` with zones 1-3
- Check current target: `ibmcloud target`

### Schema-First Development
- **`docs/yamlforge-schema.json` is THE AUTHORITY** - always check it first
- Each provider has unique requirements and configurations
- Use `port_range` not `port` in security group rules
- Different providers have different networking and security models
- Examples may be outdated - schema is always current

### Environment Variable Configuration
**Provider Exclusion**: Control which providers are excluded from `cheapest` analysis:
```bash
# Exclude specific providers from cost optimization
export YAMLFORGE_EXCLUDE_PROVIDERS="aws,azure,gcp"
python yamlforge.py config.yaml --analyze

# DemoBuilder automatically sets this based on UI provider selection
# No manual configuration needed for DemoBuilder deployments
```

**Key Features**:
- Clean environment-based configuration (no temporary files)
- Automatic merging with existing `exclude_from_cheapest` settings
- Used by DemoBuilder for provider filtering in containerized environments
- Comma-separated list format for multiple provider exclusions

## Testing and Quality

**Vulture Integration**: Optimized unused code detection with multiple analysis modes:
- `tools/run_vulture.sh` - Enhanced script with configurable confidence levels (default 70%)
- `.vulture` file contains comprehensive ignore patterns for dynamically-called methods
- `pyproject.toml` provides alternative configuration for direct vulture usage
- Supports confidence levels, size sorting, verbose output, and whitelist generation

**Provider Validation**: Each provider includes credential validation and environment checking before Terraform generation.

**Error Handling**: Graceful degradation when cloud APIs are unavailable, with fallback to static configurations where possible.
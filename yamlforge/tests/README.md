# YamlForge Tests

This directory contains comprehensive test scripts for validating YamlForge functionality.

## Test Scripts

### `test_provider_initialization.py`
Tests that all cloud providers initialize correctly without warnings or missing file errors.

**What it tests:**
- YamlForgeConverter initialization
- All provider classes (AWS, Azure, GCP, IBM VPC/Classic, OCI, VMware, Alibaba, CNV, OpenShift)
- File path resolution for defaults and mappings
- No missing file warnings

**Usage:**
```bash
# From repository
python -m yamlforge.tests.test_provider_initialization

# From pip installation  
yamlforge-test-providers
```

### `test_terraform_generation.py`
Tests actual Terraform file generation for all major cloud providers.

**What it tests:**
- End-to-end Terraform generation workflow
- AWS, Azure, GCP, IBM VPC, IBM Classic providers
- YAML validation and processing
- File path resolution during Terraform generation
- Generated file validation

**Usage:**
```bash
# From repository
python -m yamlforge.tests.test_terraform_generation

# From pip installation
yamlforge-test-terraform
```

**Note:** This test uses `--no-credentials` mode, so no cloud authentication is required.

## Test Features

### Path Resolution Testing
Both tests validate that the centralized path resolution system works correctly:
- Repository mode (running from YamlForge directory)
- Developer mode (running from subdirectories)
- Package mode (pip installed packages)
- Environment variable override (YAMLFORGE_DATA_PATH)

### No Authentication Required
Tests are designed to run without cloud credentials:
- Provider initialization tests use analyze mode only
- Terraform generation tests use `--no-credentials` flag
- Tests focus on file resolution and code generation, not cloud connectivity

### Comprehensive Coverage
- **10 cloud providers** tested for initialization
- **5 major providers** tested for Terraform generation
- **All mapping files** validated (images, locations, flavors, defaults)
- **Error handling** and warning detection

## Expected Results

### Successful Run
```
🚀 YAMLFORGE PROVIDER INITIALIZATION TEST
✅ PASS AWS
✅ PASS Azure
✅ PASS GCP
✅ PASS IBM VPC
✅ PASS IBM Classic
✅ PASS OCI
✅ PASS VMware
✅ PASS Alibaba
✅ PASS CNV
✅ PASS OpenShift
📈 Results: 10 passed, 0 failed
🎉 ALL PROVIDERS PASSED!
```

### What Tests Validate
- ✅ No missing file errors
- ✅ No unnecessary warnings  
- ✅ Clean provider initialization
- ✅ Proper Terraform file generation
- ✅ Path resolution working across deployment modes
- ✅ Schema validation and YAML processing

## Troubleshooting

### Common Issues
1. **Import Errors**: Ensure you're running from the YamlForge root directory
2. **Missing Files**: Check that all mappings and defaults directories exist
3. **Permission Errors**: Ensure write access to `/tmp` for temporary test files

### Debug Mode
Add `--verbose` to see detailed output:
```bash
python tests/test_terraform_generation.py --verbose
```

## Execution Environment Usage

These tests are particularly useful for validating YamlForge in Ansible execution environments:

### In Execution Environments
```bash
# After installing yamlforge-infra package in EE
yamlforge-test-providers
yamlforge-test-terraform
```

### Benefits for EE Validation
- ✅ **Path Resolution Testing**: Validates that all defaults, mappings, and docs files are found via pip package resources
- ✅ **No External Dependencies**: Tests work without cloud credentials or network access
- ✅ **Comprehensive Coverage**: Tests all 10 cloud providers and major functionality
- ✅ **Quick Validation**: Confirms YamlForge is properly installed and functional

### Typical EE Workflow
1. Build execution environment with yamlforge-infra package
2. Run `yamlforge-test-providers` to validate provider initialization
3. Run `yamlforge-test-terraform` to validate Terraform generation
4. Use YamlForge in Ansible playbooks with confidence

## Adding New Tests

When adding new providers or features:
1. Add provider tests to `test_provider_initialization.py`
2. Add Terraform generation tests to `test_terraform_generation.py`  
3. Update this README with new test descriptions
4. Ensure tests work in `--no-credentials` mode
5. Test console script entry points work from pip installations
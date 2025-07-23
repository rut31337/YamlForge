# YamlForge Tools

Utility scripts and tools for YamlForge development and ROSA management.

## 🛠️ Available Tools

### **`get_rosa_versions.py`** - ROSA Version Management
Dynamic version fetching from Red Hat OpenShift Cluster Manager API.

```bash
# Get latest supported version
python3 tools/get_rosa_versions.py --latest

# List all supported versions
python3 tools/get_rosa_versions.py --list

# Check if specific version is supported
python3 tools/get_rosa_versions.py --check "4.18.19"

# JSON output for scripting
python3 tools/get_rosa_versions.py --latest --json
```

**Features:**
- Live version data from Red Hat API
- Automatic token refresh for Red Hat Offline Tokens
- ROSA CLI integration as backup
- JSON output for automation

### **`fix_rosa_config.sh`** - ROSA Configuration Fixer
Validates and fixes ROSA configuration issues in YAML files.

```bash
# Fix YAML with dynamic version checking
tools/fix_rosa_config.sh --auto-fix my-rosa-config.yaml

# Preview changes (dry run)
tools/fix_rosa_config.sh --dry-run my-rosa-config.yaml

# Interactive mode
tools/fix_rosa_config.sh my-rosa-config.yaml
```

**Features:**
- Updates outdated OpenShift versions to supported ones
- Fixes multi-AZ clusters to use exactly 3 availability zones
- Validates ROSA cluster configurations
- Uses latest supported version if input version is invalid

## 📋 Requirements

### **Environment Variables**
```bash
# Required for API access
export REDHAT_OPENSHIFT_TOKEN="your_offline_token"
export REDHAT_OPENSHIFT_URL="https://api.openshift.com"
```

### **Dependencies**
- Python 3.6+
- `requests` library (included in requirements.txt)
- `ansible` (if using vault-encrypted configurations)
- Network connectivity to Red Hat API

## 🚀 Quick Start

1. **Set up authentication:**
   ```bash
   export REDHAT_OPENSHIFT_TOKEN="your_offline_token_from_console.redhat.com"
   ```

2. **Check latest ROSA version:**
   ```bash
   python3 tools/get_rosa_versions.py --latest
   ```

3. **Fix configuration issues:**
   ```bash
   tools/fix_rosa_config.sh --auto-fix my-rosa-config.yaml
   ```

## 🔗 Related Documentation

- [ROSA Dynamic Versions](../docs/ROSA_DYNAMIC_VERSIONS.md) - Complete documentation
- [Red Hat Console](https://console.redhat.com/openshift/token) - Get your offline token 
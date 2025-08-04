# DemoBuilder - AI-Powered Infrastructure Assistant

DemoBuilder is a conversational AI chatbot that converts natural language requirements into validated YamlForge configurations. Describe your infrastructure needs in plain English, and DemoBuilder generates optimized, multi-cloud YAML configurations with cost analysis.

## Features

- **Natural Language Processing**: Describe infrastructure in plain English
- **Multi-Cloud Support**: All YamlForge providers (AWS, Azure, GCP, IBM, OCI, Alibaba, VMware, CNV)
- **Cost Optimization**: Automatic suggestions for cheapest providers
- **OpenShift Integration**: ROSA, ARO, CNV, and self-managed cluster support
- **Real-time Analysis**: Direct YamlForge integration for cost estimation
- **Optional Authentication**: Keycloak SSO integration for enterprise deployments
- **Infrastructure Diagrams Integration**: Optional AI-powered infrastructure insights and documentation (disabled by default)

## Quick Start

### Prerequisites
- Python 3.11+
- YamlForge parent project
- Optional: `ANTHROPIC_API_KEY` for enhanced AI features

### Installation

1. **Navigate to DemoBuilder**:
   ```bash
   cd YamlForge/demobuilder
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run locally**:
   ```bash
   python run_local.py
   ```

4. **Open browser** to `http://localhost:8501`

## Usage Examples

### Basic Infrastructure
```
"I need 3 RHEL VMs on AWS with SSH access"
"Create 2 medium Ubuntu servers on the cheapest provider"
"Deploy a GPU instance for machine learning"
```

### OpenShift Clusters
```
"Deploy a small ROSA cluster for development"
"I need an ARO cluster on Azure for production"
"Add a ROSA HCP cluster to my setup"
```

### Modifications
```
"Add a bastion host for secure access"
"Make everything use the cheapest providers"
"Add monitoring and database infrastructure"
```

## Deployment

### Local Development
```bash
# Basic usage
python run_local.py

# Advanced options
python run_local.py --port 8502 --debug
```

### OpenShift S2I Deployment

**Simple deployment without authentication:**
```bash
export ANTHROPIC_API_KEY="your-api-key"
./deployment/openshift/deploy-s2i.sh --namespace demobuilder-dev
```

**Deployment with Keycloak authentication:**
```bash
./deployment/openshift/deploy-s2i.sh \
  --namespace demobuilder-dev \
  --enable-auth \
  --keycloak-url https://keycloak.example.com \
  --client-secret your-keycloak-client-secret
```

**Deployment with Infrastructure Diagrams integration:**
```bash
./deployment/openshift/deploy-s2i.sh \
  --namespace demobuilder-dev \
```

### Docker
```bash
docker build -t demobuilder:latest .
docker run -p 8501:8501 demobuilder:latest
```

## Authentication

DemoBuilder supports optional Keycloak authentication via OAuth2 Proxy:

- **OAuth2 Proxy**: Handles OIDC authentication at ingress level
- **Role-based Access**: Power user features based on Keycloak roles
- **Development Mode**: Mock authentication for local testing
- **Enterprise Ready**: Secure session management and logout

See [CLAUDE.md](CLAUDE.md) for detailed authentication setup.

## Infrastructure Diagrams Integration

DemoBuilder supports optional Infrastructure Diagrams integration for enhanced infrastructure intelligence:

- **Infrastructure Documentation**: Access to comprehensive multi-cloud documentation
- **Best Practices**: Contextual recommendations based on workload type
- **Cost Optimization**: Provider-specific cost optimization suggestions
- **Provider Insights**: Enhanced provider comparisons and recommendations


**Benefits when enabled**:
- Smarter infrastructure recommendations
- Real-time best practices integration
- Enhanced cost optimization suggestions
- Reduced configuration errors through better documentation context

**Graceful Degradation**: DemoBuilder works normally when Infrastructure Diagrams is unavailable

## Configuration

### Environment Variables
```bash
export ANTHROPIC_API_KEY="your-api-key"        # Optional: Enhanced AI features
export KEYCLOAK_ENABLED="true"                 # Optional: Enable authentication
export AUTH_DEV_MODE="true"                    # Optional: Development mode
```

### Provider Management
Use the sidebar controls to enable/disable cloud providers. Default enabled:
- AWS, Azure, GCP, IBM VPC, IBM Classic, CNV

## Architecture

- **Streamlit UI**: Professional web interface
- **AI Engine**: Natural language to YAML conversion
- **YamlForge Integration**: Direct Python imports for analysis
- **Schema Validation**: Auto-correction and compliance checking
- **Authentication**: Optional Keycloak SSO via OAuth2 Proxy

## Project Structure

```
demobuilder/
├── app.py                      # Main Streamlit application
├── run_local.py               # Local development runner
├── core/                      # Core functionality
├── config/                    # Configuration management
├── deployment/openshift/      # OpenShift deployment files
├── README.md                  # This file
└── CLAUDE.md                  # Detailed developer documentation
```

## Contributing

1. **Development setup**:
   ```bash
   pip install -r requirements.txt
   python run_local.py --debug
   ```

2. **Code quality**:
   ```bash
   black .
   flake8 .
   pytest tests/
   ```

3. **See [CLAUDE.md](CLAUDE.md)** for detailed development guidelines

## Documentation

- **[CLAUDE.md](CLAUDE.md)**: Complete developer documentation
- **[YamlForge](../README.md)**: Core project documentation
- **[Schema Reference](../docs/yamlforge-schema.json)**: Configuration schema

## License

Part of the YamlForge ecosystem. See parent project license.

---

**Making multi-cloud infrastructure as easy as having a conversation!**
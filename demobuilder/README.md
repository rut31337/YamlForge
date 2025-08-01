# DemoBuilder - AI-Powered Infrastructure Assistant

DemoBuilder is a conversational AI chatbot that simplifies multi-cloud infrastructure deployment by converting natural language requirements into validated YamlForge configurations. Users describe their infrastructure needs in plain English, and DemoBuilder generates optimized, schema-compliant YAML configurations with cost analysis and deployment guidance.

## 🌟 Features

### Core Capabilities
- **Natural Language Processing**: Describe infrastructure in plain English
- **Multi-Cloud Support**: All 11 YamlForge providers (AWS, Azure, GCP, IBM, OCI, Alibaba, VMware, CNV, cost-optimized)
- **Schema Validation**: Auto-validates and fixes configurations against YamlForge schema
- **Cost Optimization**: Automatic suggestions for `cheapest` and `cheapest-gpu` providers
- **OpenShift Integration**: Full support for ROSA (Classic & HCP), ARO, CNV, and self-managed clusters
- **Real-time Analysis**: Direct YamlForge integration for cost estimation and provider selection
- **Configuration Modification**: Add/remove instances and clusters to existing configurations through conversation

### User Experience
- **Professional UI**: Clean, enterprise-ready Streamlit interface
- **Provider Controls**: Sidebar toggles to enable/disable specific cloud providers
- **Workflow Stages**: Clear progression through requirements → generation → analysis → refinement
- **YAML Preview**: Syntax-highlighted configuration display with download capability
- **Interactive Refinement**: Iterative conversation to perfect configurations

### Enterprise Ready
- **OpenShift Deployment**: Container-ready for Kubernetes/OpenShift environments
- **Keycloak SSO Ready**: Authentication abstraction for future SSO integration
- **Analysis-Only Mode**: No cloud credentials required - generates configurations for user deployment
- **Professional Appearance**: Suitable for enterprise demonstrations and customer-facing use

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- YamlForge parent project (for schema validation and analysis)

### Installation

1. **Clone and navigate to DemoBuilder**:
   ```bash
   cd YamlForge/demobuilder
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application**:
   ```bash
   streamlit run app.py
   ```

4. **Open your browser** to `http://localhost:8501`

### First Use

1. **Describe your infrastructure**: 
   ```
   "I need 3 RHEL VMs on AWS in us-east with SSH and HTTP access"
   ```

2. **Review generated configuration**: DemoBuilder creates validated YAML automatically

3. **Analyze costs and providers**: See estimated costs and provider reasoning

4. **Refine as needed**: Make adjustments through natural language

5. **Download and deploy**: Get final YAML with deployment instructions

## 📖 Usage Examples

### Basic VM Deployment
```
"Create 2 medium Ubuntu VMs on the cheapest cloud provider with SSH access"
```

### GPU Workload
```
"I need 1 large RHEL VM with NVIDIA T4 GPU for machine learning on AWS us-west"
```

### OpenShift Cluster
```
"Deploy a small ROSA cluster in us-east-1 for development"
"Add a ROSA HCP cluster to my existing infrastructure"
"I need an ARO cluster on Azure for production"
```

### Multi-Cloud Setup
```
"Create 1 VM on AWS and 1 on Azure, both with web server access, in a workspace called 'multi-cloud-demo'"
"AWS web servers with Azure database and GCP API server"
```

### Configuration Modification (AI-Powered)
```
"Add 2 more instances to the current setup"
"Add an OpenShift HCP cluster"
"Add a bastion host for secure access"
"Add monitoring and database infrastructure"
"Change all instances to use the cheapest provider"
"Remove one VM and add a GPU instance"
"Scale up the web servers and add load balancing"
"Add a development environment with SSH access"
```

### CNV Deployment
```
"I need 2 VMs on OpenShift CNV with medium specs for containerized workloads"
```

## 🎯 Workflow Stages

### 1. Requirements Gathering 📝
- Natural language input processing
- Infrastructure requirement extraction
- Provider preference detection

### 2. YAML Generation ⚙️
- Schema-compliant configuration creation
- Automatic field validation and correction
- Provider-specific optimization

### 3. Analysis 📊
- YamlForge `--analyze` execution
- Cost estimation and breakdown
- Provider selection reasoning

### 4. Refinement 🔧 (AI-Powered)
- **Context-Aware Modifications**: AI understands existing configuration and user intent
- **Natural Language Processing**: Handle requests like "add a bastion", "make it cheaper", "add monitoring"
- **Infrastructure Preservation**: Maintains existing resources while adding only requested changes
- **Smart Instance Naming**: Automatically generates meaningful names (bastion-host, web-server, database)
- **Real-time Validation**: Immediate schema compliance checking and re-analysis

### 5. Completion ✅
- Final configuration download
- Dynamic cloud credential setup instructions (only for selected providers)
- Deployment guidance
- **Post-Approval Changes**: Continue making modifications even after approval - the system automatically returns to refinement mode while preserving the existing configuration

## 🤖 AI-Powered Configuration Management

### Intelligent Modification Engine
DemoBuilder uses advanced AI to understand infrastructure contexts and user intentions without relying on static keyword matching:

**How It Works:**
1. **Context Analysis**: AI analyzes the existing YAML configuration structure
2. **Intent Recognition**: Natural language processing identifies what the user wants to change
3. **Preservation Logic**: AI maintains all existing infrastructure components
4. **Smart Addition**: New resources are added with contextually appropriate configurations
5. **Schema Validation**: All modifications are validated against YamlForge schema

**Example Conversation Flow:**
```
User: "Deploy a ROSA HCP cluster for development"
→ AI generates YAML with ROSA HCP cluster configuration

User: "Add a bastion host for secure access"
→ AI preserves the cluster, adds bastion-host instance with SSH configuration

User: "Add monitoring infrastructure and a database"
→ AI adds monitoring-server and database instances while preserving existing resources

User: "Make everything use the cheapest providers"
→ AI updates all components to use cost-optimized providers
```

**Advanced Capabilities:**
- **Semantic Understanding**: Recognizes intent behind phrases like "secure access", "monitoring", "database"
- **Configuration Continuity**: Maintains workspace names, GUIDs, and existing relationships
- **Provider Intelligence**: Understands cost optimization requests and provider-specific features
- **Error Recovery**: Graceful handling of ambiguous requests with clarification prompts

## 🔧 Configuration

### Provider Management
Use the sidebar controls to enable/disable specific cloud providers. Default enabled providers are marked with ✅:

**Default Enabled Providers:**
- ✅ Amazon Web Services (AWS) - GPU: ✅, OpenShift: ✅
- ✅ Microsoft Azure - GPU: ✅, OpenShift: ✅
- ✅ Google Cloud Platform (GCP) - GPU: ✅, OpenShift: ❌
- ✅ IBM Cloud VPC - GPU: ❌, OpenShift: ❌
- ✅ IBM Cloud Classic - GPU: ❌, OpenShift: ❌
- ✅ Container Native Virtualization (CNV) - GPU: ✅, OpenShift: ✅

**Additional Providers (disabled by default):**
- ⬜ Oracle Cloud Infrastructure (OCI) - GPU: ✅, OpenShift: ❌
- ⬜ Alibaba Cloud - GPU: ✅, OpenShift: ❌
- ⬜ VMware vSphere - GPU: ❌, OpenShift: ❌
- ⬜ Cost Optimized GPU - GPU: ✅, OpenShift: ❌

### Cost Optimization
- **Manual cost optimization**: Users can request "cheapest" providers through natural language
- **GPU workload optimization**: Smart selection of `cheapest-gpu` for AI/ML workloads when requested
- **Provider-specific insights**: Cost comparisons and reasoning

## 🏗️ Architecture

### Core Components
- **`app.py`**: Main Streamlit application with professional UI
- **`core/yaml_generator.py`**: Natural language → YAML conversion
- **`core/validation.py`**: Schema validation and auto-correction
- **`core/yamlforge_integration.py`**: Direct YamlForge analysis integration
- **`config/app_config.py`**: Provider configuration and settings

### Integration Points
- **YamlForge Schema**: Validates against `docs/yamlforge-schema.json`
- **Direct Python Imports**: Uses YamlForge core modules for analysis
- **Analysis-Only Mode**: Executes `--analyze` without requiring cloud credentials

## 🐳 Deployment

### Docker Deployment
```bash
# Build container
docker build -t demobuilder:latest .

# Run locally
docker run -p 8501:8501 demobuilder:latest
```

### OpenShift Deployment
```bash
# Deploy to OpenShift
oc apply -f deployment/openshift/

# Access via route
oc get routes demobuilder
```

### Environment Variables
```bash
# Optional: Anthropic API key for enhanced features
export ANTHROPIC_API_KEY="your-api-key"

# Optional: Redis for session persistence
export REDIS_URL="redis://localhost:6379"
```

## 🧪 Example Conversations

### Development Environment
```
User: "Set up a development environment with 2 small RHEL VMs and SSH access"

DemoBuilder: "I've created a configuration with 2 small RHEL9 VMs using the cost-optimized provider. The configuration includes SSH access via security groups. Cost analysis shows $0.0624/hour total across both instances."

User: "Yes, and can you make them medium size instead?"

DemoBuilder: "I've updated the VMs to medium size and re-analyzed. The estimated cost is $0.1248/hour total for both medium instances. The configuration is ready for deployment!"

User: "Add an OpenShift HCP cluster to this setup"

DemoBuilder: "I've added a ROSA HCP cluster to your existing configuration. The cluster will be deployed alongside your VMs with an estimated additional cost of $0.8640/hour for the small cluster size."
```

### Production Workload
```
User: "I need a production setup with 1 large VM on AWS us-east-1 with HTTPS and SSH, plus a ROSA cluster"

DemoBuilder: "I've configured a large AWS instance in us-east-1 with security groups for HTTPS and SSH access, plus a ROSA classic cluster. This setup is production-ready. Would you like me to suggest any cost optimizations?"
```

## 🆕 Recent Improvements

### Pure AI-Driven Configuration Management
- **Context-Aware Modifications**: Replaced static keyword matching with intelligent AI that understands existing configurations and user intent
- **Natural Language Understanding**: Advanced AI processes requests like "add a bastion host", "add monitoring infrastructure", "make it cheaper" without predefined keywords
- **Infrastructure Preservation**: AI automatically preserves existing resources while adding only requested changes
- **Smart Instance Naming**: Contextual naming based on request content (bastion-host, web-server, database, monitoring-server)
- **Real-time Adaptation**: AI learns from configuration context to make appropriate modifications
- **Post-Approval Changes**: Users can continue making modifications after approval - system automatically returns to refinement mode

### Enhanced Provider Management
- **Optimized Default Selection**: Streamlined to 6 core providers (AWS, Azure, GCP, IBM VPC, IBM Classic, CNV) enabled by default
- **Provider Ordering**: CNV repositioned after IBM providers for logical grouping
- **Dynamic Credential Instructions**: Setup instructions automatically filter to only show relevant providers
- **Cost Optimization Integration**: Cheapest provider selection now respects UI provider enablement settings

### Enhanced OpenShift Support
- **ROSA HCP Detection**: Improved recognition of "HCP" keyword for hosted control plane clusters
- **Cluster Modification**: Full support for adding OpenShift clusters to existing configurations
- **Cost Calculation**: Fixed OpenShift cluster cost analysis with proper size-based configuration
- **Multiple Cluster Types**: Support for ROSA Classic, ROSA HCP, ARO, and self-managed clusters

### Advanced Configuration Management
- **Schema Pre-validation**: Catches invalid YAML before YamlForge analysis
- **Intelligent Fixes**: Auto-correction of common configuration issues including AI flavor object errors
- **Interactive Refinement**: Seamless modification of existing configurations through pure AI conversation
- **Cores/Memory Specification**: Enhanced handling of hardware specifications (2 cores, 4GB RAM) with automatic flavor matching
- **Exact Instance Name Requirements**: Prevents AI assumptions during removals - requires specific instance names
- **Cost-aware Generation**: Automatic cheapest provider suggestions with discount support
- **Fallback Generation**: Robust error handling with automatic fallback when AI generation fails

### User Experience Improvements
- **Professional Footer**: Enterprise-ready styling with proper legal links and privacy policy links
- **Provider Controls**: Enhanced sidebar with collapsible provider configuration and acronyms
- **Real-time Validation**: Immediate feedback on configuration validity
- **Clear Workflow**: Visual progress through all configuration stages
- **Raw Output Access**: Debug toggle button available during refinement and completion stages
- **Continuous Workflow**: Seamless transition from completion back to refinement for further changes

## 🔍 Troubleshooting

### Common Issues

**Schema Validation Errors**: DemoBuilder automatically fixes most schema issues. If persistent, check the generated YAML against `yamlforge-schema.json`.

**Analysis Failures**: Ensure YamlForge parent project is accessible. DemoBuilder falls back to subprocess calls if direct imports fail.

**Provider Not Available**: Check provider enablement in sidebar controls. Some providers may be disabled by default.

**YAML Generation Issues**: Try rephrasing requirements with more specific details (provider, region, size, etc.).

**OpenShift Cluster Addition**: If "add an openshift cluster" isn't working, try being more specific: "add a ROSA cluster" or "add a ROSA HCP cluster".

**Configuration Modifications**: The AI understands natural language - use phrases like "add a bastion host", "add monitoring infrastructure", "make it cheaper", or "add database servers". No specific keywords required.

**AI Modification Issues**: If the AI doesn't understand a modification request, try rephrasing with more context: instead of "add stuff", say "add monitoring and database infrastructure for a web application".

### Debug Mode
Set environment variable for detailed logging:
```bash
export STREAMLIT_LOGGER_LEVEL=debug
streamlit run app.py
```

## 🤝 Contributing

### Development Setup
```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests
pytest tests/

# Code formatting
black .
flake8 .
mypy .
```

### Project Structure
```
demobuilder/
├── app.py                          # Main Streamlit application
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── CLAUDE.md                       # Developer documentation
├── core/                           # Core functionality
│   ├── yaml_generator.py           # Natural language processing
│   ├── validation.py               # Schema validation
│   └── yamlforge_integration.py    # YamlForge analysis
├── config/                         # Configuration management
│   └── app_config.py               # Provider and app settings
├── tests/                          # Test suite
└── deployment/                     # Container and OpenShift configs
    ├── docker/
    └── openshift/
```

## 📄 License

This project is part of the YamlForge ecosystem. Please refer to the parent project's license terms.

## 🔗 Related Projects

- **[YamlForge](../README.md)**: Core multi-cloud infrastructure converter
- **[YamlForge Schema](../docs/yamlforge-schema.json)**: Configuration schema reference
- **[YamlForge Examples](../examples/)**: Sample configurations and use cases

## 📞 Support

For issues and questions:
1. Check this README and the [CLAUDE.md](CLAUDE.md) developer guide
2. Review YamlForge parent project documentation
3. File issues in the main YamlForge repository

---

**DemoBuilder**: Making multi-cloud infrastructure as easy as having a conversation! 🚀
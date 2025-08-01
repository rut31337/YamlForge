# DemoBuilder - YamlForge Chatbot

This file provides guidance to Claude Code when working with the DemoBuilder chatbot project.

## Project Overview

DemoBuilder is a conversational AI chatbot that helps users create multi-cloud infrastructure configurations using YamlForge as the backend engine. Users provide requirements in natural language, and DemoBuilder generates YamlForge YAML configurations with iterative refinement capabilities.

## Quick Commands

### Development
```bash
# Install dependencies
cd demobuilder
pip install -r requirements.txt

# Run the Streamlit app
streamlit run app.py

# Run tests
pytest tests/

# Code formatting
black .
flake8 .
mypy .
```

### Docker/OpenShift Deployment
```bash
# Build container locally
docker build -t demobuilder:latest .

# Run locally
docker run -p 8501:8501 demobuilder:latest

# Deploy to OpenShift with internal build
cd demobuilder
oc new-build --binary --strategy=docker --name=demobuilder
oc start-build demobuilder --from-dir=. --follow
oc apply -k deployment/openshift/

# Deploy with Fedora base (for broader access)
oc start-build demobuilder --from-dir=. --build-arg BASE_IMAGE=python:3.11

# Check deployment
oc get pods -n demobuilder
oc get routes -n demobuilder

# Get application URL and open in browser
echo "Application available at:"
echo "https://$(oc get route demobuilder -n demobuilder -o jsonpath='{.spec.host}')"
```

## Architecture Overview

### Core Components

**app.py** - Main Streamlit application entry point with professional UI
**core/workflow.py** - LangGraph state machine managing conversation flow
**core/yaml_generator.py** - Schema-aware YAML generation with validation
**core/yamlforge_integration.py** - Direct YamlForge Python imports for analysis
**ui/chat_interface.py** - Clean chat interface with provider controls
**ui/provider_controls.py** - Provider masking and configuration UI
**ui/analysis_display.py** - YamlForge analysis results visualization
**config/auth_config.py** - Keycloak SSO abstraction (future feature)

### Workflow States

1. **Requirements Gathering** - Natural language input processing
2. **YAML Generation** - Schema-compliant configuration creation
3. **Analysis Execution** - YamlForge `--analyze` processing
4. **Refinement Loop** - User feedback and iterative improvements
5. **Final Output** - YAML delivery with setup instructions

### Integration Architecture

**YamlForge Integration**: Direct Python imports, no subprocess calls
- Import `yamlforge.core.converter` for analysis functionality
- Use schema validation from `docs/yamlforge-schema.json`
- Execute only `--analyze` mode (no credentials required)

**Context7 Integration**: Intermediate approach with MCP server
- Session-based memory for conversation continuity
- Cached infrastructure documentation
- Intelligent context retrieval for multi-cloud knowledge

**LangGraph Memory**: In-memory persistence with Redis option
- Conversation state management
- User preference tracking
- Provider selection persistence

## Development Guidelines

### Code Quality
- Follow PEP 8 formatting standards
- Use type hints throughout codebase
- Maintain test coverage above 80%
- Run pre-commit hooks before commits

### Schema Compliance
- **ALWAYS validate against YamlForge schema first**
- Pre-screen generated YAML before YamlForge processing
- Handle all required fields: `yamlforge.cloud_workspace.name`
- Support all provider types including `cheapest` and `cnv`

### User Experience
- Professional, clean UI design
- Real-time YAML preview with syntax highlighting
- Clear progress indicators through workflow phases
- Intuitive provider masking controls
- Cost optimization suggestions

### Security & Authentication
- Keycloak SSO ready (toggleable)
- No cloud credentials stored or processed
- Analysis-only mode (no Terraform generation)
- Secure session management

## Key Features Implementation

### Provider Support
- All YamlForge providers: AWS, Azure, GCP, OCI, IBM (VPC/Classic), VMware, Alibaba, CNV
- Cost optimization via `cheapest` and `cheapest-gpu` providers
- User-configurable provider masking
- Automatic cheaper option suggestions

### YAML Generation
- Schema-compliant configuration generation
- Required field validation (GUID, cloud_workspace.name)
- Provider-specific configuration handling
- OpenShift cluster support (ROSA, ARO, self-managed)
- CNV and traditional VM support

### Analysis Integration
- Direct YamlForge Python imports
- `--analyze` mode execution only
- Cost breakdown visualization
- Provider selection reasoning
- Error handling and validation

### Conversation Management
- Multi-turn conversation support
- Context-aware refinement processing
- User preference learning
- Session persistence across interactions

## File Structure Details

```
demobuilder/
├── app.py                          # Streamlit main application
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Container build configuration
├── CLAUDE.md                       # This documentation file
├── core/
│   ├── __init__.py
│   ├── workflow.py                 # LangGraph state machine
│   ├── yaml_generator.py           # Schema-aware YAML generation
│   ├── yamlforge_integration.py    # Direct YamlForge imports
│   ├── context_manager.py          # Context7 integration
│   └── validation.py               # YAML schema validation
├── ui/
│   ├── __init__.py
│   ├── chat_interface.py           # Main chat UI component
│   ├── provider_controls.py        # Provider selection UI
│   ├── analysis_display.py         # Analysis results visualization
│   └── yaml_preview.py             # YAML preview with highlighting
├── config/
│   ├── __init__.py
│   ├── auth_config.py              # Keycloak abstraction
│   ├── app_config.py               # Application configuration
│   └── provider_config.py          # Provider mapping configuration
├── tests/
│   ├── __init__.py
│   ├── test_workflow.py            # Workflow state machine tests
│   ├── test_yaml_generation.py     # YAML generation tests
│   ├── test_validation.py          # Schema validation tests
│   └── test_integration.py         # YamlForge integration tests
└── deployment/
    ├── docker/
    │   └── Dockerfile
    └── openshift/
        ├── deployment.yaml
        ├── service.yaml
        └── route.yaml
```

## Development Workflow

### Phase 1: Core Implementation
1. Basic Streamlit UI with chat interface
2. LangGraph workflow with simple state management
3. YamlForge integration for analysis execution
4. Schema validation and YAML generation

### Phase 2: Enhancement
1. Context7 integration for infrastructure knowledge
2. Advanced provider controls and masking
3. Improved UI with YAML preview and analysis display
4. Cost optimization suggestions

### Phase 3: Production Ready
1. Keycloak SSO integration
2. OpenShift deployment configuration
3. Performance optimization and caching
4. Comprehensive testing and documentation

## Testing Strategy

### Unit Tests
- YAML generation with various provider combinations
- Schema validation against YamlForge schema
- Workflow state transitions
- Provider masking logic

### Integration Tests
- YamlForge analysis execution
- Context7 documentation retrieval
- End-to-end conversation flows
- Error handling and recovery

### UI Tests
- Streamlit component rendering
- User interaction flows
- Provider control functionality
- Analysis result display

## Important Notes

### YamlForge Integration
- Use direct Python imports, not subprocess calls
- Only execute `--analyze` mode
- No cloud credentials required or processed
- Handle all provider types including cost optimization

### Schema Compliance
- `docs/yamlforge-schema.json` is THE AUTHORITY
- All generated YAML must validate against schema
- Handle required vs optional fields correctly
- Support provider-specific configurations

### User Experience
- Professional appearance suitable for enterprise use
- Clear workflow progression indicators
- Intuitive provider selection controls
- Helpful cost optimization suggestions

### Future Considerations
- Keycloak SSO integration architecture
- OpenShift deployment scalability
- Multi-tenant support
- Advanced analytics and usage tracking

## Dependencies Management

### Core Dependencies
- **streamlit**: Modern web UI framework
- **langgraph**: Workflow state machine management
- **langchain-anthropic**: Claude integration
- **pydantic**: Data validation and serialization
- **jsonschema**: YAML schema validation

### Integration Dependencies
- **redis**: Session persistence and caching
- **requests**: HTTP client for Context7 API
- **python-keycloak**: Future SSO integration

### Development Dependencies
- **pytest**: Testing framework
- **black**: Code formatting
- **flake8**: Linting
- **mypy**: Type checking

## Error Handling

### Schema Validation Errors
- Pre-validate all generated YAML
- Provide clear error messages to users
- Automatic correction attempts when possible
- Fallback to simpler configurations

### YamlForge Integration Errors
- Handle missing provider support gracefully
- Validate analysis output parsing
- Provide meaningful error feedback
- Maintain conversation flow continuity

### UI/UX Error States
- Loading indicators during processing
- Clear error message display
- Recovery options for users
- State preservation during errors

## OpenShift Deployment Guide

### Prerequisites and Setup

**Required Tools:**
- OpenShift CLI (`oc`) configured and authenticated
- Access to OpenShift cluster with appropriate permissions
- Container registry access (internal OpenShift registry recommended)

**Essential Commands:**
```bash
# Create build config (one-time setup)
oc new-build --binary --strategy=docker --name=demobuilder

# Build image from source
oc start-build demobuilder --from-dir=. --follow

# Deploy application stack
oc apply -k deployment/openshift/

# Monitor deployment
oc get pods -n demobuilder --watch
oc get routes -n demobuilder

# Access application after deployment
echo "=== DemoBuilder Ready ==="
ROUTE_HOST=$(oc get route demobuilder -n demobuilder -o jsonpath='{.spec.host}')
echo "Application URL: https://${ROUTE_HOST}"
echo "Health Check: https://${ROUTE_HOST}/_stcore/health"
```

### Base Image Selection

**RHEL UBI9 (Default - Recommended for Production):**
```bash
# Default build uses RHEL UBI9 Python 3.11
oc start-build demobuilder --from-dir=. --follow
```

**Fedora (Alternative for Broader Access):**
```bash
# Use Fedora base for environments without RHEL access
oc start-build demobuilder --from-dir=. --build-arg BASE_IMAGE=python:3.11
```

**Custom Base Images:**
```bash
# Use any Python 3.11+ compatible image
oc start-build demobuilder --from-dir=. --build-arg BASE_IMAGE=registry.company.com/python:3.11
```

### Security Context Constraints

**Critical Requirements for OpenShift:**
- **NEVER** use hardcoded user IDs (`runAsUser: 1001`)
- **NEVER** use hardcoded group IDs (`fsGroup: 1001`) 
- Always use `runAsNonRoot: true`
- Let OpenShift assign UIDs dynamically
- Use group permissions (`chgrp -R 0` and `chmod -R g=u`)

**Working Security Context:**
```yaml
securityContext:
  runAsNonRoot: true
  # No runAsUser or fsGroup specified
containers:
- name: demobuilder
  securityContext:
    allowPrivilegeEscalation: false
    readOnlyRootFilesystem: false
    runAsNonRoot: true
    # No runAsUser specified
    capabilities:
      drop: [ALL]
```

### Configuration Management

**Environment Variables (ConfigMap):**
```bash
# View current configuration
oc get configmap demobuilder-config -o yaml

# Update configuration
oc edit configmap demobuilder-config
```

**Secrets Management:**
```bash
# Set Anthropic API key from environment
oc create secret generic demobuilder-secrets \
  --from-literal=anthropic-api-key="${ANTHROPIC_API_KEY}" \
  -n demobuilder --dry-run=client -o yaml | oc apply -f -

# Verify secret
oc get secret demobuilder-secrets -o yaml
```

### Networking and Routes

**Internal Service:**
- Port 8501 (Streamlit default)
- ClusterIP service for internal communication

**External Access:**
- HTTP route: `demobuilder-demobuilder.apps.<cluster-domain>`
- HTTPS route: `demobuilder-secure-demobuilder.apps.<cluster-domain>`

**Network Policies:**
- Ingress allowed from OpenShift router
- Pod-to-pod communication within namespace
- External traffic blocked except through routes

### Troubleshooting Guide

**Common Issues and Solutions:**

1. **Image Pull Errors:**
```bash
# Check build status
oc get builds -l build=demobuilder
oc logs build/demobuilder-1

# Verify image in registry
oc get imagestream demobuilder
```

2. **Security Context Violations:**
```bash
# Check for SCC errors in events
oc describe pod <pod-name> | grep -A 10 Events
oc get events --field-selector reason=FailedCreate
```

3. **Application Startup Issues:**
```bash
# Check pod logs
oc logs <pod-name> -n demobuilder

# Verify health endpoint
oc exec <pod-name> -- curl -f http://localhost:8501/_stcore/health
```

4. **Configuration Problems:**
```bash
# Test environment variables
oc exec <pod-name> -- env | grep -E "(ANTHROPIC|APP_)"

# Verify secret mounting
oc exec <pod-name> -- ls -la /var/run/secrets/
```

### Kustomize Template Structure

**Base Manifests (`deployment/openshift/`):**
- `kustomization.yaml` - Main kustomize configuration
- `namespace.yaml` - Namespace definition
- `serviceaccount.yaml` - Service account and RBAC
- `configmap.yaml` - Application configuration
- `secret.yaml` - Sensitive configuration template
- `deployment.yaml` - Pod specification and deployment
- `service.yaml` - Internal service
- `route.yaml` - External access routes
- `networkpolicy.yaml` - Network security
- `horizontalpodautoscaler.yaml` - Auto-scaling configuration

**Environment Overlays:**
```bash
# Create production overlay
mkdir -p deployment/openshift/overlays/production
cat > deployment/openshift/overlays/production/kustomization.yaml << EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: demobuilder-prod
resources:
- ../../base
replicas:
- name: demobuilder
  count: 5
EOF
```

### Production Deployment Checklist

**Security:**
- [ ] Use specific image tags, not `latest`
- [ ] Implement external secret management
- [ ] Enable network policies
- [ ] Regular security updates
- [ ] Resource quotas and limits

**Performance:**
- [ ] Tune resource requests/limits based on load testing
- [ ] Configure horizontal pod autoscaler
- [ ] Implement persistent storage for sessions if needed
- [ ] Set up proper monitoring and alerting

**High Availability:**
- [ ] Multiple replicas across availability zones
- [ ] Pod disruption budgets
- [ ] Proper health checks with appropriate timeouts
- [ ] External Redis for session persistence

## Lessons Learned from Development

### AI-Driven Configuration Management
- **Pure AI Approach**: Static keyword matching is inflexible and becomes unwieldy. Pure AI with context understanding is more maintainable and user-friendly
- **Context Preservation**: AI must understand and preserve existing infrastructure when making modifications
- **Exact Instance Names**: For removals, require specific instance names to prevent AI assumptions and wrong removals
- **Post-Processing Validation**: AI sometimes creates invalid YAML structures (like flavor objects) that need automatic correction

### Schema and Validation
- **Cores/Memory vs Flavor**: Instance sizing can use either flavor strings OR cores/memory integers, never mix both
- **RAM Terminology**: Users say "RAM", "memory", "system memory" - all should map to YAML `memory` field
- **Schema Authority**: `docs/yamlforge-schema.json` is THE AUTHORITY, examples can be outdated
- **Auto-fixing**: Implement validation with automatic correction rather than just error reporting

### Provider Management
- **Default Selection**: Start with core enterprise providers (AWS, Azure, GCP, IBM, CNV) rather than all providers
- **Provider Ordering**: Logical grouping (e.g., CNV after IBM providers) improves UX
- **Enabled Provider Filtering**: UI selections must be respected in backend analysis (cheapest provider selection)
- **Dynamic Credentials**: Show only relevant credential setup instructions based on actual provider usage

### Workflow Management
- **Post-Approval Changes**: Users want to continue refining after approval - reset to refinement stage with config preserved
- **Workflow Stage Clarity**: Clear progression indicators help users understand where they are in the process
- **Raw Output Access**: Debug toggles should be available during refinement and completion stages

### Cost Analysis Integration
- **Closest Flavor Matching**: When users specify cores/memory, find closest provider flavor and show cost
- **Provider Discounts**: Support environment variable overrides for provider-specific discounts
- **Dynamic Provider Exclusion**: Temporarily modify core config to exclude disabled providers from cheapest analysis

### User Experience Patterns
- **Conversational Flow**: Natural language works better than rigid command structures
- **Error Recovery**: When AI fails, provide clear guidance rather than technical error messages
- **Progressive Enhancement**: Start simple, add complexity only when needed
- **Context Awareness**: System should remember previous configurations and build upon them

### Testing and Quality
- **DemoBuilder Testing Protocol**:
  - Test with default provider selection (AWS, Azure, GCP, IBM VPC/Classic, CNV)
  - Verify post-approval modification workflow by approving config then requesting changes
  - Test AI understanding of cores/memory specifications vs flavor strings
  - Validate exact instance name requirements for removals
  - Test dynamic credential filtering by enabling/disabling providers
  - Verify CNV provider appears after IBM providers in UI
  - Test fallback generation when AI fails
  - Validate schema compliance with auto-correction features

### OpenShift Deployment Lessons Learned

#### Security Context Constraints (Critical)
- **Never use hardcoded UIDs/GIDs**: OpenShift dynamically assigns user IDs in ranges like `[1000890000, 1000899999]`
- **Always use `runAsNonRoot: true`**: Required for most OpenShift security policies
- **Use group permissions**: `chgrp -R 0 /app && chmod -R g=u /app` for OpenShift compatibility
- **Let OpenShift assign security context**: Remove `runAsUser` and `fsGroup` from manifests

#### Container Image Strategy
- **RHEL UBI9 for production**: Use Red Hat Universal Base Images for enterprise deployments
- **Fedora fallback**: Provide alternative base images for broader accessibility
- **Internal registry preferred**: Use OpenShift's internal registry to avoid external dependencies
- **Build arguments**: Support multiple base images via `ARG BASE_IMAGE`

#### Build and Deployment Process
- **Binary builds work best**: `oc new-build --binary` for source-to-image workflows
- **Update deployment image references**: Point to internal registry after successful builds
- **Deployment selector immutability**: Delete and recreate deployments when changing selectors
- **Watch build logs**: Use `oc start-build --follow` to monitor build progress

#### Configuration Management
- **Environment variables via ConfigMaps**: Separate configuration from deployment manifests
- **Secrets for sensitive data**: Use OpenShift secrets for API keys and credentials
- **Kustomize for environment management**: Use overlays for different deployment environments
- **Health checks are critical**: Proper readiness/liveness probes prevent deployment issues

#### Networking and Access
- **Routes vs Services**: Use OpenShift routes for external access, services for internal
- **Network policies**: Implement proper network segmentation for security
- **TLS termination**: Use edge or reencrypt termination based on requirements
- **Internal DNS**: Leverage OpenShift's internal service discovery

#### Troubleshooting Best Practices
- **Check events first**: `oc get events --sort-by='.lastTimestamp'` shows most recent issues
- **Pod describe for SCC errors**: Security context violations appear in pod events
- **Build logs for image issues**: Failed builds show detailed error information
- **Test inside pods**: Use `oc exec` to verify configuration and connectivity

#### Production Deployment
- **Resource limits required**: OpenShift quotas require proper resource specifications
- **Horizontal pod autoscaling**: Configure HPA for automatic scaling based on metrics
- **Pod disruption budgets**: Ensure availability during cluster maintenance
- **External secret management**: Use operators like External Secrets for production secrets
# DemoBuilder - Technical Implementation Guide

This file provides comprehensive technical guidance for Claude Code when working with the DemoBuilder project.

## Quick Reference Commands

### Development
```bash
# Setup and run locally
cd demobuilder && pip install -r requirements.txt
python run_local.py --debug

# Code quality
black . && flake8 . && pytest tests/

# OpenShift deployment
./deployment/openshift/deploy-s2i.sh --namespace demobuilder-dev
./deployment/openshift/deploy-s2i.sh --namespace demobuilder-dev --enable-auth \
  --keycloak-url https://keycloak.example.com --client-secret your-secret
```

## Architecture Overview

### Core Components

**app.py** - Main Streamlit application entry point with professional UI and authentication awareness
**core/yaml_generator.py** - Schema-aware YAML generation with validation
**core/yamlforge_integration.py** - Direct YamlForge Python imports for analysis
**core/validation.py** - YAML schema validation and auto-correction
**config/app_config.py** - Application configuration and provider management
**config/auth_config.py** - Optional Keycloak authentication integration via OAuth2 Proxy

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

**Infrastructure Visualization**: Interactive diagrams and insights
- Real-time infrastructure diagrams from YamlForge analysis
- Mini diagrams in sidebar with click-to-expand full view
- Resource summaries and cost estimates
- Provider-specific color coding and layouts

**Authentication Integration**: Optional Keycloak SSO via OAuth2 Proxy
- OAuth2 Proxy handles OIDC authentication at ingress level
- User information extracted from proxy headers
- Role-based access control for power user features
- Seamless operation with or without authentication enabled

## Authentication Architecture

### Optional Keycloak Integration

DemoBuilder supports optional Keycloak authentication through OAuth2 Proxy deployment:

**Authentication Flow:**
1. User accesses DemoBuilder route
2. OAuth2 Proxy intercepts request and redirects to Keycloak if not authenticated
3. After successful Keycloak login, OAuth2 Proxy forwards request with user headers
4. Streamlit application extracts user information from headers for session management

**Key Components:**
- **OAuth2 Proxy**: Handles OIDC authentication and user header injection
- **Authentication Middleware**: `config/auth_config.py` extracts user info from headers
- **Role-Based Features**: Power user capabilities based on Keycloak roles
- **Environment Toggle**: `KEYCLOAK_ENABLED` environment variable controls authentication

**Security Features:**
- Cookie-based session management with secure settings
- HTTPS-only authentication flows
- Role-based access control (admin, power-user roles)
- Session timeout and logout functionality

**Development Mode:**
- `AUTH_DEV_MODE=true` enables testing without OAuth2 Proxy
- Mock user information via environment variables
- Seamless development workflow

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
├── run_local.py                    # Local development runner script
├── requirements.txt                # Python dependencies
├── Dockerfile                      # Container build configuration
├── CLAUDE.md                       # This documentation file
├── core/
│   ├── __init__.py
│   ├── workflow.py                 # LangGraph state machine
│   ├── yaml_generator.py           # Schema-aware YAML generation
│   ├── yamlforge_integration.py    # Direct YamlForge imports
│   ├── context_manager.py          # Infrastructure Diagrams integration
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
        ├── route.yaml
        ├── oauth2-proxy.yaml         # OAuth2 Proxy deployment for authentication
        └── deploy-s2i.sh             # Enhanced S2I deployment script with auth support
```

## Key Environment Variables

```bash
# Required
export ANTHROPIC_API_KEY="sk-ant-..."              # AI functionality

# Optional
export YAMLFORGE_EXCLUDE_PROVIDERS="aws,azure"     # Provider filtering
export KEYCLOAK_ENABLED="true"                     # Enable authentication
export AUTH_DEV_MODE="true"                        # Development authentication
export AUTH_DEV_USER="dev-user"                    # Mock user for testing
export AI_MODEL="gemini"                           # Use gemini models on Vertex AI (defaults to claude)
export AI_MODEL_VERSION="gemini-1.5-pro-001"       # Specific model version (optional)
export ANTHROPIC_VERTEX_PROJECT_ID="your-project"  # Google Cloud project ID (REQUIRED for AI_MODEL=gemini)
```

### AI Model Configuration

DemoBuilder supports two AI model families with different requirements:

#### Claude Models (Default)
- **Environment**: `AI_MODEL="claude"` (or omit - this is the default)
- **Authentication**: Uses `ANTHROPIC_API_KEY` for direct Anthropic API access
- **Project ID**: `ANTHROPIC_VERTEX_PROJECT_ID` is NOT required
- **Version Control**: Use `AI_MODEL_VERSION` to specify exact Claude model version
- **Fallback**: If Vertex AI project is configured, can also use Claude via Vertex AI

#### Gemini Models  
- **Environment**: `AI_MODEL="gemini"`
- **Authentication**: Requires Google Cloud authentication
- **Project ID**: `ANTHROPIC_VERTEX_PROJECT_ID` is REQUIRED (your GCP project ID)
- **Version Control**: Use `AI_MODEL_VERSION` to specify exact Gemini model version
- **Access**: Only available through Vertex AI

**Usage Examples:**
```bash
# Use Claude (default) - only needs Anthropic API key
export ANTHROPIC_API_KEY="sk-ant-..."
export AI_MODEL="claude"  # Optional, this is the default

# Use specific Claude model version
export ANTHROPIC_API_KEY="sk-ant-..."
export AI_MODEL="claude"
export AI_MODEL_VERSION="claude-3-5-sonnet-20241022"

# Use Gemini - requires Google Cloud project
export AI_MODEL="gemini"
export ANTHROPIC_VERTEX_PROJECT_ID="your-gcp-project-id"

# Use specific Gemini model version
export AI_MODEL="gemini"
export AI_MODEL_VERSION="gemini-1.5-pro-001"
export ANTHROPIC_VERTEX_PROJECT_ID="your-gcp-project-id"
```

**Available Model Versions:**

*Claude Models:*
- `claude-3-haiku-20240307` (default, fast and cost-effective)
- `claude-3-5-sonnet-20241022` (most capable)
- `claude-3-opus-20240229` (highest performance)

*Gemini Models:*
- `gemini-2.0-flash-001` (most capable, default)
- `gemini-1.5-pro-001` (good balance)
- `gemini-1.5-flash-001` (fast and efficient)
- `gemini-1.0-pro` (stable)

## Development Guidelines

### Code Quality Standards
- Follow PEP 8 formatting and meaningful variable names
- Run `./tools/run_vulture.sh` before changes to identify unused code
- Remove identified unused code but keep clearly marked future feature stubs
- Use LF line endings (Unix format, not CRLF)
- No emoji characters in code, comments, or output messages

### File and Repository Management
- Never create test files or output directories inside the repository
- Use `/tmp/yamlforge-test-{timestamp}` for all testing and output
- Clean up test artifacts after completion

### YAML Configuration Development
- Study existing examples in `examples/` directory before creating new YAML
- Review schema documentation in `docs/yamlforge-schema.json` 
- Understand the complete YamlForge schema before creating any YAML files
- `docs/yamlforge-schema.json` is THE AUTHORITY - always check it first

### Testing Protocol
- Always read the complete schema FIRST: `docs/yamlforge-schema.json`
- Create unique test directories: `mkdir -p /tmp/yamlforge-test-$(date +%s)`
- Pre-create output directories before running yamlforge.py
- Use unique GUIDs for all test configurations

### Authentication Development
- `config/auth_config.py` handles optional Keycloak integration
- Use `AUTH_DEV_MODE=true` for local testing without OAuth2 Proxy
- Mock user data via environment variables for development
- Test both authenticated and non-authenticated modes

## Critical Implementation Details

### YamlForge Integration
- Direct Python imports only, no subprocess calls
- Execute only `--analyze` mode (no credentials required)
- Handle all provider types including `cheapest` and `cnv`
- `docs/yamlforge-schema.json` is authoritative for validation

### Authentication Architecture
- OAuth2 Proxy handles OIDC at ingress level
- Streamlit extracts user info from headers (`X-Auth-Request-*`)
- Role-based access: `demobuilder-admin`, `demobuilder-power`
- Environment toggle: `KEYCLOAK_ENABLED` controls authentication

### OpenShift Deployment
- Use variable namespaces with `-n` flag, never hardcode
- OAuth2 Proxy deployment when `--enable-auth` specified
- Security context: `runAsNonRoot: true`, no hardcoded UIDs
- S2I deployment script handles both auth and non-auth modes

## Lessons Learned from Development

### AI-Driven Configuration Management
- Pure AI approach with context understanding is more maintainable than static keyword matching
- AI must preserve existing infrastructure when making modifications
- Require specific instance names for removals to prevent AI assumptions
- Post-processing validation with automatic correction is essential

### Schema and Validation
- Cores/Memory vs Flavor: Use either flavor strings OR cores/memory integers, never mix
- RAM terminology: Users say "RAM", "memory", "system memory" - all map to YAML `memory` field
- Auto-fixing: Implement validation with automatic correction rather than just error reporting

### Provider Management
- Start with core enterprise providers (AWS, Azure, GCP, IBM, CNV) rather than all providers
- Logical provider ordering (CNV after IBM providers) improves UX
- Dynamic credentials: Show only relevant setup instructions based on actual provider usage

### OpenShift Deployment Lessons

#### Security Context Constraints (Critical)
- Never use hardcoded UIDs/GIDs: OpenShift assigns dynamic ranges like `[1000890000, 1000899999]`
- Always use `runAsNonRoot: true` for security policies
- Use group permissions: `chgrp -R 0 /app && chmod -R g=u /app`
- Let OpenShift assign security context: Remove `runAsUser` and `fsGroup` from manifests

#### Build and Deployment Process
- Binary builds work best: `oc new-build --binary` for S2I workflows
- Use `-n` flag for namespace management instead of hardcoding in YAML
- Watch build logs: Use `oc start-build --follow` to monitor progress
- Delete and recreate deployments when changing selectors (immutability)

**Critical Requirements for OpenShift:**
- **NEVER** use hardcoded user IDs (`runAsUser: 1001`)
- **NEVER** use hardcoded group IDs (`fsGroup: 1001`) 
- Always use `runAsNonRoot: true`
- Let OpenShift assign UIDs dynamically
- Use group permissions (`chgrp -R 0` and `chmod -R g=u`)

## Technical Implementation Notes

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
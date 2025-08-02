# DemoBuilder Deployment Guide

DemoBuilder is an AI-powered conversational assistant for YamlForge that helps users generate multi-cloud infrastructure configurations through natural language interactions.

## Prerequisites

- **Anthropic API Key**: Required for AI functionality
- **OpenShift cluster** OR **Docker/Podman** for containerized deployment
- **Python 3.11+** for local development

## Environment Variables

DemoBuilder requires the following environment variables:

### Required
- `ANTHROPIC_API_KEY`: Your Anthropic API key for Claude integration

### Optional
- `PORT`: Application port (default: 8501)
- `STREAMLIT_SERVER_PORT`: Streamlit server port (default: 8501)
- `STREAMLIT_SERVER_ADDRESS`: Server address (default: 0.0.0.0)
- `STREAMLIT_SERVER_HEADLESS`: Run in headless mode (default: true)
- `APP_TITLE`: Application title (default: "DemoBuilder - YamlForge Assistant")

## Deployment Options

### Option 1: OpenShift S2I Deployment (Recommended)

**One-Command Deployment:**
```bash
export ANTHROPIC_API_KEY="your-api-key-here"
./demobuilder/deployment/openshift/deploy-s2i.sh
```

**What the script does:**
1. Creates `demobuilder` namespace if needed
2. Builds application from Git source using S2I (Source-to-Image)
3. Configures environment variables and secrets
4. Creates HTTPS route with clean domain name
5. Deploys to OpenShift with proper port configuration

**Manual OpenShift Deployment:**
```bash
# 1. Create namespace
oc new-project demobuilder

# 2. Create S2I application
oc new-app python:3.11-ubi9~https://github.com/rut31337/YamlForge.git \
  --name=demobuilder

# 3. Update service to use correct port
oc delete service demobuilder
oc expose deployment demobuilder --port=8501 --target-port=8501 --name=demobuilder

# 4. Configure secrets
oc create secret generic demobuilder-secrets \
  --from-literal=anthropic-api-key="${ANTHROPIC_API_KEY}"

# 5. Set environment variables
oc set env deployment/demobuilder --from=secret/demobuilder-secrets

# 6. Create HTTPS route
oc create route edge demobuilder \
  --service=demobuilder \
  --port=8501 \
  --hostname=demobuilder.$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}')

# 7. Wait for deployment
oc rollout status deployment/demobuilder
```

**Access Application:**
```bash
# Get application URL
echo "https://$(oc get route demobuilder -n demobuilder -o jsonpath='{.spec.host}')"

# Check deployment status
oc get pods -n demobuilder
oc logs deployment/demobuilder -n demobuilder
```

### Option 2: Docker/Podman Deployment

**Using Docker:**
```bash
# 1. Clone repository
git clone https://github.com/rut31337/YamlForge.git
cd YamlForge

# 2. Build container image
docker build -t demobuilder:latest -f demobuilder/Dockerfile .

# 3. Run container
docker run -d \
  --name demobuilder \
  -p 8501:8501 \
  -e ANTHROPIC_API_KEY="your-api-key-here" \
  -e STREAMLIT_SERVER_PORT=8501 \
  -e STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
  -e STREAMLIT_SERVER_HEADLESS=true \
  demobuilder:latest

# 4. Access application
echo "Application running at: http://localhost:8501"
```

**Using Podman:**
```bash
# 1. Clone repository
git clone https://github.com/rut31337/YamlForge.git
cd YamlForge

# 2. Build container image
podman build -t demobuilder:latest -f demobuilder/Dockerfile .

# 3. Run container
podman run -d \
  --name demobuilder \
  -p 8501:8501 \
  -e ANTHROPIC_API_KEY="your-api-key-here" \
  -e STREAMLIT_SERVER_PORT=8501 \
  -e STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
  -e STREAMLIT_SERVER_HEADLESS=true \
  demobuilder:latest

# 4. Access application
echo "Application running at: http://localhost:8501"
```

**Using Docker Compose:**
```bash
# 1. Navigate to docker deployment directory
cd demobuilder/deployment/docker

# 2. Set environment variables
export ANTHROPIC_API_KEY="your-api-key-here"

# 3. Deploy with compose
docker-compose up -d

# 4. Access application
echo "Application running at: http://localhost:8501"
```

### Option 3: Local Development

**Direct Python Execution:**
```bash
# 1. Clone and setup
git clone https://github.com/rut31337/YamlForge.git
cd YamlForge

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set environment variables
export ANTHROPIC_API_KEY="your-api-key-here"
export STREAMLIT_SERVER_PORT=8501

# 4. Run application
cd demobuilder
streamlit run app.py --server.port=8501 --server.address=0.0.0.0

# 5. Access application
echo "Application running at: http://localhost:8501"
```

## Configuration Details

### Dockerfile Overview
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
WORKDIR /app/demobuilder
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
```

### S2I Configuration
DemoBuilder includes S2I (Source-to-Image) configuration for OpenShift:

**`.s2i/environment`:**
```
PORT=8501
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=0.0.0.0
STREAMLIT_SERVER_HEADLESS=true
APP_TITLE="DemoBuilder - YamlForge Assistant"
ANTHROPIC_API_KEY=""
EXPOSE=8501
```

**`.s2i/bin/run`:**
- Automatically detects if running from repository root
- Changes to `demobuilder` directory if needed
- Starts Streamlit with proper configuration

## Security Considerations

### API Key Management
- **Never commit API keys to version control**
- Use OpenShift secrets or environment variables
- Rotate API keys regularly
- Monitor API usage and costs

### Network Security
- Use HTTPS routes in production (automatic with OpenShift edge termination)
- Implement network policies to restrict access
- Consider authentication/authorization for production deployments

### Container Security
- Uses non-root user in containers
- Minimal base images (python:3.11-slim)
- No privileged capabilities required

## Troubleshooting

### Common Issues

**1. Port Binding Issues:**
```bash
# Check if port 8501 is in use
netstat -tulpn | grep 8501

# Use different port
export STREAMLIT_SERVER_PORT=8502
```

**2. API Key Issues:**
```bash
# Verify API key is set
echo $ANTHROPIC_API_KEY

# Check logs for authentication errors
oc logs deployment/demobuilder -n demobuilder
```

**3. S2I Build Failures:**
```bash
# Check build logs
oc logs build/demobuilder-1 -n demobuilder

# Common issues:
# - Missing git access
# - Python dependency conflicts
# - Resource limits
```

**4. Application Not Accessible:**
```bash
# Check pod status
oc get pods -n demobuilder

# Check service and route
oc get svc,route -n demobuilder

# Verify port configuration
oc describe svc demobuilder -n demobuilder
```

### Health Checks
```bash
# Application health endpoint
curl -f http://localhost:8501/_stcore/health

# In OpenShift
oc exec deployment/demobuilder -- curl -f http://localhost:8501/_stcore/health
```

### Logs and Monitoring
```bash
# View application logs
oc logs -f deployment/demobuilder -n demobuilder

# Monitor resource usage
oc top pods -n demobuilder

# Check events
oc get events -n demobuilder --sort-by='.lastTimestamp'
```

## Scaling and Production

### Horizontal Pod Autoscaler
```bash
# Create HPA for OpenShift
oc autoscale deployment demobuilder --min=2 --max=10 --cpu-percent=70 -n demobuilder
```

### Resource Limits
```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "100m"
  limits:
    memory: "1Gi"
    cpu: "500m"
```

### High Availability
- Deploy multiple replicas
- Use persistent storage for session data (if needed)
- Implement load balancing
- Set up monitoring and alerting

## Integration with YamlForge

DemoBuilder automatically integrates with the YamlForge core engine:

- **Schema Validation**: Uses `yamlforge-schema.json` for configuration validation
- **Provider Analysis**: Leverages YamlForge's `--analyze` functionality  
- **Cost Estimation**: Integrates with YamlForge cost analysis
- **Environment Variables**: Uses `YAMLFORGE_EXCLUDE_PROVIDERS` for provider filtering

No additional YamlForge setup required - everything is included in the container image.

## Support and Documentation

- **YamlForge Documentation**: `../CLAUDE.md`
- **Schema Reference**: `yamlforge-schema.json`
- **API Documentation**: [Anthropic Claude API](https://docs.anthropic.com/)
- **Streamlit Documentation**: [Streamlit Docs](https://docs.streamlit.io/)

## Version Information

- **Python**: 3.11+
- **Streamlit**: 1.29.0+
- **YamlForge**: Latest (bundled)
- **Base Image**: python:3.11-ubi9 (OpenShift S2I)
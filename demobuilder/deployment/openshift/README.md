# DemoBuilder OpenShift Deployment

This directory contains Kustomize manifests for deploying DemoBuilder to OpenShift.

## Prerequisites

- OpenShift cluster access with appropriate permissions
- `oc` CLI configured and logged in
- Access to container registry (internal OpenShift registry or external)

## Quick Deployment

### 1. Deploy with Internal Image Build

```bash
# Navigate to demobuilder directory
cd demobuilder

# Create build configuration (one-time setup)
oc new-build --binary --strategy=docker --name=demobuilder

# Build the image
oc start-build demobuilder --from-dir=. --follow

# Deploy with kustomize
oc apply -k deployment/openshift/

# Check deployment status
oc get pods -n demobuilder
oc get routes -n demobuilder

# Get application URL
./deployment/openshift/get-url.sh
```

### 2. Deploy with External Image

If using an external image registry:

```bash
# Update the image reference in deployment.yaml
# Then deploy
oc apply -k deployment/openshift/
```

## Accessing the Application

### Quick Access Helper

Use the provided script for easy access to your deployed application:

```bash
# Run the helper script
./deployment/openshift/get-url.sh

# Or specify a different namespace
./deployment/openshift/get-url.sh my-namespace
```

### Get Application URLs

Once deployment is complete, retrieve the application URLs:

```bash
# List all routes
oc get routes -n demobuilder

# Get the primary HTTPS URL
echo "DemoBuilder application:"
echo "https://$(oc get route demobuilder -n demobuilder -o jsonpath='{.spec.host}')"

# Get the secure route URL (if different)
echo "Secure route:"
echo "https://$(oc get route demobuilder-secure -n demobuilder -o jsonpath='{.spec.host}')"
```

### Verify Application is Running

```bash
# Check pod status
oc get pods -n demobuilder

# Verify pods are ready (should show 1/1 Ready)
oc get pods -n demobuilder -o wide

# Check application logs
oc logs deployment/demobuilder -n demobuilder

# Test health endpoint
ROUTE_HOST=$(oc get route demobuilder -n demobuilder -o jsonpath='{.spec.host}')
curl -k "https://${ROUTE_HOST}/_stcore/health"
```

### Complete Application Access Example

```bash
# Complete verification and access workflow
echo "=== DemoBuilder Deployment Status ==="

# Check pods
echo "Pod Status:"
oc get pods -n demobuilder

# Check routes
echo -e "\nRoute Status:"
oc get routes -n demobuilder

# Get application URL
echo -e "\n=== Application Access ==="
ROUTE_HOST=$(oc get route demobuilder -n demobuilder -o jsonpath='{.spec.host}')
echo "Application URL: https://${ROUTE_HOST}"
echo "Health Check: https://${ROUTE_HOST}/_stcore/health"

# Test connectivity
echo -e "\n=== Connectivity Test ==="
if curl -k -s "https://${ROUTE_HOST}/_stcore/health" > /dev/null; then
    echo "SUCCESS: Application is accessible and healthy"
    echo "Open your browser to: https://${ROUTE_HOST}"
else
    echo "ERROR: Application health check failed"
    echo "Check pod logs: oc logs deployment/demobuilder -n demobuilder"
fi
```

## Base Image Options

The Dockerfile supports multiple base images for broader accessibility:

### RHEL UBI9 (Default - Recommended for OpenShift)
```bash
# Default build uses RHEL UBI9
oc start-build demobuilder --from-dir=.
```

### Fedora (Alternative for broader access)
```bash
# Build with Fedora base image
oc start-build demobuilder --from-dir=. --build-arg BASE_IMAGE=python:3.11
```

### Custom Base Image
```bash
# Use any Python 3.11+ compatible base image
oc start-build demobuilder --from-dir=. --build-arg BASE_IMAGE=your-registry/python:3.11
```

## Configuration

### Environment Variables

The application is configured via ConfigMap (`configmap.yaml`):

```yaml
data:
  app_title: "DemoBuilder - YamlForge Assistant"
  max_conversation_turns: "10"
  anthropic_model: "claude-3-5-sonnet-20241022"
  context7_enabled: "false"
  context7_mcp_url: ""
  redis_enabled: "false"
  keycloak_enabled: "false"
  log_level: "INFO"
```

### Secrets

API keys and sensitive configuration via Secret (`secret.yaml`):

```yaml
data:
  anthropic-api-key: ""  # Base64 encoded
  redis-url: ""          # Base64 encoded (if Redis enabled)
```

**Important**: Set your Anthropic API key:

```bash
# Set API key from environment variable
oc create secret generic demobuilder-secrets \
  --from-literal=anthropic-api-key="${ANTHROPIC_API_KEY}" \
  -n demobuilder --dry-run=client -o yaml | oc apply -f -
```

## Security Context Constraints

The deployment is configured to work with OpenShift's Security Context Constraints:

- Uses `runAsNonRoot: true`
- No hardcoded user IDs (allows OpenShift to assign)
- Compatible with `restricted-v2` SCC
- Proper group permissions for OpenShift

## Networking

### Services
- **demobuilder**: Internal service on port 8501

### Routes
- **demobuilder**: HTTP route with edge termination
- **demobuilder-secure**: HTTPS route with reencrypt termination

### Network Policy
- Allows ingress from OpenShift router
- Allows internal pod-to-pod communication
- Blocks external traffic except through routes

## Scaling and Resources

### Horizontal Pod Autoscaler
Automatically scales based on CPU/memory usage:
- Min replicas: 2
- Max replicas: 10
- Target CPU: 70%
- Target Memory: 80%

### Resource Limits
Per pod:
- **Requests**: 250m CPU, 512Mi memory
- **Limits**: 500m CPU, 1Gi memory

## Health Checks

### Readiness Probe
- Path: `/_stcore/health`
- Initial delay: 5s
- Period: 10s

### Liveness Probe  
- Path: `/_stcore/health`
- Initial delay: 30s
- Period: 30s

## Troubleshooting

### Common Issues

#### 1. Image Pull Errors
```bash
# Check if build completed successfully
oc get builds -l build=demobuilder

# Check build logs
oc logs build/demobuilder-1

# Verify image stream
oc get imagestream demobuilder
```

#### 2. Security Context Constraints Violations
```bash
# Check pod events for SCC errors
oc describe pod <pod-name> -n demobuilder

# Verify SCC assignment
oc get pod <pod-name> -o yaml | grep "openshift.io/scc"
```

#### 3. Configuration Issues
```bash
# Check configmap
oc get configmap demobuilder-config -o yaml

# Check secrets (values are base64 encoded)
oc get secret demobuilder-secrets -o yaml

# Test configuration in pod
oc exec <pod-name> -- env | grep -E "(ANTHROPIC|APP_)"
```

#### 4. Application Not Starting
```bash
# Check pod logs
oc logs <pod-name> -n demobuilder

# Check streamlit health endpoint
oc exec <pod-name> -- curl -f http://localhost:8501/_stcore/health
```

### Debug Commands

```bash
# Get all resources
oc get all -n demobuilder

# Check events
oc get events -n demobuilder --sort-by='.lastTimestamp'

# Describe deployment
oc describe deployment demobuilder -n demobuilder

# Port forward for local testing
oc port-forward svc/demobuilder 8501:8501 -n demobuilder
```

## Customization

### Kustomize Overlays

Create environment-specific overlays:

```bash
# Create overlay directory
mkdir -p deployment/openshift/overlays/production

# Create kustomization.yaml
cat > deployment/openshift/overlays/production/kustomization.yaml << EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

namespace: demobuilder-prod

resources:
- ../../base

patchesStrategicMerge:
- deployment-patch.yaml

replicas:
- name: demobuilder
  count: 5
EOF

# Deploy overlay
oc apply -k deployment/openshift/overlays/production/
```

### Custom Images

To use a custom image:

1. Update `deployment.yaml`:
```yaml
spec:
  template:
    spec:
      containers:
      - name: demobuilder
        image: your-registry/demobuilder:tag
```

2. Or use kustomize image transformer:
```yaml
images:
- name: demobuilder
  newName: your-registry/demobuilder
  newTag: v1.2.3
```

## Monitoring

### Prometheus Integration

The deployment includes prometheus annotations:
```yaml
annotations:
  prometheus.io/scrape: "false"  # Set to "true" to enable
  prometheus.io/port: "8501"
  prometheus.io/path: "/metrics"
```

### Application Metrics

Streamlit provides health endpoints:
- `/_stcore/health` - Health check
- `/_stcore/metrics` - Application metrics (if enabled)

## Cleanup

```bash
# Delete namespace (removes everything)
oc delete namespace demobuilder

# Or delete individual components
oc delete -k deployment/openshift/

# Clean up build artifacts
oc delete bc,is demobuilder
```

## Production Considerations

### Security
- Use external secret management (e.g., External Secrets Operator)
- Enable network policies
- Use specific image tags, not `latest`
- Regular security updates

### Performance
- Tune resource requests/limits based on usage
- Consider using persistent storage for session data
- Implement proper logging and monitoring

### High Availability
- Spread pods across availability zones
- Use pod disruption budgets
- Configure proper health checks
- Consider external Redis for session persistence

## Support

For issues specific to OpenShift deployment:
1. Check this README troubleshooting section
2. Review pod logs and events
3. Verify OpenShift permissions and quotas
4. Consult OpenShift documentation for SCC and networking
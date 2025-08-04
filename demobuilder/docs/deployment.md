# DemoBuilder Deployment Guide

Complete deployment guide for DemoBuilder in various environments.

## OpenShift S2I Deployment (Recommended)

### Prerequisites
- OpenShift CLI (`oc`) configured and authenticated
- Access to OpenShift cluster with appropriate permissions
- Keycloak instance (if authentication is enabled)

### Environment Variables
- `ANTHROPIC_API_KEY`: Required for AI functionality
- Optional authentication variables (when using `--enable-auth`)

### Basic Deployment

**Simple deployment without authentication:**
```bash
export ANTHROPIC_API_KEY="your-api-key"
./deployment/openshift/deploy-s2i.sh --namespace demobuilder-dev
```

**Deployment with custom route:**
```bash
./deployment/openshift/deploy-s2i.sh \
  --namespace demobuilder-dev \
  --route-host demobuilder-custom.apps.cluster.example.com
```

### Authentication-Enabled Deployment

**Deploy with Keycloak authentication:**
```bash
./deployment/openshift/deploy-s2i.sh \
  --namespace demobuilder-dev \
  --enable-auth \
  --keycloak-url https://keycloak.example.com \
  --realm master \
  --client-id demobuilder \
  --client-secret your-keycloak-client-secret
```

### Deployment Script Options

| Option | Description | Default |
|--------|-------------|---------|
| `--namespace NAME` | Target namespace | `demobuilder` |
| `--enable-auth` | Enable Keycloak authentication | `false` |
| `--keycloak-url URL` | Keycloak server URL | - |
| `--realm NAME` | Keycloak realm | `master` |
| `--client-id ID` | Keycloak client ID | `demobuilder` |
| `--client-secret SECRET` | Keycloak client secret | - |
| `--route-host HOST` | Custom route hostname | auto-generated |

### Post-Deployment Operations

**Check deployment status:**
```bash
oc get pods -n demobuilder-dev
oc get routes -n demobuilder-dev
```

**View logs:**
```bash
oc logs -f deployment/demobuilder -n demobuilder-dev
oc logs -f deployment/oauth2-proxy -n demobuilder-dev  # If auth enabled
```

**Scale deployment:**
```bash
oc scale deployment/demobuilder --replicas=3 -n demobuilder-dev
```

**Clean up:**
```bash
oc delete project demobuilder-dev
```

## Docker Deployment

### Build and Run Locally

```bash
# Build container
docker build -t demobuilder:latest .

# Run with environment variables
docker run -p 8501:8501 \
  -e ANTHROPIC_API_KEY="your-api-key" \
  demobuilder:latest
```

### Docker Compose

```yaml
version: '3.8'
services:
  demobuilder:
    build: .
    ports:
      - "8501:8501"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - KEYCLOAK_ENABLED=false
```

## Traditional OpenShift Build

### Manual Build Process

```bash
# Create build config
oc new-build --binary --strategy=docker --name=demobuilder -n demobuilder-dev

# Build image from source
oc start-build demobuilder --from-dir=. --follow -n demobuilder-dev

# Deploy using Kustomize
oc apply -k deployment/openshift/ -n demobuilder-dev

# Monitor deployment
oc rollout status deployment/demobuilder -n demobuilder-dev
```

## Security Context Constraints

### OpenShift Security Requirements

- **NEVER** use hardcoded user IDs (`runAsUser: 1001`)
- **NEVER** use hardcoded group IDs (`fsGroup: 1001`)
- Always use `runAsNonRoot: true`
- Let OpenShift assign UIDs dynamically
- Use group permissions (`chgrp -R 0` and `chmod -R g=u`)

### Working Security Context

```yaml
securityContext:
  runAsNonRoot: true
containers:
- name: demobuilder
  securityContext:
    allowPrivilegeEscalation: false
    readOnlyRootFilesystem: false
    runAsNonRoot: true
    capabilities:
      drop: [ALL]
```

## Base Image Selection

### RHEL UBI9 (Default - Production)
```bash
# Uses RHEL UBI9 Python 3.11
oc start-build demobuilder --from-dir=. --follow
```

### Fedora (Alternative)
```bash
# Use Fedora base for broader access
oc start-build demobuilder --from-dir=. --build-arg BASE_IMAGE=python:3.11
```

### Custom Base Images
```bash
# Use any Python 3.11+ compatible image
oc start-build demobuilder --from-dir=. --build-arg BASE_IMAGE=registry.company.com/python:3.11
```

## Configuration Management

### ConfigMaps
```bash
# View current configuration
oc get configmap demobuilder-config -o yaml -n demobuilder-dev

# Update configuration
oc edit configmap demobuilder-config -n demobuilder-dev
```

### Secrets Management
```bash
# Create secrets
oc create secret generic demobuilder-secrets \
  --from-literal=anthropic-api-key="$ANTHROPIC_API_KEY" \
  -n demobuilder-dev

# Verify secrets
oc get secret demobuilder-secrets -o yaml -n demobuilder-dev
```

## Networking and Routes

### Internal Service
- Port 8501 (Streamlit default)
- ClusterIP service for internal communication

### External Access
- HTTP route: Auto-generated or custom hostname
- HTTPS route: TLS edge termination
- OAuth2 Proxy route: When authentication enabled

### Network Policies
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: demobuilder-netpol
spec:
  podSelector:
    matchLabels:
      app: demobuilder
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: openshift-ingress
```

## Troubleshooting

### Common Issues

**Image Pull Errors:**
```bash
# Check build status
oc get builds -l build=demobuilder -n demobuilder-dev
oc logs build/demobuilder-1 -n demobuilder-dev

# Verify image in registry
oc get imagestream demobuilder -n demobuilder-dev
```

**Security Context Violations:**
```bash
# Check for SCC errors
oc describe pod <pod-name> -n demobuilder-dev
oc get events --field-selector reason=FailedCreate -n demobuilder-dev
```

**Application Startup Issues:**
```bash
# Check pod logs
oc logs <pod-name> -n demobuilder-dev

# Verify health endpoint
oc exec <pod-name> -n demobuilder-dev -- curl -f http://localhost:8501/_stcore/health
```

**Authentication Problems:**
```bash
# Check OAuth2 Proxy logs
oc logs deployment/oauth2-proxy -n demobuilder-dev

# Verify secrets
oc get secret oauth2-proxy-secrets -o yaml -n demobuilder-dev

# Test redirect URL
curl -I https://your-route/oauth2/auth
```

### Performance Tuning

**Resource Requests/Limits:**
```yaml
resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

**Horizontal Pod Autoscaler:**
```bash
oc autoscale deployment demobuilder --cpu-percent=70 --min=2 --max=10 -n demobuilder-dev
```

## Production Deployment Checklist

### Security
- [ ] Use specific image tags, not `latest`
- [ ] Implement external secret management
- [ ] Enable network policies
- [ ] Regular security updates
- [ ] Resource quotas and limits

### Performance
- [ ] Tune resource requests/limits based on load testing
- [ ] Configure horizontal pod autoscaler
- [ ] Implement persistent storage for sessions if needed
- [ ] Set up proper monitoring and alerting

### High Availability
- [ ] Multiple replicas across availability zones
- [ ] Pod disruption budgets
- [ ] Proper health checks with appropriate timeouts
- [ ] External Redis for session persistence

### Monitoring
- [ ] Application metrics collection
- [ ] Log aggregation
- [ ] Health check monitoring
- [ ] Performance baseline establishment
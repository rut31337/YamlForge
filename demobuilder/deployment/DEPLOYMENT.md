# DemoBuilder OpenShift Deployment Guide

This guide provides comprehensive instructions for deploying DemoBuilder on OpenShift clusters.

## 📋 Prerequisites

### OpenShift Cluster Requirements
- OpenShift 4.8+ or Kubernetes 1.21+
- Cluster admin access or sufficient RBAC permissions
- Access to container registry (for custom images)
- **Required**: Anthropic API key (DemoBuilder is a conversational AI application)
- Optional: Context7 API key for enhanced infrastructure knowledge
- Optional: Persistent storage for Redis (future enhancement)

### Local Tools Required
```bash
# Install OpenShift CLI
curl -O https://mirror.openshift.com/pub/openshift-v4/clients/ocp/latest/openshift-client-linux.tar.gz
tar -xvf openshift-client-linux.tar.gz
sudo mv oc kubectl /usr/local/bin/

# Install Kustomize (optional)
curl -s "https://raw.githubusercontent.com/kubernetes-sigs/kustomize/master/hack/install_kustomize.sh" | bash
sudo mv kustomize /usr/local/bin/

# Verify tools
oc version
kubectl version --client
```

## 🚀 Quick Deployment

### Method 1: Direct Apply (Recommended for Testing)

1. **Login to OpenShift**:
   ```bash
   oc login https://api.your-cluster.com:6443
   ```

2. **Deploy DemoBuilder** (creates namespace and empty secret automatically):
   ```bash
   cd demobuilder/deployment/openshift
   oc apply -f .
   ```

3. **Add your Anthropic API key** (required for DemoBuilder to function):
   ```bash
   # Set your API key as an environment variable (easier for copy/paste)
   export ANTHROPIC_API_KEY="your-anthropic-api-key-here"
   
   # Add the key to the secret
   oc patch secret demobuilder-secrets -n demobuilder \
     --type='json' -p='[{"op": "add", "path": "/data/anthropic-api-key", "value":"'$(echo -n "$ANTHROPIC_API_KEY" | base64)'"}]'
   
   # Restart to pick up the API key
   oc rollout restart deployment/demobuilder -n demobuilder
   ```

4. **Get the application URL**:
   ```bash
   oc get route demobuilder -n demobuilder -o jsonpath='{.spec.host}'
   ```

5. **Access DemoBuilder**:
   ```
   https://demobuilder-demobuilder.apps.your-cluster.com
   ```

### Method 2: Using Kustomize (Recommended for Production)

1. **Build and apply with Kustomize** (creates namespace and empty secret automatically):
   ```bash
   cd demobuilder/deployment/openshift
   oc apply -k .
   ```

   **Note**: The kustomization.yaml uses modern syntax (not deprecated fields). If you have an older version of kustomize and see warnings about `commonLabels` or `patchesStrategicMerge`, upgrade to kustomize v4.1+ or use `kustomize edit fix` to automatically update deprecated syntax.

2. **Add your Anthropic API key** (required for DemoBuilder to function):
   ```bash
   # Set your API key as an environment variable (easier for copy/paste)
   export ANTHROPIC_API_KEY="your-anthropic-api-key-here"
   
   # Add the key to the secret
   oc patch secret demobuilder-secrets -n demobuilder \
     --type='json' -p='[{"op": "add", "path": "/data/anthropic-api-key", "value":"'$(echo -n "$ANTHROPIC_API_KEY" | base64)'"}]'
   
   # Restart to pick up the API key
   oc rollout restart deployment/demobuilder -n demobuilder
   ```

3. **Verify deployment**:
   ```bash
   oc get all -n demobuilder
   
   # Check that all pods are running
   oc get pods -n demobuilder
   
   # Verify labels are applied correctly
   oc get deployment demobuilder -n demobuilder -o yaml | grep -A 10 labels
   ```

## 🔧 Configuration Options

### Environment Variables

Edit `configmap.yaml` to customize application behavior:

```yaml
data:
  # Application settings
  app_title: "Your Custom Title"
  max_conversation_turns: "100"
  
  # AI Configuration (current production model)
  anthropic_model: "claude-3-5-sonnet-20241022"
  
  # Context7 MCP Integration for enhanced infrastructure knowledge
  context7_enabled: "true"
  context7_mcp_url: "https://mcp.context7.com/mcp"
  
  # Optional features (disabled by default)
  redis_enabled: "false"
  keycloak_enabled: "false"
  
  # Logging level (INFO, DEBUG, WARNING, ERROR)
  log_level: "INFO"
```

### Secrets Management

The deployment creates an empty secret that you need to populate with your API keys:

**Step 1: Deploy the application first** (this creates the empty secret):
```bash
cd demobuilder/deployment/openshift
oc apply -k .  # or oc apply -f .
```

**Step 2: Add your API keys to the existing secret**:
```bash
# Set your API keys as environment variables (easier for copy/paste)
export ANTHROPIC_API_KEY="your-anthropic-api-key-here"
export CONTEXT7_API_KEY="your-context7-api-key-here"  # Optional

# Add Anthropic API key (REQUIRED - DemoBuilder needs this to function)
oc patch secret demobuilder-secrets -n demobuilder \
  --type='json' -p='[{"op": "add", "path": "/data/anthropic-api-key", "value":"'$(echo -n "$ANTHROPIC_API_KEY" | base64)'"}]'

# Optionally add Context7 API key for enhanced infrastructure knowledge
oc patch secret demobuilder-secrets -n demobuilder \
  --type='json' -p='[{"op": "add", "path": "/data/context7-api-key", "value":"'$(echo -n "$CONTEXT7_API_KEY" | base64)'"}]'

# Restart deployment to pick up the new secrets
oc rollout restart deployment/demobuilder -n demobuilder
```

**Alternative: Pre-populate before deployment** (advanced users):
```bash
# Edit the secret.yaml file directly before applying
# Add your base64-encoded keys to the data section:
echo -n "your-anthropic-api-key" | base64  # Copy this value
# Edit demobuilder/deployment/openshift/secret.yaml
# Then deploy normally
```

**Update existing secrets**:
```bash
# Set your new API key as an environment variable
export ANTHROPIC_API_KEY="your-new-anthropic-api-key"

# Update Anthropic API key
oc patch secret demobuilder-secrets -n demobuilder \
  --type='json' -p='[{"op": "replace", "path": "/data/anthropic-api-key", "value":"'$(echo -n "$ANTHROPIC_API_KEY" | base64)'"}]'

# Restart to apply changes
oc rollout restart deployment/demobuilder -n demobuilder
```

**Note**: While DemoBuilder does not require cloud credentials for YAML generation and cost analysis, it **requires an Anthropic API key** to function as it is a conversational AI application.

### Resource Limits

Adjust resource requests and limits in `deployment.yaml`:

```yaml
resources:
  requests:
    memory: "512Mi"   # Minimum for 2 concurrent users
    cpu: "250m"       # Minimum for basic operation
  limits:
    memory: "1Gi"     # Maximum for 10+ concurrent users
    cpu: "500m"       # Maximum for heavy workloads
```

### Scaling Configuration

Modify `horizontalpodautoscaler.yaml` for auto-scaling:

```yaml
spec:
  minReplicas: 2      # Always maintain 2 pods
  maxReplicas: 10     # Scale up to 10 pods under load
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70  # Scale at 70% CPU
```

## 🏗️ Custom Image Build

### Building Your Own Container Image

1. **Build the image**:
   ```bash
   cd demobuilder
   
   # Using Docker
   docker build -t your-registry/demobuilder:v1.0.0 .
   
   # Using Podman
   podman build -t your-registry/demobuilder:v1.0.0 .
   
   # Using OpenShift BuildConfig
   oc new-build --binary --name=demobuilder
   oc start-build demobuilder --from-dir=. --follow
   ```

2. **Push to registry**:
   ```bash
   # Docker/Podman
   docker push your-registry/demobuilder:v1.0.0
   
   # OpenShift internal registry
   oc tag demobuilder:latest your-registry/demobuilder:v1.0.0
   ```

3. **Update deployment**:
   ```bash
   # Update image reference in kustomization.yaml
   images:
   - name: demobuilder
     newName: your-registry/demobuilder
     newTag: v1.0.0
   
   # Apply changes
   oc apply -k .
   ```

### Using OpenShift Source-to-Image (S2I)

1. **Create BuildConfig from source**:
   ```bash
   oc new-app python:3.11~https://github.com/your-org/yamlforge.git \
     --context-dir=demobuilder \
     --name=demobuilder \
     -n demobuilder
   ```

2. **Trigger build**:
   ```bash
   oc start-build demobuilder -n demobuilder --follow
   ```

## 🔒 Security Configuration

### Network Policies

The included `networkpolicy.yaml` provides:
- Ingress only from OpenShift router
- Egress for DNS, HTTPS, and internal communication
- Isolation from other namespaces

### RBAC Permissions

Default service account has minimal permissions:
- Read ConfigMaps and Secrets in own namespace
- Read pods for health checks
- Future: CNV resource access for VM management

### Security Context

Pods run with security hardening:
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1001
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: false
  capabilities:
    drop: [ALL]
```

## 🔍 Monitoring and Observability

### Health Checks

Built-in health endpoints:
- **Liveness**: `/_stcore/health` (checks if app is responsive)
- **Readiness**: `/_stcore/health` (checks if app can serve traffic)

### Logging

Application logs are sent to stdout and collected by OpenShift:

```bash
# View logs
oc logs -f deployment/demobuilder -n demobuilder

# View logs from all pods
oc logs -f -l app=demobuilder -n demobuilder

# Stream logs
oc logs --tail=100 -f pod/demobuilder-xxx-xxx -n demobuilder
```

### Metrics (Optional)

To enable Prometheus monitoring:

1. **Add monitoring labels**:
   ```yaml
   metadata:
     annotations:
       prometheus.io/scrape: "true"
       prometheus.io/port: "8501"
       prometheus.io/path: "/metrics"
   ```

2. **Create ServiceMonitor**:
   ```yaml
   apiVersion: monitoring.coreos.com/v1
   kind: ServiceMonitor
   metadata:
     name: demobuilder
     namespace: demobuilder
   spec:
     selector:
       matchLabels:
         app: demobuilder
     endpoints:
     - port: http
   ```

## 🚀 Advanced Deployment Scenarios

### Multi-Environment Setup

**Development Environment**:
```bash
# Create dev namespace
oc create namespace demobuilder-dev

# Deploy with reduced resources
sed 's/namespace: demobuilder/namespace: demobuilder-dev/g' deployment.yaml | \
sed 's/replicas: 2/replicas: 1/g' | \
oc apply -f -
```

**Production Environment**:
```bash
# Use production configuration
oc apply -k overlays/production/
```

### Custom Domain Configuration

1. **Update route with custom hostname**:
   ```yaml
   apiVersion: route.openshift.io/v1
   kind: Route
   metadata:
     name: demobuilder-custom
   spec:
     host: demobuilder.company.com
     tls:
       termination: edge
       certificate: |
         -----BEGIN CERTIFICATE-----
         # Your custom certificate
         -----END CERTIFICATE-----
       key: |
         -----BEGIN PRIVATE KEY-----
         # Your private key
         -----END PRIVATE KEY-----
   ```

2. **Configure DNS**:
   ```bash
   # Add CNAME record pointing to OpenShift router
   demobuilder.company.com CNAME router-default.apps.cluster.com
   ```

### High Availability Setup

1. **Multi-zone deployment**:
   ```yaml
   spec:
     template:
       spec:
         affinity:
           podAntiAffinity:
             preferredDuringSchedulingIgnoredDuringExecution:
             - weight: 100
               podAffinityTerm:
                 labelSelector:
                   matchExpressions:
                   - key: app
                     operator: In
                     values: [demobuilder]
                 topologyKey: topology.kubernetes.io/zone
   ```

2. **Enable persistent storage** (for future Redis integration):
   ```yaml
   volumeClaimTemplates:
   - metadata:
       name: redis-data
     spec:
       accessModes: [ReadWriteOnce]
       resources:
         requests:
           storage: 1Gi
   ```

## 🔧 Troubleshooting

### Common Issues

**Pod CrashLoopBackOff**:
```bash
# Check pod logs
oc logs pod/demobuilder-xxx-xxx -n demobuilder

# Check events
oc get events -n demobuilder --sort-by='.lastTimestamp'

# Describe pod for detailed info
oc describe pod/demobuilder-xxx-xxx -n demobuilder
```

**Image Pull Errors**:
```bash
# Check if image exists
oc describe deployment demobuilder -n demobuilder

# Verify image pull secrets
oc get secrets -n demobuilder
```

**Route Not Accessible**:
```bash
# Check route status
oc get route demobuilder -n demobuilder -o yaml

# Verify service endpoints
oc get endpoints demobuilder -n demobuilder

# Test internal connectivity
oc rsh deployment/demobuilder curl localhost:8501/_stcore/health
```

**Resource Issues**:
```bash
# Check resource usage
oc top pods -n demobuilder

# Check HPA status
oc get hpa -n demobuilder

# Check node resources
oc describe node
```

### Debug Mode

Enable debug logging:
```bash
# Update ConfigMap for debug logging
oc patch configmap demobuilder-config -n demobuilder \
  --type merge -p '{"data":{"log_level":"DEBUG"}}'

# Restart deployment to apply changes
oc rollout restart deployment/demobuilder -n demobuilder

# Monitor logs for debugging
oc logs -f deployment/demobuilder -n demobuilder
```

### AI Configuration Troubleshooting

**Anthropic Model Issues**:
```bash
# Verify correct model format (should be: claude-3-5-sonnet-20241022)
oc get configmap demobuilder-config -n demobuilder -o yaml | grep anthropic_model

# Update to latest model if needed
oc patch configmap demobuilder-config -n demobuilder \
  --type merge -p '{"data":{"anthropic_model":"claude-3-5-sonnet-20241022"}}'
```

**Context7 Integration Issues**:
```bash
# Check Context7 MCP configuration
oc get configmap demobuilder-config -n demobuilder -o yaml | grep context7

# Disable Context7 if experiencing connectivity issues
oc patch configmap demobuilder-config -n demobuilder \
  --type merge -p '{"data":{"context7_enabled":"false"}}'
```

**Secret Management Issues**:
```bash
# Check if secret exists and what keys it contains
oc get secret demobuilder-secrets -n demobuilder -o yaml

# View secret keys (without values)
oc get secret demobuilder-secrets -n demobuilder -o jsonpath='{.data}' | jq -r 'keys[]'

# If secret exists error occurs during creation:
oc delete secret demobuilder-secrets -n demobuilder --ignore-not-found=true
oc create secret generic demobuilder-secrets \
  --from-literal=anthropic-api-key="your-key" \
  -n demobuilder

# Verify deployment picks up secret changes
oc rollout status deployment/demobuilder -n demobuilder
```

**Kustomize Deployment Issues**:
```bash
# If you see deprecation warnings about commonLabels or patchesStrategicMerge
# The current kustomization.yaml uses modern syntax, but if you have issues:

# Check kustomize version (should be v4.1+)
kustomize version

# If using older version, you can build separately and apply
kustomize build demobuilder/deployment/openshift | oc apply -f -

# For namespace annotation warnings, apply namespace first
oc apply -f demobuilder/deployment/openshift/namespace.yaml
oc apply -k demobuilder/deployment/openshift
```

### Performance Tuning

**For high concurrency**:
```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "2Gi"
    cpu: "1000m"
```

**For development/testing**:
```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "512Mi"
    cpu: "250m"
```

## 📝 Maintenance

### Updates and Rollbacks

**Update application**:
```bash
# Update image tag
oc patch deployment demobuilder -n demobuilder \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"demobuilder","image":"demobuilder:v1.1.0"}]}}}}'

# Monitor rollout
oc rollout status deployment/demobuilder -n demobuilder
```

**Rollback if needed**:
```bash
# View rollout history
oc rollout history deployment/demobuilder -n demobuilder

# Rollback to previous version
oc rollout undo deployment/demobuilder -n demobuilder
```

### Backup and Restore

**Configuration backup**:
```bash
# Backup all resources
oc get all,configmap,secret,route -n demobuilder -o yaml > demobuilder-backup.yaml

# Backup specific configurations
oc get configmap demobuilder-config -n demobuilder -o yaml > config-backup.yaml
```

**Restore configuration**:
```bash
# Restore from backup
oc apply -f demobuilder-backup.yaml
```

## 🎯 Next Steps

1. **Access your deployed DemoBuilder** at the route URL
2. **Test the application** with sample infrastructure requirements
3. **Configure monitoring** if required for production use
4. **Set up CI/CD pipelines** for automated deployments
5. **Enable additional features** like Keycloak SSO when ready

For issues or questions, refer to the main DemoBuilder documentation or create an issue in the YamlForge repository.
# DemoBuilder OpenShift Deployment

This guide covers deploying DemoBuilder to OpenShift using Source-to-Image (S2I) builds that pull directly from the Git repository.

## Prerequisites

- OpenShift cluster access with appropriate permissions
- `oc` CLI configured and logged in
- Git repository access (public or with credentials configured)

## Quick S2I Deployment

### 1. Create New Application with S2I

Deploy DemoBuilder directly from the Git repository using OpenShift's S2I capability:

```bash
# Create a new application from the Git repository
oc new-app python:3.11~https://github.com/rut31337/YamlForge.git \
  --context-dir=demobuilder \
  --name=demobuilder \
  --env=PORT=8501

# Expose the service
oc expose svc/demobuilder

# Create secure route (optional)
oc create route edge demobuilder-secure --service=demobuilder --port=8501
```

### 2. Configure Environment Variables

Set up required configuration and API keys:

```bash
# Create secret for API keys
oc create secret generic demobuilder-secrets \
  --from-literal=anthropic-api-key="${ANTHROPIC_API_KEY}"

# Create configmap for application settings
oc create configmap demobuilder-config \
  --from-literal=app_env="production" \
  --from-literal=anthropic_model="claude-3-5-sonnet-20241022" \
  --from-literal=ai_enabled="true"

# Update deployment to use secrets and configmap
oc set env deployment/demobuilder --from=secret/demobuilder-secrets
oc set env deployment/demobuilder --from=configmap/demobuilder-config
```

### 3. Advanced S2I Configuration

For more control over the build process, create a BuildConfig manually:

```bash
# Create BuildConfig with specific Git branch/tag
oc create -f - <<EOF
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: demobuilder
  labels:
    app: demobuilder
spec:
  source:
    type: Git
    git:
      uri: https://github.com/rut31337/YamlForge.git
      ref: master
    contextDir: demobuilder
  strategy:
    type: Source
    sourceStrategy:
      from:
        kind: ImageStreamTag
        name: python:3.11
      env:
        - name: ENABLE_PIPENV
          value: "0"
        - name: UPGRADE_PIP_TO_LATEST
          value: "1"
  output:
    to:
      kind: ImageStreamTag
      name: demobuilder:latest
  triggers:
    - type: ConfigChange
    - type: GitHub
      github:
        secret: webhook-secret
    - type: Generic
      generic:
        secret: webhook-secret
EOF

# Create ImageStream
oc create imagestream demobuilder

# Start the build
oc start-build demobuilder --follow
```

## Deployment Options

### Option A: Using Kustomize (Recommended)

Deploy using the provided Kustomize manifests after building the image:

```bash
# Ensure the image exists
oc get imagestream demobuilder

# Deploy with kustomize
oc apply -k deployment/openshift/

# Check deployment
oc get pods -n demobuilder
```

### Option B: Simple Deployment

Create a basic deployment directly:

```bash
# Create deployment
oc create deployment demobuilder --image=image-registry.openshift-image-registry.svc:5000/$(oc project -q)/demobuilder:latest

# Set environment variables
oc set env deployment/demobuilder \
  --from=secret/demobuilder-secrets \
  --from=configmap/demobuilder-config

# Expose the service
oc expose deployment/demobuilder --port=8501 --target-port=8501
oc expose service/demobuilder
```

## Webhook Configuration (Optional)

Set up automatic builds when code is pushed to Git:

```bash
# Get webhook URL
WEBHOOK_URL=$(oc describe bc demobuilder | grep "Webhook GitHub" -A 1 | tail -1 | awk '{print $2}')

echo "Add this webhook URL to your GitHub repository:"
echo "$WEBHOOK_URL"

# Configure webhook secret (if needed)
oc set triggers bc/demobuilder --from-github --remove
oc set triggers bc/demobuilder --from-github=webhook-secret-value
```

## Troubleshooting S2I Builds

### Common Issues and Solutions

1. **Build Fails - Missing Dependencies**:
```bash
# Check build logs
oc logs build/demobuilder-1

# Verify requirements.txt exists in context directory
oc describe bc demobuilder | grep "Context Dir"
```

2. **Python Version Issues**:
```bash
# Use specific Python version
oc patch bc demobuilder -p '{"spec":{"strategy":{"sourceStrategy":{"from":{"name":"python:3.11"}}}}}'

# Or try UBI Python image
oc patch bc demobuilder -p '{"spec":{"strategy":{"sourceStrategy":{"from":{"name":"ubi9/python-311"}}}}}'
```

3. **Application Won't Start**:
```bash
# Check if app.py is in the right location
oc exec deployment/demobuilder -- ls -la /opt/app-root/src/

# Check Streamlit port configuration
oc exec deployment/demobuilder -- cat /opt/app-root/src/app.py | head -20
```

4. **Dependency Installation Issues**:
```bash
# Force pip upgrade during build
oc set env bc/demobuilder UPGRADE_PIP_TO_LATEST=1

# Disable pipenv if causing issues
oc set env bc/demobuilder ENABLE_PIPENV=0

# Rebuild
oc start-build demobuilder --follow
```

## Monitoring and Maintenance

### Check Application Status

```bash
# Get application URL
./deployment/openshift/get-url.sh

# Check pod health
oc get pods -l app=demobuilder -o wide

# View application logs
oc logs -f deployment/demobuilder

# Check resource usage
oc top pods -l app=demobuilder
```

### Update Application

```bash
# Trigger new build from latest Git
oc start-build demobuilder --follow

# Force deployment rollout
oc rollout restart deployment/demobuilder

# Check rollout status
oc rollout status deployment/demobuilder
```

### Scaling

```bash
# Scale up for high availability
oc scale deployment/demobuilder --replicas=3

# Enable autoscaling
oc autoscale deployment/demobuilder --min=2 --max=10 --cpu-percent=70
```

## Configuration Management

### Environment Variables

```bash
# View current configuration
oc set env deployment/demobuilder --list

# Update API model
oc patch configmap demobuilder-config \
  --type merge -p '{"data":{"anthropic_model":"claude-3-5-sonnet-20241022"}}'

# Update API key
oc create secret generic demobuilder-secrets \
  --from-literal=anthropic-api-key="new-key" \
  --dry-run=client -o yaml | oc apply -f -

# Restart to pick up changes
oc rollout restart deployment/demobuilder
```

### Resource Limits

```bash
# Set resource limits
oc set resources deployment/demobuilder \
  --requests=cpu=200m,memory=512Mi \
  --limits=cpu=1000m,memory=1Gi
```

## Security Configuration

### Network Policies

```bash
# Apply network policies (if using the kustomize deployment)
oc apply -f deployment/openshift/networkpolicy.yaml
```

### Service Account

```bash
# Create dedicated service account
oc create serviceaccount demobuilder

# Use custom service account
oc patch deployment demobuilder -p '{"spec":{"template":{"spec":{"serviceAccountName":"demobuilder"}}}}'
```

## Complete Deployment Example

Here's a complete deployment workflow:

```bash
#!/bin/bash
set -e

echo "=== DemoBuilder S2I Deployment ==="

# 1. Create new S2I application
echo "Creating S2I application..."
oc new-app python:3.11~https://github.com/rut31337/YamlForge.git \
  --context-dir=demobuilder \
  --name=demobuilder \
  --env=PORT=8501

# 2. Create configuration
echo "Setting up configuration..."
oc create secret generic demobuilder-secrets \
  --from-literal=anthropic-api-key="${ANTHROPIC_API_KEY}" \
  --dry-run=client -o yaml | oc apply -f -

oc create configmap demobuilder-config \
  --from-literal=app_env="production" \
  --from-literal=anthropic_model="claude-3-5-sonnet-20241022" \
  --from-literal=ai_enabled="true" \
  --dry-run=client -o yaml | oc apply -f -

# 3. Configure deployment
echo "Configuring deployment..."
oc set env deployment/demobuilder --from=secret/demobuilder-secrets
oc set env deployment/demobuilder --from=configmap/demobuilder-config

# 4. Expose service
echo "Exposing service..."
oc expose svc/demobuilder
oc create route edge demobuilder-secure --service=demobuilder --port=8501 || true

# 5. Wait for deployment
echo "Waiting for deployment..."
oc rollout status deployment/demobuilder --timeout=300s

# 6. Show results
echo "=== Deployment Complete ==="
oc get pods -l app=demobuilder
oc get routes

echo ""
echo "Application URLs:"
echo "HTTP:  http://$(oc get route demobuilder -o jsonpath='{.spec.host}')"
echo "HTTPS: https://$(oc get route demobuilder-secure -o jsonpath='{.spec.host}')"
```

Save this as `deploy-s2i.sh` and run it for a complete S2I deployment.
#!/bin/bash
set -e

echo "=== DemoBuilder S2I Deployment ==="

# Check if ANTHROPIC_API_KEY is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Error: ANTHROPIC_API_KEY environment variable is not set"
    echo "Please set it with: export ANTHROPIC_API_KEY='your-api-key'"
    exit 1
fi

# 1. Create new S2I application
echo "Creating S2I application..."
oc new-app python:3.11-ubi9~https://github.com/rut31337/YamlForge.git \
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
# Remove any incorrect environment variable and set it properly
oc set env deployment/demobuilder ANTHROPIC_API_KEY-
oc set env deployment/demobuilder --from=secret/demobuilder-secrets

# 4. Create single HTTPS route with clean domain name
echo "Creating HTTPS route..."
oc create route edge demobuilder \
  --service=demobuilder \
  --port=8501 \
  --hostname=demobuilder.$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}')

# 5. Wait for deployment
echo "Waiting for deployment..."
oc rollout status deployment/demobuilder --timeout=300s

# 6. Show results
echo "=== Deployment Complete ==="
oc get pods -l app=demobuilder
oc get routes

echo ""
echo "Application URL:"
echo "HTTPS: https://$(oc get route demobuilder -o jsonpath='{.spec.host}')"

echo ""
echo "To check logs: oc logs -f deployment/demobuilder"
echo "To scale up: oc scale deployment/demobuilder --replicas=3"
echo "To delete: oc delete all -l app=demobuilder"
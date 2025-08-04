#!/bin/bash
set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# DemoBuilder S2I Deployment with Optional Keycloak Authentication
# Usage: ./deploy-s2i.sh [options]
# 
# Options:
#   --namespace NAME          Target namespace (default: demobuilder)
#   --enable-auth            Enable Keycloak authentication via OAuth2 Proxy
#   --keycloak-realm-url URL Full Keycloak realm URL (required if --enable-auth)
#                            Example: https://keycloak.example.com/auth/realms/master
#   --client-id ID           Keycloak client ID (default: demobuilder)
#   --client-secret SECRET   Keycloak client secret (required if --enable-auth)
#   --route-host HOST        Custom route hostname (optional)
#   --app-port PORT          Application port (default: 8501)
#   --help                   Show this help message

# Default values
NAMESPACE="demobuilder"
ENABLE_AUTH="false"
KEYCLOAK_REALM_URL=""
KEYCLOAK_URL=""
KEYCLOAK_REALM=""
KEYCLOAK_CLIENT_ID="demobuilder"
KEYCLOAK_CLIENT_SECRET=""
ROUTE_HOST=""
APP_PORT="8501"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --enable-auth)
            ENABLE_AUTH="true"
            shift
            ;;
        --keycloak-realm-url)
            KEYCLOAK_REALM_URL="$2"
            shift 2
            ;;
        --client-id)
            KEYCLOAK_CLIENT_ID="$2"
            shift 2
            ;;
        --client-secret)
            KEYCLOAK_CLIENT_SECRET="$2"
            shift 2
            ;;
        --route-host)
            ROUTE_HOST="$2"
            shift 2
            ;;
        --app-port)
            APP_PORT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Deploy DemoBuilder with S2I build and optional Keycloak authentication"
            echo ""
            echo "Options:"
            echo "  --namespace NAME          Target namespace (default: demobuilder)"
            echo "  --enable-auth            Enable Keycloak authentication via OAuth2 Proxy"
            echo "  --keycloak-realm-url URL Full Keycloak realm URL (required if --enable-auth)"
            echo "                           Example: https://keycloak.example.com/auth/realms/master"
            echo "  --client-id ID           Keycloak client ID (default: demobuilder)"
            echo "  --client-secret SECRET   Keycloak client secret (required if --enable-auth)"
            echo "  --route-host HOST        Custom route hostname (optional)"
            echo "  --app-port PORT          Application port (default: 8501)"
            echo "  --help                   Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  ANTHROPIC_API_KEY        Required: Your Anthropic API key"
            echo ""
            echo "Examples:"
            echo "  # Deploy to demobuilder-dev without authentication"
            echo "  $0 --namespace demobuilder-dev"
            echo ""
            echo "  # Deploy with Keycloak authentication"
            echo "  $0 --namespace demobuilder-dev --enable-auth \\"
            echo "     --keycloak-realm-url https://keycloak.example.com/auth/realms/master \\"
            echo "     --client-secret your-secret-here"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "=== DemoBuilder S2I Deployment ==="
echo "Namespace: $NAMESPACE"
echo "Authentication: $ENABLE_AUTH"

# Validate required parameters
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "Error: ANTHROPIC_API_KEY environment variable is not set"
    echo "Please set it with: export ANTHROPIC_API_KEY='your-api-key'"
    exit 1
fi

if [ "$ENABLE_AUTH" = "true" ]; then
    if [ -z "$KEYCLOAK_REALM_URL" ]; then
        echo "Error: --keycloak-realm-url is required when --enable-auth is specified"
        echo "Example: --keycloak-realm-url https://keycloak.example.com/auth/realms/master"
        exit 1
    fi
    
    # Parse Keycloak realm URL to extract base URL and realm name
    if [[ "$KEYCLOAK_REALM_URL" =~ ^(https?://[^/]+)(.*)/realms/([^/]+)/?$ ]]; then
        KEYCLOAK_URL="${BASH_REMATCH[1]}${BASH_REMATCH[2]}"
        KEYCLOAK_REALM="${BASH_REMATCH[3]}"
    else
        echo "Error: Invalid Keycloak realm URL format"
        echo "Expected format: https://host/path/realms/realm-name"
        echo "Example: https://keycloak.example.com/auth/realms/master"
        exit 1
    fi
    if [ -z "$KEYCLOAK_CLIENT_SECRET" ]; then
        echo "Error: --client-secret is required when --enable-auth is specified"
        exit 1
    fi
    echo "Keycloak Realm URL: $KEYCLOAK_REALM_URL"
    echo "Keycloak Base URL: $KEYCLOAK_URL"
    echo "Keycloak Realm: $KEYCLOAK_REALM"
    echo "Keycloak Client ID: $KEYCLOAK_CLIENT_ID"
fi

# 0. Create namespace if it doesn't exist
echo "Creating namespace $NAMESPACE..."
oc new-project "$NAMESPACE" 2>/dev/null || oc project "$NAMESPACE"

# 1. Create new S2I application
echo "Creating S2I application..."
oc new-app python:3.11-ubi9~https://github.com/rut31337/YamlForge.git \
  --name=demobuilder \
  --namespace="$NAMESPACE"

# Delete the auto-created service and create one with correct port
echo "Updating service to use correct port..."
oc delete service demobuilder -n "$NAMESPACE"
oc expose deployment demobuilder --port=$APP_PORT --target-port=$APP_PORT --name=demobuilder -n "$NAMESPACE"

# 2. Create configuration
echo "Setting up configuration..."
oc create secret generic demobuilder-secrets \
  --from-literal=anthropic-api-key="$ANTHROPIC_API_KEY" \
  --namespace="$NAMESPACE" \
  --dry-run=client -o yaml | oc apply -f -

oc create configmap demobuilder-config \
  --from-literal=app_env="production" \
  --from-literal=anthropic_model="claude-3-5-sonnet-20241022" \
  --from-literal=ai_enabled="true" \
  --from-literal=keycloak_enabled="$ENABLE_AUTH" \
  --namespace="$NAMESPACE" \
  --dry-run=client -o yaml | oc apply -f -

# 3. Configure deployment
echo "Configuring deployment..."
oc set env deployment/demobuilder --from=secret/demobuilder-secrets -n "$NAMESPACE"
oc set env deployment/demobuilder --from=configmap/demobuilder-config -n "$NAMESPACE"
# Remove any incorrect environment variable and set it properly
oc set env deployment/demobuilder ANTHROPIC_API_KEY- -n "$NAMESPACE"
oc set env deployment/demobuilder --from=secret/demobuilder-secrets -n "$NAMESPACE"

# 4. Deploy OAuth2 Proxy if authentication is enabled
if [ "$ENABLE_AUTH" = "true" ]; then
    echo "Deploying OAuth2 Proxy for authentication..."
    
    # Apply OAuth2 Proxy deployment - namespace will be overridden by -n flag
    oc apply -f "$SCRIPT_DIR/oauth2-proxy.yaml" -n "$NAMESPACE"
    
    # Generate cookie secret using Python instead of openssl (32 hex characters for AES)
    COOKIE_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(16))")
    
    # Get cluster domain for redirect URL
    CLUSTER_DOMAIN=$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}')
    if [ -z "$ROUTE_HOST" ]; then
        ROUTE_HOST="$NAMESPACE.$CLUSTER_DOMAIN"
    fi
    REDIRECT_URL="https://$ROUTE_HOST/oauth2/callback"
    OIDC_ISSUER_URL="$KEYCLOAK_URL/realms/$KEYCLOAK_REALM"
    
    echo "OAuth2 Proxy configuration:"
    echo "  Redirect URL: $REDIRECT_URL"
    echo "  OIDC Issuer: $OIDC_ISSUER_URL"
    
    # Create OAuth2 Proxy secrets
    oc create secret generic oauth2-proxy-secrets \
      --from-literal=cookie-secret="$COOKIE_SECRET" \
      --from-literal=client-id="$KEYCLOAK_CLIENT_ID" \
      --from-literal=client-secret="$KEYCLOAK_CLIENT_SECRET" \
      --from-literal=oidc-issuer-url="$OIDC_ISSUER_URL" \
      --namespace="$NAMESPACE" \
      --dry-run=client -o yaml | oc apply -f -
    
    # Update OAuth2 Proxy deployment with redirect URL
    oc patch deployment oauth2-proxy -n "$NAMESPACE" --patch "{
      \"spec\": {
        \"template\": {
          \"spec\": {
            \"containers\": [
              {
                \"name\": \"oauth2-proxy\",
                \"args\": [
                  \"--provider=keycloak-oidc\",
                  \"--email-domain=*\",
                  \"--upstream=http://demobuilder:$APP_PORT\",
                  \"--http-address=0.0.0.0:4180\",
                  \"--redirect-url=$REDIRECT_URL\",
                  \"--pass-user-headers=true\",
                  \"--set-xauthrequest=true\",
                  \"--skip-provider-button=true\",
                  \"--insecure-oidc-allow-unverified-email=true\",
                  \"--oidc-extra-audience=account\"
                ]
              }
            ]
          }
        }
      }
    }"
fi

# 5. Create routes
if [ "$ENABLE_AUTH" = "true" ]; then
    echo "Creating authenticated route..."
    if [ -n "$ROUTE_HOST" ]; then
        oc create route edge demobuilder-auth \
          --service=oauth2-proxy \
          --port=4180 \
          --hostname="$ROUTE_HOST" \
          --namespace="$NAMESPACE" \
          --dry-run=client -o yaml | oc apply -f -
    else
        oc create route edge demobuilder-auth \
          --service=oauth2-proxy \
          --port=4180 \
          --namespace="$NAMESPACE"
    fi
else
    echo "Creating direct route..."
    if [ -n "$ROUTE_HOST" ]; then
        oc create route edge demobuilder \
          --service=demobuilder \
          --port=$APP_PORT \
          --hostname="$ROUTE_HOST" \
          --namespace="$NAMESPACE" \
          --dry-run=client -o yaml | oc apply -f -
    else
        oc create route edge demobuilder \
          --service=demobuilder \
          --port=$APP_PORT \
          --namespace="$NAMESPACE"
    fi
fi

# 6. Wait for build to complete and update deployment image
echo "Waiting for build to complete..."
oc wait --for=condition=Complete build/demobuilder-1 --timeout=600s -n "$NAMESPACE"

echo "Updating deployment with built image..."
oc set image deployment/demobuilder demobuilder=image-registry.openshift-image-registry.svc:5000/$NAMESPACE/demobuilder:latest -n "$NAMESPACE"

echo "Updating deployment container port to $APP_PORT..."
oc patch deployment demobuilder -n "$NAMESPACE" --patch "{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"demobuilder\",\"ports\":[{\"containerPort\":$APP_PORT,\"protocol\":\"TCP\"}]}]}}}}"

# 7. Wait for deployment
echo "Waiting for DemoBuilder deployment..."
oc rollout status deployment/demobuilder --timeout=300s -n "$NAMESPACE"

if [ "$ENABLE_AUTH" = "true" ]; then
    echo "Waiting for OAuth2 Proxy deployment..."
    oc rollout status deployment/oauth2-proxy --timeout=300s -n "$NAMESPACE"
fi

# 8. Show results
echo "=== Deployment Complete ==="
echo "Namespace: $NAMESPACE"
echo "Authentication: $ENABLE_AUTH"

oc get pods -n "$NAMESPACE"
oc get routes -n "$NAMESPACE"

echo ""
echo "Application URLs:"
if [ "$ENABLE_AUTH" = "true" ]; then
    ACTUAL_HOST=$(oc get route demobuilder-auth -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "$ROUTE_HOST")
    echo "Authenticated: https://$ACTUAL_HOST"
    echo ""
    echo "Keycloak Configuration Required:"
    echo "  1. Create OIDC client '$KEYCLOAK_CLIENT_ID' in realm '$KEYCLOAK_REALM'"
    echo "  2. Set Valid Redirect URIs: https://$ACTUAL_HOST/oauth2/callback"
    echo "  3. Set Client Authentication: ON"
    echo "  4. Set Client Secret: (use the value you provided)"
    echo "  5. Set Access Type: confidential"
    echo "  6. Set Standard Flow Enabled: ON"
else
    ACTUAL_HOST=$(oc get route demobuilder -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null || echo "$ROUTE_HOST")
    echo "Direct: https://$ACTUAL_HOST"
fi

echo ""
echo "Useful commands:"
echo "  Check logs: oc logs -f deployment/demobuilder -n $NAMESPACE"
if [ "$ENABLE_AUTH" = "true" ]; then
    echo "  Check auth logs: oc logs -f deployment/oauth2-proxy -n $NAMESPACE"
fi
echo "  Scale up: oc scale deployment/demobuilder --replicas=3 -n $NAMESPACE"
echo "  Delete: oc delete project $NAMESPACE"

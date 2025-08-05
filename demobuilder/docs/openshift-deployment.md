# DemoBuilder OpenShift Deployment Guide

This guide covers deploying DemoBuilder to OpenShift with optional Keycloak authentication.

## Quick Deployment

### Basic Deployment (No Authentication)
```bash
cd demobuilder/deployment/openshift
export ANTHROPIC_API_KEY="your-api-key"
./deploy-s2i.sh --namespace my-demobuilder
```

### Authenticated Deployment with Keycloak
```bash
cd demobuilder/deployment/openshift
export ANTHROPIC_API_KEY="your-api-key"
./deploy-s2i.sh \
  --namespace my-demobuilder \
  --enable-auth \
  --keycloak-realm-url https://keycloak.example.com/auth/realms/master \
  --client-secret 48f673b0-2d03-4fcf-b59c-153c823109d8
```

## Keycloak Client Configuration

### 1. Create Keycloak Client

Use the example client configuration in `docs/keycloak-client-example.json`:

```json
{
  "clientId": "demobuilder",
  "name": "DemoBuilder Application",
  "enabled": true,
  "clientAuthenticatorType": "client-secret",
  "redirectUris": [
    "https://demobuilder-auth-{namespace}.apps.your-cluster.com/oauth2/callback"
  ],
  "webOrigins": [
    "https://demobuilder-auth-{namespace}.apps.your-cluster.com"
  ],
  "standardFlowEnabled": true,
  "protocol": "openid-connect",
  "fullScopeAllowed": true
}
```

### 2. Update Redirect URIs

After deployment, update your Keycloak client with the actual redirect URI:
- **Format**: `https://{namespace}.apps.{cluster-domain}/oauth2/callback`
- **Example**: `https://my-namespace.apps.example-cluster.com/oauth2/callback`

### 3. Required Keycloak Settings

- **Client Authentication**: ON
- **Standard Flow**: Enabled
- **Access Type**: confidential
- **Valid Redirect URIs**: Set to your actual callback URL
- **Web Origins**: Set to your application base URL

## Deployment Options

### Command Line Parameters

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `--namespace` | Target OpenShift namespace | No | `demobuilder` |
| `--enable-auth` | Enable Keycloak authentication | No | `false` |
| `--keycloak-realm-url` | Full Keycloak realm URL | Yes (if auth) | - |
| `--client-id` | Keycloak client ID | No | `demobuilder` |
| `--client-secret` | Keycloak client secret | Yes (if auth) | - |
| `--route-host` | Custom route hostname | No | Auto-generated |
| `--app-port` | Application port | No | `8501` |
| `--enable-diagrams` | Enable Infrastructure Diagrams integration | No | `false` |
| `--enable-diagrams (infrastructure diagrams are now built-in)

### Environment Variables

- `ANTHROPIC_API_KEY` - **Required**: Your Anthropic API key
- `YAMLFORGE_EXCLUDE_PROVIDERS` - Optional: Comma-separated list of providers to exclude

## Authentication Flow

When authentication is enabled:

1. **User Access**: User visits the authenticated URL
2. **OAuth2 Proxy**: Intercepts request and redirects to Keycloak
3. **Keycloak Login**: User authenticates with Keycloak
4. **Token Validation**: OAuth2 proxy validates the returned token
5. **Application Access**: User is forwarded to DemoBuilder with auth headers

### OAuth2 Proxy Configuration

The deployment automatically configures OAuth2 proxy with:

- **Provider**: `keycloak-oidc`
- **Email Domain**: `*` (allows all email domains)
- **Unverified Email**: Allowed (for Red Hat SSO compatibility)
- **Extra Audience**: `account` (Keycloak default audience)
- **User Headers**: Passed to application for user identification

## Troubleshooting

### Common Issues

#### 1. OAuth2 Proxy CrashLoopBackOff
**Symptoms**: OAuth2 proxy pods failing to start
**Solution**: Check secret creation and environment variables

```bash
# Check secret exists and has correct keys
oc get secret oauth2-proxy-secrets -n your-namespace -o yaml

# Verify required keys: client-id, client-secret, cookie-secret, oidc-issuer-url
```

#### 2. "Email not verified" Error
**Symptoms**: 500 error during OAuth callback
**Solution**: The deployment includes `--insecure-oidc-allow-unverified-email=true`

#### 3. "Audience mismatch" Error
**Symptoms**: "audience from claim aud with value [account] does not match"
**Solution**: The deployment includes `--oidc-extra-audience=account`

#### 4. "Application not available"
**Symptoms**: Route shows application unavailable
**Solution**: Check OAuth2 proxy pod status and logs

```bash
oc get pods -n your-namespace | grep oauth2
oc logs deployment/oauth2-proxy -n your-namespace
```

### Debugging Commands

```bash
# Check all resources
oc get all -n your-namespace

# Check OAuth2 proxy logs
oc logs deployment/oauth2-proxy -n your-namespace --tail=20

# Check DemoBuilder application logs
oc logs deployment/demobuilder -n your-namespace --tail=20

# Check routes
oc get routes -n your-namespace

# Test OAuth2 proxy configuration
oc describe deployment oauth2-proxy -n your-namespace
```

## Key Improvements in This Version

### 1. Fixed Cookie Secret Generation
- Uses Python `secrets.token_hex(16)` instead of openssl
- Generates proper 32-character hex string for AES encryption
- No dependency on openssl being available in the environment

### 2. Improved Keycloak Compatibility
- Added `--insecure-oidc-allow-unverified-email=true` for Red Hat SSO
- Added `--oidc-extra-audience=account` for Keycloak default audience
- Removed config file dependency, uses command-line arguments

### 3. Enhanced Keycloak URL Handling
- New `--keycloak-realm-url` parameter accepts full realm URL
- Automatic parsing to extract base URL and realm name
- Example: `https://keycloak.example.com/auth/realms/master`

### 4. Parameterized Port Configuration
- Added `APP_PORT` variable with default value `8501`
- Added `--app-port` command line parameter
- All port references now use configurable variable

### 5. Dynamic Route Configuration
- Automatically detects cluster domain
- Generates proper redirect URLs
- Updates OAuth2 proxy configuration with actual route

### 6. Enhanced Error Handling
- Better validation of required parameters
- Clearer error messages for common misconfigurations
- Comprehensive logging of deployment steps

### 7. Simplified Architecture
- Removed complex config file management
- Direct command-line argument configuration
- Reduced points of failure in OAuth2 proxy setup

## Security Considerations

### Authentication
- OAuth2 proxy validates all requests before forwarding to application
- Keycloak tokens are verified using OIDC discovery
- User information is passed via secure headers

### Cookie Security
- Secure cookies enabled (HTTPS only)
- HttpOnly flag prevents JavaScript access
- SameSite=Lax for CSRF protection
- 168-hour expiration (7 days)

### Network Security
- TLS termination at OpenShift route level
- Internal communication over HTTP (within cluster)
- No external access to DemoBuilder without authentication

## Production Deployment Checklist

- [ ] Anthropic API key configured
- [ ] Keycloak client created and configured
- [ ] Redirect URIs updated in Keycloak
- [ ] Resource limits configured appropriately
- [ ] Persistent storage configured if needed
- [ ] Monitoring and logging configured
- [ ] Backup procedures established
- [ ] SSL certificates valid and monitored

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review OpenShift pod logs
3. Verify Keycloak client configuration
4. Check network connectivity and DNS resolution
# OpenShift Logging and Analytics Guide for DemoBuilder

This guide demonstrates how to set up modern logging infrastructure and create analytics dashboards for DemoBuilder using Vector, LokiStack, and Grafana.

## Log Structure

DemoBuilder logs are captured through the OpenShift logging pipeline using OAuth2 proxy logs and Streamlit application logs. The modern logging stack consists of:

- **Vector**: Log collection and forwarding (replaces deprecated Fluentd)
- **LokiStack**: Log storage and querying (replaces deprecated Elasticsearch)  
- **Grafana**: Visualization and dashboards (replaces deprecated Kibana)

### OAuth2 Proxy Log Format
User authentication logs containing email addresses and session information:
```
[2025/01/01 12:00:00] [app.go:123] GET /path HTTP/1.1 "user@example.com" 1.234.567.890:12345
```

### Streamlit Application Logs
Active session tracking through `_stcore/stream` endpoints:
```
GET /_stcore/stream HTTP/1.1 200 1234 5.678 "user@example.com"
```

## User Analytics with LogQL Queries

Modern log analysis uses LogQL queries through Grafana's Explore interface to analyze user behavior patterns.

### 1. Active Users Analysis

```logql
# Current active users (last 30 minutes)
count by () (count by (user) (rate({kubernetes_namespace_name="demobuilder", kubernetes_container_name="oauth2-proxy"} |= "@" != "kube-probe" != "ready" != "ping" != "health" [30m])))

# Most active users (last 2 hours)
topk(10, count by (user) (count_over_time({kubernetes_namespace_name="demobuilder"} |= "@" != "kube-probe" != "ready" != "ping" != "health" | regexp "(?P<user>[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,})" [2h])))
```

### 2. Session Tracking

```logql
# Active Streamlit sessions (live connections)
count_over_time({kubernetes_namespace_name="demobuilder"} |= "_stcore/stream" [5m])

# Session duration analysis
avg_over_time({kubernetes_namespace_name="demobuilder"} |= "_stcore/stream" | regexp "HTTP/1\\.1\" (?P<status>\\d+) (?P<size>\\d+) (?P<duration>\\d+\\.\\d+)" | unwrap duration [1h])
```

### 3. User Interaction Patterns

```logql
# Real-time user activity (excludes all automated traffic)
{kubernetes_namespace_name="demobuilder"} |= "@" != "kube-probe" != "ready" != "ping" != "/_stcore/health" != "/_stcore/host-config"

# User request patterns by path
sum by (path) (count_over_time({kubernetes_namespace_name="demobuilder"} |= "@" != "kube-probe" | regexp "GET\\s+(?P<path>/[^\\s\\?]*)" [2h]))
```

### 4. Performance Monitoring

```logql
# Response time analysis (95th percentile)
quantile_over_time(0.95, ({kubernetes_namespace_name="demobuilder"} |= "HTTP/1.1" != "kube-probe" | regexp "HTTP/1\\.1\" (?P<status>\\d+) (?P<size>\\d+) (?P<duration>\\d+\\.\\d+)" | unwrap duration) [1h])

# User interaction rate over time
sum(rate({kubernetes_namespace_name="demobuilder"} |= "@" != "kube-probe" != "ready" != "ping" != "health" [5m]))
```

## Grafana Dashboard Creation

Create analytics dashboards using OAuth authentication and ConfigMap provisioning for persistent dashboard storage.

### 1. OAuth Authentication Setup

Configure Grafana with OpenShift OAuth for seamless authentication and token forwarding to LokiStack:

```bash
# Create dedicated service account with proper RBAC
oc create serviceaccount grafana-loki-reader -n openshift-logging
oc create clusterrole grafana-loki-reader --verb=get,list --resource=pods,pods/log,users,projects
oc create clusterrolebinding grafana-loki-reader --clusterrole=grafana-loki-reader --serviceaccount=openshift-logging:grafana-loki-reader

# Create OAuth client for Grafana
oc create -f - <<EOF
apiVersion: oauth.openshift.io/v1
kind: OAuthClient
metadata:
  name: grafana-oauth
grantMethod: auto
redirectURIs:
- https://grafana-openshift-logging.apps.cluster-domain.com/login/generic_oauth
secret: grafana-oauth-secret
EOF
```

### 2. Critical OAuth Configuration Requirements

**Grafana OAuth Configuration** (grafana.ini):
```ini
[auth.generic_oauth]
enabled = true
name = OpenShift
client_id = grafana-oauth
client_secret = grafana-oauth-secret
# CRITICAL: Use broader scopes for LokiStack authorization
scopes = user:full user:list-projects
auth_url = https://oauth-openshift.apps.cluster-domain.com/oauth/authorize
token_url = https://oauth-openshift.apps.cluster-domain.com/oauth/token
api_url = https://api.cluster-domain.com:6443/apis/user.openshift.io/v1/users/~
# CRITICAL: Proper attribute mapping for OpenShift
email_attribute_path = metadata.name
login_attribute_path = metadata.name
name_attribute_path = fullName
# CRITICAL: Skip TLS verification for self-signed certificates
tls_skip_verify_insecure = true
auto_assign_org_role = Admin
```

**Key Lessons Learned:**
- **OAuth Scopes**: `user:info user:check-access` are insufficient. LokiStack requires `user:full user:list-projects` for proper authorization
- **API Endpoint**: Use `/apis/user.openshift.io/v1/users/~` not `/oauth/userinfo` for OpenShift user data
- **TLS Configuration**: `tls_skip_verify_insecure = true` required for self-signed OpenShift certificates
- **Database Reset**: If switching from local admin to OAuth, delete Grafana PVC to force OAuth user creation

### 2. Dashboard Panels

Key dashboard panels for DemoBuilder analytics:

**Active Users Panel:**
```json
{
  "title": "Active Users (Last 30min)",
  "type": "stat",
  "targets": [{
    "expr": "count by () (count by (user) (rate({kubernetes_namespace_name=\"demobuilder\", kubernetes_container_name=\"oauth2-proxy\"} |= \"@\" != \"kube-probe\" != \"ready\" != \"ping\" != \"health\" [30m])))"
  }]
}
```

**Session Timeline Panel:**
```json
{
  "title": "User Activity Timeline", 
  "type": "timeseries",
  "targets": [{
    "expr": "sum(rate({kubernetes_namespace_name=\"demobuilder\"} |= \"@\" != \"kube-probe\" != \"ready\" != \"ping\" != \"health\" [5m]))",
    "legendFormat": "User Activity"
  }]
}
```

## Modern Logging Stack Configuration

### LokiStack and Vector Setup

```yaml
# LokiStack configuration for log storage
apiVersion: loki.grafana.com/v1
kind: LokiStack
metadata:
  name: logging-loki
  namespace: openshift-logging
spec:
  size: 1x.medium  # Scaled for rate limiting performance
  storage:
    schemas:
    - version: v12
      effectiveDate: "2022-06-01"
    secret:
      name: logging-loki-s3
      type: s3
  tenants:
    mode: openshift-logging
```

```yaml
# ClusterLogging with Vector collector
apiVersion: logging.coreos.com/v1
kind: ClusterLogging
metadata:
  name: instance
  namespace: openshift-logging
spec:
  collection:
    type: vector
  logStore:
    type: lokistack
    lokistack:
      name: logging-loki
  managementState: Managed
```

### 3. Dashboard Provisioning via ConfigMaps (Recommended)

Use ConfigMaps for persistent dashboard storage that survives Grafana restarts and database resets:

```bash
# Create dashboard JSON file
cat > demobuilder-dashboard.json << 'EOF'
{
  "title": "DemoBuilder User Activity Dashboard",
  "uid": "demobuilder-activity",
  "tags": ["demobuilder", "analytics"],
  "panels": [
    {
      "id": 1,
      "title": "Active Users (Last 30min)",
      "type": "stat",
      "targets": [
        {
          "expr": "count by () (count by (user) (rate({kubernetes_namespace_name=\"demobuilder\", kubernetes_container_name=\"oauth2-proxy\"} |= \"@\" != \"kube-probe\" != \"ready\" != \"ping\" != \"health\" [30m])))",
          "datasource": {"type": "loki", "uid": "P8CA42C45B3683B87"}
        }
      ]
    },
    {
      "id": 2,
      "title": "User Activity Timeline",
      "type": "timeseries",
      "targets": [
        {
          "expr": "sum(rate({kubernetes_namespace_name=\"demobuilder\"} |= \"@\" != \"kube-probe\" != \"ready\" != \"ping\" != \"health\" [5m]))",
          "datasource": {"type": "loki", "uid": "P8CA42C45B3683B87"}
        }
      ]
    }
  ],
  "time": {"from": "now-2h", "to": "now"},
  "refresh": "30s"
}
EOF

# Create ConfigMaps for dashboard provisioning
oc create configmap grafana-dashboard-demobuilder \
  --from-file=demobuilder-dashboard.json \
  -n openshift-logging

# Create dashboard provisioning configuration
cat > dashboard-config.yaml << 'EOF'
apiVersion: 1
providers:
- name: 'demobuilder-dashboards'
  orgId: 1
  folder: ''
  type: file
  disableDeletion: false
  updateIntervalSeconds: 10
  allowUiUpdates: true
  options:
    path: /etc/grafana/provisioning/dashboards/demobuilder
EOF

oc create configmap grafana-dashboard-config \
  --from-file=dashboards.yaml=dashboard-config.yaml \
  -n openshift-logging

# Update Grafana deployment to mount dashboard ConfigMaps
oc patch deployment grafana -n openshift-logging --patch '{
  "spec": {
    "template": {
      "spec": {
        "volumes": [
          {
            "name": "grafana-dashboard-config",
            "configMap": {"name": "grafana-dashboard-config"}
          },
          {
            "name": "grafana-dashboard-demobuilder", 
            "configMap": {"name": "grafana-dashboard-demobuilder"}
          }
        ],
        "containers": [
          {
            "name": "grafana",
            "volumeMounts": [
              {
                "name": "grafana-dashboard-config",
                "mountPath": "/etc/grafana/provisioning/dashboards"
              },
              {
                "name": "grafana-dashboard-demobuilder",
                "mountPath": "/etc/grafana/provisioning/dashboards/demobuilder"
              }
            ]
          }
        ]
      }
    }
  }
}'
```

**Benefits of ConfigMap Provisioning:**
- **Persistent**: Dashboards survive database resets and pod restarts
- **Version Control**: Dashboard JSON can be stored in Git
- **Automated**: No manual API calls or UI recreation needed
- **Consistent**: Same dashboard across environments

## Key Metrics to Monitor

### Primary Analytics KPIs
1. **Active Users**: Users with activity in last 30 minutes
2. **Active Sessions**: `_stcore/stream` connections in last 5 minutes  
3. **Session Duration**: Average time users spend actively using the app
4. **User Interaction Rate**: Requests per second (excluding health checks)
5. **Feature Usage**: Static resource patterns showing which app features are used

### Performance Monitoring
- Response time analysis (95th percentile)
- Peak usage identification
- Long-running session detection
- Geographic distribution analysis

## Common LogQL Queries for Analytics

### User Activity Analysis
```logql
# Daily active users pattern
count by () (count by (user) (count_over_time({kubernetes_namespace_name="demobuilder"} |= "@" != "kube-probe" | regexp "(?P<user>[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,})" [24h])))

# Peak usage hours 
sum by () (count_over_time({kubernetes_namespace_name="demobuilder"} |= "@" != "kube-probe" != "ready" != "ping" != "health" [1h]))

# Feature usage patterns
sum by (resource) (count_over_time({kubernetes_namespace_name="demobuilder"} |= "static/" | regexp "GET\\s+/static/(?P<resource>[^\\s]*)" [2h]))
```

### Session Analysis
```logql
# Session start detection
{kubernetes_namespace_name="demobuilder"} |= "GET / \"/\"" |= "@" != "kube-probe"

# Long-running sessions (over 60 seconds)
{kubernetes_namespace_name="demobuilder"} |= "_stcore/stream" | regexp "HTTP/1\\.1\" (?P<status>\\d+) (?P<size>\\d+) (?P<duration>[6-9]\\d+\\.\\d+|\\d{3,}\\.\\d+)" | unwrap duration > 60

# Geographic analysis from client IPs
sum by (user, client_ip) (count_over_time({kubernetes_namespace_name="demobuilder"} |= "@" != "kube-probe" | regexp "(?P<client_ip>\\d+\\.\\d+\\.\\d+\\.\\d+)" | regexp "(?P<user>[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,})" [2h]))
```

## Troubleshooting

### 1. OAuth Authentication Issues

**Symptom**: Datasource test fails with "Unable to connect with Loki"
**Solution**: Check OAuth scopes and user authentication

```bash
# Check LokiStack gateway logs for authentication errors
oc logs deployment/logging-loki-gateway -n openshift-logging | grep -E "(error|401|403)"

# Common error: insufficient OAuth scopes
# Error: "scopes [user:info user:check-access] prevent this action"
# Fix: Update Grafana OAuth scopes to "user:full user:list-projects"

# Check if user is properly authenticated via OAuth
oc logs deployment/grafana -n openshift-logging | grep "uname="
# Should show OAuth username (e.g., "uname=user@domain.com") not "uname=admin"
```

**Symptom**: "The specified user's auth provider is not oauth"
**Solution**: Force OAuth user creation by resetting database

```bash
# Scale down Grafana, delete PVC, and restart
oc scale deployment grafana --replicas=0 -n openshift-logging
oc delete pvc grafana-storage -n openshift-logging
oc scale deployment grafana --replicas=1 -n openshift-logging

# This forces new OAuth user creation instead of local admin
```

### 2. OAuth Configuration Errors

**Symptom**: "tls: failed to verify certificate: x509: certificate signed by unknown authority"
**Solution**: Add TLS skip verification to Grafana OAuth config

```ini
[auth.generic_oauth]
tls_skip_verify_insecure = true
```

**Symptom**: "token is not in JWT format"
**Solution**: OpenShift tokens are not JWT - this is expected and can be ignored

**Symptom**: OAuth login redirects to wrong URL
**Solution**: Check OAuth client redirect URIs match Grafana route

```bash
oc get oauthclient grafana-oauth -o yaml
# redirectURIs should match: https://grafana-route/login/generic_oauth
```

### 3. Datasource Provisioning Issues

**Symptom**: Datasource not appearing despite ConfigMap being mounted
**Solution**: Check datasource UID and restart Grafana

```bash
# Verify datasource UID in ConfigMap matches panel references
oc get configmap grafana-datasources -n openshift-logging -o yaml

# Restart Grafana to reload provisioned datasources
oc rollout restart deployment/grafana -n openshift-logging
```

### 4. Loki Data Source Connectivity
```bash
# Test Loki connectivity with OAuth token
oc run loki-test --image=curlimages/curl:latest --rm -it --restart=Never -- \
  curl -k -H "Authorization: Bearer $(oc whoami -t)" \
  "https://logging-loki-gateway-http.openshift-logging.svc.cluster.local:8080/api/logs/v1/application/loki/api/v1/labels"

# Check available namespaces in logs
oc run query-test --image=curlimages/curl:latest --rm -it --restart=Never -- \
  curl -k -H "Authorization: Bearer $(oc whoami -t)" \
  "https://logging-loki-gateway-http.openshift-logging.svc.cluster.local:8080/api/logs/v1/application/loki/api/v1/label/kubernetes_namespace_name/values"
```

### 2. Dashboard Panel Issues
- Ensure LogQL syntax is properly escaped in JSON (use `\\\\d+` instead of `\\d+`)
- Test queries in Grafana Explore before adding to dashboards  
- Verify data source UID matches in panel configurations
- Check time ranges align with available log data

### 3. Performance Optimization
- Scale LokiStack from `1x.small` to `1x.medium` for higher query loads
- Use rate limiting exclusion filters: `!= "kube-probe" != "ready" != "ping" != "health"`
- Optimize query time ranges for responsiveness

This modern logging approach provides real-time user analytics and behavioral insights using the Vector/LokiStack/Grafana stack, replacing deprecated Elasticsearch/Fluentd/Kibana components.
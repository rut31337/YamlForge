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

Create analytics dashboards using the Grafana API and LogQL queries.

### 1. Data Source Setup

Configure LokiStack as a Grafana data source with OAuth authentication:

```bash
# Create service account for Loki access
oc create serviceaccount loki-reader -n openshift-logging
oc adm policy add-cluster-role-to-user cluster-admin system:serviceaccount:openshift-logging:loki-reader

# Generate authentication token
oc create token loki-reader -n openshift-logging --duration=24h
```

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

### Complete Dashboard Import via API

```bash
# Setup authentication
GRAFANA_URL="https://grafana-namespace.apps.cluster-domain.com"
GRAFANA_AUTH="Basic $(echo -n 'admin:password' | base64)"

# Create complete user activity dashboard
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: $GRAFANA_AUTH" \
  -d '{
    "dashboard": {
      "title": "DemoBuilder User Activity Dashboard",
      "panels": [
        {
          "title": "Active Users (Last 30min)",
          "type": "stat",
          "targets": [{
            "expr": "count by () (count by (user) (rate({kubernetes_namespace_name=\"demobuilder\", kubernetes_container_name=\"oauth2-proxy\"} |= \"@\" != \"kube-probe\" != \"ready\" != \"ping\" != \"health\" [30m])))"
          }]
        }
      ]
    }
  }' \
  "$GRAFANA_URL/api/dashboards/db"
```

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

### 1. Loki Data Source Issues
```bash
# Test Loki connectivity
oc run loki-test --image=curlimages/curl:latest --rm -it --restart=Never -- \
  curl -k -H "Authorization: Bearer $(cat /tmp/loki-token.txt)" \
  "https://logging-loki-gateway-http.openshift-logging.svc.cluster.local:8080/api/logs/v1/application/loki/api/v1/labels"

# Check available namespaces in logs
oc run query-test --image=curlimages/curl:latest --rm -it --restart=Never -- \
  curl -k -H "Authorization: Bearer $(cat /tmp/loki-token.txt)" \
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
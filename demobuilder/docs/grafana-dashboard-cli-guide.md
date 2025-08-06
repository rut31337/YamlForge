# Grafana Dashboard Creation via CLI for Application Analytics

## Overview

This guide demonstrates how to create Grafana dashboards programmatically using the CLI and API to analyze application logs from OpenShift Container Platform. All examples are based on analyzing user activity for containerized applications.

## Prerequisites

- Existing Grafana instance with Loki data source configured
- OpenShift CLI (`oc`) access 
- `curl` for API calls
- Application logs flowing through the logging pipeline

## Authentication Setup

### 1. Grafana Basic Authentication

Most operations use Grafana's admin credentials:

```bash
# Base64 encode admin credentials for API calls
GRAFANA_AUTH="Basic $(echo -n 'admin:admin_password' | base64)"
GRAFANA_URL="https://grafana-namespace.apps.cluster-domain.com"
```

### 2. Service Account for Loki Access

```bash
# Create service account with proper permissions
oc create serviceaccount loki-reader -n openshift-logging

# Add cluster-admin permissions (adjust as needed for your security requirements)
oc adm policy add-cluster-role-to-user cluster-admin system:serviceaccount:openshift-logging:loki-reader

# Generate token for data source configuration
oc create token loki-reader -n openshift-logging --duration=24h > /tmp/loki-token.txt
```

## Data Source Configuration

### 1. Create Loki Data Source via API

```bash
# Create data source JSON configuration
cat > /tmp/loki-datasource.json << 'EOF'
{
  "name": "Application-Logs",
  "type": "loki",
  "url": "https://logging-loki-gateway-http.openshift-logging.svc.cluster.local:8080/api/logs/v1/application",
  "access": "proxy",
  "isDefault": true,
  "jsonData": {
    "timeout": 60,
    "maxLines": 1000,
    "httpHeaderName1": "Authorization"
  },
  "secureJsonData": {
    "httpHeaderValue1": "Bearer TOKEN_PLACEHOLDER"
  }
}
EOF

# Insert service account token
LOKI_TOKEN=$(cat /tmp/loki-token.txt)
sed "s/TOKEN_PLACEHOLDER/$LOKI_TOKEN/" /tmp/loki-datasource.json > /tmp/loki-datasource-final.json

# Create data source via API
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: $GRAFANA_AUTH" \
  -d @/tmp/loki-datasource-final.json \
  "$GRAFANA_URL/api/datasources"
```

### 2. Test Data Source Connection

```bash
# Check data source health
curl -X GET \
  -H "Authorization: $GRAFANA_AUTH" \
  "$GRAFANA_URL/api/datasources/1/health"
```

## Dashboard Creation

### 1. Basic User Activity Dashboard

Create a dashboard JSON file with panels for application analytics:

```bash
cat > /tmp/user-activity-dashboard.json << 'EOF'
{
  "dashboard": {
    "id": null,
    "title": "Application User Activity",
    "tags": ["application", "users", "activity"],
    "timezone": "browser",
    "panels": [
      {
        "id": 1,
        "title": "Active Users (Last 30min)",
        "type": "stat",
        "targets": [
          {
            "datasource": {
              "type": "loki",
              "uid": "DATA_SOURCE_UID"
            },
            "expr": "count by () (count by (user) (rate({kubernetes_namespace_name=\"your-app-namespace\"} |= \"@\" != \"probe\" [30m])))",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "color": {
              "mode": "thresholds"
            },
            "thresholds": {
              "steps": [
                {"color": "green", "value": null},
                {"color": "yellow", "value": 3},
                {"color": "red", "value": 10}
              ]
            }
          }
        },
        "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0}
      },
      {
        "id": 2,
        "title": "Total Requests (Last Hour)",
        "type": "stat",
        "targets": [
          {
            "datasource": {
              "type": "loki",
              "uid": "DATA_SOURCE_UID"
            },
            "expr": "count_over_time({kubernetes_namespace_name=\"your-app-namespace\"} != \"probe\" [1h])",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "color": {
              "mode": "thresholds"
            },
            "thresholds": {
              "steps": [
                {"color": "blue", "value": null}
              ]
            }
          }
        },
        "gridPos": {"h": 8, "w": 6, "x": 6, "y": 0}
      },
      {
        "id": 3,
        "title": "User Activity Timeline",
        "type": "timeseries",
        "targets": [
          {
            "datasource": {
              "type": "loki",
              "uid": "DATA_SOURCE_UID"
            },
            "expr": "sum(rate({kubernetes_namespace_name=\"your-app-namespace\"} |= \"@\" != \"probe\" [5m]))",
            "refId": "A",
            "legendFormat": "User Activity Rate"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "custom": {
              "drawStyle": "line",
              "lineInterpolation": "linear",
              "lineWidth": 2,
              "fillOpacity": 10
            },
            "unit": "reqps"
          }
        },
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
      },
      {
        "id": 4,
        "title": "Recent User Activity",
        "type": "logs",
        "targets": [
          {
            "datasource": {
              "type": "loki",
              "uid": "DATA_SOURCE_UID"
            },
            "expr": "{kubernetes_namespace_name=\"your-app-namespace\"} |= \"@\" != \"probe\"",
            "refId": "A"
          }
        ],
        "options": {
          "showTime": true,
          "showLabels": false,
          "wrapLogMessage": true,
          "enableLogDetails": true,
          "sortOrder": "Descending"
        },
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
      }
    ],
    "time": {
      "from": "now-2h",
      "to": "now"
    },
    "refresh": "30s",
    "schemaVersion": 39,
    "version": 1
  },
  "overwrite": true
}
EOF
```

### 2. Update Dashboard with Data Source UID

Get the data source UID and update the dashboard:

```bash
# Get data source UID
DATA_SOURCE_UID=$(curl -s -H "Authorization: $GRAFANA_AUTH" \
  "$GRAFANA_URL/api/datasources/name/Application-Logs" | \
  jq -r '.uid')

# Update dashboard JSON with actual UID
sed "s/DATA_SOURCE_UID/$DATA_SOURCE_UID/g" /tmp/user-activity-dashboard.json > /tmp/dashboard-final.json

# Replace placeholder namespace with your actual application namespace
sed -i 's/your-app-namespace/actual-namespace-name/g' /tmp/dashboard-final.json
```

### 3. Import Dashboard via API

```bash
# Import dashboard
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: $GRAFANA_AUTH" \
  -d @/tmp/dashboard-final.json \
  "$GRAFANA_URL/api/dashboards/db"
```

## Advanced LogQL Queries

### Common Patterns for Application Analytics

```bash
# Active users (extract email addresses from logs)
count by (user) (count_over_time({kubernetes_namespace_name="app-ns"} |= "@" | regexp "(?P<user>[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,})" [30m]))

# Request patterns (extract paths)
sum by (path) (count_over_time({kubernetes_namespace_name="app-ns"} | regexp "GET\\s+(?P<path>/[^\\s\\?]*)" [1h]))

# Response time analysis
quantile_over_time(0.95, ({kubernetes_namespace_name="app-ns"} | regexp "(?P<duration>\\d+\\.\\d+)" | unwrap duration) [1h])

# Error rate
sum(rate({kubernetes_namespace_name="app-ns"} |= "error" [5m]))

# Filter out health checks and probes
{kubernetes_namespace_name="app-ns"} != "health" != "ready" != "ping" != "probe"
```

### User Session Analysis

```bash
# Session duration tracking
{kubernetes_namespace_name="app-ns"} |= "session" | regexp "duration=(?P<duration>\\d+)" | unwrap duration

# User interaction frequency
topk(10, count by (user) (count_over_time({kubernetes_namespace_name="app-ns"} |= "@" [2h])))

# Geographic analysis (if IP logged)
sum by (region) (count_over_time({kubernetes_namespace_name="app-ns"} | regexp "ip=(?P<ip>\\d+\\.\\d+\\.\\d+\\.\\d+)" [1h]))
```

## Dashboard Management

### List Existing Dashboards

```bash
# List all dashboards
curl -s -H "Authorization: $GRAFANA_AUTH" \
  "$GRAFANA_URL/api/search?type=dash-db" | jq '.'

# Search for specific dashboard
curl -s -H "Authorization: $GRAFANA_AUTH" \
  "$GRAFANA_URL/api/search?query=Application" | jq '.'
```

### Update Existing Dashboard

```bash
# Get existing dashboard
DASHBOARD_UID="your-dashboard-uid"
curl -s -H "Authorization: $GRAFANA_AUTH" \
  "$GRAFANA_URL/api/dashboards/uid/$DASHBOARD_UID" > /tmp/existing-dashboard.json

# Modify and update
# Edit /tmp/existing-dashboard.json as needed
curl -X POST \
  -H "Content-Type: application/json" \
  -H "Authorization: $GRAFANA_AUTH" \
  -d @/tmp/existing-dashboard.json \
  "$GRAFANA_URL/api/dashboards/db"
```

### Delete Dashboard

```bash
# Delete dashboard by UID
curl -X DELETE \
  -H "Authorization: $GRAFANA_AUTH" \
  "$GRAFANA_URL/api/dashboards/uid/$DASHBOARD_UID"
```

## Troubleshooting

### Common Issues and Solutions

**Data Source Connection Failed:**
```bash
# Test Loki connectivity from within cluster
oc run loki-test --image=curlimages/curl:latest --rm -it --restart=Never -- \
  curl -k -H "Authorization: Bearer $(cat /tmp/loki-token.txt)" \
  "https://logging-loki-gateway-http.openshift-logging.svc.cluster.local:8080/api/logs/v1/application/loki/api/v1/labels"
```

**No Data in Panels:**
```bash
# Check if logs exist for your namespace
oc run query-test --image=curlimages/curl:latest --rm -it --restart=Never -- \
  curl -k -H "Authorization: Bearer $(cat /tmp/loki-token.txt)" \
  "https://logging-loki-gateway-http.openshift-logging.svc.cluster.local:8080/api/logs/v1/application/loki/api/v1/label/kubernetes_namespace_name/values"
```

**Query Syntax Errors:**
- Ensure LogQL syntax is properly escaped in JSON
- Use double backslashes for regex patterns: `\\d+` instead of `\d+`
- Test queries in Grafana Explore before adding to dashboards

## Example: Complete Setup Script

```bash
#!/bin/bash

# Configuration
GRAFANA_URL="https://grafana-namespace.apps.cluster-domain.com"
GRAFANA_USER="admin"
GRAFANA_PASS="admin_password"
APP_NAMESPACE="your-application-namespace"

# Setup authentication
GRAFANA_AUTH="Basic $(echo -n "$GRAFANA_USER:$GRAFANA_PASS" | base64)"

# Create service account and token
oc create serviceaccount loki-reader -n openshift-logging
oc adm policy add-cluster-role-to-user cluster-admin system:serviceaccount:openshift-logging:loki-reader
oc create token loki-reader -n openshift-logging --duration=24h > /tmp/loki-token.txt

# Create data source
LOKI_TOKEN=$(cat /tmp/loki-token.txt)
cat > /tmp/datasource.json << EOF
{
  "name": "App-Logs",
  "type": "loki",
  "url": "https://logging-loki-gateway-http.openshift-logging.svc.cluster.local:8080/api/logs/v1/application",
  "access": "proxy",
  "isDefault": true,
  "jsonData": {
    "timeout": 60,
    "maxLines": 1000,
    "httpHeaderName1": "Authorization"
  },
  "secureJsonData": {
    "httpHeaderValue1": "Bearer $LOKI_TOKEN"
  }
}
EOF

curl -X POST -H "Content-Type: application/json" -H "Authorization: $GRAFANA_AUTH" \
  -d @/tmp/datasource.json "$GRAFANA_URL/api/datasources"

# Get data source UID
DATA_SOURCE_UID=$(curl -s -H "Authorization: $GRAFANA_AUTH" \
  "$GRAFANA_URL/api/datasources/name/App-Logs" | jq -r '.uid')

# Create and import dashboard (using templates above)
# ... dashboard creation code here ...

echo "Dashboard setup complete!"
echo "Access: $GRAFANA_URL"
```

## Best Practices

1. **Use descriptive panel titles** that clearly indicate what metric is being shown
2. **Filter out noise** from logs (health checks, probes, etc.)
3. **Set appropriate time ranges** for different metrics (30m for active users, 2h for trends)
4. **Use consistent color schemes** across related dashboards
5. **Include legend formats** for time series to make charts readable
6. **Test queries in Explore** before adding them to dashboards
7. **Document dashboard purpose** in description fields
8. **Use dashboard tags** for organization and searchability

## Security Considerations

- Use least-privilege service accounts for Loki access
- Rotate authentication tokens regularly
- Sanitize logs to remove sensitive information before visualization
- Use RBAC to control dashboard access
- Consider data retention policies for log storage
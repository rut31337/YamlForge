# OpenShift Logging Guide for DemoBuilder

This guide demonstrates how to analyze DemoBuilder logs using native OpenShift logging capabilities.

## Log Structure

DemoBuilder outputs structured JSON logs to stdout, automatically collected by OpenShift's logging infrastructure. Each log entry includes:

### Standard Fields
- `timestamp`: ISO 8601 formatted timestamp
- `component`: Application component (app, metrics, performance)
- `session_id`: Unique session identifier for tracking user interactions
- `openshift`: OpenShift context (pod, namespace, node, cluster)
- `app`: Always "demobuilder"
- `version`: Application version

### Event-Specific Fields
- `event_type`: Type of event (user_action, infrastructure_request, yaml_generation, etc.)
- `event_data`: Event-specific data payload

## Log Analysis Examples

### 1. View All DemoBuilder Logs

```bash
# View all logs from DemoBuilder deployment
oc logs -l app=demobuilder -n demobuilder

# Follow logs in real-time
oc logs -f deployment/demobuilder -n demobuilder

# View logs from last hour
oc logs -l app=demobuilder -n demobuilder --since=1h
```

### 2. User Session Tracking

```bash
# Find session start events
oc logs -l app=demobuilder -n demobuilder | grep '"event_type":"session_start"'

# Track a specific user session (replace SESSION_ID)
oc logs -l app=demobuilder -n demobuilder | grep '"session_id":"SESSION_ID"'
```

### 3. Infrastructure Request Analysis

```bash
# Find all infrastructure requests
oc logs -l app=demobuilder -n demobuilder | grep '"event_type":"infrastructure_request"'

# Count requests by provider
oc logs -l app=demobuilder -n demobuilder | \
  grep '"event_type":"infrastructure_request"' | \
  jq -r '.event_data.providers[]' | sort | uniq -c
```

### 4. YAML Generation Metrics

```bash
# Track YAML generation success/failure rates
oc logs -l app=demobuilder -n demobuilder | \
  grep '"event_type":"yaml_generation"' | \
  jq -r '.event_data.success' | sort | uniq -c

# Find failed YAML generations with errors
oc logs -l app=demobuilder -n demobuilder | \
  grep '"event_type":"yaml_generation"' | \
  jq 'select(.event_data.success == false) | .event_data.error'
```

### 5. User Interaction Patterns

```bash
# Track provider enablement/disablement
oc logs -l app=demobuilder -n demobuilder | \
  grep -E '"action":"provider_(enabled|disabled)"'

# Analyze conversation patterns
oc logs -l app=demobuilder -n demobuilder | \
  grep '"event_type":"conversation_turn"' | \
  jq '.event_data.turn_number' | sort -n | tail -10
```

### 6. Performance Monitoring

```bash
# Find slow operations (> 5 seconds)
oc logs -l app=demobuilder -n demobuilder | \
  grep '"event_type":"performance_metric"' | \
  jq 'select(.event_data.duration_ms > 5000)'

# Average response times by operation
oc logs -l app=demobuilder -n demobuilder | \
  grep '"event_type":"performance_metric"' | \
  jq -r '"\(.event_data.operation),\(.event_data.duration_ms)"' | \
  awk -F, '{sum[$1]+=$2; count[$1]++} END {for(op in sum) print op": "sum[op]/count[op]"ms"}'
```

### 7. Error Analysis

```bash
# Find all application errors
oc logs -l app=demobuilder -n demobuilder | \
  grep '"event_type":"application_error"'

# Group errors by type
oc logs -l app=demobuilder -n demobuilder | \
  grep '"event_type":"application_error"' | \
  jq -r '.event_data.error_type' | sort | uniq -c
```

## Elasticsearch Queries (If Cluster Logging Enabled)

If your OpenShift cluster has the cluster logging operator installed, you can use these Elasticsearch queries in Kibana:

### 1. User Session Analysis
```json
{
  "query": {
    "bool": {
      "must": [
        {"match": {"kubernetes.labels.app": "demobuilder"}},
        {"match": {"message.event_type": "session_start"}},
        {"range": {"@timestamp": {"gte": "now-24h"}}}
      ]
    }
  }
}
```

### 2. Provider Usage Trends
```json
{
  "query": {
    "bool": {
      "must": [
        {"match": {"kubernetes.labels.app": "demobuilder"}},
        {"match": {"message.event_type": "provider_selection"}}
      ]
    }
  },
  "aggs": {
    "providers": {
      "terms": {
        "field": "message.event_data.enabled_providers"
      }
    }
  }
}
```

### 3. Infrastructure Request Patterns
```json
{
  "query": {
    "bool": {
      "must": [
        {"match": {"kubernetes.labels.app": "demobuilder"}},
        {"match": {"message.event_type": "infrastructure_request"}}
      ]
    }
  },
  "aggs": {
    "instance_counts": {
      "histogram": {
        "field": "message.event_data.instance_count",
        "interval": 1
      }
    }
  }
}
```

## Log Retention and Storage

### OpenShift Logging Configuration
```yaml
# Example ClusterLogging configuration for DemoBuilder
apiVersion: logging.coreos.com/v1
kind: ClusterLogging
metadata:
  name: instance
  namespace: openshift-logging
spec:
  collection:
    logs:
      type: fluentd
      fluentd:
        tolerations:
        - operator: Exists
  logStore:
    type: elasticsearch
    retentionPolicy:
      application:
        maxAge: 30d  # Retain DemoBuilder logs for 30 days
  visualization:
    type: kibana
```

### Log Export for Analysis
```bash
# Export logs to file for offline analysis
oc logs -l app=demobuilder -n demobuilder --since=24h > demobuilder-logs.json

# Export with specific time range
oc logs -l app=demobuilder -n demobuilder \
  --since-time="2025-01-01T00:00:00Z" \
  --until-time="2025-01-02T00:00:00Z" > demobuilder-logs-jan1.json
```

## Monitoring and Alerting

### PrometheusRule for DemoBuilder Metrics
```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: demobuilder-logging-alerts
  namespace: demobuilder
spec:
  groups:
  - name: demobuilder.logging
    rules:
    - alert: DemoBuilderHighErrorRate
      expr: |
        (
          rate(log_entries{app="demobuilder",level="ERROR"}[5m]) /
          rate(log_entries{app="demobuilder"}[5m])
        ) > 0.1
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "High error rate in DemoBuilder"
        description: "DemoBuilder error rate is {{ $value | humanizePercentage }}"
    
    - alert: DemoBuilderSlowResponse
      expr: |
        histogram_quantile(0.95, rate(demobuilder_operation_duration_seconds_bucket[5m])) > 10
      for: 2m
      labels:
        severity: warning
      annotations:
        summary: "DemoBuilder slow response times"
        description: "95th percentile response time is {{ $value }}s"
```

## Usage Analytics Examples

### Daily Active Users
```bash
# Count unique sessions per day
oc logs -l app=demobuilder -n demobuilder --since=7d | \
  grep '"event_type":"session_start"' | \
  jq -r '.timestamp[0:10]' | sort | uniq -c
```

### Popular Provider Combinations
```bash
# Find most common provider selections
oc logs -l app=demobuilder -n demobuilder --since=7d | \
  grep '"event_type":"provider_selection"' | \
  jq -r '.event_data.enabled_providers | sort | join(",")' | \
  sort | uniq -c | sort -nr | head -10
```

### Average Session Duration
```bash
# Calculate session durations (requires custom processing)
oc logs -l app=demobuilder -n demobuilder --since=24h | \
  grep -E '"event_type":"(session_start|yaml_downloaded)"' | \
  jq -r '"\(.session_id),\(.event_type),\(.timestamp)"' | \
  sort | # Process with custom script to calculate durations
```

### Configuration Complexity Trends
```bash
# Track instance counts in configurations
oc logs -l app=demobuilder -n demobuilder --since=7d | \
  grep '"event_type":"infrastructure_request"' | \
  jq -r '.event_data.instance_count' | \
  awk '{sum+=$1; count++} END {print "Average instances per config:", sum/count}'
```

## Troubleshooting Common Issues

### 1. Missing Logs
```bash
# Check if pods are running
oc get pods -l app=demobuilder -n demobuilder

# Check pod events
oc get events -n demobuilder --field-selector involvedObject.name=demobuilder-xxx

# Verify logging configuration
oc get configmap demobuilder-config -n demobuilder -o yaml
```

### 2. Log Format Issues
```bash
# Check for malformed JSON logs
oc logs -l app=demobuilder -n demobuilder | head -100 | jq empty

# Validate log structure
oc logs -l app=demobuilder -n demobuilder | head -10 | jq '.timestamp, .component, .event_type'
```

### 3. Performance Issues
```bash
# Check for performance bottlenecks
oc logs -l app=demobuilder -n demobuilder | \
  grep '"event_type":"performance_metric"' | \
  jq 'select(.event_data.duration_ms > 3000)' | head -5
```

This logging implementation provides comprehensive visibility into DemoBuilder usage patterns, performance characteristics, and user behavior while maintaining security and privacy through structured, anonymized logging.
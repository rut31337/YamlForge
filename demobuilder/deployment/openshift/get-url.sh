#!/bin/bash

# DemoBuilder OpenShift URL Helper Script
# This script retrieves the application URL after deployment

set -e

NAMESPACE=${1:-demobuilder}

echo "=== DemoBuilder Application Access ==="
echo

# Check if namespace exists
if ! oc get namespace "$NAMESPACE" >/dev/null 2>&1; then
    echo "ERROR: Namespace '$NAMESPACE' not found"
    echo "Usage: $0 [namespace]"
    echo "Default namespace: demobuilder"
    exit 1
fi

# Check pod status
echo "Pod Status:"
if oc get pods -n "$NAMESPACE" -l app=demobuilder --no-headers 2>/dev/null | grep -q .; then
    oc get pods -n "$NAMESPACE" -l app=demobuilder
    
    READY_PODS=$(oc get pods -n "$NAMESPACE" -l app=demobuilder --no-headers 2>/dev/null | grep "1/1.*Running" | wc -l)
    TOTAL_PODS=$(oc get pods -n "$NAMESPACE" -l app=demobuilder --no-headers 2>/dev/null | wc -l)
    
    if [ "$READY_PODS" -eq 0 ]; then
        echo "WARNING: No pods are ready yet. Please wait for deployment to complete."
        echo "   Monitor with: oc get pods -n $NAMESPACE --watch"
        exit 1
    elif [ "$READY_PODS" -lt "$TOTAL_PODS" ]; then
        echo "WARNING: Only $READY_PODS of $TOTAL_PODS pods are ready"
    else
        echo "SUCCESS: All $READY_PODS pods are ready"
    fi
else
    echo "ERROR: No DemoBuilder pods found in namespace '$NAMESPACE'"
    echo "   Deploy first with: oc apply -k deployment/openshift/"
    exit 1
fi

echo

# Check routes
echo "Routes:"
if oc get routes -n "$NAMESPACE" --no-headers 2>/dev/null | grep -q .; then
    oc get routes -n "$NAMESPACE"
    echo
    
    # Get primary route
    if ROUTE_HOST=$(oc get route demobuilder -n "$NAMESPACE" -o jsonpath='{.spec.host}' 2>/dev/null); then
        APP_URL="https://$ROUTE_HOST"
        HEALTH_URL="$APP_URL/_stcore/health"
        
        echo "=== Application Access ==="
        echo "Application URL: $APP_URL"
        echo "Health Check:    $HEALTH_URL"
        echo
        
        # Test connectivity
        echo "Testing connectivity..."
        if curl -k -s --connect-timeout 10 "$HEALTH_URL" >/dev/null 2>&1; then
            echo "SUCCESS: Application is accessible and healthy!"
            echo
            echo "Ready to use! Open your browser to:"
            echo "   $APP_URL"
        else
            echo "ERROR: Application health check failed"
            echo "   The app may still be starting up"
            echo "   Check logs: oc logs deployment/demobuilder -n $NAMESPACE"
            echo "   Try again in a few moments"
        fi
    else
        echo "ERROR: Could not find route 'demobuilder' in namespace '$NAMESPACE'"
    fi
else
    echo "ERROR: No routes found in namespace '$NAMESPACE'"
    echo "   Deploy first with: oc apply -k deployment/openshift/"
fi

echo
echo "=== Quick Commands ==="
echo "View logs:     oc logs deployment/demobuilder -n $NAMESPACE -f"
echo "Watch pods:    oc get pods -n $NAMESPACE --watch"
echo "Port forward:  oc port-forward svc/demobuilder 8501:8501 -n $NAMESPACE"
echo "Delete app:    oc delete -k deployment/openshift/"
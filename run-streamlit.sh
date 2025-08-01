#!/bin/bash
set -e

echo "Starting Streamlit DemoBuilder application..."

# Export Streamlit configuration from environment variables
export STREAMLIT_SERVER_PORT=${STREAMLIT_SERVER_PORT:-8080}
export STREAMLIT_SERVER_ADDRESS=${STREAMLIT_SERVER_ADDRESS:-0.0.0.0}
export STREAMLIT_SERVER_HEADLESS=${STREAMLIT_SERVER_HEADLESS:-true}

echo "Streamlit configuration:"
echo "  Port: $STREAMLIT_SERVER_PORT"
echo "  Address: $STREAMLIT_SERVER_ADDRESS"  
echo "  Headless: $STREAMLIT_SERVER_HEADLESS"

# Start Streamlit server
exec streamlit run demobuilder/app.py \
  --server.port=$STREAMLIT_SERVER_PORT \
  --server.address=$STREAMLIT_SERVER_ADDRESS \
  --server.headless=$STREAMLIT_SERVER_HEADLESS \
  --browser.gatherUsageStats=false \
  --theme.base=light
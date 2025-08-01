#!/bin/bash
set -e

# DemoBuilder startup script
# Configurable for both local development and S2I deployment

# Use environment variables with sensible defaults
PORT=${STREAMLIT_SERVER_PORT:-8501}
ADDRESS=${STREAMLIT_SERVER_ADDRESS:-0.0.0.0}
HEADLESS=${STREAMLIT_SERVER_HEADLESS:-true}

echo "Starting DemoBuilder..."
echo "Access the application at: http://$ADDRESS:$PORT"

# Check if we're in the demobuilder directory or root
if [ -f "app.py" ]; then
    APP_PATH="app.py"
else
    APP_PATH="demobuilder/app.py"
fi

exec streamlit run $APP_PATH \
  --server.headless=$HEADLESS \
  --server.port=$PORT \
  --server.address=$ADDRESS \
  --browser.gatherUsageStats=false
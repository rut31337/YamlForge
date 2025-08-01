#!/bin/bash

# DemoBuilder startup script
# Prevents browser auto-open

echo "Starting DemoBuilder..."
echo "Access the application at: http://localhost:8501"

streamlit run app.py \
  --server.headless=true \
  --server.port=8501 \
  --server.address=0.0.0.0
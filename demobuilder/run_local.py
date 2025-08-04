#!/usr/bin/env python3
"""
Local development runner for DemoBuilder.

This script starts the Streamlit application for local development and testing.
It does not interfere with Docker/Podman builds or OpenShift S2I deployments.

Usage:
    python run_local.py
    python run_local.py --port 8502
    python run_local.py --debug
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def setup_environment():
    """Set up the development environment."""
    # Ensure we're in the demobuilder directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Add the parent directory to Python path for YamlForge imports
    parent_dir = script_dir.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))
    
    print(f"Working directory: {os.getcwd()}")
    print(f"Python path includes: {parent_dir}")

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import streamlit
        print(f"✓ Streamlit {streamlit.__version__} found")
    except ImportError:
        print("✗ Streamlit not found. Install with: pip install streamlit")
        return False
    
    try:
        import yaml
        print(f"✓ PyYAML found")
    except ImportError:
        print("✗ PyYAML not found. Install with: pip install pyyaml")
        return False
    
    # Check for YamlForge
    yamlforge_path = Path("../yamlforge").resolve()
    if yamlforge_path.exists():
        print(f"✓ YamlForge found at {yamlforge_path}")
    else:
        print(f"✗ YamlForge not found at {yamlforge_path}")
        return False
    
    return True

def check_environment_variables():
    """Check and display relevant environment variables."""
    print("\nEnvironment Variables:")
    
    # AI Configuration
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        print(f"✓ ANTHROPIC_API_KEY: {anthropic_key[:8]}...")
    else:
        print("⚠ ANTHROPIC_API_KEY not set (AI features will be limited)")
    
    # Vertex AI
    vertex_project = os.getenv("ANTHROPIC_VERTEX_PROJECT_ID")
    if vertex_project:
        print(f"✓ ANTHROPIC_VERTEX_PROJECT_ID: {vertex_project}")
    else:
        print("- ANTHROPIC_VERTEX_PROJECT_ID not set (Vertex AI unavailable)")
    
    # Provider exclusion
    excluded_providers = os.getenv("YAMLFORGE_EXCLUDE_PROVIDERS")
    if excluded_providers:
        print(f"✓ YAMLFORGE_EXCLUDE_PROVIDERS: {excluded_providers}")
    else:
        print("- YAMLFORGE_EXCLUDE_PROVIDERS not set (all providers enabled)")
    
    # Infrastructure diagrams
    print("✓ Infrastructure diagram visualization: enabled")

def main():
    """Main entry point for local development runner."""
    parser = argparse.ArgumentParser(description="DemoBuilder Local Development Runner")
    parser.add_argument("--port", type=int, default=8501, help="Port to run Streamlit on (default: 8501)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser automatically")
    
    args = parser.parse_args()
    
    print("DemoBuilder Local Development Runner")
    print("=" * 40)
    
    # Setup environment
    setup_environment()
    
    # Check dependencies
    if not check_dependencies():
        print("\n✗ Dependency check failed. Please install missing packages.")
        sys.exit(1)
    
    # Check environment variables
    check_environment_variables()
    
    # Prepare Streamlit command
    streamlit_cmd = [
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", str(args.port),
        "--server.address", "0.0.0.0"
    ]
    
    if args.no_browser:
        streamlit_cmd.extend(["--server.headless", "true"])
    
    if args.debug:
        streamlit_cmd.extend(["--logger.level", "debug"])
    
    print(f"\nStarting DemoBuilder on port {args.port}...")
    print(f"Command: {' '.join(streamlit_cmd)}")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 40)
    
    try:
        # Start Streamlit
        subprocess.run(streamlit_cmd)
    except KeyboardInterrupt:
        print("\n\nStopping DemoBuilder...")
    except FileNotFoundError:
        print("\n✗ Streamlit not found. Install with: pip install streamlit")
        sys.exit(1)

if __name__ == "__main__":
    main()
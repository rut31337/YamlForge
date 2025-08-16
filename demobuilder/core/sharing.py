"""
DemoBuilder State Sharing Module

Handles encoding/decoding of application state for URL-based sharing.
Captures conversation history, provider settings, and workflow state.
"""

import json
import base64
import urllib.parse
from typing import Dict, Any, Optional, List
import streamlit as st
from demobuilder.version import __version__


def capture_shareable_state() -> Dict[str, Any]:
    """
    Capture the current application state that should be shared.
    
    Returns:
        Dict containing all shareable state information
    """
    state = {
        'version': __version__,  # For future compatibility
        'conversation_history': getattr(st.session_state, 'conversation_history', []),
        'current_yaml': getattr(st.session_state, 'current_yaml', ''),
        'workflow_stage': getattr(st.session_state, 'workflow_stage', 'requirements'),
        'enabled_providers': getattr(st.session_state, 'enabled_providers', []),
        'original_requirements': getattr(st.session_state, 'original_requirements', ''),
        'analysis_result': getattr(st.session_state, 'analysis_result', None),
        'show_diagrams_in_chat': getattr(st.session_state, 'show_diagrams_in_chat', True),
        'timestamp': None  # Will be set by calling function
    }
    
    # Only include non-sensitive analysis result data
    if state['analysis_result'] and not state['analysis_result'].get('error'):
        # Include only summary information, not full raw output
        filtered_analysis = {
            'guid': state['analysis_result'].get('guid'),
            'workspace_name': state['analysis_result'].get('workspace_name'),
            'validation_status': state['analysis_result'].get('validation_status'),
            'providers_detected': state['analysis_result'].get('providers_detected', []),
            'resource_summary': state['analysis_result'].get('resource_summary', {}),
            'estimated_costs': state['analysis_result'].get('estimated_costs', {})
        }
        state['analysis_result'] = filtered_analysis
    
    return state


def encode_state_to_url_param(state: Dict[str, Any]) -> str:
    """
    Encode state dictionary to URL-safe base64 string.
    
    Args:
        state: State dictionary to encode
        
    Returns:
        URL-safe base64 encoded string
    """
    try:
        # Convert to JSON string
        json_str = json.dumps(state, separators=(',', ':'))  # Compact JSON
        
        # Encode to bytes then base64
        json_bytes = json_str.encode('utf-8')
        b64_bytes = base64.urlsafe_b64encode(json_bytes)
        
        # Convert to string and remove padding
        b64_str = b64_bytes.decode('ascii').rstrip('=')
        
        return b64_str
    except Exception as e:
        st.error(f"Failed to encode state: {str(e)}")
        return ""


def decode_url_param_to_state(param: str) -> Optional[Dict[str, Any]]:
    """
    Decode URL parameter back to state dictionary.
    
    Args:
        param: URL-safe base64 encoded string
        
    Returns:
        Decoded state dictionary or None if decoding fails
    """
    try:
        # Add padding back if needed
        missing_padding = len(param) % 4
        if missing_padding:
            param += '=' * (4 - missing_padding)
        
        # Decode from base64 to bytes
        json_bytes = base64.urlsafe_b64decode(param.encode('ascii'))
        
        # Decode from bytes to JSON string to dict
        json_str = json_bytes.decode('utf-8')
        state = json.loads(json_str)
        
        return state
    except Exception as e:
        st.error(f"Failed to decode shared state: {str(e)}")
        return None


def generate_share_url(base_url: str = None) -> str:
    """
    Generate a shareable URL with current application state.
    
    Args:
        base_url: Base URL for the application (auto-detected if None)
        
    Returns:
        Complete shareable URL
    """
    try:
        # Capture current state
        state = capture_shareable_state()
        
        # Add timestamp
        import time
        state['timestamp'] = int(time.time())
        
        # Encode state
        encoded_state = encode_state_to_url_param(state)
        
        if not encoded_state:
            return ""
        
        # Get base URL - build complete URL with domain
        if base_url is None:
            try:
                # Try to detect the current server URL
                server_address = st.get_option("server.address") or "localhost"
                server_port = st.get_option("server.port") or 8501
                
                # Handle different address formats
                if server_address == "0.0.0.0":
                    # When bound to all interfaces, use localhost for the URL
                    server_address = "localhost"
                
                # Build the base URL
                if server_port in [80, 443]:
                    # Standard ports don't need to be specified
                    protocol = "https" if server_port == 443 else "http"
                    base_url = f"{protocol}://{server_address}"
                else:
                    # Non-standard ports need to be specified
                    base_url = f"http://{server_address}:{server_port}"
                
                # Add any configured base path
                base_path = st.get_option("server.baseUrlPath") or ""
                if base_path:
                    if not base_path.startswith("/"):
                        base_path = "/" + base_path
                    base_url += base_path
                
            except Exception:
                # Fallback to relative URL
                base_url = "/"
        
        # Ensure base_url ends with proper separator
        if not base_url.endswith("/") and not base_url.endswith("?"):
            if "?" in base_url:
                base_url += "&"
            else:
                base_url += "?"
        elif base_url.endswith("/"):
            base_url += "?"
        
        # Construct URL with query parameter
        share_url = f"{base_url}share={encoded_state}"
        
        return share_url
    except Exception as e:
        st.error(f"Failed to generate share URL: {str(e)}")
        return ""


def restore_state_from_url_params() -> bool:
    """
    Check URL parameters and restore shared state if present.
    
    Returns:
        True if state was restored, False otherwise
    """
    try:
        # Get query parameters from Streamlit
        query_params = st.query_params
        
        # Check if share parameter exists
        if 'share' not in query_params:
            return False
        
        encoded_state = query_params['share']
        if not encoded_state:
            return False
        
        # Decode the state
        state = decode_url_param_to_state(encoded_state)
        if not state:
            return False
        
        # Validate state version for compatibility
        if state.get('version') != __version__:
            st.warning("This shared link uses an incompatible version. Please generate a new share link.")
            return False
        
        # Restore state to session
        restore_session_state(state)
        
        # Clear the query parameter to clean up the URL
        st.query_params.clear()
        
        return True
    except Exception as e:
        st.error(f"Failed to restore shared state: {str(e)}")
        return False


def restore_session_state(state: Dict[str, Any]) -> None:
    """
    Restore session state from decoded shared state.
    
    Args:
        state: Decoded state dictionary
    """
    try:
        # Restore conversation history
        st.session_state.conversation_history = state.get('conversation_history', [])
        
        # Restore YAML configuration
        st.session_state.current_yaml = state.get('current_yaml', '')
        
        # Restore workflow stage
        st.session_state.workflow_stage = state.get('workflow_stage', 'requirements')
        
        # Restore enabled providers
        st.session_state.enabled_providers = state.get('enabled_providers', [])
        
        # Restore original requirements
        if 'original_requirements' in state:
            st.session_state.original_requirements = state['original_requirements']
        
        # Restore analysis result if present
        if state.get('analysis_result'):
            st.session_state.analysis_result = state['analysis_result']
        
        # Restore UI preferences
        st.session_state.show_diagrams_in_chat = state.get('show_diagrams_in_chat', True)
        
        # Reinitialize core components if needed
        if 'yaml_generator' not in st.session_state:
            from core.yaml_generator import YamlForgeGenerator
            st.session_state.yaml_generator = YamlForgeGenerator()
        
        if 'yamlforge_analyzer' not in st.session_state:
            from core.yamlforge_integration import YamlForgeAnalyzer
            st.session_state.yamlforge_analyzer = YamlForgeAnalyzer()
        
        # Show success message
        st.success("🔗 Shared configuration loaded successfully!")
        
    except Exception as e:
        st.error(f"Failed to restore session state: {str(e)}")


def get_shareable_summary(state: Dict[str, Any] = None) -> str:
    """
    Generate a human-readable summary of what will be shared.
    
    Args:
        state: State dictionary (current state if None)
        
    Returns:
        Human-readable summary string
    """
    if state is None:
        state = capture_shareable_state()
    
    summary_parts = []
    
    # Conversation length
    conv_count = len(state.get('conversation_history', []))
    if conv_count > 0:
        summary_parts.append(f"{conv_count} conversation messages")
    
    # Workflow stage
    stage = state.get('workflow_stage', 'requirements')
    stage_names = {
        'requirements': 'Requirements gathering',
        'generation': 'YAML generation', 
        'analysis': 'Analysis in progress',
        'refinement': 'Configuration refinement',
        'complete': 'Completed configuration'
    }
    stage_name = stage_names.get(stage, stage)
    summary_parts.append(f"Workflow: {stage_name}")
    
    # Provider selection
    providers = state.get('enabled_providers', [])
    if providers:
        summary_parts.append(f"{len(providers)} enabled providers")
    
    # YAML configuration
    if state.get('current_yaml'):
        summary_parts.append("Generated configuration")
    
    # Analysis results
    if state.get('analysis_result'):
        summary_parts.append("Analysis results")
    
    return " • ".join(summary_parts) if summary_parts else "Empty session"


def validate_share_state(state: Dict[str, Any]) -> bool:
    """
    Validate that shared state contains required fields and is safe to restore.
    
    Args:
        state: Decoded state dictionary
        
    Returns:
        True if state is valid and safe
    """
    try:
        # Check required fields
        required_fields = ['version', 'conversation_history', 'workflow_stage']
        for field in required_fields:
            if field not in state:
                return False
        
        # Validate conversation history structure
        conv_history = state['conversation_history']
        if not isinstance(conv_history, list):
            return False
        
        for message in conv_history:
            if not isinstance(message, dict) or 'role' not in message or 'content' not in message:
                return False
            if message['role'] not in ['user', 'assistant']:
                return False
        
        # Validate workflow stage
        valid_stages = ['requirements', 'generation', 'analysis', 'refinement', 'complete']
        if state['workflow_stage'] not in valid_stages:
            return False
        
        # Validate enabled providers is a list
        providers = state.get('enabled_providers', [])
        if not isinstance(providers, list):
            return False
        
        return True
    except Exception:
        return False
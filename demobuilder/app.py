import streamlit as st
import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, Any, List
import yaml

from core.yaml_generator import YamlForgeGenerator
from core.validation import validate_and_fix_yaml
from core.yamlforge_integration import YamlForgeAnalyzer
from config.app_config import get_app_config, get_enabled_providers
from config.auth_config import get_auth_config, show_auth_info, is_power_user, get_display_username
from core.infrastructure_diagram import (
    display_mermaid_diagram,
    display_diagram_in_chat
)
from core.sharing import (
    generate_share_url,
    restore_state_from_url_params,
    get_shareable_summary
)
from core.rhdp_integration import get_rhdp_integration
from core.openshift_logging import app_logger, metrics, log_execution_time


def validate_essential_files():
    """Validate that all required YamlForge mapping files are present."""
    # Complete list of all mapping files that should exist
    required_files = [
        'mappings/cloud_patterns.yaml',
        'mappings/flavors/alibaba.yaml',
        'mappings/flavors/aro.yaml',
        'mappings/flavors/aws.yaml',
        'mappings/flavors/azure.yaml',
        'mappings/flavors/cheapest.yaml',
        'mappings/flavors/cnv.yaml',
        'mappings/flavors/gcp.yaml',
        'mappings/flavors/generic.yaml',
        'mappings/flavors/ibm_classic.yaml',
        'mappings/flavors/ibm_vpc.yaml',
        'mappings/flavors/oci.yaml',
        'mappings/flavors/vmware.yaml',
        'mappings/flavors_openshift/openshift_alibaba.yaml',
        'mappings/flavors_openshift/openshift_aws.yaml',
        'mappings/flavors_openshift/openshift_azure.yaml',
        'mappings/flavors_openshift/openshift_gcp.yaml',
        'mappings/flavors_openshift/openshift_generic.yaml',
        'mappings/flavors_openshift/openshift_ibm_classic.yaml',
        'mappings/flavors_openshift/openshift_ibm_vpc.yaml',
        'mappings/flavors_openshift/openshift_oci.yaml',
        'mappings/flavors_openshift/openshift_vmware.yaml',
        'mappings/gcp/machine-type-availability.yaml',
        'mappings/images.yaml',
        'mappings/locations.yaml'
    ]
    
    # Find the correct base path
    possible_paths = [
        Path('.'),
        Path('..'),
        Path('/opt/app-root/src'),
        Path('/app')
    ]
    
    base_path = None
    for path in possible_paths:
        if (path / 'mappings').exists():
            base_path = path
            break
    
    if not base_path:
        st.error("❌ **DemoBuilder Startup Failed**")
        st.error("Could not locate YamlForge mappings directory.")
        st.stop()
    
    # Check each required file
    missing_files = []
    for file_path in required_files:
        full_path = base_path / file_path
        if not full_path.exists():
            missing_files.append(file_path)
    
    if missing_files:
        st.error("❌ **DemoBuilder Startup Failed**")
        st.error("Required YamlForge mapping files are missing:")
        for file_path in missing_files:
            st.code(file_path)
        st.error("These files are required for infrastructure analysis. Please ensure all mapping files are included in the build.")
        st.stop()


def init_session_state():
    # Check for shared state first, before initializing defaults
    shared_state_restored = False
    if not getattr(st.session_state, '_shared_state_restored', False):
        if restore_state_from_url_params():
            shared_state_restored = True
        st.session_state._shared_state_restored = True
    
    # Always initialize these core states (even after shared state restore)
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []
    
    if 'current_yaml' not in st.session_state:
        st.session_state.current_yaml = ""
    
    if 'analysis_result' not in st.session_state:
        st.session_state.analysis_result = None
    
    if 'workflow_stage' not in st.session_state:
        st.session_state.workflow_stage = "requirements"
    
    if 'enabled_providers' not in st.session_state:
        config = get_app_config()
        st.session_state.enabled_providers = get_enabled_providers(config)
    
    if 'yaml_generator' not in st.session_state:
        st.session_state.yaml_generator = YamlForgeGenerator()
    
    if 'yamlforge_analyzer' not in st.session_state:
        st.session_state.yamlforge_analyzer = YamlForgeAnalyzer()
    
    # Initialize UI state (always needed)
    if 'show_examples' not in st.session_state:
        st.session_state.show_examples = False
    
    # Don't clear share URL automatically - let user control it with Clear button
    
    # Cost optimization feature removed


def get_theme_styles():
    """No custom CSS needed - using native Streamlit dark theme."""
    return ""


def display_header():
    st.set_page_config(
        page_title="DemoBuilder - Infrastructure Assistant",
        page_icon="🏗️",
        layout="wide",
        menu_items={
            'Get Help': 'https://docs.anthropic.com/en/docs/claude-code',
            'Report a bug': "https://github.com/anthropics/claude-code/issues", 
            'About': """
            # 🏗️ DemoBuilder
            AI-Powered Multi-Cloud Infrastructure Assistant
            
            Professional dark theme for enhanced focus and reduced eye strain.
            
            ---
            *Built with [Claude Code](https://claude.ai/code)*
            """
        }
    )
    
    # Remove space above content
    st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # Header with title and user authentication status
    username = get_display_username()
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("🏗️ DemoBuilder")
        st.caption("AI-Powered Multi-Cloud Infrastructure Assistant")
    with col2:
        if username:
            st.markdown(f"<div style='text-align: right; padding-top: 20px; font-size: 14px;'>👤 {username}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='text-align: right; padding-top: 20px; font-size: 14px;'>Not Authenticated</div>", unsafe_allow_html=True)


def display_workflow_stage():
    stage_info = {
        "requirements": ("📝", "Requirements Gathering", "Describe your demo infrastructure needs in natural language"),
        "generation": ("⚙️", "YAML Generation", "Generating YamlForge configuration from your requirements"),
        "analysis": ("📊", "Analysis", "Analyzing configuration and estimating costs"),
        "refinement": ("🔧", "Refinement", "Review and refine your configuration"),
        "complete": ("✅", "Complete", "Configuration ready for deployment")
    }
    
    stage = st.session_state.workflow_stage
    emoji, title, description = stage_info.get(stage, ("❓", "Unknown", "Unknown stage"))
    
    with st.container():
        st.subheader(f"{emoji} {title}")
        st.write(description)


def clear_session_state():
    """Clear all session state to start over"""
    # Clear all session state except app config
    keys_to_clear = [
        'conversation_history',
        'current_yaml', 
        'analysis_result',
        'workflow_stage',
        'yaml_generator',
        'yamlforge_analyzer'
    ]
    
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    # Reset workflow stage
    st.session_state.workflow_stage = "requirements"
    st.session_state.conversation_history = []
    st.session_state.current_yaml = ""
    st.session_state.analysis_result = None
    
    # Reinitialize core components
    st.session_state.yaml_generator = YamlForgeGenerator()
    st.session_state.yamlforge_analyzer = YamlForgeAnalyzer()


def handle_share_button_click():
    """Handle the share button click and display the shareable link"""
    try:
        share_url = generate_share_url()
        if share_url:
            # Store the share URL in session state to persist across reruns
            st.session_state.current_share_url = share_url
            # Set a flag to show the share URL was just generated
            st.session_state.share_url_generated = True
        else:
            st.sidebar.error("❌ Failed to generate share link")
    except Exception as e:
        st.sidebar.error(f"❌ Error generating share link: {str(e)}")


def display_share_link_section():
    """Display the share link section if a share URL exists"""
    # Debug: Check if share URL exists
    has_share_url = hasattr(st.session_state, 'current_share_url') and st.session_state.current_share_url
    
    if has_share_url:
        # Only show success message if URL was just generated
        if getattr(st.session_state, 'share_url_generated', False):
            st.sidebar.success("✅ Share link generated!")
            # Clear the flag so it doesn't show again
            st.session_state.share_url_generated = False
        
        # Use a unique key that changes with the URL to avoid caching issues
        share_key = f"share_url_{hash(st.session_state.current_share_url) % 10000}"
        st.sidebar.text_input(
            "Copy this link to share:",
            value=st.session_state.current_share_url,
            key=share_key,
            help="Select all (Ctrl+A) and copy (Ctrl+C) this URL to share your requirements"
        )
        
        if st.sidebar.button(
            "🗑️ Clear", 
            help="Clear the share link display",
            use_container_width=True
        ):
            # Clear the share URL from session state
            if hasattr(st.session_state, 'current_share_url'):
                del st.session_state.current_share_url
            if hasattr(st.session_state, 'share_url_generated'):
                del st.session_state.share_url_generated
            st.rerun()


def display_provider_controls():
    # Authentication info moved to header - no sidebar auth section needed
    
    
    # Start Over and Share buttons - only show if user has conversation history
    if st.session_state.conversation_history:
        # Debug: Show current share state
        if hasattr(st.session_state, 'current_share_url') and st.session_state.current_share_url:
            st.sidebar.caption(f"🔗 Share URL active ({len(st.session_state.current_share_url)} chars)")
            
        if st.sidebar.button(
            "🆕 Start Over", 
            help="Clear all conversation history and start fresh",
            use_container_width=True
        ):
            clear_session_state()
            st.rerun()
        
        if st.sidebar.button(
            "🔗 Share Requirements Link", 
            help="Generate a shareable link with your current requirements",
            use_container_width=True
        ):
            handle_share_button_click()
        
        # Display the share link section if a share URL exists
        display_share_link_section()
        
        st.sidebar.divider()
    
    # Add RHDP refresh credentials section for complete stage
    display_rhdp_refresh_section()
    
    # Add diagram toggle control
    st.sidebar.header("Diagram Settings")
    if 'show_diagrams_in_chat' not in st.session_state:
        st.session_state.show_diagrams_in_chat = True
    
    st.session_state.show_diagrams_in_chat = st.sidebar.checkbox(
        "📊 Show infrastructure diagrams in chat",
        value=st.session_state.show_diagrams_in_chat,
        help="Toggle whether to include visual diagrams in analysis results"
    )
    
    st.sidebar.divider()
    
    st.sidebar.header("Provider Configuration")
    
    config = get_app_config()
    
    # Collapsible Enabled Providers section
    if 'show_sidebar_providers' not in st.session_state:
        st.session_state.show_sidebar_providers = False
    
    providers_button_text = "➖ Enabled Providers (For cheapest cost analysis)" if st.session_state.show_sidebar_providers else "➕ Enabled Providers (For cheapest cost analysis)"
    if st.sidebar.button(providers_button_text, help="Toggle provider configuration"):
        st.session_state.show_sidebar_providers = not st.session_state.show_sidebar_providers
        st.rerun()
    
    provider_updates = {}
    
    if st.session_state.show_sidebar_providers:
        for provider_name, provider_config in config.providers.items():
            current_enabled = provider_name in st.session_state.enabled_providers
            
            new_enabled = st.sidebar.checkbox(
                provider_config.display_name,
                value=current_enabled,
                key=f"provider_{provider_name}",
                help=f"{'GPU Support: ✅' if provider_config.supports_gpu else 'GPU Support: ❌'} | "
                     f"{'OpenShift: ✅' if provider_config.supports_openshift else 'OpenShift: ❌'}"
            )
            
            if new_enabled != current_enabled:
                provider_updates[provider_name] = new_enabled
        
        if provider_updates:
            for provider, enabled in provider_updates.items():
                if enabled and provider not in st.session_state.enabled_providers:
                    st.session_state.enabled_providers.append(provider)
                    app_logger.log_user_action("provider_enabled", provider=provider)
                elif not enabled and provider in st.session_state.enabled_providers:
                    st.session_state.enabled_providers.remove(provider)
                    app_logger.log_user_action("provider_disabled", provider=provider)
            
            # Log the current provider selection
            enabled_providers = list(st.session_state.enabled_providers)
            disabled_providers = [p for p in config.providers.keys() if p not in enabled_providers]
            metrics.track_provider_selection(enabled_providers, disabled_providers)
    
    # Cost optimization section removed as requested
    
    # Examples moved to right pane - removed from sidebar
    
    return False  # Cost optimization disabled


def render_credentials_widgets(content: str) -> str:
    """Render credentials widgets with reveal/copy functionality"""
    import re
    import base64
    
    # Find credentials widget placeholders using a simpler approach
    # Look for the specific pattern we generate
    pattern = r'\[CREDENTIALS_WIDGET:([^:]+):(.*?)\]'
    
    matches = []
    start = 0
    while True:
        match = re.search(r'\[CREDENTIALS_WIDGET:([^:]+):(.*?)\]', content[start:], re.DOTALL)
        if not match:
            break
        
        # Extract reveal_id and the rest of the content
        reveal_id = match.group(1)
        rest_content = match.group(2)
        
        # Split the rest by the first occurrence of ':' to separate hidden and revealed
        if ':' in rest_content:
            parts = rest_content.split(':', 1)
            if len(parts) == 2:
                hidden_example = parts[0]
                revealed_example = parts[1]
                matches.append((reveal_id, hidden_example, revealed_example))
        
        start += match.end()
    
    # Process matches in reverse order to avoid position shifting
    for reveal_id, hidden_example, revealed_example in reversed(matches):
        # Create widget placeholder
        widget_placeholder = f'[CREDENTIALS_WIDGET:{reveal_id}:{hidden_example}:{revealed_example}]'
        
        # Create a container for this widget
        widget_key = f"creds_{reveal_id}"
        
        # Replace the placeholder with a marker for later processing
        # Use base64 encoding to avoid issues with special characters
        hidden_b64 = base64.b64encode(hidden_example.encode()).decode()
        revealed_b64 = base64.b64encode(revealed_example.encode()).decode()
        
        content = content.replace(widget_placeholder, f'[RENDER_CREDENTIALS_WIDGET:{widget_key}:{reveal_id}:{hidden_b64}:{revealed_b64}]')
    
    return content


def render_chat_message_with_diagrams(content: str):
    """Render a chat message that may contain Mermaid diagrams or credentials widgets"""
    # Handle credentials widgets first
    if '[CREDENTIALS_WIDGET:' in content:
        content = render_credentials_widgets(content)
    
    # Check for credentials widgets to render as interactive components
    if '[RENDER_CREDENTIALS_WIDGET:' in content:
        import re
        import base64
        pattern = r'\[RENDER_CREDENTIALS_WIDGET:([^:]+):([^:]+):([^:]+):([^\]]+)\]'
        
        # Split content around widgets
        parts = re.split(pattern, content)
        
        for i in range(0, len(parts)):
            if i % 5 == 0:  # Text parts (non-widget)
                if parts[i].strip():
                    st.write(parts[i].strip())
            elif i % 5 == 1:  # Widget parameters start
                widget_key = parts[i]
                reveal_id = parts[i+1] 
                hidden_b64 = parts[i+2]
                revealed_b64 = parts[i+3]
                
                # Decode base64 content
                try:
                    hidden_example = base64.b64decode(hidden_b64).decode()
                    revealed_example = base64.b64decode(revealed_b64).decode()
                    
                    # Render the interactive credentials widget
                    render_interactive_credentials_widget(widget_key, reveal_id, hidden_example, revealed_example)
                except Exception as e:
                    st.error(f"Error rendering credentials widget: {e}")
        return
    
    # Check if the message contains a Mermaid diagram
    if '[MERMAID_DIAGRAM]:' in content and '[/MERMAID_DIAGRAM]' in content:
        # Split the content around the diagram
        parts = content.split('[MERMAID_DIAGRAM]:')
        
        # Render the text before the diagram
        if parts[0].strip():
            st.write(parts[0].strip())
        
        # Extract and render the diagram
        if len(parts) > 1:
            diagram_part = parts[1].split('[/MERMAID_DIAGRAM]')[0]
            remaining_content = parts[1].split('[/MERMAID_DIAGRAM]')[1] if '[/MERMAID_DIAGRAM]' in parts[1] else ''
            
            # Render the Mermaid diagram
            if diagram_part.strip():
                display_mermaid_diagram(diagram_part.strip(), f"chat_{hash(diagram_part)%10000}")
            
            # Render any remaining content after the diagram
            if remaining_content.strip():
                st.write(remaining_content.strip())
    else:
        # No diagram, render normally
        st.write(content)


def render_interactive_credentials_widget(widget_key: str, reveal_id: str, hidden_example: str, revealed_example: str):
    """Render an interactive credentials widget with reveal/copy functionality"""
    # Initialize widget state
    if f"{widget_key}_revealed" not in st.session_state:
        st.session_state[f"{widget_key}_revealed"] = False
    
    # Show hidden or revealed content based on state
    if st.session_state[f"{widget_key}_revealed"]:
        # Show actual credentials when revealed
        st.code(revealed_example.replace('```bash\n', '').replace('\n```', ''), language='bash')
        
        if st.button("🔒 Hide Credentials", key=f"{widget_key}_hide"):
            st.session_state[f"{widget_key}_revealed"] = False
            st.rerun()
    else:
        # Show hidden credentials visually
        st.code(hidden_example.replace('```bash\n', '').replace('\n```', ''), language='bash')
        
        if st.button("🔓 Reveal Credentials (For Copy)", key=f"{widget_key}_reveal"):
            st.session_state[f"{widget_key}_revealed"] = True
            st.rerun()


def display_chat_interface():
    st.subheader("💬 Conversation")
    
    # Chat input at the top
    user_input = st.chat_input("Describe your demo infrastructure requirements...")
    
    # Latest Response Section - show most recent assistant response
    if st.session_state.conversation_history:
        # Find the most recent assistant message
        latest_assistant_message = None
        for message in reversed(st.session_state.conversation_history):
            if message["role"] == "assistant":
                latest_assistant_message = message
                break
        
        if latest_assistant_message:
            st.markdown("### 🔄 Latest Response")
            # Use Streamlit's native info container for clean styling
            with st.container():
                render_chat_message_with_diagrams(latest_assistant_message["content"])
            
            st.divider()
    
    # Process user input
    if user_input:
        # Log user interaction
        turn_number = len([msg for msg in st.session_state.conversation_history if msg["role"] == "user"]) + 1
        app_logger.log_user_action("chat_input", 
                                 turn_number=turn_number,
                                 input_length=len(user_input),
                                 workflow_stage=st.session_state.workflow_stage)
        
        st.session_state.conversation_history.append({"role": "user", "content": user_input})
        
        with st.chat_message("user"):
            st.write(user_input)
        
        with st.chat_message("assistant"):
            with st.spinner("Processing your requirements..."):
                response = process_user_input(user_input)
                render_chat_message_with_diagrams(response)
        
        # Log conversation turn metrics
        metrics.track_conversation_turn(
            turn_number=turn_number,
            user_input_length=len(user_input),
            ai_response_length=len(response)
        )
        
        st.session_state.conversation_history.append({"role": "assistant", "content": response})
        # Force rerun to ensure sidebar updates properly
        st.rerun()
    
    # Check if there's a pre-filled example to auto-submit
    if 'example_text' in st.session_state:
        example_text = st.session_state.example_text
        del st.session_state.example_text  # Remove after using
        
        # Auto-submit the example
        st.session_state.conversation_history.append({"role": "user", "content": example_text})
        
        with st.chat_message("user"):
            st.write(example_text)
        
        with st.chat_message("assistant"):
            with st.spinner("Processing your requirements..."):
                response = process_user_input(example_text)
                render_chat_message_with_diagrams(response)
        
        st.session_state.conversation_history.append({"role": "assistant", "content": response})
        st.rerun()
    
    # Full conversation history section
    if st.session_state.conversation_history:
        st.markdown("### 📜 Full Conversation History")
        for message in st.session_state.conversation_history:
            with st.chat_message(message["role"]):
                render_chat_message_with_diagrams(message["content"])


def process_user_input(user_input: str) -> str:
    if st.session_state.workflow_stage == "requirements":
        return handle_requirements_stage(user_input)
    elif st.session_state.workflow_stage == "refinement":
        return handle_refinement_stage(user_input)
    elif st.session_state.workflow_stage == "complete":
        return handle_complete_stage(user_input)
    else:
        return "I'm currently processing your request. Please wait for the analysis to complete."


@log_execution_time("requirements_processing")
def handle_requirements_stage(user_input: str) -> str:
    # Log workflow stage transition
    metrics.track_workflow_stage("generation")
    app_logger.log_user_action("requirements_processing_started", 
                             requirements_length=len(user_input))
    
    st.session_state.workflow_stage = "generation"
    
    # Store original requirements for potential cheapest regeneration
    st.session_state.original_requirements = user_input
    
    try:
        enhanced_input = user_input
        
        # For initial generation, don't pass existing config
        is_valid, yaml_config, messages = st.session_state.yaml_generator.generate_from_text(
            enhanced_input, auto_fix=True, use_cheapest=False
        )
        
        if is_valid:
            # Log successful YAML generation
            providers = get_providers_from_current_yaml() if yaml_config else []
            app_logger.log_yaml_generation(True, providers, 
                                         config_size=len(yaml_config))
            metrics.track_workflow_stage("analysis")
            
            st.session_state.current_yaml = yaml_config
            st.session_state.workflow_stage = "analysis"
            
            run_analysis()
            
            response = ""
            
            # Include analysis results in the chat response
            if st.session_state.analysis_result:
                analysis_message = format_analysis_as_chat_message()
                if analysis_message:
                    response = analysis_message
                st.session_state.workflow_stage = "refinement"
                metrics.track_workflow_stage("refinement")
            else:
                response += "\n\n⚠️ I generated the YAML but had trouble analyzing it. You can still review the configuration on the right."
                st.session_state.workflow_stage = "refinement"
                metrics.track_workflow_stage("refinement")
            
            return response
        else:
            # Log failed YAML generation
            app_logger.log_yaml_generation(False, [], 
                                         error=', '.join(messages))
            st.session_state.workflow_stage = "requirements"
            return f"I had trouble generating the configuration. Issues found: {', '.join(messages)}. Could you please clarify your requirements?"
    
    except Exception as e:
        # Log the error
        app_logger.log_error("requirements_processing_error", str(e))
        app_logger.log_yaml_generation(False, [], error=str(e))
        
        st.session_state.workflow_stage = "requirements"
        return f"Sorry, I encountered an error processing your request: {str(e)}. Could you please try rephrasing your requirements?"


def handle_refinement_stage(user_input: str) -> str:
    user_input_lower = user_input.lower()
    
    if any(keyword in user_input_lower for keyword in ['approve', 'accept', 'looks good', 'proceed', 'deploy']):
        st.session_state.workflow_stage = "complete"
        return generate_final_instructions()
    
    # Check for cheapest/cheaper keywords to handle cost optimization requests
    if any(keyword in user_input_lower for keyword in ['cheapest', 'cheaper', 'cost optimize', 'reduce cost']):
        # If user just said "cheapest" without other requirements, regenerate existing config with cheapest providers
        if user_input_lower.strip() in ['cheapest', 'cheaper', 'use cheapest', 'make it cheapest']:
            if st.session_state.current_yaml and hasattr(st.session_state, 'original_requirements'):
                # Regenerate using original requirements with cheapest enabled
                original_text = st.session_state.original_requirements
                
                is_valid, yaml_config, messages = st.session_state.yaml_generator.generate_from_text(
                    original_text, auto_fix=True, use_cheapest=True
                )
                
                if is_valid:
                    st.session_state.current_yaml = yaml_config
                    run_analysis()
                    
                    response = "I've updated the configuration to use the cheapest providers. "
                    
                    # Include updated analysis results in the chat response
                    if st.session_state.analysis_result:
                        analysis_message = format_analysis_as_chat_message()
                        if analysis_message:
                            response += "\n\n" + analysis_message
                    
                    return response
                else:
                    return "I had trouble updating to cheapest providers. Please try describing your requirements again."
            else:
                return "Please provide your infrastructure requirements first, then I can optimize for cost."
    
    try:
        # Pass existing configuration for modifications
        existing_yaml = st.session_state.current_yaml if hasattr(st.session_state, 'current_yaml') else None
        # Determine if request mentions cheapest for cost optimization
        use_cheapest = any(keyword in user_input.lower() for keyword in ['cheapest', 'cheaper', 'cost optimize', 'reduce cost'])
        is_valid, yaml_config, messages = st.session_state.yaml_generator.generate_from_text(
            user_input, auto_fix=True, use_cheapest=use_cheapest, existing_yaml=existing_yaml
        )
        
        
        if is_valid:
            st.session_state.current_yaml = yaml_config
            run_analysis()
            
            response = "I've updated the configuration based on your feedback. "
            
            # Include updated analysis results in the chat response
            if st.session_state.analysis_result:
                analysis_message = format_analysis_as_chat_message()
                if analysis_message:
                    response += "\n\n" + analysis_message
            else:
                response += "Please review the updated configuration on the right."
            
            return response
        else:
            # Format error messages more clearly
            if len(messages) == 1:
                return f"❌ {messages[0]}"
            else:
                error_text = "❌ I had trouble updating the configuration:\n\n"
                for i, msg in enumerate(messages, 1):
                    error_text += f"{i}. {msg}\n"
                error_text += "\nCould you please clarify what you'd like to change?"
                return error_text
    
    except Exception as e:
        return f"Sorry, I encountered an error processing your changes: {str(e)}. Could you please try again?"


def handle_complete_stage(user_input: str) -> str:
    """Handle user input after configuration has been approved - restart refinement process"""
    # Reset workflow stage back to refinement to allow modifications
    st.session_state.workflow_stage = "refinement"
    
    # Process the modification request using the existing refinement logic
    return handle_refinement_stage(user_input)


def run_analysis():
    try:
        analyzer = st.session_state.yamlforge_analyzer
        
        # Pass enabled providers to the analyzer
        enabled_providers = getattr(st.session_state, 'enabled_providers', None)
        
        success, result, errors = asyncio.run(
            analyzer.analyze_configuration(st.session_state.current_yaml, enabled_providers)
        )
        
        if success:
            st.session_state.analysis_result = result
            st.session_state.workflow_stage = "refinement"
        else:
            st.session_state.analysis_result = {
                'error': True,
                'errors': errors
            }
    except Exception as e:
        st.session_state.analysis_result = {
            'error': True,
            'errors': [f"Analysis failed: {str(e)}"]
        }


def display_yaml_preview():
    # Authentication-aware features section
    auth_config = get_auth_config()
    if auth_config.enabled and auth_config.is_authenticated():
        user = auth_config.get_current_user()
        if user and is_power_user():
            st.subheader("Power User Features")
            with st.expander("Advanced Options", expanded=False):
                st.info("Power user features will be available here")
                st.write("• Advanced configuration options")
                st.write("• Historical configurations")
                st.write("• Team collaboration features")
                st.write("• Custom provider templates")
    
    # Examples section in right pane - always visible at the top
    st.subheader("Examples")
    
    button_text = "Hide Examples" if st.session_state.show_examples else "Show Examples"
    if st.button(button_text, help="Toggle example prompts"):
        st.session_state.show_examples = not st.session_state.show_examples
        st.rerun()
    
    
    # Display examples in right pane if toggled on
    if st.session_state.show_examples:
        display_examples_in_right_pane()
    
    # Show approval button during refinement stage
    if st.session_state.workflow_stage == "refinement" and st.session_state.current_yaml:
        st.markdown("---")
        st.subheader("🔍 Review & Approve")
        col1, col2 = st.columns([2, 1])
        with col1:
            st.write("Review the analysis results in the chat, then click Approve Configuration to proceed.")
        with col2:
            if st.button("Approve Configuration", type="primary", help="Approve this configuration and proceed to download"):
                handle_approval()
    
    # Show download button after approval
    if st.session_state.workflow_stage == "complete" and st.session_state.current_yaml:
        st.markdown("---")
        st.subheader("📄 Configuration Approved")
        # Download button to replace the text
        if st.download_button(
            label="📄 Download YamlForge Configuration",
            data=st.session_state.current_yaml,
            file_name="yamlforge-config.yaml",
            mime="text/yaml",
            type="primary"
        ):
            # Log the download event
            providers = get_providers_from_current_yaml()
            config_size = len(st.session_state.current_yaml)
            
            app_logger.log_user_action("yaml_downloaded", 
                                     providers=providers,
                                     config_size_bytes=config_size)
            
            metrics.track_yaml_download(config_size, providers)
    
    # Generated configuration section below examples
    if st.session_state.current_yaml:
        st.markdown("---")
        st.subheader("📄 Generated Configuration")
        
        # Only show view options if user has approved (reached completion stage)
        if st.session_state.workflow_stage == "complete":
            # Expandable section to view YAML content
            with st.expander("🔍 View YamlForge Configuration", expanded=False):
                st.code(st.session_state.current_yaml, language='yaml')
        else:
            st.info("⏳ YamlForge configuration will be available for download after you approve the configuration")
        
        # Raw YamlForge Output debug toggle button - available during refinement and complete stages
        if st.session_state.workflow_stage in ["refinement", "complete"] and st.session_state.analysis_result:
            if 'show_raw_output' not in st.session_state:
                st.session_state.show_raw_output = False
            
            raw_button_text = "➖ Raw YamlForge Output" if st.session_state.show_raw_output else "➕ Raw YamlForge Output"
            if st.button(raw_button_text, help="Toggle raw debug output from YamlForge analysis"):
                st.session_state.show_raw_output = not st.session_state.show_raw_output
                st.rerun()
            
            # Display raw output if toggled on and available
            if st.session_state.show_raw_output:
                raw_output = st.session_state.analysis_result.get('raw_output')
                if raw_output:
                    with st.expander("🔧 Raw YamlForge Debug Output", expanded=True):
                        st.code(raw_output, language='text')
                else:
                    st.warning("No raw output available - analysis may have failed")


def display_analysis_results():
    if st.session_state.analysis_result:
        st.subheader("📊 Analysis Results")
        
        result = st.session_state.analysis_result
        
        if result.get('error'):
            st.error("Analysis failed:")
            for error in result.get('errors', []):
                st.write(f"• {error}")
            return
        
        # Highlight the analysis during review stage
        if st.session_state.workflow_stage == "refinement":
            st.success("✅ Configuration analyzed successfully!")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Configuration Summary:**")
            st.write(f"• GUID: {result.get('guid', 'Not specified')}")
            st.write(f"• Workspace: {result.get('workspace_name', 'Unknown')}")
            st.write(f"• Status: {result.get('validation_status', 'Unknown')}")
        
        with col2:
            providers = result.get('providers_detected', [])
            if providers:
                # Expandable button for providers
                if 'show_providers' not in st.session_state:
                    st.session_state.show_providers = False
                
                providers_button_text = "➖ Enabled Providers" if st.session_state.show_providers else "➕ Enabled Providers"
                if st.button(providers_button_text, help="Toggle provider list", key="providers_toggle"):
                    st.session_state.show_providers = not st.session_state.show_providers
                    st.rerun()
                
                if st.session_state.show_providers:
                    for provider in providers:
                        st.write(f"• {provider}")
        
        if result.get('resource_summary'):
            st.write("**Resource Summary:**")
            for key, value in result.get('resource_summary', {}).items():
                st.write(f"• {key}: {value}")
        
        if result.get('estimated_costs'):
            st.write("**Estimated Costs:**")
            for key, value in result.get('estimated_costs', {}).items():
                st.write(f"• {key}: {value}")
        
        # Show approval reminder during refinement stage
        if st.session_state.workflow_stage == "refinement":
            st.info("💬 Review the configuration and click the 'Approve Configuration' button on the right to proceed with deployment instructions, or suggest changes to refine the configuration.")
        
        if result.get('raw_output'):
            with st.expander("View Raw Analysis Output"):
                st.text(result['raw_output'])
        
        suggest_cost_optimization()


def format_analysis_as_chat_message() -> str:
    """Format analysis results as a chat message"""
    if not st.session_state.analysis_result:
        return ""
    
    result = st.session_state.analysis_result
    
    if result.get('error'):
        message = "⚠️ **Analysis encountered some issues:**\n\n"
        for error in result.get('errors', []):
            message += f"• {error}\n"
        return message
    
    # Just show the relevant parts of the raw YamlForge output as preformatted text
    raw_output = result.get('raw_output', '')
    if not raw_output:
        return "No analysis results available."
    
    message = "📊 **Analysis Results:**\n\n"
    
    # Extract and clean up the relevant sections
    lines = raw_output.split('\n')
    relevant_lines = []
    
    # Skip header and find relevant sections
    in_instances = False
    in_clusters = False
    in_providers = False
    in_cost_summary = False
    
    for line in lines:
        if 'INSTANCES (' in line:
            in_instances = True
            in_clusters = False
            relevant_lines.append(line)
            continue
        elif 'OPENSHIFT CLUSTERS (' in line or 'CLUSTERS (' in line:
            in_instances = False
            in_clusters = True
            relevant_lines.append(line)
            continue
        elif 'REQUIRED PROVIDERS:' in line:
            in_instances = False
            in_clusters = False
            in_providers = True
            relevant_lines.append(line)
            continue
        elif 'COST SUMMARY:' in line:
            in_instances = False
            in_clusters = False
            in_providers = False
            in_cost_summary = True
            relevant_lines.append(line)
            continue
        elif 'ANALYSIS COMPLETE' in line:
            break
        elif line.startswith('==='):
            continue
        
        if (in_instances or in_clusters) and line.strip():
            # Skip the dashes
            if line.strip() == '----------------------------------------':
                continue
            # Skip region lines if unspecified
            if 'Region: unspecified' in line:
                continue
            relevant_lines.append(line)
        elif in_providers and line.strip():
            if line.strip() == '----------------------------------------':
                continue
            relevant_lines.append(line)
        elif in_cost_summary and line.strip():
            if line.strip() == '----------------------------------------':
                continue
            relevant_lines.append(line)
    
    # Show as preformatted text
    if relevant_lines:
        message += "```\n"
        message += '\n'.join(relevant_lines)
        message += "\n```\n\n"
    
    # Add infrastructure diagram marker for rendering (if enabled)
    if getattr(st.session_state, 'show_diagrams_in_chat', True):
        yaml_content = getattr(st.session_state, 'current_yaml', '')
        user_requirements = getattr(st.session_state, 'original_requirements', '')
        diagram_mermaid = display_diagram_in_chat(result, yaml_content, user_requirements)
        
        if diagram_mermaid:
            # Check generation source from the comment in the mermaid code
            generation_source = "Unknown"
            if "%% Generated by: AI Generated" in diagram_mermaid:
                generation_source = "AI Generated"
            elif "%% Generated by: Fallback" in diagram_mermaid:
                generation_source = "Fallback"
            
            message += f"📊 **Infrastructure Diagram** *({generation_source})*:\n\n"
            # Use a special marker that will be processed during display
            message += f"[MERMAID_DIAGRAM]:{diagram_mermaid}[/MERMAID_DIAGRAM]\n\n"
    
    message += "---\n"
    message += "Click the **Approve** button to the right of the analysis or suggest further changes in chat to refine the configuration."
    
    return message

def suggest_cost_optimization():
    # Cost optimization suggestions removed - functionality simplified
    pass


def display_examples_in_right_pane():
    """Display examples in right pane format"""
    st.markdown("**Quick Start Examples:**")
    
    quick_examples = [
        "Three RHEL VMs on AWS with SSH access",
        "Small ROSA cluster for development", 
        "Cheapest medium sized GPU instance for AI/ML",
        "Build a LAMP stack with Linux, Apache, MySQL, PHP on cheapest provider",
        "Two medium sized web servers behind two small load balancer instances - cheapest",
        "Two development VMs on cheapest provider",
        "Two Windows Server 2022 VMs on Azure",
        "PostgreSQL, haproxy, and apache three tier setup on GCP",
        "Multi-cloud: AWS web servers with Azure database and GCP API server",
        "ROSA HCP cluster on AWS"
    ]
    
    # Display examples in a grid format for the right pane
    for i in range(0, len(quick_examples), 2):
        col1, col2 = st.columns(2)
        
        with col1:
            if i < len(quick_examples):
                if st.button(f"📝 {quick_examples[i]}", key=f"right_try_{hash(quick_examples[i])}", use_container_width=True):
                    # Reset session state for fresh start
                    st.session_state.current_yaml = ""
                    st.session_state.analysis_result = None
                    st.session_state.workflow_stage = "requirements"
                    st.session_state.conversation_history = []
                    st.session_state.example_text = quick_examples[i]
                    st.session_state.show_examples = False
                    st.rerun()
        
        with col2:
            if i + 1 < len(quick_examples):
                if st.button(f"📝 {quick_examples[i + 1]}", key=f"right_try_{hash(quick_examples[i + 1])}", use_container_width=True):
                    # Reset session state for fresh start
                    st.session_state.current_yaml = ""
                    st.session_state.analysis_result = None
                    st.session_state.workflow_stage = "requirements"
                    st.session_state.conversation_history = []
                    st.session_state.example_text = quick_examples[i + 1]
                    st.session_state.show_examples = False
                    st.rerun()
    
    st.markdown("---")
    st.markdown("**Usage Tips:**")
    st.markdown("• Type 'cheapest' for cost optimization")
    st.markdown("• Say 'add a node' to expand infrastructure") 
    st.markdown("• Specify providers, sizes, and regions")
    st.markdown("• Click 'Approve' button when ready to download")


def display_examples_in_chat():
    if st.session_state.show_examples:
        st.markdown("---")
        with st.container():
                st.markdown("## 💡 DemoBuilder Conversation Examples")
                st.markdown("Here are examples of effective ways to communicate with DemoBuilder:")
                
                # Basic Examples
                st.markdown("### 🏗️ Basic Infrastructure")
                with st.expander("Simple VM Deployment", expanded=True):
                    st.markdown("""
                    **Good Examples:**
                    - "I need 3 medium RHEL VMs on AWS in us-east with SSH access"
                    - "Create 2 Ubuntu servers on the cheapest cloud provider with web access"
                    - "Deploy 1 large Windows VM on Azure in eastus with RDP access"
                    
                    **What works well:**
                    - ✅ Specify number of VMs
                    - ✅ Mention size (small, medium, large) or specs
                    - ✅ Include OS preference (RHEL, Ubuntu, Windows)
                    - ✅ Specify cloud provider or use "cheapest"
                    - ✅ Mention required access (SSH, HTTP, HTTPS, RDP)
                    """)
                
                with st.expander("GPU Workloads"):
                    st.markdown("""
                    **Good Examples:**
                    - "I need 1 VM with NVIDIA T4 GPU for machine learning on AWS"
                    - "Create a GPU instance for AI training, use the cheapest option"
                    - "Deploy 2 VMs with A100 GPUs on Azure for deep learning"
                    
                    **What works well:**
                    - ✅ Mention "GPU", "AI", "ML", or "machine learning"
                    - ✅ Specify GPU type if you have a preference
                    - ✅ Use "cheapest-gpu" for cost optimization
                    """)
                
                # OpenShift Examples
                st.markdown("### ☸️ OpenShift Clusters")
                with st.expander("OpenShift Deployments"):
                    st.markdown("""
                    **Good Examples:**
                    - "Deploy a small ROSA cluster in us-east-1 for development"
                    - "I need a production ARO cluster on Azure with 6 workers"
                    - "Create a medium OpenShift cluster for testing applications"
                    
                    **What works well:**
                    - ✅ Specify cluster type (ROSA, ARO, self-managed)
                    - ✅ Mention size (small, medium, large) or worker count
                    - ✅ Include purpose (development, production, testing)
                    - ✅ Specify region if important
                    """)
                
                # Advanced Examples
                st.markdown("### 🚀 Advanced Scenarios")
                with st.expander("Multi-Cloud Setups"):
                    st.markdown("""
                    **Good Examples:**
                    - "Create 1 VM on AWS and 1 on Azure, both with web server access"
                    - "Deploy development environment: 2 VMs on cheapest provider + small OpenShift cluster"
                    - "I need VMs on IBM Cloud for compliance and AWS for general workloads"
                    
                    **What works well:**
                    - ✅ Clearly separate requirements for different clouds
                    - ✅ Explain why you need specific providers
                    - ✅ Use workspace names to organize resources
                    """)
                
                with st.expander("Container Workloads"):
                    st.markdown("""
                    **Good Examples:**
                    - "Deploy 2 VMs on OpenShift CNV for containerized applications"
                    - "I need virtual machines running on Kubernetes using CNV"
                    - "Create CNV instances with medium specs for microservices"
                    
                    **What works well:**
                    - ✅ Mention "CNV", "Container Native Virtualization", or "KubeVirt"
                    - ✅ Specify that you want VMs on Kubernetes/OpenShift
                    """)
                
                # Best Practices
                st.markdown("### ✨ Best Practices")
                with st.expander("Communication Tips", expanded=True):
                    st.markdown("""
                    **Be Specific:**
                    - Include quantities, sizes, and purposes
                    - Mention security requirements (SSH, HTTP, HTTPS)
                    - Specify regions if you have preferences
                    
                    **Use Natural Language:**
                    - "I need..." or "Create..." or "Deploy..."
                    - "for development/production/testing"
                    - "with access to..." or "that can run..."
                    
                    **Ask for Refinements:**
                    - "Make those VMs larger"
                    - "Change to Azure instead of AWS"
                    - "Add HTTPS access to the security group"
                    - "Use cheaper alternatives"
                    
                    **Cost Optimization:**
                    - Use "cheapest" for general workloads
                    - Use "cheapest-gpu" for AI/ML workloads
                    - Ask "what would be cheaper?" for alternatives
                    """)
                
                # Quick Examples
                st.markdown("### ⚡ Quick Start Examples")
                quick_examples = [
                    "Three RHEL VMs on AWS with SSH access",
                    "Small ROSA cluster for development",
                    "GPU instance for machine learning",
                    "Web servers with load balancer setup",
                    "Two development VMs on cheapest provider"
                ]
                
                st.markdown("**Try these quick examples:**")
                for example in quick_examples:
                    col_a, col_b = st.columns([6, 2])
                    with col_a:
                        st.code(example)
                    with col_b:
                        if st.button("Try", key=f"try_{hash(example)}"):
                            # Reset session state for fresh start
                            st.session_state.current_yaml = ""
                            st.session_state.analysis_result = None
                            st.session_state.workflow_stage = "requirements"
                            st.session_state.conversation_history = []
                            st.session_state.example_text = example
                            st.session_state.show_examples = False
                            st.rerun()
                
                # Note: Examples can be hidden using the toggle button at the top


def handle_approval():
    """Handle user approval of the current configuration"""
    if st.session_state.workflow_stage == "refinement":
        # Log the approval action
        providers = get_providers_from_current_yaml()
        config_size = len(st.session_state.current_yaml) if st.session_state.current_yaml else 0
        
        app_logger.log_user_action("configuration_approved", 
                                 providers=providers,
                                 config_size_bytes=config_size)
        
        metrics.track_workflow_stage("complete")
        
        st.session_state.workflow_stage = "complete"
        # Add approval message to conversation history
        st.session_state.conversation_history.append({"role": "user", "content": "approve"})
        approval_response = generate_final_instructions()
        st.session_state.conversation_history.append({"role": "assistant", "content": approval_response})
        st.rerun()

def get_providers_from_current_yaml() -> List[str]:
    """Extract provider names from the current YAML configuration."""
    if not st.session_state.current_yaml:
        return []
    
    try:
        config_dict = yaml.safe_load(st.session_state.current_yaml)
        providers = set()
        
        # Check instances for providers
        instances = config_dict.get('yamlforge', {}).get('instances', [])
        for instance in instances:
            provider = instance.get('provider', '')
            if provider:
                providers.add(provider)
        
        # Check clusters for providers
        clusters = config_dict.get('yamlforge', {}).get('openshift_clusters', [])
        for cluster in clusters:
            provider = cluster.get('provider', '')
            if provider:
                providers.add(provider)
        
        # Handle special providers
        resolved_providers = set()
        for provider in providers:
            if provider in ['cheapest', 'cheapest-gpu']:
                # For cheapest providers, include all enabled providers from UI
                enabled_providers = getattr(st.session_state, 'enabled_providers', [])
                # Filter out the special cheapest providers themselves
                enabled_providers = [p for p in enabled_providers if p not in ['cheapest', 'cheapest-gpu']]
                resolved_providers.update(enabled_providers)
            else:
                resolved_providers.add(provider)
        
        return sorted(list(resolved_providers))
    
    except Exception as e:
        # If parsing fails, return all enabled providers as fallback
        return getattr(st.session_state, 'enabled_providers', [])


def generate_credentials_section(providers_used: List[str]) -> str:
    """Generate credential setup instructions for specific providers."""
    if not providers_used:
        return "No cloud credentials needed for this configuration."
    
    # Try to get RHDP credentials first
    rhdp = get_rhdp_integration()
    rhdp_credentials = {}
    
    if rhdp.enabled:
        rhdp_credentials = rhdp.get_all_available_credentials()
    
    credentials_info = {
        "aws": {
            "name": "Amazon Web Services (AWS)",
            "env_vars": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION"],
            "example": """```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```"""
        },
        "azure": {
            "name": "Microsoft Azure",
            "env_vars": ["ARM_CLIENT_ID", "ARM_CLIENT_SECRET", "ARM_SUBSCRIPTION_ID", "ARM_TENANT_ID"],
            "example": """```bash
export ARM_CLIENT_ID="your-client-id"
export ARM_CLIENT_SECRET="your-client-secret"
export ARM_SUBSCRIPTION_ID="your-subscription-id"
export ARM_TENANT_ID="your-tenant-id"
```"""
        },
        "gcp": {
            "name": "Google Cloud Platform (GCP)",
            "env_vars": ["GOOGLE_CREDENTIALS", "GOOGLE_PROJECT"],
            "example": """```bash
export GOOGLE_CREDENTIALS="/path/to/service-account.json"
export GOOGLE_PROJECT="your-project-id"
```"""
        },
        "ibm_vpc": {
            "name": "IBM Cloud VPC",
            "env_vars": ["IC_API_KEY", "IC_REGION"],
            "example": """```bash
export IC_API_KEY="your-api-key"
export IC_REGION="us-south"
```"""
        },
        "ibm_classic": {
            "name": "IBM Cloud Classic",
            "env_vars": ["IC_API_KEY", "IAAS_CLASSIC_USERNAME", "IAAS_CLASSIC_API_KEY"],
            "example": """```bash
export IC_API_KEY="your-api-key"
export IAAS_CLASSIC_USERNAME="your-username"
export IAAS_CLASSIC_API_KEY="your-classic-api-key"
```"""
        },
        "oci": {
            "name": "Oracle Cloud Infrastructure (OCI)",
            "env_vars": ["OCI_CONFIG_FILE", "OCI_CONFIG_PROFILE"],
            "example": """```bash
export OCI_CONFIG_FILE="~/.oci/config"
export OCI_CONFIG_PROFILE="DEFAULT"
```"""
        },
        "alibaba": {
            "name": "Alibaba Cloud",
            "env_vars": ["ALICLOUD_ACCESS_KEY", "ALICLOUD_SECRET_KEY", "ALICLOUD_REGION"],
            "example": """```bash
export ALICLOUD_ACCESS_KEY="your-access-key"
export ALICLOUD_SECRET_KEY="your-secret-key"
export ALICLOUD_REGION="us-east-1"
```"""
        },
        "vmware": {
            "name": "VMware vSphere",
            "env_vars": ["VSPHERE_SERVER", "VSPHERE_USER", "VSPHERE_PASSWORD"],
            "example": """```bash
export VSPHERE_SERVER="vcenter.example.com"
export VSPHERE_USER="administrator@vsphere.local"
export VSPHERE_PASSWORD="your-password"
```"""
        },
        "cnv": {
            "name": "Container Native Virtualization (CNV)",
            "env_vars": ["KUBECONFIG"],
            "example": """```bash
export KUBECONFIG="/path/to/kubeconfig"
```"""
        }
    }
    
    def generate_provider_example(provider: str, info: dict) -> str:
        """Generate example with actual values if available from RHDP."""
        # Check if we have RHDP credentials for this provider
        if provider in rhdp_credentials:
            creds = rhdp_credentials[provider]
            example_lines = []
            hidden_lines = []
            reveal_id = f"reveal_{provider}_{hash(str(creds)) % 10000}"
            
            # Build example with actual values
            for env_var in info['env_vars']:
                if env_var in creds:
                    # Use actual value from RHDP - create hidden version
                    value = creds[env_var]
                    hidden_value = "•" * min(len(value), 20)  # Show dots instead of value
                    example_lines.append(f'export {env_var}="{hidden_value}"')
                    hidden_lines.append(f'export {env_var}="{value}"')
                else:
                    # Fall back to placeholder
                    placeholder = env_var.lower().replace('_', '-')
                    example_lines.append(f'export {env_var}="your-{placeholder}"')
                    hidden_lines.append(f'export {env_var}="your-{placeholder}"')
            
            # Create hidden and revealed versions
            hidden_example = "```bash\n" + "\n".join(example_lines) + "\n```"
            revealed_example = "```bash\n" + "\n".join(hidden_lines) + "\n```"
            
            # Use a placeholder that will be replaced with interactive content in render function
            return f"[CREDENTIALS_WIDGET:{reveal_id}:{hidden_example}:{revealed_example}]"
        else:
            # Use default placeholder example
            return info['example']
    
    if len(providers_used) == 1:
        provider = providers_used[0]
        info = credentials_info.get(provider)
        if info:
            example = generate_provider_example(provider, info)
            rhdp_note = ""
            if provider in rhdp_credentials:
                rhdp_note = f"\n**Note:** These credentials were automatically extracted from RHDP.\n"
            
            # Add refresh credentials button for RHDP users
            refresh_section = ""
            if rhdp.enabled:
                refresh_section = f"""

**Refresh Credentials**: If you just ordered an OPEN environment, use the refresh section below to update credentials while preserving your current configuration."""

            return f"""Set up your {info['name']} credentials:

{example}{rhdp_note}{refresh_section}

For detailed setup instructions, check the [YamlForge envvars.sh example](https://github.com/rut31337/YamlForge/blob/master/envvars.example.sh)."""
        else:
            return f"Set up credentials for {provider} provider."
    
    else:
        sections = []
        for provider in providers_used:
            info = credentials_info.get(provider)
            if info:
                example = generate_provider_example(provider, info)
                rhdp_note = ""
                if provider in rhdp_credentials:
                    rhdp_note = " *(values from RHDP)*"
                
                sections.append(f"**{info['name']}:{rhdp_note}**\n{example}")
            else:
                sections.append(f"**{provider.upper()}:** Set up credentials for {provider}")
        
        credentials_text = "\n\n".join(sections)
        has_rhdp_creds = any(p in rhdp_credentials for p in providers_used)
        rhdp_footer = ""
        if has_rhdp_creds:
            rhdp_footer = "\n**Note:** Some credentials were automatically extracted from RHDP."
        
        # Add refresh credentials button for RHDP users
        refresh_section = ""
        if rhdp.enabled:
            refresh_section = f"""

**Refresh Credentials**: If you just ordered OPEN environments, use the refresh section below to update credentials while preserving your current configuration."""

        return f"""Set up credentials for your selected cloud providers:

{credentials_text}{rhdp_footer}{refresh_section}

For detailed setup instructions, check the [YamlForge envvars.sh example](https://github.com/rut31337/YamlForge/blob/master/envvars.example.sh)."""


def display_rhdp_refresh_section():
    """Display RHDP refresh credentials section in sidebar when appropriate."""
    rhdp = get_rhdp_integration()
    
    # Only show for RHDP enabled users in complete stage
    if not rhdp.enabled or st.session_state.workflow_stage != "complete":
        return
    
    # Check if current config uses supported providers
    providers_used = get_providers_from_current_yaml()
    supported_providers = {'aws', 'azure', 'gcp'}
    rhdp_providers = [p for p in providers_used if p in supported_providers]
    
    if not rhdp_providers:
        return
    
    # Get all available services grouped by provider for selection interface
    all_services = rhdp.get_all_resource_claims_grouped()
    
    # Show service selection interface if multiple services per provider
    has_multiple_services = any(len(services) > 1 for services in all_services.values())
    
    if has_multiple_services:
        st.sidebar.header("🔧 RHDP Service Selection")
        st.sidebar.write("We have detected multiple candidates to put your infrastructure, select which services to use:")
        
        # Initialize selected services in session state if not present
        if 'rhdp_selected_claims' not in st.session_state:
            st.session_state.rhdp_selected_claims = {}
        
        # Provider display names
        provider_names = {
            'aws': 'AWS',
            'azure': 'Azure', 
            'gcp': 'GCP'
        }
        
        # Show selection interface for each provider with multiple services
        selection_changed = False
        for provider in rhdp_providers:
            if provider in all_services and len(all_services[provider]) > 1:
                services = all_services[provider]
                
                # Get current selection or default to first service
                current_selection = st.session_state.rhdp_selected_claims.get(provider)
                if not current_selection:
                    current_selection = services[0].get('metadata', {}).get('name', '')
                
                # Create options for dropdown
                options = []
                for service in services:
                    service_info = rhdp.get_claim_display_info(service)
                    # Extract just the GUID (last part after final dash)
                    full_name = service_info['name']
                    guid = full_name.split('-')[-1] if '-' in full_name else full_name
                    display_name = f"{guid} ({service_info['status']}, {service_info['creation_time']})"
                    options.append((service_info['name'], display_name))
                
                # Find current selection index
                current_index = 0
                for i, (name, _) in enumerate(options):
                    if name == current_selection:
                        current_index = i
                        break
                
                # Show selection dropdown
                selected_option = st.sidebar.selectbox(
                    f"{provider_names.get(provider, provider.upper())} Service:",
                    options,
                    index=current_index,
                    format_func=lambda x: x[1],  # Display the formatted name
                    key=f"rhdp_service_select_{provider}"
                )
                
                # Update selection if changed
                new_selection = selected_option[0]
                if new_selection != st.session_state.rhdp_selected_claims.get(provider):
                    st.session_state.rhdp_selected_claims[provider] = new_selection
                    selection_changed = True
        
        # If selection changed, update credentials automatically
        if selection_changed:
            # Update the last assistant message with new credentials
            if st.session_state.conversation_history and st.session_state.conversation_history[-1]["role"] == "assistant":
                st.session_state.conversation_history[-1]["content"] = generate_final_instructions()
            st.rerun()
        
        st.sidebar.divider()
    
    st.sidebar.header("🔄 RHDP Credentials")
    
    st.sidebar.write("If you just ordered OPEN environments:")
    
    if st.sidebar.button(
        "🔄 Refresh Credentials",
        help="Clear credential cache and reload from RHDP services",
        use_container_width=True
    ):
        # Clear RHDP integration cache to force re-query
        if 'rhdp_integration' in st.session_state:
            del st.session_state.rhdp_integration
        
        # Clear service selections to force re-detection
        if 'rhdp_selected_claims' in st.session_state:
            del st.session_state.rhdp_selected_claims
        
        # Regenerate the final instructions with fresh credentials
        providers_used = get_providers_from_current_yaml()
        credentials_section = generate_credentials_section(providers_used)
        
        # Update the last assistant message with refreshed credentials
        if st.session_state.conversation_history and st.session_state.conversation_history[-1]["role"] == "assistant":
            st.session_state.conversation_history[-1]["content"] = generate_final_instructions()
        
        st.sidebar.success("✅ Credentials refreshed!")
        st.rerun()
    
    st.sidebar.caption("💡 Refresh after OPEN environment provisioning completes")
    st.sidebar.divider()


def generate_refresh_credentials_button() -> str:
    """Generate instructions for refreshing credentials."""
    return """
**To refresh credentials after ordering OPEN environments:**
1. Wait for your OPEN environment(s) to be provisioned (check email for completion)
2. Use the "🔄 Refresh Credentials" button in the sidebar
3. Your configuration will be preserved and credentials will be automatically detected
4. If you have multiple services per provider, use the service selection dropdown to choose which one to use
"""


def generate_open_environment_section(providers_used: List[str]) -> str:
    """Generate OPEN environment ordering instructions for RHDP users."""
    rhdp = get_rhdp_integration()
    
    if not rhdp.enabled:
        return ""
    
    # Only show for supported providers that need OPEN environments
    supported_providers = {'aws', 'azure', 'gcp'}
    rhdp_providers = [p for p in providers_used if p in supported_providers]
    
    if not rhdp_providers:
        return ""
    
    # Get current RHDP credentials to check what's already available
    rhdp_credentials = rhdp.get_all_available_credentials()
    
    # Deep links for ordering OPEN environments
    open_environment_links = {
        'aws': 'https://catalog.demo.redhat.com/catalog?item=babylon-catalog-prod/sandboxes-gpte.sandbox-open.prod&utm_source=webapp&utm_medium=share-link',
        'azure': 'https://catalog.demo.redhat.com/catalog?item=babylon-catalog-prod/azure-gpte.open-environment-azure-subscription.prod&utm_source=webapp&utm_medium=share-link',
        'gcp': 'https://catalog.demo.redhat.com/catalog?item=babylon-catalog-prod/gcp-gpte.open-environment-gcp.prod&utm_source=webapp&utm_medium=share-link'
    }
    
    provider_names = {
        'aws': 'Amazon Web Services (AWS)',
        'azure': 'Microsoft Azure', 
        'gcp': 'Google Cloud Platform (GCP)'
    }
    
    # Build provider list with checkmarks for existing credentials or links to order
    provider_items = []
    for provider in rhdp_providers:
        name = provider_names[provider]
        if provider in rhdp_credentials:
            # Show checkmark if credentials are available
            provider_items.append(f"• **{name}**: ✅ Ready (RHDP)")
        else:
            # Show link to order environment
            link = open_environment_links[provider]
            provider_items.append(f"• **{name}**: [Order Environment]({link})")
    
    provider_list = "\n\n".join(provider_items)
    
    return f"""If you haven't already, you can order Blank OPEN environments for:  

{provider_list}

*Note: Environment provisioning may take several minutes. You can refresh credentials below once your environments are ready.*

---

"""

def generate_final_instructions() -> str:
    # Get current YAML to determine which providers are actually used
    providers_used = get_providers_from_current_yaml()
    
    # Generate OPEN environment ordering section
    open_env_section = generate_open_environment_section(providers_used)
    
    # Generate dynamic credential instructions based on used providers
    credentials_section = generate_credentials_section(providers_used)
    
    instructions = f"""🎉 **Configuration Complete!**

Your YamlForge configuration is ready for deployment. Here's what to do next:

{open_env_section}### 1. Save the Configuration
The configuration file is available for download to the right of the page.

### 2. Set up Cloud Credentials
{credentials_section}

### 3. Prerequisites (Optional Setup)

**If you need to install YamlForge:**
```bash
# Clone the YamlForge repository
git clone https://github.com/rut31337/YamlForge.git
cd YamlForge

# Install Python dependencies
pip install -r requirements.txt
```

**If you need to install Terraform:**
```bash
# On macOS with Homebrew
brew install terraform

# On Ubuntu/Debian
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
sudo apt-get update && sudo apt-get install terraform

# On Windows with Chocolatey
choco install terraform

# Verify installation
terraform version
```

### 4. Deploy Your Infrastructure
```bash
# Change to YamlForge directory (where you cloned it)
cd YamlForge

# Create output directory
mkdir -p output

# Generate Terraform files
python yamlforge.py your-config.yaml -d output/

# Initialize Terraform
cd output && terraform init

# Review the plan
terraform plan

# Apply if everything looks good
terraform apply
```

### 5. Next Steps
- Review the generated Terraform files
- Customize any provider-specific settings if needed
- Set up monitoring and backup procedures
- Configure any additional security settings

Need help with specific cloud provider setup? Check the [YamlForge documentation](https://github.com/rut31337/YamlForge/blob/master/README.md)!
"""
    return instructions


@log_execution_time("main_app_execution")
def main():
    # Initialize logging and track session start
    try:
        app_logger.log_event("application_start", 
                           streamlit_version=st.__version__,
                           python_version=sys.version,
                           environment="openshift")
        
        # Track session initiation
        if 'logging_initialized' not in st.session_state:
            user_agent = st.context.headers.get("User-Agent", "unknown")
            metrics.track_session_start(user_agent=user_agent)
            st.session_state.logging_initialized = True
            app_logger.log_user_action("session_initialized")
        
        validate_essential_files()
        init_session_state()
        display_header()
        display_workflow_stage()
    except Exception as e:
        app_logger.log_error("main_function_error", str(e))
        st.error(f"Application initialization error: {str(e)}")
        raise
    
    display_provider_controls()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        display_chat_interface()
    
    # Full diagram modal removed - now shows in chat
    
    with col2:
        # Always show examples section
        display_yaml_preview()
        
        # Show status messages for YAML when not available
        if not st.session_state.current_yaml:
            if st.session_state.workflow_stage in ["requirements", "generation"]:
                st.info("⏳ YAML configuration will appear here after you approve the analysis.")
            elif st.session_state.workflow_stage in ["analysis", "refinement"]:
                st.info("💬 Review the analysis in the chat and click the 'Approve' button to see the YAML configuration.")
    
    if st.session_state.workflow_stage == "complete":
        st.success("Configuration complete! Follow the instructions above to deploy your infrastructure.")
    
    # Footer with copyright and license information
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; font-size: 0.8rem; margin-top: 2rem;'>
            <!-- <p><a href="https://www.redhat.com" target="_blank"><img src="https://www.redhat.com/cms/managed-files/Logo-Red_Hat-A-Standard-RGB.svg" width="60" height="24" style="vertical-align: middle; margin-right: 8px;" alt="Red Hat Logo"/></a>Copyright © 2025 Red Hat, Inc. - Open Source Software</p> /-->
            <p>Licensed under <a href="https://github.com/rut31337/YamlForge/blob/master/LICENSE" target="_blank">Apache License 2.0</a> | 
            <a href="https://github.com/rut31337/YamlForge" target="_blank"><img src="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png" width="16" height="16" style="vertical-align: middle; margin-right: 4px;"/> View on GitHub</a> | 
            <a href="https://www.redhat.com/en/about/privacy-policy" target="_blank">Privacy Policy</a> | 
            <a href="https://www.redhat.com/en/about/terms-use" target="_blank">Terms of Use</a> | 
            <a href="https://www.redhat.com/en/about/all-policies-guidelines" target="_blank">All Policies</a> |
            No cookies used - All data stays in your browser session</p>
        </div>
        """, 
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()

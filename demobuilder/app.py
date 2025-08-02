import streamlit as st
import asyncio
from typing import Dict, Any, List
import yaml

from core.yaml_generator import YamlForgeGenerator
from core.validation import validate_and_fix_yaml
from core.yamlforge_integration import YamlForgeAnalyzer
from config.app_config import get_app_config, get_enabled_providers


def init_session_state():
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
    
    
    if 'show_examples' not in st.session_state:
        st.session_state.show_examples = False
    
    # Cost optimization feature removed


def get_theme_styles():
    """Get dark mode CSS styles for professional appearance."""
    return """
    <style>
    /* Force dark theme on main containers */
    .stApp, [data-testid="stAppViewContainer"], .main, .block-container {
        background-color: #0e1117 !important;
        color: #fafafa !important;
    }
    
    /* Simple text color override for OpenShift compatibility - exclude code elements */
    p:not(code):not(pre), div:not(.stCode):not([data-testid="stCode"]), 
    span:not(code span), h1, h2, h3, h4, h5, h6, label, a {
        color: #fafafa !important;
    }
    
    /* Hide Streamlit header and toolbar */
    header[data-testid="stHeader"], div[data-testid="stToolbar"], 
    div[data-testid="stDecoration"] {
        display: none !important;
    }
    
    .stAppViewContainer > .main {
        padding-top: 0 !important;
    }
    
    /* Header styling */
    .main-header {
        font-size: 2.2rem;
        color: #fafafa !important;
        text-align: center;
        margin-top: 0;
        margin-bottom: 0.5rem;
    }
    
    .subtitle {
        font-size: 1.1rem;
        opacity: 0.8;
        text-align: center;
        margin-bottom: 1rem;
        color: #fafafa !important;
    }
    
    /* Workflow stage styling */
    .workflow-stage {
        background-color: rgba(255,255,255,0.05) !important;
        color: #fafafa !important;
        padding: 0.75rem;
        border-radius: 0.5rem;
        margin-bottom: 0.75rem;
        border: 1px solid rgba(250, 250, 250, 0.2) !important;
    }
    
    /* YAML preview styling */
    .yaml-preview {
        background-color: #1e1e1e !important;
        color: #e2e8f0 !important;
        padding: 1rem;
        border-radius: 0.5rem;
        font-family: 'Courier New', monospace;
        font-size: 0.9rem;
        border: 1px solid rgba(250, 250, 250, 0.2) !important;
    }
    
    /* Hide deploy button */
    button[title="Deploy this app"] {
        display: none !important;
    }
    
    /* Button styling - black background with light grey text */
    .stButton > button, button {
        background-color: #262730 !important;
        color: #d0d0d0 !important;
        border: 1px solid rgba(250, 250, 250, 0.2) !important;
    }
    
    .stButton > button:hover, button:hover {
        background-color: #3a3a3a !important;
        color: #fafafa !important;
        border-color: #58a6ff !important;
    }
    
    /* Sidebar and provider configuration - grey background with white text */
    section[data-testid="stSidebar"], .stSidebar {
        background-color: #262730 !important;
        color: #fafafa !important;
    }
    
    section[data-testid="stSidebar"] *, .stSidebar * {
        color: #fafafa !important;
    }
    
    /* Text input fields - grey background with light grey text */
    .stTextInput > div > div > input,
    .stChatInput > div > div > input,
    input[type="text"], textarea {
        background-color: #262730 !important;
        color: #e0e0e0 !important;
        border: none !important;
        border-radius: 0.5rem !important;
    }
    
    /* Input field placeholders */
    input::placeholder, textarea::placeholder {
        color: #888 !important;
    }
    
    /* Footer links - light grey */
    a, a:link, a:visited {
        color: #d0d0d0 !important;
    }
    
    a:hover {
        color: #fafafa !important;
    }
    
    /* Analysis results and expanders - grey background with white text */
    .streamlit-expanderHeader, [data-testid="expander"] {
        background-color: #262730 !important;
        color: #fafafa !important;
    }
    
    /* Chat messages - grey background with white text */
    .stChatMessage, [data-testid="chatMessage"] {
        background-color: #262730 !important;
        color: #fafafa !important;
    }
    
    .stChatMessage *:not(code):not(code *), [data-testid="chatMessage"] *:not(code):not(code *) {
        color: #fafafa !important;
    }
    
    /* Only fix text areas in expandable sections if they have readability issues */
    .stTextArea > div > div > textarea {
        background-color: #1e1e1e !important;
        color: #fafafa !important;
        border: none !important;
    }
    
    /* Restore proper padding for preformatted text in chat */
    .stChatMessage code, .stChatMessage pre {
        margin-right: 1rem !important;
        padding-right: 1rem !important;
        max-width: calc(100% - 2rem) !important;
    }
    
    /* Fix preformatted text boxes - dark background in OpenShift */
    .stChatMessage pre, [data-testid="chatMessage"] pre {
        background-color: #1e1e1e !important;
    }
    
    /* Fix text input field container - dark background to match field */
    .stChatInput, .stChatInput > div, .stChatInput > div > div {
        background-color: #262730 !important;
        border: none !important;
        border-radius: 0.5rem !important;
    }
    
    /* Override any remaining black text - simple approach */
    [style*="color: rgb(0, 0, 0)"],
    [style*="color: black"],
    [style*="color: #000"],
    [style*="color: #000000"] {
        color: #fafafa !important;
    }
    </style>
    """


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
    
    # Apply dark theme styles
    st.markdown(get_theme_styles(), unsafe_allow_html=True)
    
    # Simple clean header
    st.markdown('<h1 class="main-header">🏗️ DemoBuilder</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">AI-Powered Multi-Cloud Infrastructure Assistant</p>', unsafe_allow_html=True)


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
    
    st.markdown(f"""
    <div class="workflow-stage">
        <h3>{emoji} {title}</h3>
        <p>{description}</p>
    </div>
    """, unsafe_allow_html=True)


def display_provider_controls():
    st.sidebar.header("🔧 Provider Configuration")
    
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
                elif not enabled and provider in st.session_state.enabled_providers:
                    st.session_state.enabled_providers.remove(provider)
    
    # Cost optimization section removed as requested
    
    # Examples moved to right pane - removed from sidebar
    
    return False  # Cost optimization disabled


def display_chat_interface():
    st.subheader("💬 Conversation")
    
    # Chat input at the top
    user_input = st.chat_input("Describe your demo infrastructure requirements...")
    
    # Examples are now in the sidebar - remove from main area
    
    # Process user input
    if user_input:
        st.session_state.conversation_history.append({"role": "user", "content": user_input})
        
        with st.chat_message("user"):
            st.write(user_input)
        
        with st.chat_message("assistant"):
            with st.spinner("Processing your requirements..."):
                response = process_user_input(user_input)
                st.write(response)
        
        st.session_state.conversation_history.append({"role": "assistant", "content": response})
    
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
                st.write(response)
        
        st.session_state.conversation_history.append({"role": "assistant", "content": response})
        st.rerun()
    
    # Display conversation history
    for message in st.session_state.conversation_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])


def process_user_input(user_input: str) -> str:
    if st.session_state.workflow_stage == "requirements":
        return handle_requirements_stage(user_input)
    elif st.session_state.workflow_stage == "refinement":
        return handle_refinement_stage(user_input)
    elif st.session_state.workflow_stage == "complete":
        return handle_complete_stage(user_input)
    else:
        return "I'm currently processing your request. Please wait for the analysis to complete."


def handle_requirements_stage(user_input: str) -> str:
    st.session_state.workflow_stage = "generation"
    
    # Store original requirements for potential cheapest regeneration
    st.session_state.original_requirements = user_input
    
    try:
        # For initial generation, don't pass existing config
        is_valid, yaml_config, messages = st.session_state.yaml_generator.generate_from_text(
            user_input, auto_fix=True, use_cheapest=False
        )
        
        if is_valid:
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
            else:
                response += "\n\n⚠️ I generated the YAML but had trouble analyzing it. You can still review the configuration on the right."
                st.session_state.workflow_stage = "refinement"
            
            return response
        else:
            st.session_state.workflow_stage = "requirements"
            return f"I had trouble generating the configuration. Issues found: {', '.join(messages)}. Could you please clarify your requirements?"
    
    except Exception as e:
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
    # Examples section in right pane - always visible at the top
    st.subheader("💡 Examples")
    
    button_text = "➖ Hide Examples" if st.session_state.show_examples else "➕ Show Examples"
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
        st.download_button(
            label="📄 Download YamlForge Configuration",
            data=st.session_state.current_yaml,
            file_name="yamlforge-config.yaml",
            mime="text/yaml",
            type="primary"
        )
    
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
    
    if len(providers_used) == 1:
        provider = providers_used[0]
        info = credentials_info.get(provider)
        if info:
            return f"""Set up your {info['name']} credentials:

{info['example']}

For detailed setup instructions, check the [YamlForge envvars.sh example](https://github.com/rut31337/YamlForge/blob/master/envvars.example.sh)."""
        else:
            return f"Set up credentials for {provider} provider."
    
    else:
        sections = []
        for provider in providers_used:
            info = credentials_info.get(provider)
            if info:
                sections.append(f"**{info['name']}:**\n{info['example']}")
            else:
                sections.append(f"**{provider.upper()}:** Set up credentials for {provider}")
        
        credentials_text = "\n\n".join(sections)
        return f"""Set up credentials for your selected cloud providers:

{credentials_text}

For detailed setup instructions, check the [YamlForge envvars.sh example](https://github.com/rut31337/YamlForge/blob/master/envvars.example.sh)."""


def generate_final_instructions() -> str:
    # Get current YAML to determine which providers are actually used
    providers_used = get_providers_from_current_yaml()
    
    # Generate dynamic credential instructions based on used providers
    credentials_section = generate_credentials_section(providers_used)
    
    instructions = f"""🎉 **Configuration Complete!**

Your YamlForge configuration is ready for deployment. Here's what to do next:

### 1. Save the Configuration
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


def main():
    init_session_state()
    display_header()
    display_workflow_stage()
    
    display_provider_controls()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        display_chat_interface()
    
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

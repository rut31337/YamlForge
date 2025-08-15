"""
Infrastructure diagram visualization using Graphviz for DemoBuilder.

This module creates Graphviz infrastructure diagrams from YamlForge analysis results.
"""

from typing import Dict, List, Tuple, Any
import streamlit as st
import json
import os
from .infrastructure_description import generate_infrastructure_description

# AI client imports
try:
    from anthropic import Anthropic
    ANTHROPIC_DIRECT = True
except ImportError:
    ANTHROPIC_DIRECT = False

try:
    from langchain_anthropic import ChatAnthropic
    LANGCHAIN_ANTHROPIC = True
except ImportError:
    LANGCHAIN_ANTHROPIC = False

try:
    from langchain_google_vertexai import ChatVertexAI
    VERTEX_AI = True
except ImportError:
    VERTEX_AI = False


def extract_diagram_data(analysis_result: Dict, yaml_content: str = None, user_requirements: str = None) -> Dict:
    """Extract infrastructure data from YamlForge analysis for visualization"""
    diagram_data = {
        'instances': [],
        'networks': [],
        'storage': [],
        'providers': set(),
        'regions': set(),
        'connections': []
    }
    
    # Extract from analysis result
    if analysis_result:
        # Try direct instances format first (from YamlForge analysis)
        direct_instances = analysis_result.get('instances', [])
        if isinstance(direct_instances, list) and direct_instances:
            for instance in direct_instances:
                if isinstance(instance, dict):
                    provider = instance.get('provider', 'unknown')
                    diagram_data['providers'].add(provider)
                    
                    # Create safe ID for Graphviz
                    instance_name = instance.get('name', 'instance')
                    safe_id = f"{provider}_{instance_name.replace('-', '_').replace('.', '_')}"
                    
                    diagram_data['instances'].append({
                        'name': instance_name,
                        'provider': provider,
                        'type': instance.get('instance_type', instance.get('flavor', 'unknown')),
                        'region': instance.get('region', 'unknown'),
                        'cores': instance.get('cores', 'N/A'),
                        'memory': instance.get('memory', 'N/A'),
                        'purpose': instance.get('purpose', 'compute'),
                        'id': safe_id
                    })
                    
                    if instance.get('region'):
                        diagram_data['regions'].add(f"{provider}:{instance['region']}")
        
        # Fallback to provider analysis format (for compatibility)
        if not diagram_data['instances']:
            provider_analysis = analysis_result.get('provider_analysis', {})
            
            for provider_name, provider_data in provider_analysis.items():
                if not isinstance(provider_data, dict):
                    continue
                    
                diagram_data['providers'].add(provider_name)
                
                # Extract instances/VMs
                instances = provider_data.get('instances', [])
                if isinstance(instances, list):
                    for instance in instances:
                        if isinstance(instance, dict):
                            diagram_data['instances'].append({
                                'name': instance.get('name', f'{provider_name}-instance'),
                                'provider': provider_name,
                                'type': instance.get('instance_type', instance.get('flavor', 'unknown')),
                                'region': instance.get('region', instance.get('location', 'unknown')),
                                'cores': instance.get('cores', 'N/A'),
                                'memory': instance.get('memory', 'N/A'),
                                'purpose': instance.get('purpose', 'compute'),
                                'id': f"{provider_name}_{instance.get('name', 'instance').replace('-', '_')}"
                            })
                            
                            if instance.get('region'):
                                diagram_data['regions'].add(f"{provider_name}:{instance['region']}")
                
                # Extract networking info
                networks = provider_data.get('networking', {})
                if isinstance(networks, dict):
                    vpcs = networks.get('vpcs', [])
                    if isinstance(vpcs, list):
                        for vpc in vpcs:
                            if isinstance(vpc, dict):
                                diagram_data['networks'].append({
                                    'name': vpc.get('name', f'{provider_name}-vpc'),
                                    'provider': provider_name,
                                    'type': 'vpc',
                                    'cidr': vpc.get('cidr', '10.0.0.0/16'),
                                    'id': f"{provider_name}_{vpc.get('name', 'vpc').replace('-', '_')}"
                                })
                
                # Extract storage
                storage = provider_data.get('storage', [])
                if isinstance(storage, list):
                    for storage_item in storage:
                        if isinstance(storage_item, dict):
                            diagram_data['storage'].append({
                                'name': storage_item.get('name', f'{provider_name}-storage'),
                                'provider': provider_name,
                                'type': storage_item.get('type', 'disk'),
                                'size': storage_item.get('size', 'N/A'),
                                'id': f"{provider_name}_{storage_item.get('name', 'storage').replace('-', '_')}"
                            })
    
    # If no instances found from analysis, try to generate from YAML and user requirements
    if not diagram_data['instances'] and yaml_content and user_requirements:
        try:
            infrastructure_desc = generate_infrastructure_description(yaml_content, user_requirements)
            if infrastructure_desc:
                # Convert infrastructure description format to diagram data format
                diagram_data['instances'] = infrastructure_desc.get('instances', [])
                diagram_data['networks'] = infrastructure_desc.get('networks', [])
                diagram_data['storage'] = infrastructure_desc.get('storage', [])
                
                # Extract provider names from provider info dictionaries
                provider_info_list = infrastructure_desc.get('providers', [])
                provider_names = [p.get('name', p) if isinstance(p, dict) else p for p in provider_info_list]
                diagram_data['providers'] = set(provider_names)
                
                diagram_data['regions'] = set()
                for instance in diagram_data['instances']:
                    if instance.get('region'):
                        diagram_data['regions'].add(f"{instance['provider']}:{instance['region']}")
        except Exception as e:
            # Don't show warning in non-Streamlit context
            try:
                import streamlit as st
                st.warning(f"Could not generate infrastructure description: {e}")
            except:
                print(f"Could not generate infrastructure description: {e}")
    
    # Convert sets to lists for JSON serialization
    diagram_data['providers'] = list(diagram_data['providers'])
    diagram_data['regions'] = list(diagram_data['regions'])
    
    # Generate connections between components
    diagram_data['connections'] = _generate_connections(diagram_data)
    
    return diagram_data


def _should_instance_connect_to_network_diagram(instance_purpose: str, network: Dict) -> bool:
    """Determine if an instance should connect to a network based on three-tier architecture security (diagram version)"""
    network_type = network.get('type', '')
    network_name = network.get('name', '').lower()
    
    # For isolated networks (one per instance), always connect
    if 'isolated' in network.get('description', '').lower():
        return True
    
    # For VPC networks, always connect
    if network_type == 'vpc':
        return True
    
    # Three-tier security rules with proper inter-tier connectivity:
    
    # Web servers: Connect to public subnet (for internet) AND app subnet (to reach app servers)
    if instance_purpose == 'web':
        return network_type in ['public_subnet', 'app_subnet'] or any(x in network_name for x in ['public', 'app'])
    
    # Load balancers: Public subnet only (internet-facing)
    elif instance_purpose == 'loadbalancer':
        return network_type == 'public_subnet' or 'public' in network_name
    
    # Application servers: App subnet (primary) AND db subnet (to reach databases)
    elif instance_purpose == 'application':
        return network_type in ['app_subnet', 'db_subnet'] or any(x in network_name for x in ['app', 'db', 'database'])
    
    # Database servers: Database subnet only (most restricted)
    elif instance_purpose == 'database':
        return network_type == 'db_subnet' or any(x in network_name for x in ['db', 'database'])
    
    # Legacy private subnet support (fallback for existing configs)
    elif instance_purpose in ['application', 'database'] and network_type == 'private_subnet':
        return True
    
    # General purpose instances -> connect to any network (fallback)
    else:
        return True


def _generate_connections(diagram_data: Dict) -> List[Dict]:
    """Generate logical connections between infrastructure components"""
    connections = []
    
    instances = diagram_data.get('instances', [])
    networks = diagram_data.get('networks', [])
    storage = diagram_data.get('storage', [])
    
    # Connect instances to networks (same provider) with tier-based isolation
    for instance in instances:
        instance_purpose = instance.get('purpose', 'general')
        
        for network in networks:
            if instance['provider'] == network['provider']:
                # Determine if instance should connect to this network based on purpose and network type
                should_connect = _should_instance_connect_to_network_diagram(instance_purpose, network)
                
                if should_connect:
                    connections.append({
                        'from': instance['id'],
                        'to': network['id'],
                        'type': 'network'
                    })
    
    # Storage is independent - no connections needed
    # Storage buckets are provider-level services that don't connect to instances
    
    # Connect instances across providers (multi-cloud connectivity) with realistic architecture
    # Group instances by purpose and provider
    web_servers = [inst for inst in instances if inst.get('purpose') in ['web', 'loadbalancer']]
    app_servers = [inst for inst in instances if inst.get('purpose') in ['application', 'api', 'app']]
    databases = [inst for inst in instances if inst.get('purpose') == 'database']
    
    # Web servers connect to app servers
    for web in web_servers:
        for app in app_servers:
            if web['provider'] != app['provider']:  # Only inter-cloud connections
                connections.append({
                    'from': web['id'],
                    'to': app['id'],
                    'type': 'inter-cloud'
                })
    
    # App servers connect to databases
    for app in app_servers:
        for db in databases:
            if app['provider'] != db['provider']:  # Only inter-cloud connections
                connections.append({
                    'from': app['id'],
                    'to': db['id'],
                    'type': 'inter-cloud'
                })
    
    # Fallback: if no specific purposes found, use original logic
    if not web_servers and not app_servers and not databases:
        providers = {}
        for instance in instances:
            provider = instance['provider']
            if provider not in providers:
                providers[provider] = []
            providers[provider].append(instance)
        
        provider_list = list(providers.keys())
        for i, provider1 in enumerate(provider_list):
            for j, provider2 in enumerate(provider_list[i+1:], i+1):
                if providers[provider1] and providers[provider2]:
                    inst1 = providers[provider1][0]
                    inst2 = providers[provider2][0]
                    connections.append({
                        'from': inst1['id'],
                        'to': inst2['id'],
                        'type': 'inter-cloud'
                    })
    
    return connections


def create_graphviz_diagram(diagram_data: Dict, mini: bool = False) -> str:
    """Create a Graphviz DOT diagram using AI-driven generation
    
    This function includes enhanced error handling to distinguish between:
    - Template formatting errors (f-string issues)
    - AI service availability issues  
    - DOT syntax validation errors
    - Empty/invalid responses
    
    Returns appropriate error diagrams with specific messages for each failure type.
    """
    
    if not diagram_data or not diagram_data.get('instances'):
        return """
digraph empty {
    rankdir=TB;
    splines=ortho;
    nodesep=0.3;
    ranksep=0.6;
    overlap=false;
    
    node [shape=box, style=rounded, margin=0.2];
    edge [color=gray, penwidth=1.5];
    
    nodata [label="No Infrastructure Data\\nGenerate YAML First", style=filled, fillcolor="#f9f9f9"];
}
"""
    
    # AI-only diagram generation
    try:
        ai_diagram = _generate_ai_graphviz_diagram(diagram_data, mini)
        if ai_diagram and len(ai_diagram.strip()) > 50:
            # Strict validation for proper DOT syntax
            if (ai_diagram.strip().startswith('digraph') and 
                ai_diagram.count('{') == ai_diagram.count('}')):
                # Add generation source indicator
                ai_diagram = _add_generation_source_indicator(ai_diagram, "AI Generated")
                return ai_diagram
            else:
                print("AI diagram has syntax issues")
                return _create_syntax_error_diagram()
        else:
            print("AI diagram generation returned empty or short result")
            return _create_ai_unavailable_diagram()
    except ValueError as e:
        if "Invalid format specifier" in str(e) or "unmatched" in str(e).lower():
            print(f"Prompt template formatting error: {e}")
            return _create_template_error_diagram()
        else:
            print(f"AI diagram generation value error: {e}")
            return _create_ai_unavailable_diagram()
    except Exception as e:
        error_msg = str(e).lower()
        if "ai client" in error_msg or "anthropic" in error_msg or "api" in error_msg:
            print(f"AI service error: {e}")
            return _create_ai_unavailable_diagram()
        else:
            print(f"Unknown diagram generation error: {e}")
            return _create_template_error_diagram()
    
    # Fallback - should not reach here
    return _create_ai_unavailable_diagram()


def _create_ai_unavailable_diagram() -> str:
    """Create an error diagram when AI is unavailable"""
    return """
digraph error {
    rankdir=TB;
    splines=ortho;
    nodesep=0.3;
    ranksep=0.6;
    overlap=false;
    
    node [shape=box, style=rounded, margin=0.2];
    edge [color=gray, penwidth=1.5];
    
    error [label="❌ Diagram Generation Unavailable", style=filled, fillcolor="#ffebee"];
    service [label="AI service is not available", style=filled, fillcolor="#fff3e0"];
    config [label="Please check your API configuration", style=filled, fillcolor="#fff3e0"];
    
    error -> service;
    error -> config;
}
"""


def _create_template_error_diagram() -> str:
    """Create an error diagram when prompt template has formatting issues"""
    return """
digraph template_error {
    rankdir=TB;
    splines=ortho;
    nodesep=0.3;
    ranksep=0.6;
    overlap=false;
    
    node [shape=box, style=rounded, margin=0.2];
    edge [color=gray, penwidth=1.5];
    
    error [label="❌ Prompt Template Error", style=filled, fillcolor="#ffebee"];
    fstring [label="F-string formatting issue detected", style=filled, fillcolor="#fff3e0"];
    check [label="Check diagram template for unescaped braces", style=filled, fillcolor="#fff3e0"];
    
    error -> fstring;
    error -> check;
}
"""


def _create_syntax_error_diagram() -> str:
    """Create an error diagram when AI generates invalid DOT syntax"""
    return """
digraph syntax_error {
    rankdir=TB;
    splines=ortho;
    nodesep=0.3;
    ranksep=0.6;
    overlap=false;
    
    node [shape=box, style=rounded, margin=0.2];
    edge [color=gray, penwidth=1.5];
    
    error [label="❌ Diagram Syntax Error", style=filled, fillcolor="#ffebee"];
    invalid [label="AI generated invalid DOT code", style=filled, fillcolor="#fff3e0"];
    retry [label="Please try regenerating the diagram", style=filled, fillcolor="#fff3e0"];
    
    error -> invalid;
    error -> retry;
}
"""


def _add_generation_source_indicator(dot_code: str, source: str) -> str:
    """Add a small text indicator showing whether diagram was AI generated or fallback"""
    if not dot_code:
        return dot_code
    
    # Just add it as a comment - don't add visual elements that affect layout
    lines = dot_code.split('\n')
    if lines:
        # Add it as a comment right after the digraph declaration
        indicator = f"    // Generated by: {source}"
        
        # Insert after the digraph declaration
        if len(lines) > 1:
            lines.insert(1, indicator)
        else:
            lines.append(indicator)
    
    return '\n'.join(lines)


def _generate_ai_graphviz_diagram(diagram_data: Dict, mini: bool = False) -> str:
    """Generate Graphviz DOT diagram using AI"""
    
    # Initialize AI client
    ai_client = _get_ai_client()
    if not ai_client:
        raise Exception("No AI client available")
    
    # Prepare infrastructure data for AI
    instances = diagram_data.get('instances', [])
    networks = diagram_data.get('networks', [])
    providers = diagram_data.get('providers', [])
    
    # Create simplified data structure for AI
    infrastructure_summary = {
        'providers': providers,
        'instances': [{
            'name': inst.get('name', ''),
            'purpose': inst.get('purpose', 'compute'),
            'provider': inst.get('provider', ''),
            'type': inst.get('type', '')
        } for inst in instances],
        'networks': [{
            'name': net.get('name', ''),
            'type': net.get('type', ''),
            'cidr': net.get('cidr', ''),
            'description': net.get('description', '')
        } for net in networks]
    }
    
    # Create AI prompt for diagram generation
    try:
        prompt = _create_graphviz_generation_prompt(infrastructure_summary, mini)
    except ValueError as e:
        # Re-raise with more context for f-string formatting errors
        raise ValueError(f"Prompt template formatting error: {e}")
    
    # Get AI response
    try:
        dot_code = _call_ai_for_graphviz(ai_client, prompt)
    except Exception as e:
        # Re-raise with more context for AI API errors
        raise Exception(f"AI service call failed: {e}")
    
    # Clean and validate the response
    cleaned_code = _clean_graphviz_response(dot_code)
    
    # Add proper indentation for better rendering
    formatted_code = _format_graphviz_indentation(cleaned_code)
    
    return formatted_code


def _get_ai_client():
    """Initialize and return an AI client"""
    # Try direct Anthropic API first
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key and ANTHROPIC_DIRECT:
        try:
            return ('direct', Anthropic(api_key=api_key))
        except Exception:
            pass
    
    # Try Vertex AI
    vertex_project = os.getenv("ANTHROPIC_VERTEX_PROJECT_ID")
    if vertex_project and VERTEX_AI:
        try:
            llm = ChatVertexAI(
                model="publishers/anthropic/models/claude-3-haiku@20240307",
                temperature=0.1,
                max_tokens=1500,
                project=vertex_project,
                location="us-east5"
            )
            return ('vertex', llm)
        except Exception:
            pass
    
    # Try LangChain Anthropic
    if LANGCHAIN_ANTHROPIC:
        try:
            model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
            llm = ChatAnthropic(model=model, temperature=0.1, max_tokens=1500)
            return ('langchain', llm)
        except Exception:
            pass
    
    return None


def _create_graphviz_generation_prompt(infrastructure_summary: Dict, mini: bool = False) -> str:
    """Create AI prompt for Graphviz DOT diagram generation with proper syntax documentation"""
    
    diagram_type = "compact" if mini else "detailed"
    
    prompt = f"""Create a valid Graphviz DOT diagram for this infrastructure showing network topology with perfect hierarchy. Follow the EXACT syntax rules.

INFRASTRUCTURE DATA:
{json.dumps(infrastructure_summary, indent=2)}

🔍 DEBUGGING: Look at the "provider" field of each instance above! 
- Count how many unique providers you see
- Each unique provider needs its own cloud cluster
- NEVER put instances with different providers in the same cloud!

GRAPHVIZ DOT SYNTAX RULES:

1. DIAGRAM DECLARATION:
   - MUST start with: digraph infrastructure {{
   - Use compound=true for cluster connections
   - Use rankdir=TB for top-bottom layout with internet at top
   - Use splines=ortho for angled arrows that avoid overlapping boxes
   - Use nodesep=0.3 for compact node separation
   - Use ranksep=0.6 for compact rank separation
   - Use overlap=false to prevent node overlapping

2. NODE SYNTAX:
   - Simple: nodeid [label="Node Label"];
   - With styling: nodeid [label="🌐 Web Server", shape=box, style=filled, fillcolor=white];
   - Node IDs must be alphanumeric (webserver1, dbserver, apigateway)
   - Labels can contain spaces and emojis

3. CLUSTER SYNTAX (SUBGRAPHS):
   - MUST use cluster_ prefix: subgraph cluster_aws {{
   - Label with: label="☁️ AWS Cloud";
   - Styling: style=filled; fillcolor="#FFF4E6"; color="#FF9900";
   - End with: }}

4. CONNECTION SYNTAX:
   - Simple: nodeA -> nodeB;
   - Internet to cloud: internet -> node [lhead=cluster_aws]; (every cloud needs this)
   - Cluster connections: nodeA -> nodeB [lhead=cluster_subnet];
   - For cross-cloud: nodeA -> nodeB [ltail=cluster_source, lhead=cluster_dest, style=dotted];
   - Add minlen=2 for longer edges to avoid overlapping with boxes
   - Use constraint=false for non-critical edges to improve layout

PROVIDER COLORS AND STYLING:
- AWS: fillcolor="#FFF4E6"; color="#FF9900";
- Azure: fillcolor="#E6F3FF"; color="#00BCF2";
- GCP: fillcolor="#E8F5E8"; color="#34A853";
- IBM: fillcolor="#E6F0FF"; color="#054ADA";
- Oracle: fillcolor="#FFE6E6"; color="#F80000";

PERFECT HIERARCHY EXAMPLE (Multi-Cloud):
```
digraph infrastructure {{
    compound=true;
    rankdir=TB;
    bgcolor=transparent;
    splines=ortho;
    nodesep=0.3;
    ranksep=0.6;
    overlap=false;
    
    // Global styling
    node [shape=box, style=rounded, margin=0.2];
    edge [color=gray, penwidth=1.5];
    
    // Internet node at top
    internet [label="🌐 Internet", shape=circle, style=filled, fillcolor=lightblue];
    
    // AWS Cloud
    subgraph cluster_aws {{
        label="☁️ AWS Cloud";
        style=filled;
        fillcolor="#FFF4E6";
        color="#FF9900";
        penwidth=2;
        
        // AWS VPC
        subgraph cluster_aws_vpc {{
            label="VPC (10.0.0.0/16)";
            style=filled;
            fillcolor="#F0F8FF";
            color="#4682B4";
            
            // AWS Subnet
            subgraph cluster_aws_subnet {{
                label="Public Subnet (10.0.1.0/24)";
                style=filled;
                fillcolor="#F5F5DC";
                color="#8B4513";
                
                webserver [label="🌐 web-server-1", style=filled, fillcolor=white];
            }}
        }}
    }}
    
    // Azure Cloud  
    subgraph cluster_azure {{
        label="🔷 Azure Cloud";
        style=filled;
        fillcolor="#E6F3FF";
        color="#00BCF2";
        penwidth=2;
        
        // Azure VNet
        subgraph cluster_azure_vnet {{
            label="VNet (10.1.0.0/16)";
            style=filled;
            fillcolor="#F0F8FF";
            color="#4682B4";
            
            // Azure Subnet
            subgraph cluster_azure_subnet {{
                label="App Subnet (10.1.1.0/24)";
                style=filled;
                fillcolor="#F5F5DC";
                color="#8B4513";
                
                apiserver [label="🖥️ api-server-1", style=filled, fillcolor=white];
            }}
        }}
    }}
    
    // GCP Cloud
    subgraph cluster_gcp {{
        label="🍃 GCP Cloud";
        style=filled;
        fillcolor="#E8F5E8";
        color="#34A853";
        penwidth=2;
        
        // GCP VPC
        subgraph cluster_gcp_vpc {{
            label="VPC (10.2.0.0/16)";
            style=filled;
            fillcolor="#F0F8FF";
            color="#4682B4";
            
            // GCP Subnet
            subgraph cluster_gcp_subnet {{
                label="DB Subnet (10.2.1.0/24)";
                style=filled;
                fillcolor="#F5F5DC";
                color="#8B4513";
                
                database [label="🗄️ database-1", style=filled, fillcolor=white];
            }}
        }}
    }}
    
    // Connections with enhanced routing
    internet -> webserver [lhead=cluster_aws, minlen=2];
    internet -> apiserver [lhead=cluster_azure, minlen=2];
    internet -> database [lhead=cluster_gcp, minlen=2];
    webserver -> apiserver [ltail=cluster_aws_subnet, lhead=cluster_azure_subnet, style=dotted, minlen=3];
    apiserver -> database [ltail=cluster_azure_subnet, lhead=cluster_gcp_subnet, style=dotted, minlen=3];
}}
```

SINGLE CLOUD EXAMPLE:
```
digraph infrastructure {{
    compound=true;
    rankdir=TB;
    splines=ortho;
    nodesep=0.3;
    ranksep=0.6;
    overlap=false;
    
    // Global styling
    node [shape=box, style=rounded, margin=0.2];
    edge [color=gray, penwidth=1.5];
    
    // Internet node at top
    internet [label="🌐 Internet", shape=circle, style=filled, fillcolor=lightblue];
    
    subgraph cluster_aws {{
        label="☁️ AWS Cloud";
        style=filled;
        fillcolor="#FFF4E6";
        color="#FF9900";
        
        subgraph cluster_vpc {{
            label="VPC (10.0.0.0/16)";
            style=filled;
            fillcolor="#F0F8FF";
            color="#4682B4";
            
            subgraph cluster_subnet {{
                label="Public Subnet (10.0.1.0/24)";
                style=filled;
                fillcolor="#F5F5DC";
                color="#8B4513";
                
                server1 [label="💻 server-1"];
                server2 [label="💻 server-2"];
            }}
        }}
    }}
    
    internet -> server1 [lhead=cluster_aws, minlen=2];
}}
```

STORAGE-ONLY EXAMPLE:
```
digraph infrastructure {{
    rankdir=TB;
    splines=ortho;
    nodesep=0.3;
    ranksep=0.6;
    overlap=false;
    
    // Global styling
    node [shape=box, style=rounded, margin=0.2];
    edge [color=gray, penwidth=1.5];
    
    // Internet node at top
    internet [label="🌐 Internet", shape=circle, style=filled, fillcolor=lightblue];
    
    subgraph cluster_aws {{
        label="☁️ AWS Cloud";
        style=filled;
        fillcolor="#FFF4E6";
        color="#FF9900";
        
        storage [label="🗄️ backup-storage", shape=cylinder];
    }}
    
    internet -> storage [lhead=cluster_aws, style=dotted, minlen=2];
}}
```

🚨🚨🚨 CRITICAL MULTI-CLOUD INSTANCE DISTRIBUTION 🚨🚨🚨:
- READ THE PROVIDER FIELD OF EACH INSTANCE CAREFULLY! 
- EACH instance MUST go in its own provider's cluster based on its "provider" field
- web-server-1 (provider: aws) → cluster_aws ONLY
- api-server-1 (provider: azure) → cluster_azure ONLY  
- database-1 (provider: gcp) → cluster_gcp ONLY
- NEVER put instances from different providers in the same cluster
- DO NOT default all instances to AWS - CHECK EACH INSTANCE'S PROVIDER FIELD!

STEP-BY-STEP MULTI-CLOUD ALGORITHM:
1. READ each instance's provider field from the infrastructure data
2. CREATE a list of unique providers (e.g., ["aws", "azure", "gcp"])
3. For EACH unique provider, CREATE a separate cluster_provider subgraph
4. PLACE each instance ONLY in its provider's cluster - never mix providers!

CRITICAL RULES:
- ALWAYS use nested clusters: Cloud Provider → VPC/VNet → Subnet → Instances
- Every instance MUST be inside a subnet cluster with CIDR notation
- For multi-cloud: Each provider gets its own separate cluster container
- NEVER put instances from different providers in the same cloud cluster
- Storage buckets go directly in cloud provider clusters, NOT in subnets
- Use compound=true and lhead/ltail for cluster connections
- Internet connections should target cloud clusters (lhead=cluster_aws) not internal subnets
- EVERY cloud provider needs an internet connection for physical connectivity
- Inter-cloud connections must use style=dotted to show they go over the internet
- Follow realistic architecture: web servers → app/api servers → databases (not web → database directly)
- Use splines=ortho for angled arrows that route around boxes
- Use nodesep=0.3, ranksep=0.6, overlap=false for compact spacing
- Add margin=0.2 to nodes for better arrow clearance
- Use penwidth=1.5 for clearer arrow visibility
- Perfect hierarchy is automatic with Graphviz clusters

YOUR TASK:
- Generate ONLY valid DOT code using digraph syntax
- Use top to bottom layout (rankdir=TB) with Internet node at the top
- Show network topology with clusters and CIDR blocks
- Include Internet connectivity and cloud provider containers
- For MULTI-CLOUD: Create separate clusters for each provider with dotted inter-cloud connections
- For SINGLE-CLOUD: Group instances by subnet based on purpose
- ALWAYS use nested clusters - never put instances directly in cloud containers
- Use actual instance names from the data
- Connect to clusters using lhead parameter, not individual instances
- For {diagram_type} style
- NO explanations, ONLY the DOT code

Generate the Graphviz DOT diagram:"""
    
    return prompt


def _call_ai_for_graphviz(ai_client, prompt: str) -> str:
    """Call AI service to generate Graphviz DOT diagram"""
    client_type, client = ai_client
    
    try:
        if client_type == "direct":
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1500,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        
        elif client_type in ["vertex", "langchain"]:
            response = client.invoke(prompt)
            return response.content.strip() if hasattr(response, 'content') else str(response).strip()
    
    except Exception as e:
        raise Exception(f"AI call failed: {e}")
    
    return ""


def _clean_graphviz_response(dot_code: str) -> str:
    """Clean and validate Graphviz DOT response from AI"""
    if not dot_code:
        return ""
    
    # Extract DOT code from markdown blocks if present
    if "```dot" in dot_code:
        dot_code = dot_code.split("```dot")[1].split("```")[0].strip()
    elif "```" in dot_code:
        dot_code = dot_code.split("```")[1].split("```")[0].strip()
    
    lines = dot_code.split('\n')
    cleaned_lines = []
    brace_count = 0
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('//'):  # Skip empty lines and comments
            continue
        
        # Ensure digraph declaration is first
        if not cleaned_lines:
            if not line.startswith('digraph'):
                cleaned_lines.append("digraph infrastructure {")
                brace_count += 1
        
        # Skip duplicate declarations
        if line.startswith('digraph') and cleaned_lines:
            if any(cl.startswith('digraph') for cl in cleaned_lines):
                continue
        
        # Fix invalid node IDs with dashes - convert to underscores
        import re
        # Fix node IDs in declarations: node-id [attributes]
        if '[' in line:
            line = re.sub(r'\b([a-zA-Z][a-zA-Z0-9-]*)\s*(?=\[)', lambda m: m.group(1).replace('-', '_') + ' ', line)
        # Fix node IDs in connections: node-id -> node-id
        if '->' in line:
            # Split on -> and fix node IDs on both sides
            parts = line.split('->')
            if len(parts) == 2:
                left = re.sub(r'\b([a-zA-Z][a-zA-Z0-9-]*)\b', lambda m: m.group(1).replace('-', '_'), parts[0].strip())
                right = re.sub(r'\b([a-zA-Z][a-zA-Z0-9-]*)\b', lambda m: m.group(1).replace('-', '_'), parts[1].strip())
                line = f'{left} -> {right}'
        
        # Count braces for validation
        brace_count += line.count('{') - line.count('}')
        cleaned_lines.append(line)
    
    # Ensure proper closing
    while brace_count > 0:
        cleaned_lines.append('}')
        brace_count -= 1
    
    return '\n'.join(cleaned_lines)


def _format_graphviz_indentation(dot_code: str) -> str:
    """Add proper indentation to DOT code for better rendering"""
    if not dot_code:
        return dot_code
    
    lines = dot_code.split('\n')
    formatted_lines = []
    indent_level = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Decrease indent for closing braces
        if line == '}':
            indent_level = max(0, indent_level - 1)
        
        # Add proper indentation
        if line.startswith('digraph'):
            formatted_lines.append(line)
        elif line.startswith('//'):
            # Comments at current level
            formatted_lines.append('    ' * indent_level + line)
        else:
            # Regular content with proper nesting
            formatted_lines.append('    ' * indent_level + line)
        
        # Increase indent for opening braces (but not digraph)
        if '{' in line and not line.startswith('digraph'):
            indent_level += 1
    
    return '\n'.join(formatted_lines)


def create_mini_infrastructure_diagram(diagram_data: Dict) -> str:
    """Create a mini Graphviz diagram for the sidebar"""
    return create_graphviz_diagram(diagram_data, mini=True)


def create_full_infrastructure_diagram(diagram_data: Dict) -> str:
    """Create a detailed Graphviz diagram for full view"""
    return create_graphviz_diagram(diagram_data, mini=False)


def get_resource_summary(diagram_data: Dict) -> Dict[str, int]:
    """Get summary counts of different resource types"""
    summary = {}
    
    instances = diagram_data.get('instances', [])
    networks = diagram_data.get('networks', [])
    storage = diagram_data.get('storage', [])
    
    if instances:
        summary['Instances'] = len(instances)
        
        # Count by purpose/type
        purposes = {}
        for instance in instances:
            purpose = instance.get('purpose', 'compute')
            purposes[purpose] = purposes.get(purpose, 0) + 1
        
        for purpose, count in purposes.items():
            if count > 1:
                summary[f'{purpose.title()} instances'] = count
    
    if networks:
        summary['Networks'] = len(networks)
    
    if storage:
        summary['Storage volumes'] = len(storage)
    
    return summary


def display_graphviz_diagram(dot_code: str, key: str = "diagram"):
    """Display a Graphviz diagram in Streamlit with @hpcc-js/wasm for rendering"""
    # Use larger height to give more space for proper rendering
    base_height = 300 if key == "mini" else 500
    
    # For chat diagrams, remove height restrictions to span full chat width
    is_chat_diagram = key.startswith("chat_")
    max_height = "none" if is_chat_diagram else f"{base_height}px"
    
    # Build container style based on diagram type
    container_style = f"width: 100%; border: 1px solid #e0e0e0; border-radius: 8px; background: #fafafa; margin: 10px 0; position: relative;"
    if is_chat_diagram:
        # For chat diagrams, use scrollable container with reasonable max height
        container_style += " max-height: 500px; overflow: auto; height: auto;"
    else:
        # For other diagrams, maintain scrollable behavior
        container_style += f" max-height: {max_height}; overflow: auto;"
    
    st.components.v1.html(f"""
    <div id="graphviz-container-{key}" style="{container_style}">
        <!-- Expand button -->
        <button id="expand-btn-{key}" 
                onclick="expandDiagram('{key}')" 
                style="position: absolute; top: 8px; right: 8px; z-index: 1001; 
                       background: #007acc; color: white; border: none; border-radius: 4px; 
                       padding: 4px 8px; font-size: 11px; cursor: pointer; 
                       box-shadow: 0 2px 4px rgba(0,0,0,0.2);"
                title="Expand diagram to full size">
            🔍 Expand
        </button>
        
        <div id="graphviz-{key}" style="width: 100%; {'height: auto;' if is_chat_diagram else f'min-height: {base_height}px;'} text-align: center; margin: 0; padding: {8 if is_chat_diagram else 15}px;">
            <script src="https://unpkg.com/@hpcc-js/wasm@2.13.0/dist/index.js"></script>
            <script>
                // Clear any previous content
                document.getElementById('graphviz-{key}').innerHTML = '<p>Loading Graphviz renderer...</p>';
                
                // Function to expand diagram to full size modal
                function expandDiagram(diagramKey) {{
                    const originalContainer = document.getElementById('graphviz-container-' + diagramKey);
                    
                    if (!originalContainer) return;
                    
                    // Find the topmost document (break out of iframes)
                    let targetDocument = document;
                    let targetWindow = window;
                    try {{
                        while (targetWindow.parent && targetWindow.parent !== targetWindow) {{
                            targetWindow = targetWindow.parent;
                            targetDocument = targetWindow.document;
                        }}
                    }} catch (e) {{
                        targetDocument = document;
                    }}
                    
                    // Create modal overlay
                    const modal = targetDocument.createElement('div');
                    modal.id = 'diagram-modal-' + diagramKey;
                    modal.style.cssText = `
                        position: fixed !important; top: 0 !important; left: 0 !important; 
                        width: 100vw !important; height: 100vh !important; 
                        background: rgba(0,0,0,0.95) !important; z-index: 2147483647 !important; 
                        display: flex !important; align-items: center !important; justify-content: center !important;
                        padding: 0 !important; margin: 0 !important; box-sizing: border-box !important;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
                    `;
                    
                    // Create modal content
                    const modalContent = targetDocument.createElement('div');
                    modalContent.style.cssText = `
                        background: white !important; border-radius: 12px !important; 
                        width: 95vw !important; height: 95vh !important; 
                        overflow: hidden !important; position: relative !important; 
                        box-shadow: 0 20px 60px rgba(0,0,0,0.8) !important;
                        display: flex !important; flex-direction: column !important;
                    `;
                    
                    // Create header
                    const header = targetDocument.createElement('div');
                    header.style.cssText = `
                        background: #f8f9fa !important; border-bottom: 1px solid #dee2e6 !important;
                        padding: 15px 20px !important; display: flex !important; 
                        justify-content: space-between !important; align-items: center !important;
                    `;
                    
                    const title = targetDocument.createElement('h3');
                    title.textContent = 'Infrastructure Diagram - Full Screen View';
                    title.style.cssText = `margin: 0 !important; color: #333 !important; font-size: 18px !important; font-weight: 600 !important;`;
                    
                    const closeButton = targetDocument.createElement('button');
                    closeButton.innerHTML = '✕ Close';
                    closeButton.style.cssText = `
                        background: #dc3545 !important; color: white !important; border: none !important; 
                        border-radius: 6px !important; padding: 8px 16px !important; 
                        font-size: 14px !important; cursor: pointer !important;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.2) !important; font-weight: bold !important;
                    `;
                    closeButton.onclick = () => targetDocument.body.removeChild(modal);
                    
                    header.appendChild(title);
                    header.appendChild(closeButton);
                    
                    // Create diagram container
                    const diagramContainer = targetDocument.createElement('div');
                    diagramContainer.style.cssText = `
                        flex: 1 !important; overflow: auto !important; padding: 20px !important;
                        background: white !important; display: flex !important; 
                        align-items: center !important; justify-content: center !important;
                    `;
                    
                    // Create expanded diagram
                    const expandedDiagram = targetDocument.createElement('div');
                    expandedDiagram.style.cssText = `width: fit-content !important; min-width: 800px !important; text-align: center !important; margin: 0 auto !important;`;
                    expandedDiagram.innerHTML = '<p>Rendering expanded diagram...</p>';
                    
                    diagramContainer.appendChild(expandedDiagram);
                    modalContent.appendChild(header);
                    modalContent.appendChild(diagramContainer);
                    modal.appendChild(modalContent);
                    targetDocument.body.appendChild(modal);
                    
                    // Render diagram in modal
                    renderGraphvizInElement(expandedDiagram, `{dot_code}`);
                    
                    // Close modal on outside click
                    modal.onclick = (e) => {{
                        if (e.target === modal) {{
                            targetDocument.body.removeChild(modal);
                        }}
                    }};
                    
                    // Close modal on escape key
                    const escapeHandler = (e) => {{
                        if (e.key === 'Escape') {{
                            targetDocument.body.removeChild(modal);
                            targetDocument.removeEventListener('keydown', escapeHandler);
                        }}
                    }};
                    targetDocument.addEventListener('keydown', escapeHandler);
                }}
                
                // Make expandDiagram function globally available
                window.expandDiagram = expandDiagram;
                
                // Function to render Graphviz in a specific element
                async function renderGraphvizInElement(element, dotSource) {{
                    try {{
                        // Try to load hpcc-js/wasm
                        let Graphviz;
                        if (typeof window.hpccWasm !== 'undefined') {{
                            Graphviz = window.hpccWasm.Graphviz;
                        }} else {{
                            // Dynamic import fallback
                            const module = await import('https://unpkg.com/@hpcc-js/wasm@2.13.0/dist/index.js');
                            Graphviz = module.Graphviz;
                        }}
                        
                        const graphviz = await Graphviz.load();
                        const svg = graphviz.dot(dotSource);
                        element.innerHTML = svg;
                        
                    }} catch (error) {{
                        console.error('Graphviz rendering error:', error);
                        element.innerHTML = `
                            <div style="color: red; margin-bottom: 15px;">
                                <h4>❌ Graphviz Rendering Failed</h4>
                                <p>Error: ${{error.message}}</p>
                            </div>
                            <div style="background: #f0f0f0; padding: 15px; border-radius: 4px; margin-bottom: 15px;">
                                <h4>🔗 Online Graphviz Renderer</h4>
                                <p>Copy the DOT code below and paste it into:</p>
                                <a href="https://dreampuf.github.io/GraphvizOnline/" target="_blank">Graphviz Online</a>
                            </div>
                            <div style="background: #2d3748; color: #cbd5e0; padding: 15px; border-radius: 4px; font-family: monospace; white-space: pre-wrap; font-size: 12px;">
                                ${{dotSource.replace(/</g, '&lt;').replace(/>/g, '&gt;')}}
                            </div>
                        `;
                    }}
                }}
                
                // Render the main diagram
                renderGraphvizInElement(document.getElementById('graphviz-{key}'), `{dot_code}`);
            </script>
        </div>
    </div>
    """, height=250 if is_chat_diagram else (base_height + 50))


def display_diagram_in_chat(analysis_result, yaml_content: str = '', user_requirements: str = '') -> str:
    """Generate Graphviz diagram for display in chat history"""
    try:
        diagram_data = extract_diagram_data(analysis_result, yaml_content, user_requirements)
        if diagram_data and diagram_data.get('instances'):
            full_dot = create_full_infrastructure_diagram(diagram_data)
            return full_dot
        return None
    except Exception:
        return None
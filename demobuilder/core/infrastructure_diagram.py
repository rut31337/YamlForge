"""
Infrastructure diagram visualization using Mermaid for DemoBuilder.

This module creates Mermaid infrastructure diagrams from YamlForge analysis results.
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
                    
                    # Create safe ID for Mermaid
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
    
    # Connect instances to storage (same provider)
    for instance in instances:
        for storage_item in storage:
            if instance['provider'] == storage_item['provider']:
                connections.append({
                    'from': instance['id'],
                    'to': storage_item['id'],
                    'type': 'storage'
                })
    
    # Connect instances across providers (multi-cloud connectivity)
    providers = {}
    for instance in instances:
        provider = instance['provider']
        if provider not in providers:
            providers[provider] = []
        providers[provider].append(instance)
    
    provider_list = list(providers.keys())
    for i, provider1 in enumerate(provider_list):
        for j, provider2 in enumerate(provider_list[i+1:], i+1):
            # Connect one instance from each provider
            if providers[provider1] and providers[provider2]:
                inst1 = providers[provider1][0]
                inst2 = providers[provider2][0]
                connections.append({
                    'from': inst1['id'],
                    'to': inst2['id'],
                    'type': 'inter-cloud'
                })
    
    return connections


def create_mermaid_diagram(diagram_data: Dict, mini: bool = False) -> str:
    """Create a Mermaid diagram using AI-driven generation"""
    
    if not diagram_data or not diagram_data.get('instances'):
        return """
graph TD
    A[No Infrastructure Data]
    A --> B[Generate YAML First]
    style A fill:#f9f9f9,stroke:#ccc
    style B fill:#fff2cc,stroke:#d6b656
"""
    
    # AI-only diagram generation
    try:
        ai_diagram = _generate_ai_mermaid_diagram(diagram_data, mini)
        if ai_diagram and len(ai_diagram.strip()) > 50:
            # Strict validation for proper Mermaid syntax
            if ((ai_diagram.startswith('graph') or ai_diagram.startswith('flowchart')) and 
                'subgraph' in ai_diagram and 
                ai_diagram.count('subgraph') == ai_diagram.count('end')):
                # Add generation source indicator
                ai_diagram = _add_generation_source_indicator(ai_diagram, "AI Generated")
                return ai_diagram
            else:
                print("AI diagram has syntax issues")
                return _create_ai_unavailable_diagram()
    except Exception as e:
        print(f"AI diagram generation failed: {e}")
    
    # AI unavailable - return error diagram
    return _create_ai_unavailable_diagram()


def _create_ai_unavailable_diagram() -> str:
    """Create an error diagram when AI is unavailable"""
    return """
graph TD
    A[❌ Diagram Generation Unavailable]
    A --> B[AI service is not available]
    A --> C[Please check your API configuration]
    style A fill:#ffebee,stroke:#f44336,color:#000
    style B fill:#fff3e0,stroke:#ff9800,color:#000
    style C fill:#fff3e0,stroke:#ff9800,color:#000
"""


def _add_generation_source_indicator(mermaid_code: str, source: str) -> str:
    """Add a small text indicator showing whether diagram was AI generated or fallback"""
    if not mermaid_code:
        return mermaid_code
    
    # Just add it as a comment - don't add visual elements that affect layout
    lines = mermaid_code.split('\n')
    if lines:
        # Add it as a comment right after the graph declaration
        indicator = f"    %% Generated by: {source}"
        
        # Insert after the graph declaration
        if len(lines) > 1:
            lines.insert(1, indicator)
        else:
            lines.append(indicator)
    
    return '\n'.join(lines)


def _generate_ai_mermaid_diagram(diagram_data: Dict, mini: bool = False) -> str:
    """Generate Mermaid diagram using AI"""
    
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
    prompt = _create_mermaid_generation_prompt(infrastructure_summary, mini)
    
    # Get AI response
    mermaid_code = _call_ai_for_mermaid(ai_client, prompt)
    
    # Clean and validate the response
    cleaned_code = _clean_mermaid_response(mermaid_code)
    
    # Add proper indentation for better rendering
    formatted_code = _format_mermaid_indentation(cleaned_code)
    
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


def _create_mermaid_generation_prompt(infrastructure_summary: Dict, mini: bool = False) -> str:
    """Create AI prompt for Mermaid diagram generation with proper syntax documentation"""
    
    diagram_type = "compact" if mini else "detailed"
    
    prompt = f"""Create a valid Mermaid graph diagram for this infrastructure showing network topology. Follow the EXACT syntax rules.

INFRASTRUCTURE DATA:
{json.dumps(infrastructure_summary, indent=2)}

MERMAID GRAPH SYNTAX RULES (v10.9.3):

1. DIAGRAM DECLARATION:
   - MUST start with: graph LR (left-right preferred for network flow)
   - Use "graph" for network diagrams

2. NODE SYNTAX:
   - Simple: nodeId[Label Text]
   - With icons: nodeId[🔄 Label Text]
   - Circular: nodeId(("🌐 Internet"))
   - NO quotes around node IDs
   - Node IDs must be alphanumeric (web1, dbServer, apiGateway)
   - Labels can contain spaces and emojis

3. SUBGRAPH SYNTAX:
   - CORRECT: subgraph SubId["Label Text"]
   - CORRECT: subgraph SubId[Label Text]  
   - WRONG: subgraph "Label Text"
   - MUST have unique ID followed by bracket notation

4. CONNECTION SYNTAX:
   - CORRECT: nodeA --> nodeB
   - CORRECT: nodeA -.-> nodeB (dotted)
   - Connections go OUTSIDE subgraphs
   - End subgraphs with: end

VALID EXAMPLE FOR NETWORK-BASED THREE-TIER:
```
graph LR
    Internet(("🌐 Internet"))
    
    subgraph Cloud["AWS Cloud"]
        subgraph PublicSubnet["Public Subnet (10.0.1.0/24)"]
            lb[🔄 load-balancer]
            web[🌐 web-server]
        end
        
        subgraph AppSubnet["Application Subnet (10.0.2.0/24)"]
            app[⚡ app-server]
        end
        
        subgraph DatabaseSubnet["Database Subnet (10.0.3.0/24)"]
            db[🗄️ database]
        end
    end
    
    Internet --> lb
    lb --> web
    web --> app
    app --> db
```

VALID EXAMPLE FOR MULTI-CLOUD:
```
graph LR
    Internet(("🌐 Internet"))
    
    subgraph AWS["☁️ AWS Cloud"]
        subgraph AWSVPC["VPC (10.0.0.0/16)"]
            subgraph AWSSubnet["Public Subnet (10.0.1.0/24)"]
                webServer[🌐 web-server]
            end
        end
    end
    
    subgraph Azure["🔷 Azure Cloud"]
        subgraph AzureVNet["VNet (10.1.0.0/16)"]
            subgraph AzureSubnet["Public Subnet (10.1.1.0/24)"]
                database[🗄️ database]
            end
        end
    end
    
    subgraph GCP["🟢 GCP Cloud"]
        subgraph GCPVPC["VPC (10.2.0.0/16)"]
            subgraph GCPSubnet["Public Subnet (10.2.1.0/24)"]
                apiServer[⚡ api-server]
            end
        end
    end
    
    Internet --> AWSSubnet
    Internet --> AzureSubnet  
    Internet --> GCPSubnet
    webServer --> apiServer
    apiServer --> database
    
    style AWS fill:#FF9900,stroke:#e47911,color:#000
    style Azure fill:#00BCF2,stroke:#0078D4,color:#000
    style GCP fill:#34A853,stroke:#137333,color:#fff
```

VALID EXAMPLE FOR SIMPLE CASE:
```
graph LR
    Internet(("🌐 Internet"))
    
    subgraph AWS["AWS Cloud"]
        subgraph Subnet["Subnet (10.0.1.0/24)"]
            vm1[💻 server-1]
            vm2[💻 server-2]
            vm3[💻 server-3]
        end
    end
    
    Internet --> Subnet
```

COMMON SYNTAX ERRORS TO AVOID:
- ❌ flowchart TD (use graph TD for network diagrams)
- ❌ subgraph "Web Tier" (needs ID: subgraph WebTier["Web Tier"])
- ❌ nodeId["Label"] (use nodeId[Label] instead)
- ❌ Connections inside subgraphs
- ❌ Missing "end" statements

PROVIDER ICONS AND COLORS (use these exact formats):
- AWS: subgraph AWS["☁️ AWS Cloud"] + style AWS fill:#FF9900,stroke:#e47911,color:#000
- Azure: subgraph Azure["🔷 Azure Cloud"] + style Azure fill:#00BCF2,stroke:#0078D4,color:#000  
- GCP: subgraph GCP["🟢 GCP Cloud"] + style GCP fill:#34A853,stroke:#137333,color:#fff
- IBM: subgraph IBM["🔵 IBM Cloud"] + style IBM fill:#054ADA,stroke:#003d82,color:#fff
- Oracle: subgraph Oracle["🔴 Oracle Cloud"] + style Oracle fill:#F80000,stroke:#c60000,color:#fff
- VMware: subgraph VMware["⚫ VMware Cloud"] + style VMware fill:#607078,stroke:#455a64,color:#fff

MANDATORY NETWORK STRUCTURE:
- ALWAYS use nested subgraphs: Cloud Provider → VPC/VNet → Subnet → Instances
- Every instance MUST be inside a subnet subgraph with CIDR notation
- Cloud providers MUST contain VPC/subnet containers, never bare instances
- For multi-cloud: Each provider gets its own separate subgraph container
- NEVER put instances from different providers in the same cloud container
- Use format: subgraph ProviderSubnet["Subnet Name (CIDR)"]
- CRITICAL: Each instance should appear ONLY ONCE in the diagram - never create duplicate instances outside subnets
- MULTI-CLOUD NETWORKING: If components connect across clouds, ALL subnets must be PUBLIC for inter-cloud connectivity
- DO NOT assume private subnets unless explicitly mentioned - use public subnets for general VMs with internet access
- SECURITY: Multi-cloud deployments require public subnets with security groups restricting access to specific cloud sources

OPENSHIFT CLUSTER COMPONENTS:
When you see instances with purpose='openshift' or 'control-plane' or 'worker' or 'loadbalancer', these are OpenShift cluster components:

- control-plane nodes: Use ⚙️ icon, group in "Control Plane" subnet
- worker nodes: Use 🔧 icon, group in "Worker Nodes" subnet  
- loadbalancer components: Use 🔄 icon, group in "Load Balancers" subnet
- openshift (generic): Break into logical components if cluster details available

OPENSHIFT EXAMPLE:
```
graph LR
    Internet(("🌐 Internet"))
    
    subgraph AWS["☁️ AWS Cloud"]
        subgraph ROSVPC["ROSA VPC (10.0.0.0/16)"]
            subgraph ControlPlane["Control Plane Subnet (10.0.1.0/24)"]
                controlplane1[⚙️ rosa-dev-controlplane-1]
                controlplane2[⚙️ rosa-dev-controlplane-2] 
                controlplane3[⚙️ rosa-dev-controlplane-3]
            end
            
            subgraph WorkerNodes["Worker Nodes Subnet (10.0.2.0/24)"]
                worker1[🔧 rosa-dev-worker-1]
                worker2[🔧 rosa-dev-worker-2]
                worker3[🔧 rosa-dev-worker-3]
            end
            
            subgraph LoadBalancers["Load Balancers Subnet (10.0.3.0/24)"]
                apilb[🔄 rosa-dev-api-lb]
                ingresslb[🔄 rosa-dev-ingress-lb]
            end
        end
    end
    
    Internet --> apilb
    apilb --> controlplane1
    Internet --> ingresslb
    ingresslb --> worker1
    
    style AWS fill:#FF9900,stroke:#e47911,color:#000
    style ControlPlane fill:#e3f2fd,stroke:#1976d2,color:#000
    style WorkerNodes fill:#e8f5e8,stroke:#388e3c,color:#000
    style LoadBalancers fill:#fff3e0,stroke:#f57c00,color:#000
```

YOUR TASK:
- Generate ONLY valid Mermaid code using graph syntax
- Show network topology with subnets and CIDR blocks
- Include Internet connectivity and cloud provider containers
- ALWAYS include provider icons in cloud subgraph labels (☁️ AWS Cloud, 🔷 Azure Cloud, etc.)
- For MULTI-CLOUD: Create separate subgraphs for each provider (AWS, Azure, GCP, etc.)
- For SINGLE-CLOUD: Group instances by subnet based on purpose (web/public, app, database, control-plane, worker, loadbalancer)
- For OPENSHIFT: Break cluster components into Control Plane, Worker Nodes, and Load Balancers subnets
- ALWAYS use nested subgraphs - never put instances directly in cloud containers
- ONLY include instances that actually exist in the data - DO NOT invent components
- Use actual instance names from the data
- INTERNET CONNECTION RULES: 
  * SINGLE-CLOUD: Internet → LoadBalancer (if exists), OR Internet → PublicSubnet (if no LB)
  * MULTI-CLOUD: Internet → EACH PublicSubnet in EACH cloud provider separately
  * NEVER Internet → individual instances
- Connect instances logically based on their purposes (web → app → database, loadbalancer → workers)
- CRITICAL: NO FLOATING INSTANCES - every instance must be inside a subnet, connections go to subnets or load balancers, NOT individual VMs
- ALWAYS include provider styling at the end using the brand colors above
- For {diagram_type} style
- NO explanations, ONLY the graph code

Generate the Mermaid graph:"""
    
    return prompt


def _call_ai_for_mermaid(ai_client, prompt: str) -> str:
    """Call AI service to generate Mermaid diagram"""
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


def _clean_mermaid_response(mermaid_code: str) -> str:
    """Clean and validate Mermaid response from AI with strict syntax checking"""
    if not mermaid_code:
        return ""
    
    # Extract Mermaid code from markdown blocks if present
    if "```mermaid" in mermaid_code:
        mermaid_code = mermaid_code.split("```mermaid")[1].split("```")[0].strip()
    elif "```" in mermaid_code:
        mermaid_code = mermaid_code.split("```")[1].split("```")[0].strip()
    
    lines = mermaid_code.split('\n')
    cleaned_lines = []
    in_subgraph = False
    subgraph_stack = []
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('%'):  # Skip empty lines and comments
            continue
        
        # Ensure graph/flowchart declaration is first
        if not cleaned_lines:
            if not line.startswith(('flowchart', 'graph')):
                cleaned_lines.append("graph LR")  # Default to graph LR for network diagrams
        
        # Skip duplicate declarations
        if line.startswith(('flowchart', 'graph')) and cleaned_lines:
            if any(cl.startswith(('flowchart', 'graph')) for cl in cleaned_lines):
                continue
        
        # Fix subgraph syntax - ensure proper ID and label format
        if line.startswith('subgraph'):
            in_subgraph = True
            # Extract ID and label properly
            rest = line[8:].strip()  # Remove 'subgraph'
            
            if '[' in rest and ']' in rest:
                # Already properly formatted
                subgraph_id = rest.split('[')[0].strip()
                subgraph_stack.append(subgraph_id)
                cleaned_lines.append(line)
            elif '"' in rest:
                # Has quotes but wrong format: subgraph "Label"
                parts = rest.split('"')
                if len(parts) >= 2:
                    label = parts[1]
                    # Create safe subgraph ID - remove special chars and ensure valid identifier
                    subgraph_id = label.replace(' ', '').replace('🌐', 'Web').replace('⚡', 'App').replace('🗄️', 'Data')
                    subgraph_id = ''.join(c for c in subgraph_id if c.isalnum())  # Only alphanumeric
                    if not subgraph_id:
                        subgraph_id = f'Cloud{len(subgraph_stack)}'  # Fallback ID
                    line = f'subgraph {subgraph_id}["{label}"]'
                    subgraph_stack.append(subgraph_id)
                    cleaned_lines.append(line)
            else:
                # Plain text label - ensure safe ID
                subgraph_id = rest.replace(' ', '').replace('-', '').replace('_', '')
                subgraph_id = ''.join(c for c in subgraph_id if c.isalnum())  # Only alphanumeric
                if not subgraph_id:
                    subgraph_id = f'Container{len(subgraph_stack)}'  # Fallback ID
                line = f'subgraph {subgraph_id}[{rest}]'
                subgraph_stack.append(subgraph_id)
                cleaned_lines.append(line)
            continue
        
        # Handle 'end' statements
        if line == 'end':
            if subgraph_stack:
                subgraph_stack.pop()
                if not subgraph_stack:
                    in_subgraph = False
            cleaned_lines.append(line)
            continue
        
        # Fix node syntax - remove extra quotes and ensure valid node IDs
        if '[' in line and ']' in line and not line.startswith(('subgraph', 'flowchart', 'graph')):
            # Fix node labels with extra quotes
            line = line.replace('["', '[').replace('"]', ']')
            
            # Ensure node IDs are valid (start of line before '[')
            if '-->' not in line and '---' not in line:  # Not a connection line
                parts = line.split('[', 1)
                if len(parts) == 2:
                    node_id = parts[0].strip()
                    node_label = '[' + parts[1]
                    
                    # Clean node ID - only alphanumeric and underscore
                    clean_id = ''.join(c if c.isalnum() or c == '_' else '_' for c in node_id)
                    if clean_id and clean_id[0].isdigit():
                        clean_id = 'node_' + clean_id  # Ensure doesn't start with digit
                    if not clean_id:
                        clean_id = 'node'
                    
                    line = clean_id + node_label
        
        cleaned_lines.append(line)
    
    # Ensure all subgraphs are properly closed
    while subgraph_stack:
        cleaned_lines.append('end')
        subgraph_stack.pop()
    
    # Basic validation - must have graph/flowchart declaration and valid structure
    result = '\n'.join(cleaned_lines)
    if not (result.startswith('graph') or result.startswith('flowchart')) or result.count('subgraph') != result.count('end'):
        # Invalid structure, return empty to force fallback
        return ""
    
    return result


def _format_mermaid_indentation(mermaid_code: str) -> str:
    """Add proper indentation to Mermaid code for better rendering"""
    if not mermaid_code:
        return mermaid_code
    
    lines = mermaid_code.split('\n')
    formatted_lines = []
    indent_level = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Decrease indent for 'end' statements
        if line == 'end':
            indent_level = max(0, indent_level - 1)
        
        # Add proper indentation
        if line.startswith(('graph', 'flowchart')):
            formatted_lines.append(line)
        elif line.startswith('style ') or line.startswith('%'):
            # Style statements and comments at root level
            formatted_lines.append('    ' + line)
        else:
            # Regular content with proper nesting
            formatted_lines.append('    ' * (indent_level + 1) + line)
        
        # Increase indent for subgraph statements
        if line.startswith('subgraph'):
            indent_level += 1
    
    # Add empty line after graph declaration for spacing
    if formatted_lines and formatted_lines[0].startswith(('graph', 'flowchart')):
        formatted_lines.insert(1, '')
    
    # Add empty lines before style section
    style_start = -1
    for i, line in enumerate(formatted_lines):
        if line.strip().startswith('style '):
            style_start = i
            break
    
    if style_start > 0:
        formatted_lines.insert(style_start, '')
    
    return '\n'.join(formatted_lines)






def create_mini_infrastructure_diagram(diagram_data: Dict) -> str:
    """Create a mini Mermaid diagram for the sidebar"""
    return create_mermaid_diagram(diagram_data, mini=True)


def create_full_infrastructure_diagram(diagram_data: Dict) -> str:
    """Create a detailed Mermaid diagram for full view"""
    return create_mermaid_diagram(diagram_data, mini=False)


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


def display_mermaid_diagram(mermaid_code: str, key: str = "diagram"):
    """Display a Mermaid diagram in Streamlit with scrollable container and expand button"""
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
    <div id="mermaid-container-{key}" style="{container_style}">
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
        
        
        
        <div id="mermaid-{key}" style="width: 100%; {f'height: auto;' if is_chat_diagram else f'min-height: {base_height}px;'} text-align: center; margin: 0; padding: {8 if is_chat_diagram else 15}px;">
            <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
            <script>
                // Clear any previous mermaid content
                document.getElementById('mermaid-{key}').innerHTML = '';
                
                mermaid.initialize({{ 
                    startOnLoad: false,
                    theme: 'base',
                    themeVariables: {{
                        primaryColor: '#fff',
                        primaryTextColor: '#333',
                        primaryBorderColor: '#333',
                        lineColor: '#666',
                        clusterBkg: '#f9f9f9',
                        clusterBorder: '#333'
                    }},
                    flowchart: {{
                        useMaxWidth: {str(is_chat_diagram).lower()},
                        htmlLabels: true,
                        subgraphTitleMargin: {{
                            top: {3 if is_chat_diagram else 5},
                            bottom: {10 if is_chat_diagram else 25}
                        }},
                        padding: {8 if is_chat_diagram else 15},
                        nodeSpacing: {20 if is_chat_diagram else 30},
                        rankSpacing: {20 if is_chat_diagram else 30}
                    }}
                }});
                
                // Function to expand diagram to full size modal
                function expandDiagram(diagramKey) {{
                    const originalContainer = document.getElementById('mermaid-container-' + diagramKey);
                    const originalContent = document.getElementById('mermaid-' + diagramKey);
                    
                    if (!originalContainer || !originalContent) return;
                    
                    // Find the topmost document (break out of iframes)
                    let targetDocument = document;
                    let targetWindow = window;
                    try {{
                        while (targetWindow.parent && targetWindow.parent !== targetWindow) {{
                            targetWindow = targetWindow.parent;
                            targetDocument = targetWindow.document;
                        }}
                    }} catch (e) {{
                        // Cross-origin restriction, use current document
                        targetDocument = document;
                    }}
                    
                    // Create modal overlay that covers the entire top-level viewport
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
                    
                    // Create modal content container
                    const modalContent = targetDocument.createElement('div');
                    modalContent.style.cssText = `
                        background: white !important; border-radius: 12px !important; 
                        width: 95vw !important; height: 95vh !important; 
                        overflow: hidden !important; position: relative !important; 
                        box-shadow: 0 20px 60px rgba(0,0,0,0.8) !important;
                        display: flex !important; flex-direction: column !important;
                    `;
                    
                    // Create header with title and close button
                    const header = targetDocument.createElement('div');
                    header.style.cssText = `
                        background: #f8f9fa !important; border-bottom: 1px solid #dee2e6 !important;
                        padding: 15px 20px !important; display: flex !important; 
                        justify-content: space-between !important; align-items: center !important;
                    `;
                    
                    const title = targetDocument.createElement('h3');
                    title.textContent = 'Infrastructure Diagram - Full Screen View';
                    title.style.cssText = `
                        margin: 0 !important; color: #333 !important; font-size: 18px !important;
                        font-weight: 600 !important;
                    `;
                    
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
                    
                    // Create diagram container that fills remaining space
                    const diagramContainer = targetDocument.createElement('div');
                    diagramContainer.style.cssText = `
                        flex: 1 !important; overflow: auto !important; padding: 20px !important;
                        background: white !important; display: flex !important; 
                        align-items: center !important; justify-content: center !important;
                    `;
                    
                    // Create new diagram div with original mermaid code
                    const expandedDiagram = targetDocument.createElement('div');
                    expandedDiagram.className = 'mermaid';
                    expandedDiagram.style.cssText = `
                        width: fit-content !important; min-width: 800px !important; 
                        text-align: center !important; margin: 0 auto !important;
                    `;
                    expandedDiagram.textContent = `{mermaid_code}`;
                    
                    diagramContainer.appendChild(expandedDiagram);
                    
                    // Assemble modal
                    modalContent.appendChild(header);
                    modalContent.appendChild(diagramContainer);
                    modal.appendChild(modalContent);
                    targetDocument.body.appendChild(modal);
                    
                    // Load Mermaid in the target document if not already loaded
                    if (!targetDocument.querySelector('script[src*="mermaid"]')) {{
                        const mermaidScript = targetDocument.createElement('script');
                        mermaidScript.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
                        targetDocument.head.appendChild(mermaidScript);
                        
                        mermaidScript.onload = () => {{
                            initializeAndRenderDiagram();
                        }};
                    }} else {{
                        initializeAndRenderDiagram();
                    }}
                    
                    function initializeAndRenderDiagram() {{
                        // Initialize mermaid in target document
                        if (targetWindow.mermaid) {{
                            targetWindow.mermaid.initialize({{
                                startOnLoad: false,
                                theme: 'base',
                                themeVariables: {{
                                    primaryColor: '#fff',
                                    primaryTextColor: '#333',
                                    primaryBorderColor: '#333',
                                    lineColor: '#666',
                                    clusterBkg: '#f9f9f9',
                                    clusterBorder: '#333'
                                }},
                                flowchart: {{
                                    useMaxWidth: false,
                                    htmlLabels: true,
                                    subgraphTitleMargin: {{
                                        top: 5,
                                        bottom: 25
                                    }},
                                    padding: 15,
                                    nodeSpacing: 30,
                                    rankSpacing: 30
                                }}
                            }});
                            
                            // Render the diagram
                            try {{
                                targetWindow.mermaid.init(undefined, expandedDiagram);
                            }} catch (error) {{
                                console.error('Error rendering expanded diagram:', error);
                                expandedDiagram.innerHTML = '<p style="color: #666; padding: 20px; font-size: 16px;">Error rendering expanded diagram</p>';
                            }}
                        }}
                    }}
                    
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
                
                // Render the diagram
                const diagramDiv = document.createElement('div');
                diagramDiv.className = 'mermaid';
                diagramDiv.style.width = {'\"100%\"' if is_chat_diagram else '\"fit-content\"'};
                diagramDiv.style.minWidth = '100%';
                diagramDiv.style.minHeight = '150px';
                diagramDiv.style.display = 'block';
                diagramDiv.style.margin = '0 auto';
                diagramDiv.style.padding = {'\"5px\"' if is_chat_diagram else '\"20px\"'};
                diagramDiv.textContent = `{mermaid_code}`;
                
                document.getElementById('mermaid-{key}').appendChild(diagramDiv);
                
                // Force re-render with proper error handling
                try {{
                    mermaid.init(undefined, diagramDiv);
                    
                    // After rendering, check if scrollbars are needed and add visual indicator
                    setTimeout(() => {{
                        const container = document.getElementById('mermaid-container-{key}');
                        const content = document.getElementById('mermaid-{key}');
                        
                        if (container && content) {{
                            const hasHorizontalScroll = content.scrollWidth > container.clientWidth;
                            const hasVerticalScroll = content.scrollHeight > container.clientHeight;
                            
                            if (hasHorizontalScroll || hasVerticalScroll) {{
                                // Add scroll indicator
                                const indicator = document.createElement('div');
                                indicator.style.cssText = 'position: absolute; top: 35px; right: 8px; background: rgba(0,0,0,0.7); color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; z-index: 1000;';
                                indicator.textContent = '↕ ↔ Scroll to view';
                                container.appendChild(indicator);
                            }}
                        }}
                    }}, 500);
                    
                }} catch (error) {{
                    console.error('Mermaid rendering error:', error);
                    diagramDiv.innerHTML = '<p style="color: #666; padding: 20px;">Diagram rendering error. Please check the syntax.</p>';
                }}
            </script>
        </div>
    </div>
    """, height=250 if is_chat_diagram else (base_height + 50))


def test_mermaid_html_structure():
    """Test function to examine Mermaid HTML output structure"""
    test_mermaid = """
graph LR
    Internet(("🌐 Internet"))
    subgraph AWS["AWS Cloud"]
        subgraph AWSVPC["VPC (10.0.0.0/16)"]
            webServer[🌐 web-server]
        end
    end
    style AWS fill:#FF9900,stroke:#e47911,color:#000
"""
    
    # Generate the HTML that would be created
    html_output = f"""
    <div id="mermaid-test" style="width: 100%; min-height: 400px; text-align: center;">
        <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
        <script>
            mermaid.initialize({{ 
                startOnLoad: true,
                theme: 'default',
                flowchart: {{
                    useMaxWidth: true,
                    htmlLabels: true,
                    subGraphTitleMargin: {{
                        top: 5,
                        bottom: 25
                    }},
                    padding: 15
                }}
            }});
        </script>
        <div class="mermaid">
{test_mermaid}
        </div>
    </div>
    """
    
    print("=== GENERATED HTML STRUCTURE ===")
    print(html_output)
    print("=== END HTML ===")
    
    return html_output


def display_diagram_in_chat(analysis_result, yaml_content: str = '', user_requirements: str = '') -> str:
    """Generate Mermaid diagram for display in chat history"""
    try:
        diagram_data = extract_diagram_data(analysis_result, yaml_content, user_requirements)
        if diagram_data and diagram_data.get('instances'):
            full_mermaid = create_full_infrastructure_diagram(diagram_data)
            return full_mermaid
        return None
    except Exception:
        return None
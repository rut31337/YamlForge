import re
import yaml
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from .validation import validate_and_fix_yaml

# Import YamlForge utilities
import sys

def find_yamlforge_root():
    """Find YamlForge root directory using multiple strategies"""
    current_file = Path(__file__).resolve()
    
    # Strategy 1: Standard relative path from demobuilder/core/yaml_generator.py
    yamlforge_root = current_file.parent.parent.parent
    if (yamlforge_root / 'yamlforge' / 'utils.py').exists():
        return str(yamlforge_root)
    
    # Strategy 2: Search upward from current file location
    search_path = current_file.parent
    for _ in range(5):  # Limit search to 5 levels up
        if (search_path / 'yamlforge' / 'utils.py').exists():
            return str(search_path)
        search_path = search_path.parent
        if search_path == search_path.parent:  # Reached filesystem root
            break
    
    # Strategy 3: Check if yamlforge is already importable (pip installed)
    try:
        import yamlforge.utils
        return None  # Already available in path
    except ImportError:
        pass
    
    raise ImportError("Could not find YamlForge installation")

yamlforge_path = find_yamlforge_root()
if yamlforge_path and str(yamlforge_path) not in sys.path:
    sys.path.insert(0, str(yamlforge_path))

from yamlforge.utils import find_yamlforge_file
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

AI_AVAILABLE = ANTHROPIC_DIRECT or LANGCHAIN_ANTHROPIC or VERTEX_AI


@dataclass
class InfrastructureRequirement:
    instances: List[Dict[str, Any]]
    openshift_clusters: List[Dict[str, Any]]
    security_groups: List[Dict[str, Any]]
    storage_buckets: List[Dict[str, Any]]
    workspace_name: str
    guid: Optional[str] = None
    tags: Dict[str, str] = None


class YamlForgeGenerator:
    def __init__(self):
        self.use_ai = AI_AVAILABLE
        self.client_type = None
        self.ai_model = os.getenv("AI_MODEL", "claude").lower()
        self.ai_model_version = os.getenv("AI_MODEL_VERSION")
        # AI client initialization (debug output removed for cleaner logs)
        
        if self.use_ai:
            # Try direct Anthropic API first if API key is available
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key and ANTHROPIC_DIRECT:
                try:
                    self.anthropic = Anthropic(api_key=api_key)
                    self.client_type = "direct"
                    # Direct Anthropic client ready
                except Exception as e:
                    print(f"DEBUG: Direct Anthropic client initialization failed: {e}")
            
            # Try Vertex AI if needed based on AI_MODEL setting
            vertex_project = os.getenv("ANTHROPIC_VERTEX_PROJECT_ID")
            
            # Handle Gemini requirement for Vertex AI
            if self.ai_model == "gemini" and not vertex_project:
                print("DEBUG: AI_MODEL=gemini requires ANTHROPIC_VERTEX_PROJECT_ID environment variable")
                self.use_ai = False
                return
            
            # Only use Vertex AI if:
            # 1. AI_MODEL is set to "gemini" (requires Vertex AI), OR
            # 2. AI_MODEL is "claude" but we want to use Claude via Vertex AI and have project ID
            use_vertex = (
                (self.ai_model == "gemini" and vertex_project and VERTEX_AI) or
                (self.ai_model == "claude" and vertex_project and VERTEX_AI and self.client_type is None)
            )
            
            if use_vertex:
                # Try multiple model and location combinations
                
                if self.ai_model == "gemini":
                    if self.ai_model_version:
                        # Use specific version if provided
                        vertex_configs = [
                            {"model": self.ai_model_version, "location": "us-east5"},
                            {"model": self.ai_model_version, "location": "us-central1"},
                        ]
                    else:
                        # Use default Gemini models in order of preference
                        vertex_configs = [
                            # Try Gemini 2.0 Flash (most capable)
                            {"model": "gemini-2.0-flash-001", "location": "us-east5"},
                            {"model": "gemini-2.0-flash-001", "location": "us-central1"},
                            # Try Gemini 1.5 Pro (good balance)
                            {"model": "gemini-1.5-pro-001", "location": "us-east5"},
                            {"model": "gemini-1.5-pro-001", "location": "us-central1"},
                            # Try Gemini 1.5 Flash (fast and efficient)
                            {"model": "gemini-1.5-flash-001", "location": "us-east5"},
                            {"model": "gemini-1.5-flash-001", "location": "us-central1"},
                            # Try Gemini 1.0 Pro (stable)
                            {"model": "gemini-1.0-pro", "location": "us-east5"},
                            {"model": "gemini-1.0-pro", "location": "us-central1"},
                        ]
                else:  # Claude models
                    if self.ai_model_version:
                        # Use specific Claude version if provided
                        vertex_configs = [
                            {"model": self.ai_model_version, "location": "us-east5"},
                            {"model": self.ai_model_version, "location": "us-central1"},
                            {"model": self.ai_model_version, "location": "europe-west1"},
                        ]
                    else:
                        # Use default Claude models in order of preference
                        vertex_configs = [
                            # Try the standard Claude 3 Haiku (most likely to work)
                            {"model": "claude-3-haiku@20240307", "location": "us-east5"},
                            {"model": "claude-3-haiku@20240307", "location": "us-central1"},
                            {"model": "claude-3-haiku@20240307", "location": "europe-west1"},
                            # Try Claude 3.5 Sonnet
                            {"model": "claude-3-5-sonnet@20241022", "location": "us-east5"},
                            {"model": "claude-3-5-sonnet@20241022", "location": "us-central1"},
                            # Try without publisher prefix (direct model name)
                            {"model": "claude-3-haiku@20240307", "location": "us-east5", "no_publisher": True},
                        ]
                
                for config in vertex_configs:
                    try:
                        model_name = config["model"]
                        # Only add publisher prefix for Claude models
                        if self.ai_model == "claude" and not config.get("no_publisher", False):
                            model_name = f"publishers/anthropic/models/{model_name}"
                        
                        test_llm = ChatVertexAI(
                            model=model_name,
                            temperature=0.1,
                            max_tokens=100,
                            project=vertex_project,
                            location=config["location"],
                            max_retries=1
                        )
                        
                        # Test the model with a simple query to verify it works
                        print(f"DEBUG: Testing Vertex AI config - model: {model_name}, location: {config['location']}")
                        test_response = test_llm.invoke("Hello")
                        print(f"DEBUG: Test successful for {model_name}")
                        
                        # If we get here, the model works
                        self.llm = test_llm
                        self.client_type = "vertex"
                        print(f"DEBUG: Vertex AI client initialized and tested successfully with model: {model_name}, location: {config['location']}, project: {vertex_project}")
                        break  # Success, exit the loop
                    except Exception as e:
                        print(f"DEBUG: Vertex AI config failed - model: {config['model']}, location: {config['location']}, error: {str(e)[:100]}...")
                        continue
                
                if self.client_type != "vertex":
                    print("DEBUG: All Vertex AI configurations failed")
            
            # Fall back to regular LangChain if direct API and Vertex failed
            if self.client_type is None and LANGCHAIN_ANTHROPIC and self.ai_model == "claude":
                try:
                    # Use AI_MODEL_VERSION if set, otherwise fall back to ANTHROPIC_MODEL, then default
                    model = self.ai_model_version or os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
                    self.llm = ChatAnthropic(model=model, temperature=0.1, max_tokens=2000)
                    self.client_type = "langchain"
                    print(f"DEBUG: LangChain Anthropic client initialized successfully with model: {model}")
                except Exception as e:
                    print(f"DEBUG: LangChain Anthropic client initialization failed: {e}")
            
            # If none worked, disable AI
            if self.client_type is None:
                self.use_ai = False
                print("DEBUG: No working AI client available")
        
        # Load YamlForge mapping data for AI context
        self.yamlforge_mappings = self._load_yamlforge_mappings()
        
        # Supported YamlForge providers (for AI reference)
        self.supported_providers = [
            'aws', 'azure', 'gcp', 'ibm_vpc', 'ibm_classic', 'oci', 
            'alibaba', 'vmware', 'cnv', 'cheapest', 'cheapest-gpu'
        ]
    
    def _get_claude_model_name(self) -> str:
        """Get the Claude model name to use for direct Anthropic API calls."""
        if self.ai_model_version:
            return self.ai_model_version
        else:
            return "claude-3-haiku-20240307"  # Default Claude model
    
    def _load_yamlforge_mappings(self) -> Dict[str, Any]:
        """Load YamlForge mapping files for AI context."""
        try:
            mappings = {}
            
            # Load images mapping using centralized path resolution
            try:
                images_file = find_yamlforge_file("mappings/images.yaml")
                with open(images_file, 'r') as f:
                    images_yaml = yaml.safe_load(f)
                    # Extract the actual images dict from the nested structure
                    if images_yaml and 'images' in images_yaml:
                        mappings['images'] = images_yaml['images']
                    else:
                        mappings['images'] = images_yaml
            except FileNotFoundError:
                mappings['images'] = {}
            
            # Load locations mapping using centralized path resolution
            try:
                locations_file = find_yamlforge_file("mappings/locations.yaml")
                with open(locations_file, 'r') as f:
                    mappings['locations'] = yaml.safe_load(f)
            except FileNotFoundError:
                mappings['locations'] = {}
            
            # Load generic flavors (most commonly used)
            try:
                flavors_file = find_yamlforge_file("mappings/flavors/generic.yaml")
                with open(flavors_file, 'r') as f:
                    mappings['flavors'] = yaml.safe_load(f)
            except FileNotFoundError:
                mappings['flavors'] = {}
            
            return mappings
        except Exception as e:
            print(f"Warning: Could not load YamlForge mappings: {e}")
            return {}
    
    def parse_natural_language_requirements(self, text: str, use_cheapest: bool = False) -> InfrastructureRequirement:
        text = text.lower().strip()
        
        workspace_name = self._extract_workspace_name(text)
        instances = self._extract_instances(text, use_cheapest=use_cheapest)
        openshift_clusters = self._extract_openshift_clusters(text, use_cheapest=use_cheapest)
        security_groups = self._extract_security_groups(text)
        storage_buckets = self._extract_storage_buckets(text, use_cheapest=use_cheapest)
        tags = self._extract_tags(text)
        
        return InfrastructureRequirement(
            instances=instances,
            openshift_clusters=openshift_clusters,
            security_groups=security_groups,
            storage_buckets=storage_buckets,
            workspace_name=workspace_name,
            tags=tags
        )
    
    def _extract_workspace_name(self, text: str) -> str:
        patterns = [
            r'workspace[:\s]+([a-zA-Z0-9\-_]+)',
            r'project[:\s]+([a-zA-Z0-9\-_]+)',
            r'environment[:\s]+([a-zA-Z0-9\-_]+)',
            r'called[:\s]+([a-zA-Z0-9\-_]+)',
            r'named[:\s]+([a-zA-Z0-9\-_]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        
        if 'demo' in text or 'test' in text:
            return 'demo-environment'
        elif 'prod' in text or 'production' in text:
            return 'production-environment'
        elif 'dev' in text or 'development' in text:
            return 'development-environment'
        else:
            return 'infrastructure-workspace'
    
    def _extract_instances(self, text: str, use_cheapest: bool = False) -> List[Dict[str, Any]]:
        instances = []
        
        vm_patterns = [
            r'(\d+)\s+(?:virtual\s+machines?|vms?|instances?|servers?)',
            r'(\d+)\s+(?:nodes?|hosts?)',
            r'(\d+)\s+(?:rhel|ubuntu|windows|centos|fedora)\s+(?:vms?|instances?|machines?)',
            r'(\d+)\s+(?:\w+\s+)?(?:rhel|ubuntu|windows|centos|fedora)\s+(?:vms?|instances?|machines?)',
            r'(\d+)\s+(?:\w+\s+)*(?:vms?|instances?|machines?|servers?|nodes?)',
            r'create\s+(\d+)\s+(?:vms?|instances?|machines?)',
            r'need\s+(\d+)\s+(?:\w+\s+)*(?:vms?|instances?|machines?|servers?)'
        ]
        
        count = 1
        for pattern in vm_patterns:
            match = re.search(pattern, text)
            if match:
                count = int(match.group(1))
                break
        
        if not any(keyword in text for keyword in ['vm', 'instance', 'server', 'machine', 'node', 'host']):
            return instances
        
        provider = self._extract_provider(text, use_cheapest=use_cheapest)
        region = self._extract_region(text)
        size = self._extract_size(text)
        os_image = self._extract_os(text)
        gpu_info = self._extract_gpu_requirements(text)
        
        names = self._extract_instance_names(text, count)
        
        for i in range(count):
            instance = {
                'name': names[i] if i < len(names) else f'instance-{i+1}',
                'provider': provider,
                'flavor': size,
                'image': os_image
            }
            
            if region:
                instance['location'] = region
            
            if gpu_info['gpu_type']:
                instance['gpu_type'] = gpu_info['gpu_type']
                instance['gpu_count'] = gpu_info['gpu_count']
            
            instances.append(instance)
        
        return instances
    
    def _extract_openshift_clusters(self, text: str, use_cheapest: bool = False) -> List[Dict[str, Any]]:
        clusters = []
        
        if not any(keyword in text for keyword in ['openshift', 'rosa', 'aro', 'ocp', 'kubernetes']):
            return clusters
        
        cluster_patterns = [
            r'(\d+)\s+(?:openshift|rosa|aro|ocp)\s+clusters?',
            r'(\d+)\s+clusters?',
            r'create\s+(\d+)\s+(?:openshift|rosa|aro|ocp)\s+clusters?'
        ]
        
        count = 1
        for pattern in cluster_patterns:
            match = re.search(pattern, text)
            if match:
                count = int(match.group(1))
                break
        
        # Check for single cluster patterns without count
        if count == 1:
            single_cluster_patterns = [
                r'create\s+(?:an?\s+)?(?:openshift|rosa|aro|ocp)\s+cluster',
                r'(?:deploy|need|want)\s+(?:an?\s+)?(?:openshift|rosa|aro|ocp)\s+cluster',
                r'(?:small|medium|large)\s+(?:openshift|rosa|aro|ocp)\s+cluster'
            ]
            for pattern in single_cluster_patterns:
                if re.search(pattern, text):
                    count = 1
                    break
        
        cluster_type = 'rosa-classic'
        if 'hcp' in text:
            cluster_type = 'rosa-hcp'
        elif 'rosa' in text and 'hcp' in text:
            cluster_type = 'rosa-hcp'
        elif 'aro' in text or 'azure' in text:
            cluster_type = 'aro'
        elif 'self-managed' in text or 'self managed' in text:
            cluster_type = 'self-managed'
        
        region = self._extract_region(text)
        size = self._extract_cluster_size(text)
        
        for i in range(count):
            cluster = {
                'name': f'cluster-{i+1}' if count > 1 else 'openshift-cluster',
                'type': cluster_type,
                'size': size
            }
            
            if region:
                cluster['region'] = self._map_location_to_region(region, cluster_type)
            
            clusters.append(cluster)
        
        return clusters
    
    def _extract_security_groups(self, text: str) -> List[Dict[str, Any]]:
        security_groups = []
        
        if not any(keyword in text for keyword in ['security', 'firewall', 'port', 'ssh', 'http', 'https']):
            return security_groups
        
        sg = {
            'name': 'default-security-group',
            'description': 'Default security group with common ports',
            'rules': []
        }
        
        if 'ssh' in text or 'port 22' in text:
            sg['rules'].append({
                'direction': 'ingress',
                'protocol': 'tcp',
                'port_range': '22',
                'source': '0.0.0.0/0',
                'description': 'SSH access'
            })
        
        if 'http' in text or 'port 80' in text or 'web' in text:
            sg['rules'].append({
                'direction': 'ingress',
                'protocol': 'tcp',
                'port_range': '80',
                'source': '0.0.0.0/0',
                'description': 'HTTP access'
            })
        
        if 'https' in text or 'port 443' in text or 'ssl' in text:
            sg['rules'].append({
                'direction': 'ingress',
                'protocol': 'tcp',
                'port_range': '443',
                'source': '0.0.0.0/0',
                'description': 'HTTPS access'
            })
        
        if sg['rules']:
            security_groups.append(sg)
        
        return security_groups
    
    def _extract_storage_buckets(self, text: str, use_cheapest: bool = False) -> List[Dict[str, Any]]:
        storage_buckets = []
        
        if not any(keyword in text for keyword in ['storage', 'bucket', 's3', 'blob', 'object store', 'file storage']):
            return storage_buckets
        
        bucket_patterns = [
            r'(\\d+)\\s+(?:storage\\s+)?buckets?',
            r'(\\d+)\\s+(?:s3\\s+)?buckets?',
            r'(\\d+)\\s+(?:object\\s+)?storage\\s+buckets?',
            r'create\\s+(\\d+)\\s+(?:storage\\s+)?buckets?',
            r'need\\s+(\\d+)\\s+(?:storage\\s+)?buckets?'
        ]
        
        count = 1
        for pattern in bucket_patterns:
            match = re.search(pattern, text)
            if match:
                count = int(match.group(1))
                break
        
        # Check for single bucket patterns without count
        if count == 1:
            single_bucket_patterns = [
                r'create\\s+(?:an?\\s+)?(?:storage\\s+)?bucket',
                r'(?:deploy|need|want)\\s+(?:an?\\s+)?(?:storage\\s+)?bucket',
                r'(?:s3|blob|object)\\s+storage',
                r'file\\s+storage'
            ]
            for pattern in single_bucket_patterns:
                if re.search(pattern, text):
                    count = 1
                    break
        
        provider = self._extract_provider(text, use_cheapest=use_cheapest)
        region = self._extract_region(text)
        
        # Extract bucket names and access settings
        bucket_names = self._extract_storage_bucket_names(text, count)
        
        for i in range(count):
            bucket = {
                'name': bucket_names[i] if i < len(bucket_names) else f'storage-bucket-{i+1}',
                'provider': provider
            }
            
            if region:
                bucket['location'] = region
            
            # Determine access level
            if any(keyword in text for keyword in ['public', 'public-read', 'publicly accessible']):
                bucket['public'] = True
            else:
                bucket['public'] = False
            
            # Determine versioning
            if any(keyword in text for keyword in ['versioning', 'version control', 'backup']):
                bucket['versioning'] = True
            else:
                bucket['versioning'] = False
            
            # Determine encryption (default to enabled)
            if any(keyword in text for keyword in ['no encryption', 'unencrypted']):
                bucket['encryption'] = False
            else:
                bucket['encryption'] = True
            
            storage_buckets.append(bucket)
        
        return storage_buckets
    
    def _extract_storage_bucket_names(self, text: str, count: int) -> List[str]:
        """Extract meaningful storage bucket names from text"""
        text_lower = text.lower()
        names = []
        
        # Specific storage patterns
        if 'backup' in text_lower:
            names.append('backup-storage')
        if 'log' in text_lower or 'logs' in text_lower:
            names.append('log-storage')
        if 'data' in text_lower and 'lake' in text_lower:
            names.append('data-lake')
        if 'archive' in text_lower:
            names.append('archive-storage')
        if 'media' in text_lower or 'image' in text_lower or 'video' in text_lower:
            names.append('media-storage')
        if 'document' in text_lower or 'file' in text_lower:
            names.append('document-storage')
        if 'web' in text_lower and ('static' in text_lower or 'asset' in text_lower):
            names.append('web-assets')
        
        # If no specific patterns found, use generic names
        if len(names) == 0:
            if 's3' in text_lower:
                names.extend([f's3-bucket-{i+1}' for i in range(count)])
            elif 'blob' in text_lower:
                names.extend([f'blob-storage-{i+1}' for i in range(count)])
            else:
                names.extend([f'storage-bucket-{i+1}' for i in range(count)])
        
        # Ensure we have enough names
        while len(names) < count:
            names.append(f'storage-bucket-{len(names)+1}')
        
        return names[:count]
    
    def _ai_extract_infrastructure_element(self, text: str, element_type: str, context: Dict[str, Any] = None) -> Any:
        """Use AI to extract infrastructure elements from natural language."""
        if not self.use_ai:
            raise ValueError(f"AI is required for {element_type} extraction but is not available")
        
        try:
            # Prepare context data for AI
            available_options = self._get_available_options(element_type)
            
            # Create prompt for AI extraction
            prompt = self._create_extraction_prompt(text, element_type, available_options, context)
            
            # Get AI response
            if self.client_type == "direct":
                response = self.anthropic.messages.create(
                    model=self._get_claude_model_name(),
                    max_tokens=200,
                    messages=[{"role": "user", "content": prompt}]
                )
                result = response.content[0].text.strip()
            elif self.client_type in ["langchain", "vertex"]:
                response = self.llm.invoke(prompt)
                result = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            else:
                raise ValueError(f"No valid AI client available for {element_type} extraction")
            
            # Parse and validate AI response
            return self._parse_ai_response(result, element_type, available_options)
            
        except Exception as e:
            print(f"Error: AI extraction failed for {element_type}: {e}")
            raise
    
    def _extract_provider(self, text: str, use_cheapest: bool = False) -> str:
        # Handle cheapest override first
        if use_cheapest:
            if any(gpu_keyword in text for gpu_keyword in ['gpu', 'ai', 'ml', 'machine learning', 'training']):
                return 'cheapest-gpu'
            return 'cheapest'
        
        # Use AI to extract provider
        result = self._ai_extract_infrastructure_element(text, 'provider', {'use_cheapest': use_cheapest})
        return result if result else 'cheapest'
    
    def _extract_region(self, text: str) -> Optional[str]:
        # Use AI to extract region/location
        result = self._ai_extract_infrastructure_element(text, 'region')
        return result
    
    def _extract_size(self, text: str) -> str:
        # Use AI to extract instance size/flavor
        result = self._ai_extract_infrastructure_element(text, 'size')
        return result if result else 'medium'
    
    def _extract_os(self, text: str) -> str:
        # Use AI to extract OS/image
        result = self._ai_extract_infrastructure_element(text, 'os')
        return result  # No fallback - let YamlForge handle pattern-based RHEL images
    
    def _extract_gpu_requirements(self, text: str) -> Dict[str, Any]:
        gpu_info = {'gpu_type': None, 'gpu_count': 1}
        
        if not any(keyword in text for keyword in ['gpu', 'graphics', 'ai', 'ml', 'cuda', 'nvidia']):
            return gpu_info
        
        gpu_types = {
            't4': 'NVIDIA T4',
            'v100': 'NVIDIA V100',
            'a100': 'NVIDIA A100',
            'l4': 'NVIDIA L4',
            'l40s': 'NVIDIA L40S',
            'k80': 'NVIDIA K80'
        }
        
        for keyword, gpu_type in gpu_types.items():
            if keyword in text:
                gpu_info['gpu_type'] = gpu_type
                break
        
        if not gpu_info['gpu_type']:
            if any(keyword in text for keyword in ['ai', 'ml', 'training', 'inference']):
                gpu_info['gpu_type'] = 'NVIDIA T4'
        
        gpu_count_match = re.search(r'(\d+)\s+gpus?', text)
        if gpu_count_match:
            gpu_info['gpu_count'] = int(gpu_count_match.group(1))
        
        return gpu_info
    
    def _get_available_options(self, element_type: str) -> Dict[str, Any]:
        """Get available options for the given element type."""
        options = {}
        
        if element_type == 'provider':
            options['providers'] = self.supported_providers
            
        elif element_type == 'region':
            if 'locations' in self.yamlforge_mappings:
                options['locations'] = list(self.yamlforge_mappings['locations'].keys())
            else:
                options['locations'] = ['us-east', 'us-west', 'eu-west', 'ap-southeast']
                
        elif element_type == 'size':
            if 'flavors' in self.yamlforge_mappings:
                options['flavors'] = list(self.yamlforge_mappings['flavors'].keys())
            else:
                options['flavors'] = ['nano', 'micro', 'small', 'medium', 'large', 'xlarge']
                
        elif element_type == 'os':
            if 'images' in self.yamlforge_mappings:
                options['images'] = list(self.yamlforge_mappings['images'].keys())
            else:
                options['images'] = ['RHEL9-latest', 'RHEL8-latest', 'Ubuntu22-latest', 'Windows2022-latest']
        
        return options
    
    def _create_extraction_prompt(self, text: str, element_type: str, available_options: Dict[str, Any], context: Dict[str, Any] = None) -> str:
        """Create AI prompt for extracting infrastructure elements."""
        base_prompt = f"Extract the {element_type} from this infrastructure request: '{text}'\n\n"
        
        if element_type == 'provider':
            base_prompt += f"Available providers: {', '.join(available_options['providers'])}\n"
            base_prompt += "For 'aws', 'amazon', 'ec2' use 'aws'. For 'azure', 'microsoft' use 'azure'. "
            base_prompt += "For 'google', 'gcp' use 'gcp'. For 'oracle' use 'oci'. "
            base_prompt += "For cost optimization, use 'cheapest' or 'cheapest-gpu' for GPU workloads.\n"
            
        elif element_type == 'region':
            base_prompt += f"Available regions: {', '.join(available_options['locations'][:10])}...\n"
            base_prompt += "Map 'us east', 'virginia', 'east coast' to 'us-east'. "
            base_prompt += "Map 'us west', 'california', 'oregon' to 'us-west'. "
            base_prompt += "Map 'europe', 'eu', 'london' to 'eu-west'. "
            base_prompt += "Always return full location names from the available list - never abbreviated forms.\n"
            
        elif element_type == 'size':
            base_prompt += f"Available sizes: {', '.join(available_options['flavors'])}\n"
            base_prompt += "Map 'tiny' to 'small'. Map 'extra large', 'xl', '2xl' to 'xlarge'. "
            base_prompt += "Also consider cores/memory: 1-2 cores = small, 3-4 cores = medium, 5-8 cores = large, 9+ cores = xlarge.\n"
            
        elif element_type == 'os':
            # Show first 20 image options including gold images
            image_list = available_options['images'][:20] if len(available_options['images']) > 20 else available_options['images']
            base_prompt += f"Available images: {', '.join(image_list)}\n"
            base_prompt += "IMPORTANT: For 'rhel gold', 'gold rhel', 'rhel byos', 'byos rhel' use 'RHEL10-GOLD-latest', 'RHEL-10-GOLD-latest', 'RHEL9-GOLD-latest', 'RHEL-9-GOLD-latest', 'RHEL8-GOLD-latest', or 'RHEL-8-GOLD-latest'. "
            base_prompt += "For regular RHEL use 'RHEL10-latest', 'RHEL-10-latest', 'RHEL9-latest', 'RHEL-9-latest', 'RHEL8-latest', or 'RHEL-8-latest'. "
            base_prompt += "For Ubuntu use 'Ubuntu22-latest' or 'Ubuntu20-latest'.\n"
            
        elif element_type == 'storage':
            base_prompt += "Available storage providers: aws, azure, gcp, oci, ibm_vpc, alibaba, cheapest\n"
            base_prompt += "Map 'aws', 'amazon', 's3' to 'aws'. Map 'azure', 'microsoft', 'blob' to 'azure'. "
            base_prompt += "Map 'google', 'gcp', 'cloud storage' to 'gcp'. "
            base_prompt += "For cost optimization, use 'cheapest' to select the most cost-effective provider.\n"
        
        if element_type == 'os':
            base_prompt += f"Return ONLY the exact {element_type} value. You can use images from the available list OR pattern-based RHEL images (RHEL10-GOLD-latest, RHEL-10-GOLD-latest, RHEL10-latest, RHEL-10-latest, etc.), no explanation."
        else:
            base_prompt += f"Return ONLY the exact {element_type} value from the available options, no explanation."
        return base_prompt
    
    def _parse_ai_response(self, response: str, element_type: str, available_options: Dict[str, Any]) -> Any:
        """Parse and validate AI response."""
        import re
        response = response.strip().strip('"').strip("'")
        
        # Validate response against available options
        if element_type == 'provider' and response in available_options['providers']:
            return response
        elif element_type == 'region' and response in available_options['locations']:
            return response
        elif element_type == 'size' and response in available_options['flavors']:
            return response
        elif element_type == 'os':
            # Allow exact match from available options
            if response in available_options['images']:
                return response
            # Also allow RHEL pattern-based images (YamlForge handles these dynamically)
            elif re.match(r'^RHEL-?\d+(\.\d+)?(-GOLD)?-latest$', response, re.IGNORECASE):
                return response
        elif element_type == 'storage':
            # Storage providers validation
            valid_storage_providers = ['aws', 'azure', 'gcp', 'oci', 'ibm_vpc', 'alibaba', 'cheapest']
            if response in valid_storage_providers:
                return response
        
        # If exact match fails, try partial matching for some types
        if element_type == 'region':
            for location in available_options['locations']:
                if response.lower() in location.lower() or location.lower() in response.lower():
                    return location
        
        return None
    
    
    def _extract_cluster_size(self, text: str) -> str:
        if any(keyword in text for keyword in ['large', 'production', 'prod', 'enterprise']):
            return 'large'
        elif any(keyword in text for keyword in ['small', 'dev', 'development', 'test', 'demo']):
            return 'small'
        else:
            return 'medium'
    
    def _extract_tags(self, text: str) -> Dict[str, str]:
        tags = {}
        
        if any(keyword in text for keyword in ['dev', 'development', 'testing']):
            tags['Environment'] = 'Development'
        elif any(keyword in text for keyword in ['prod', 'production']):
            tags['Environment'] = 'Production'
        elif any(keyword in text for keyword in ['stage', 'staging']):
            tags['Environment'] = 'Staging'
        
        if any(keyword in text for keyword in ['demo', 'poc', 'proof of concept']):
            tags['Purpose'] = 'Demo'
        elif any(keyword in text for keyword in ['training', 'lab', 'learning']):
            tags['Purpose'] = 'Training'
        
        return tags
    
    def _map_location_to_region(self, location: str, cluster_type: str) -> str:
        aws_regions = {
            'us-east': 'us-east-1',
            'us-west': 'us-west-2',
            'eu-west': 'eu-west-1',
            'ap-southeast': 'ap-southeast-1'
        }
        
        azure_regions = {
            'us-east': 'eastus',
            'us-west': 'westus2',
            'eu-west': 'westeurope',
            'ap-southeast': 'southeastasia'
        }
        
        if cluster_type == 'aro':
            return azure_regions.get(location, 'eastus')
        else:
            return aws_regions.get(location, 'us-east-1')
    
    def generate_yaml_config(self, requirements: InfrastructureRequirement) -> str:
        config = {
            'yamlforge': {
                'cloud_workspace': {
                    'name': requirements.workspace_name
                }
            }
        }
        
        # Always include a GUID - use provided one or placeholder for analysis
        config['guid'] = requirements.guid if requirements.guid else 'demo1'
        
        if requirements.instances:
            config['yamlforge']['instances'] = requirements.instances
        
        if requirements.openshift_clusters:
            config['yamlforge']['openshift_clusters'] = requirements.openshift_clusters
        
        if requirements.security_groups:
            config['yamlforge']['security_groups'] = requirements.security_groups
        
        if requirements.storage_buckets:
            config['yamlforge']['storage'] = requirements.storage_buckets
        
        if requirements.tags:
            config['yamlforge']['tags'] = requirements.tags
        
        return yaml.dump(config, default_flow_style=False, sort_keys=False)
    
    def generate_from_text(self, text: str, auto_fix: bool = True, use_cheapest: bool = False, existing_yaml: str = None) -> tuple[bool, str, List[str]]:
        try:
            if existing_yaml and self._is_modification_request(text):
                # Modify existing configuration
                return self.modify_existing_config(text, existing_yaml, auto_fix, use_cheapest)
            else:
                # Use AI generation only - no fallback
                if self.use_ai:
                    yaml_config = self.generate_yaml_with_ai(text, use_cheapest)
                    if yaml_config:
                        # AI generation succeeded, check for provider defaults and add informative messages
                        messages = ["Generated using AI"]
                        
                        # Check if storage defaults to cheapest provider
                        additional_messages = self._check_for_provider_defaults(text, yaml_config, use_cheapest)
                        messages.extend(additional_messages)
                        
                        return True, yaml_config, messages
                    else:
                        return False, "", ["AI generation failed - no fallback available"]
                else:
                    return False, "", ["AI is not available and no fallback is configured"]
                
        except Exception as e:
            return False, "", [f"Generation failed: {str(e)}"]
    
    def generate_yaml_with_ai(self, text: str, use_cheapest: bool = False) -> str:
        """Generate YamlForge YAML using AI with schema validation"""
        
        # Pre-analyze the request to set explicit flags
        text_lower = text.lower().strip()
        
        # Check what user actually requested
        requests_storage = any(keyword in text_lower for keyword in ['storage', 'bucket', 's3', 'blob', 'object store'])
        requests_instances = any(keyword in text_lower for keyword in ['vm', 'instance', 'server', 'machine', 'node', 'host'])
        requests_clusters = any(keyword in text_lower for keyword in ['cluster', 'openshift', 'rosa', 'aro', 'kubernetes'])
        
        # Check for multi-cloud complexity (multiple providers mentioned)
        cloud_keywords = ['aws', 'azure', 'gcp', 'google', 'microsoft', 'amazon', 'oracle', 'oci', 'ibm', 'alibaba', 'vmware']
        mentioned_clouds = [cloud for cloud in cloud_keywords if cloud in text_lower]
        is_multi_cloud = len(mentioned_clouds) > 1
        
        # Check for complex architecture (multiple roles/tiers mentioned)
        role_keywords = ['web', 'database', 'api', 'load balancer', 'frontend', 'backend', 'app server', 'db']
        mentioned_roles = [role for role in role_keywords if role in text_lower]
        is_multi_tier = len(mentioned_roles) > 1
        
        # Build explicit instruction based on analysis
        if requests_storage and not requests_instances and not requests_clusters:
            explicit_instruction = "CREATE ONLY STORAGE - NO INSTANCES, NO CLUSTERS!"
        elif requests_instances and not requests_storage and not requests_clusters and not is_multi_cloud and not is_multi_tier:
            explicit_instruction = "CREATE ONLY INSTANCES - NO STORAGE, NO CLUSTERS!"
        elif requests_clusters and not requests_instances and not requests_storage:
            explicit_instruction = "CREATE ONLY CLUSTERS - NO INSTANCES, NO STORAGE!"
        else:
            explicit_instruction = "CREATE WHAT WAS REQUESTED"
        
        # Load the schema using centralized path resolution
        try:
            schema_path = find_yamlforge_file("docs/yamlforge-schema.json")
            with open(schema_path, 'r') as f:
                schema_content = f.read()
        except FileNotFoundError:
            schema_content = "Schema not available"
        except Exception as e:
            schema_content = "Schema not available"
        
        # Use specialized prompts based on what user requested
        if "CREATE ONLY STORAGE" in explicit_instruction:
            return self._generate_storage_only_yaml(text, use_cheapest)
        elif "CREATE ONLY INSTANCES" in explicit_instruction:
            return self._generate_instances_only_yaml(text, use_cheapest)
        elif "CREATE ONLY CLUSTERS" in explicit_instruction:
            return self._generate_clusters_only_yaml(text, use_cheapest)
        else:
            return self._generate_combined_yaml(text, use_cheapest, explicit_instruction)
    
    def _generate_storage_only_yaml(self, text: str, use_cheapest: bool = False) -> str:
        """Generate YAML for storage-only requests with focused prompt"""
        
        # Extract bucket name from request
        text_lower = text.lower()
        bucket_name = "storage-bucket"
        if "backup" in text_lower:
            bucket_name = "backup-storage"
        elif "data" in text_lower:
            bucket_name = "data-storage"
        elif "log" in text_lower:
            bucket_name = "log-storage"
        elif "media" in text_lower:
            bucket_name = "media-storage"
        
        # Handle use_cheapest parameter and detect specific providers
        text_lower = text.lower()
        provider_setting = "cheapest"
        
        if use_cheapest:
            provider_setting = "cheapest"
        elif "aws" in text_lower or "amazon" in text_lower or "s3" in text_lower:
            provider_setting = "aws"
        elif "azure" in text_lower or "microsoft" in text_lower or "blob" in text_lower:
            provider_setting = "azure"
        elif "gcp" in text_lower or "google" in text_lower or "cloud storage" in text_lower:
            provider_setting = "gcp"
        elif "oracle" in text_lower or "oci" in text_lower:
            provider_setting = "oci"
        elif "ibm" in text_lower:
            provider_setting = "ibm_vpc"
        elif "alibaba" in text_lower:
            provider_setting = "alibaba"
        else:
            provider_setting = "cheapest"
        
        prompt = f"""Generate YAML for storage request: "{text}"

Create ONLY storage, NO instances, NO clusters.

PROVIDER MAPPING RULES:
- "aws", "amazon", "s3" → provider: aws
- "azure", "microsoft", "blob" → provider: azure  
- "gcp", "google", "cloud storage" → provider: gcp
- "oracle", "oci" → provider: oci
- "ibm" → provider: ibm_vpc
- "alibaba" → provider: alibaba
- If no specific provider mentioned → provider: cheapest

Required structure:
guid: demo1
yamlforge:
  cloud_workspace:
    name: data-storage
  storage:
    - name: {bucket_name}
      provider: {provider_setting}
      location: us-east
      public: false
      versioning: false
      encryption: true

RULES:
- Create ONLY the storage section
- NO yamlforge.instances section
- NO yamlforge.openshift_clusters section
- Extract specific cloud provider from user request if mentioned
- Return YAML only, no explanation

Generate YAML:"""

        return self._call_ai_for_generation(prompt)
    
    def _generate_instances_only_yaml(self, text: str, use_cheapest: bool = False) -> str:
        """Generate YAML for instance-only requests with focused prompt"""
        
        # Handle use_cheapest parameter
        provider_guidance = ""
        if use_cheapest:
            provider_guidance = """
COST OPTIMIZATION MODE:
- Use provider: cheapest for all instances (unless specific cloud providers are mentioned)
- Use provider: cheapest-gpu for any GPU/AI/ML instances
"""
        
        prompt = f"""Generate YAML for VM/instance request: "{text}"
{provider_guidance}
Create ONLY instances, NO storage, NO clusters.

Required structure:
guid: demo1
yamlforge:
  cloud_workspace:
    name: vm-environment
  instances:
    - name: server-1
      provider: cheapest
      flavor: medium
      image: RHEL9-latest
      location: us-east

RULES:
- Create ONLY the instances section
- NO yamlforge.storage section
- NO yamlforge.openshift_clusters section
- Extract count, size, OS from request
- Map cost terms: "cheap"/"budget" → provider: cheapest, flavor: small
- NEVER use "cheap" as a flavor - use valid flavors: nano, small, medium, large, xlarge
- Return YAML only, no explanation

Generate YAML:"""

        return self._call_ai_for_generation(prompt)
    
    def _generate_clusters_only_yaml(self, text: str, use_cheapest: bool = False) -> str:
        """Generate YAML for cluster-only requests with focused prompt"""
        
        prompt = f"""Generate YAML for OpenShift cluster request: "{text}"

Create ONLY clusters, NO instances, NO storage.

Required structure:
guid: demo1
yamlforge:
  cloud_workspace:
    name: cluster-environment
  openshift_clusters:
    - name: openshift-cluster
      type: rosa-classic
      size: medium
      region: us-east-1

RULES:
- Create ONLY the openshift_clusters section
- NO yamlforge.instances section
- NO yamlforge.storage section
- Return YAML only, no explanation

Generate YAML:"""

        return self._call_ai_for_generation(prompt)
    
    def _generate_combined_yaml(self, text: str, use_cheapest: bool = False, instruction: str = "") -> str:
        """Generate YAML for mixed requests"""
        
        # Handle use_cheapest parameter
        provider_guidance = ""
        if use_cheapest:
            provider_guidance = """
COST OPTIMIZATION MODE:
- Use provider: cheapest for all instances (unless specific cloud providers are mentioned)
- Use provider: cheapest-gpu for any GPU/AI/ML instances
- Prioritize cost-effective configurations
"""
        
        prompt = f"""Generate YAML for mixed request: "{text}"

Instruction: {instruction}
{provider_guidance}
CRITICAL REQUIREMENTS:
1. 'guid' field at root level (exactly 5 lowercase alphanumeric chars like 'demo1')
2. 'yamlforge' field at root level 
3. 'yamlforge.cloud_workspace.name' field
4. Create what the user explicitly requested (instances AND/OR storage AND/OR clusters)

MULTI-CLOUD PROVIDER MAPPING:
- "AWS web servers" → provider: aws
- "Azure database" → provider: azure  
- "GCP API server" → provider: gcp
- "Oracle storage" → provider: oci
- "IBM servers" → provider: ibm_vpc
- Map cloud names to exact provider codes

INSTANCE NAMING RULES:
- "web servers" → web-server-1, web-server-2
- "database" → database-1
- "API server" → api-server-1  
- "load balancer" → load-balancer-1
- Use role-based names when user specifies roles

COST-RELATED TERMS MAPPING:
- "cheap instances" → provider: cheapest, flavor: small
- "cheap servers" → provider: cheapest, flavor: small  
- "cost-effective" → provider: cheapest, flavor: small
- "minimal cost" → provider: cheapest, flavor: nano
- "budget servers" → provider: cheapest, flavor: small
- NEVER use "cheap" as a flavor - it's not valid!

LOCATION MAPPING (use universal locations):
- All providers → location: us-east (YamlForge will map to provider-specific regions)
- DO NOT use provider-specific regions like "eastus" or "us-east1"
- Use universal locations: us-east, us-west, eu-west, ap-southeast
- NEVER use abbreviated locations like "us", "eu", "asia" - always use full location names

MULTI-CLOUD SECURITY:
- When components span multiple clouds, all instances need public connectivity
- Generate security_groups section for multi-cloud deployments
- Allow inter-cloud communication between CIDR ranges

Example for "AWS web servers with Azure database and GCP API server":
```yaml
guid: demo1
yamlforge:
  cloud_workspace:
    name: multi-cloud-app
  instances:
    - name: web-server-1
      provider: aws
      flavor: medium
      image: RHEL9-latest
      location: us-east
    - name: database-1
      provider: azure
      flavor: large
      image: RHEL9-latest
      location: us-east
    - name: api-server-1
      provider: gcp
      flavor: medium
      image: RHEL9-latest
      location: us-east
  security_groups:
    - name: multi-cloud-access
      description: Inter-cloud connectivity
      rules:
        - direction: ingress
          protocol: tcp
          port_range: "80"
          source: 0.0.0.0/0
        - direction: ingress
          protocol: tcp
          port_range: "443"
          source: 0.0.0.0/0
        - direction: ingress
          protocol: tcp
          port_range: "22"
          source: 0.0.0.0/0
```

RULES:
- Extract exact provider names from user request
- Use role-based naming when roles are specified
- Use universal locations (us-east) not provider-specific ones - NEVER use abbreviated locations
- Add security groups for multi-cloud scenarios
- Map cost terms: "cheap"/"budget" → provider: cheapest, flavor: small
- NEVER use "cheap" as a flavor - use valid flavors: nano, small, medium, large, xlarge
- Return YAML only, no explanation

Generate YAML:"""

        return self._call_ai_for_generation(prompt)
    
    def _call_ai_for_generation(self, prompt: str) -> str:
        """Call AI with the given prompt and return YAML"""
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if self.client_type == "direct":
                    response = self.anthropic.messages.create(
                        model=self._get_claude_model_name(),
                        max_tokens=1000,
                        temperature=0.1,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    yaml_content = response.content[0].text.strip()
                elif self.client_type in ["vertex", "langchain"]:
                    response = self.llm.invoke(prompt)
                    yaml_content = response.content.strip() if hasattr(response, 'content') else str(response).strip()
                else:
                    return None
                
                # Extract YAML from code blocks if present
                if "```yaml" in yaml_content:
                    yaml_content = yaml_content.split("```yaml")[1].split("```")[0].strip()
                elif "```" in yaml_content:
                    yaml_content = yaml_content.split("```")[1].split("```")[0].strip()
                
                # Validate and fix the YAML against schema
                from .validation import validate_and_fix_yaml
                is_valid, fixed_yaml, messages = validate_and_fix_yaml(yaml_content, auto_fix=True)
                
                if is_valid:
                    return fixed_yaml
                elif attempt < max_attempts - 1:
                    # If validation failed, try again with error feedback
                    error_msg = '; '.join(messages)
                    prompt += f"\n\nPrevious attempt failed validation with errors: {error_msg}\nPlease fix these issues and generate valid YAML:"
                
            except Exception as e:
                if attempt == max_attempts - 1:
                    return None
                    
        return None
    
    def modify_yaml_with_ai(self, modification_text: str, existing_yaml: str, use_cheapest: bool = False) -> str:
        """Modify existing YAML configuration using AI with context"""
        
        # Create context-aware prompt for modification
        prompt = f"""You are modifying an existing YamlForge YAML configuration based on a user request.

EXISTING CONFIGURATION:
{existing_yaml}

USER REQUEST: "{modification_text}"

CRITICAL REQUIREMENTS:
1. Preserve ALL existing infrastructure (instances, clusters, security groups, etc.) EXACTLY as they are
2. Add/modify ONLY what the user explicitly requested - DO NOT add anything extra
3. Maintain the exact same GUID and workspace name
4. Follow YamlForge schema exactly - use the same structure as the existing config
5. If adding instances, use meaningful names based on the specific request
6. If user mentions "cheapest" or cost optimization, use provider: "cheapest" or "cheapest-gpu"

STRICT MODIFICATION RULES:

ADDING RESOURCES:
- If user says "add a load balancer" → Add ONLY a load balancer instance, nothing else
- If user says "add a database" → Add ONLY a database instance, nothing else
- If user says "add monitoring" → Add ONLY a monitoring instance, nothing else
- If user says "add a bastion" → Add ONLY a bastion instance, nothing else
- If user says "add storage", "add bucket", "add s3 bucket" → Add ONLY storage bucket to yamlforge.storage section
- Storage bucket rules: Use descriptive names like "backup-storage", "data-lake", same provider/location as instances unless specified
- DO NOT add extra infrastructure that wasn't specifically requested

REMOVAL REQUIREMENTS - EXACT INSTANCE NAMES ONLY:
For removal requests, users must specify the EXACT instance name. Do not guess or assume what instances they mean.

REMOVAL LOGIC:
- "remove rhel-server-1" → Look for exact match "rhel-server-1" and remove it
- "remove web-server-2" → Look for exact match "web-server-2" and remove it  
- "remove load-balancer" → Look for exact match "load-balancer" and remove it

GENERIC REMOVAL REQUESTS - REQUIRE CLARIFICATION:
If user uses generic terms like "remove a server", "remove a Windows server", "remove a database":
→ MUST respond with ERROR_NO_MATCH format asking for exact instance name

CRITICAL: When user makes generic removal request, you MUST respond with:
"ERROR_NO_MATCH: Please specify the exact instance name to remove. Current instances: [list all instance names]. Example: 'remove rhel-server-1'"

EXAMPLE SCENARIOS:
Config: rhel-server-1, rhel-server-2, rhel-server-3
User: "remove a Windows server"
Response: "ERROR_NO_MATCH: Please specify the exact instance name to remove. Current instances: rhel-server-1, rhel-server-2, rhel-server-3. Example: 'remove rhel-server-1'"

Config: rhel-server-1, rhel-server-2, rhel-server-3
User: "remove rhel-server-2"
Action: Generate modified YAML with rhel-server-2 removed, keeping rhel-server-1 and rhel-server-3

GENERAL RULES:
- DO NOT assume the user needs additional components beyond what they asked for
- BE PRECISE: Only implement exactly what was requested (add OR remove, nothing extra)

OUTPUT FORMAT:
- If modification is successful: Generate ONLY the complete modified YAML configuration
- If cannot find instance to remove: Use ERROR_NO_MATCH format above
- Do not include explanations in successful modifications"""

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if self.client_type == "direct":
                    response = self.anthropic.messages.create(
                        model=self._get_claude_model_name(),
                        max_tokens=3000,
                        temperature=0.1,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    yaml_content = response.content[0].text.strip()
                elif self.client_type == "vertex":
                    response = self.llm.invoke(prompt)
                    yaml_content = response.content.strip()
                elif self.client_type == "langchain":
                    response = self.llm.invoke(prompt)
                    yaml_content = response.content.strip()
                else:
                    return None
                
                # Check for error response first
                if yaml_content.startswith("ERROR_NO_MATCH:"):
                    # Return the error message as a special response
                    return yaml_content
                
                # Extract YAML from code blocks if present
                if "```yaml" in yaml_content:
                    yaml_content = yaml_content.split("```yaml")[1].split("```")[0].strip()
                elif "```" in yaml_content:
                    yaml_content = yaml_content.split("```")[1].split("```")[0].strip()
                
                # Quick validation - make sure it's valid YAML and has required structure
                try:
                    parsed = yaml.safe_load(yaml_content)
                    if parsed and 'yamlforge' in parsed:
                        return yaml_content
                except yaml.YAMLError:
                    pass
                
                # If validation failed and we have more attempts, retry with feedback
                if attempt < max_attempts - 1:
                    prompt += f"\n\nPrevious attempt failed YAML parsing. Ensure the output is valid YAML syntax."
                
            except Exception as e:
                if attempt == max_attempts - 1:
                    return None
                    
        return None
    
    def _is_modification_request(self, text: str) -> bool:
        """Check if the text is asking for a modification to existing config"""
        modification_keywords = [
            'add', 'remove', 'delete', 'change', 'modify', 'update', 'increase', 'decrease',
            'more', 'another', 'additional', 'extra', 'one more', 'scale up', 'scale down'
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in modification_keywords)
    
    def modify_existing_config(self, modification_text: str, existing_yaml: str, auto_fix: bool = True, use_cheapest: bool = False) -> tuple[bool, str, List[str]]:
        """Modify an existing YAML configuration using AI"""
        try:
            # Parse existing config to validate it
            existing_config = yaml.safe_load(existing_yaml)
            if not existing_config or 'yamlforge' not in existing_config:
                # If existing config is invalid, generate new one
                return self.generate_from_text(modification_text, auto_fix, use_cheapest)
            
            
            # Use AI to modify the configuration
            if self.use_ai:
                modified_yaml = self.modify_yaml_with_ai(modification_text, existing_yaml, use_cheapest)
                if modified_yaml:
                    # Check if AI returned an error message instead of YAML
                    if modified_yaml.startswith("ERROR_NO_MATCH:"):
                        error_msg = modified_yaml.replace("ERROR_NO_MATCH: ", "")
                        return False, "", [error_msg]
                    
                    # Validate removal requests for exact name compliance
                    if 'remove' in modification_text.lower():
                        error_msg = self._validate_removal_compliance(modification_text, existing_yaml, modified_yaml)
                        if error_msg:
                            return False, "", [error_msg]
                    
                    if auto_fix:
                        is_valid, fixed_yaml, messages = validate_and_fix_yaml(modified_yaml, auto_fix=True)
                        return is_valid, fixed_yaml, messages + ["Modified using AI"]
                    else:
                        return True, modified_yaml, ["Modified using AI"]
            
            # AI not available or failed
            return False, "", ["AI modification not available - please try rephrasing your request"]
                
        except Exception as e:
            return False, "", [f"Modification failed: {str(e)}"]
    
    def _validate_removal_compliance(self, modification_text: str, existing_yaml: str, modified_yaml: str) -> str:
        """Validate that removal requests use exact instance names"""
        try:
            # Parse both configs to compare
            existing_config = yaml.safe_load(existing_yaml)
            modified_config = yaml.safe_load(modified_yaml)
            
            existing_instances = existing_config.get('yamlforge', {}).get('instances', [])
            modified_instances = modified_config.get('yamlforge', {}).get('instances', [])
            
            existing_names = [inst.get('name', '') for inst in existing_instances]
            modified_names = [inst.get('name', '') for inst in modified_instances]
            
            # Check if user specified an exact instance name
            modification_lower = modification_text.lower()
            
            # If an instance was removed, check if user used exact name
            if len(modified_names) < len(existing_names):
                # Find which instance was removed
                removed_names = [name for name in existing_names if name not in modified_names]
                
                # Check if user mentioned the exact name that was removed
                exact_name_used = False
                for removed_name in removed_names:
                    if removed_name.lower() in modification_lower:
                        exact_name_used = True
                        break
                
                # If exact name wasn't used, require it
                if not exact_name_used:
                    return f"Please specify the exact instance name to remove. Current instances: {', '.join(existing_names)}. Example: 'remove {existing_names[0]}'"
            
            return ""  # No error
        except Exception:
            return ""  # If anything fails, let it through
    
    def _extract_instance_names(self, text: str, count: int) -> List[str]:
        """Extract meaningful instance names from text"""
        text_lower = text.lower()
        names = []
        
        # Specific application/service patterns
        if 'bastion' in text_lower:
            names.append('bastion-host')
        if 'jump' in text_lower and 'host' in text_lower:
            names.append('jump-host')
        if 'postgresql' in text_lower or 'postgres' in text_lower:
            names.append('postgres-db')
        if 'haproxy' in text_lower or 'load balancer' in text_lower or 'lb' in text_lower:
            names.append('haproxy-lb')
        if 'apache' in text_lower or 'httpd' in text_lower:
            names.append('apache-web')
        if 'nginx' in text_lower:
            names.append('nginx-web')
        if 'mysql' in text_lower:
            names.append('mysql-db')
        if 'redis' in text_lower:
            names.append('redis-cache')
        if 'elasticsearch' in text_lower or 'elastic' in text_lower:
            names.append('elasticsearch')
        if 'mongodb' in text_lower or 'mongo' in text_lower:
            names.append('mongodb')
        
        # Purpose-based patterns
        if 'web server' in text_lower or 'webserver' in text_lower:
            names.append('web-server')
        if 'database' in text_lower and 'postgres' not in text_lower and 'mysql' not in text_lower:
            names.append('database')
        if 'cache' in text_lower and 'redis' not in text_lower:
            names.append('cache-server')
        if 'api' in text_lower:
            names.append('api-server')
        if 'app server' in text_lower or 'application' in text_lower:
            names.append('app-server')
        
        # GPU/ML patterns
        if 'gpu' in text_lower or 'machine learning' in text_lower or 'ml' in text_lower or 'ai' in text_lower:
            names.append('gpu-ml')
        if 'training' in text_lower:
            names.append('ml-training')
        if 'inference' in text_lower:
            names.append('ml-inference')
        
        # Development patterns
        if 'dev' in text_lower or 'development' in text_lower:
            names.extend(['dev-server-1', 'dev-server-2', 'dev-server-3'])
        if 'test' in text_lower or 'testing' in text_lower:
            names.extend(['test-server-1', 'test-server-2'])
        if 'demo' in text_lower:
            names.extend(['demo-server-1', 'demo-server-2'])
        
        # Windows patterns
        if 'windows' in text_lower:
            if 'sql' in text_lower:
                names.append('windows-sql')
            else:
                names.append('windows-server')
        
        # If we have specific names but need more instances, add numbered versions
        if len(names) > 0 and len(names) < count:
            base_names = names.copy()
            for i in range(len(names), count):
                if base_names:
                    # Cycle through base names with numbers
                    base_name = base_names[i % len(base_names)]
                    names.append(f"{base_name}-{(i // len(base_names)) + 2}")
                else:
                    names.append(f"server-{i+1}")
        
        # If no specific patterns found, use generic but meaningful names
        if len(names) == 0:
            if 'ssh' in text_lower:
                names.extend([f'ssh-server-{i+1}' for i in range(count)])
            elif 'rhel' in text_lower:
                names.extend([f'rhel-server-{i+1}' for i in range(count)])
            elif 'ubuntu' in text_lower:
                names.extend([f'ubuntu-server-{i+1}' for i in range(count)])
            elif 'windows' in text_lower:
                names.extend([f'windows-server-{i+1}' for i in range(count)])
            else:
                names.extend([f'server-{i+1}' for i in range(count)])
        
        # Ensure we have enough names
        while len(names) < count:
            names.append(f'instance-{len(names)+1}')
        
        return names[:count]
    
    def _check_for_provider_defaults(self, text: str, yaml_config: str, use_cheapest: bool) -> List[str]:
        """Check if any providers were defaulted and return informative messages"""
        messages = []
        
        try:
            import yaml
            config = yaml.safe_load(yaml_config)
            
            if not config or 'yamlforge' not in config:
                return messages
            
            yamlforge_config = config['yamlforge']
            text_lower = text.lower()
            
            # Check storage buckets for cheapest provider defaults
            if 'storage' in yamlforge_config:
                storage_buckets = yamlforge_config['storage']
                for bucket in storage_buckets:
                    if bucket.get('provider') == 'cheapest':
                        # Check if user mentioned any specific provider
                        mentioned_providers = []
                        provider_keywords = {
                            'aws': ['aws', 'amazon', 's3'],
                            'azure': ['azure', 'microsoft', 'blob'],
                            'gcp': ['gcp', 'google', 'cloud storage'],
                            'oracle': ['oracle', 'oci'],
                            'ibm': ['ibm'],
                            'alibaba': ['alibaba']
                        }
                        
                        for provider, keywords in provider_keywords.items():
                            if any(keyword in text_lower for keyword in keywords):
                                mentioned_providers.append(provider)
                        
                        # If no specific provider mentioned and not using use_cheapest flag
                        if not mentioned_providers and not use_cheapest:
                            bucket_name = bucket.get('name', 'storage bucket')
                            messages.append(f"ℹ️  No cloud provider specified for '{bucket_name}' - defaulting to cheapest available provider for cost optimization")
                        
            # Check instances for cheapest provider defaults (similar logic can be added if needed)
            if 'instances' in yamlforge_config and use_cheapest:
                instances = yamlforge_config['instances']
                cheapest_instances = [inst for inst in instances if inst.get('provider') == 'cheapest']
                if cheapest_instances and len(cheapest_instances) > 0:
                    messages.append(f"ℹ️  Using cheapest providers for cost optimization ({len(cheapest_instances)} instance(s))")
                        
        except Exception as e:
            # Don't fail the generation if message checking fails
            pass
            
        return messages
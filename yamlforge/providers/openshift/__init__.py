"""
OpenShift Provider for yamlforge
Main orchestrator that combines all OpenShift provider components
"""

from typing import Dict, List, Set, Any
from .base import BaseOpenShiftProvider
from .rosa import ROSAProvider
from .aro import AROProvider
from .self_managed import SelfManagedOpenShiftProvider
from .hypershift import HyperShiftProvider
from .dedicated import OpenShiftDedicatedProvider
from .features import (
    OpenShiftOperatorProvider,
    OpenShiftSecurityProvider,
    OpenShiftStorageProvider,
    OpenShiftNetworkingProvider,
    Day2OperationsProvider,
    ApplicationProvider
)


class OpenShiftProvider(BaseOpenShiftProvider):
    """Main OpenShift provider orchestrator"""
    
    # Mapping of OpenShift types to provider classes
    OPENSHIFT_PROVIDER_MAP = {
        'rosa-classic': 'aws',
        'rosa-hcp': 'aws', 
        'aro': 'azure',
        'openshift-dedicated': None,
        'self-managed': None,
        'hypershift': None,
    }
    
    def __init__(self, converter=None):
        """Initialize the OpenShift provider with all sub-providers."""
        super().__init__(converter)
        
        # Initialize sub-providers
        self.rosa_provider = ROSAProvider(converter)
        self.aro_provider = AROProvider(converter)
        self.self_managed_provider = SelfManagedOpenShiftProvider(converter)
        self.hypershift_provider = HyperShiftProvider(converter)
        self.dedicated_provider = OpenShiftDedicatedProvider(converter)
        
        # Initialize feature providers
        self.operator_provider = OpenShiftOperatorProvider(converter)
        self.security_provider = OpenShiftSecurityProvider(converter)
        self.storage_provider = OpenShiftStorageProvider(converter)
        self.networking_provider = OpenShiftNetworkingProvider(converter)
        self.day2_provider = Day2OperationsProvider(converter)
        self.application_provider = ApplicationProvider(converter)
    
    def generate_openshift_clusters(self, yaml_data: Dict) -> str:
        """Generate Terraform for all OpenShift clusters and related resources."""
        clusters = yaml_data.get('openshift_clusters', [])
        
        if not clusters:
            return ""
        
        terraform_config = '''
# =============================================================================
# OPENSHIFT CLUSTERS
# =============================================================================

'''
        
        # Generate Terraform providers block
        terraform_config += self.generate_terraform_providers(clusters)
        
        # Variables are generated in variables.tf by core converter
        
        # Detect deployment separation needs for different cluster types
        rosa_classic_clusters = [c for c in clusters if c.get('type') == 'rosa-classic']
        rosa_hcp_clusters = [c for c in clusters if c.get('type') == 'rosa-hcp'] 
        hypershift_mgmt_clusters = [c for c in clusters if c.get('type') == 'rosa-classic' and c.get('hypershift', {}).get('role') == 'management']
        hypershift_hosted_clusters = [c for c in clusters if c.get('type') == 'hypershift']
        
        # Determine separation needs
        needs_rosa_separation = len(rosa_classic_clusters) > 0 and len(rosa_hcp_clusters) > 0
        needs_hypershift_separation = len(hypershift_mgmt_clusters) > 0 and len(hypershift_hosted_clusters) > 0
        
        # Check ROSA deployment method early
        rosa_deployment = yaml_data.get('rosa_deployment', {})
        deployment_method = rosa_deployment.get('method', 'terraform')
        
        # Generate shared ROSA resources once if any ROSA clusters exist
        has_rosa_clusters = len(rosa_classic_clusters) > 0 or len(rosa_hcp_clusters) > 0
        if has_rosa_clusters:
            # ALWAYS create ROSA account roles via CLI first (regardless of deployment method)
            aws_provider = self.converter.get_aws_provider()
            role_creation_success = aws_provider.create_rosa_account_roles_via_cli(yaml_data)
            if not role_creation_success:
                print("Warning: Failed to create ROSA account roles via CLI. Terraform may fail.")
            
            # For terraform deployment method, generate data sources to reference CLI-created roles
            if deployment_method == 'terraform':
                terraform_config += self._generate_shared_rosa_data_sources(yaml_data)
        
        # Generate clusters by type
        for cluster in clusters:
            cluster_type = cluster.get('type')
            
            # Validate cluster type is specified
            if not cluster_type:
                raise ValueError(f"OpenShift cluster '{cluster.get('name')}' must specify a 'type' field")
            
            # Check for deprecated 'rosa' type
            if cluster_type == 'rosa':
                raise ValueError(f"OpenShift cluster '{cluster.get('name')}' uses deprecated type 'rosa'. Use 'rosa-classic' or 'rosa-hcp' instead.")
            
            # Validate cluster type is supported
            if cluster_type not in self.OPENSHIFT_PROVIDER_MAP:
                supported_types = list(self.OPENSHIFT_PROVIDER_MAP.keys())
                raise ValueError(f"Unsupported OpenShift cluster type '{cluster_type}' for cluster '{cluster.get('name')}'. Supported types: {supported_types}")
            
            # Add deployment separation flags when needed
            cluster = cluster.copy()  # Don't modify original
            
            # Handle ROSA Classic clusters (including HyperShift management clusters)
            if cluster_type == 'rosa-classic':
                if cluster.get('hypershift', {}).get('role') == 'management':
                    # HyperShift management cluster
                    if needs_hypershift_separation:
                        cluster['_needs_hypershift_separation'] = True
                        cluster['_deployment_group'] = 'hypershift_mgmt'
                else:
                    # Regular ROSA Classic cluster
                    if needs_rosa_separation:
                        cluster['_needs_rosa_separation'] = True
                        cluster['_deployment_group'] = 'rosa_classic'
            
            # Handle ROSA HCP clusters
            elif cluster_type == 'rosa-hcp':
                if needs_rosa_separation:
                    cluster['_needs_rosa_separation'] = True
                    cluster['_deployment_group'] = 'rosa_hcp'
            
            # Handle HyperShift hosted clusters
            elif cluster_type == 'hypershift':
                if needs_hypershift_separation:
                    cluster['_needs_hypershift_separation'] = True
                    cluster['_deployment_group'] = 'hypershift_hosted'
            
            # Generate cluster based on type
            if cluster_type == 'rosa-classic':
                # Only generate Terraform resources for ROSA if using Terraform deployment method
                if deployment_method == 'terraform':
                    terraform_config += self.rosa_provider.generate_rosa_classic_cluster(cluster)
                # CLI method creates clusters via rosa-setup.sh script
            elif cluster_type == 'rosa-hcp':
                # Only generate Terraform resources for ROSA if using Terraform deployment method
                if deployment_method == 'terraform':
                    terraform_config += self.rosa_provider.generate_rosa_hcp_cluster(cluster, yaml_data)
                # CLI method creates clusters via rosa-setup.sh script
            elif cluster_type == 'aro':
                terraform_config += self.aro_provider.generate_aro_cluster(cluster)
            elif cluster_type == 'openshift-dedicated':
                terraform_config += self.dedicated_provider.generate_dedicated_cluster(cluster)
            elif cluster_type == 'self-managed':
                terraform_config += self.self_managed_provider.generate_self_managed_cluster(cluster)
            elif cluster_type == 'hypershift':
                terraform_config += self.hypershift_provider.generate_hypershift_cluster(cluster, clusters)
        
        # Generate application deployment providers for clusters that will have applications
        applications = yaml_data.get('openshift_applications', [])
        
        clusters_needing_apps = set()
        
        # Identify clusters that need application deployment access
        if applications:
            for app in applications:
                if app.get('type') == 'multi-cluster':
                    target_clusters = app.get('clusters', [])
                    if not target_clusters:
                        # Deploy to all clusters if none specified
                        clusters_needing_apps.update(cluster.get('name') for cluster in clusters)
                    else:
                        clusters_needing_apps.update(target_clusters)
                else:
                    cluster_name = app.get('cluster')
                    if cluster_name:
                        clusters_needing_apps.add(cluster_name)
        
        # Generate providers and service accounts for all clusters
        if clusters:
            terraform_config += self.generate_application_providers(clusters, deployment_method)
            
            # Generate service accounts for each cluster - 3-tier model
            for cluster in clusters:
                cluster_name = cluster.get('name')
                cluster_type = cluster.get('type')
                if cluster_name:
                    # Skip service account generation for ROSA CLI clusters
                    if cluster_type in ['rosa-classic', 'rosa-hcp'] and deployment_method == 'cli':
                        continue
                        
                    # ALWAYS generate all 3 service accounts for complete access model
                    terraform_config += self.generate_full_admin_service_account(cluster)
                    terraform_config += self.generate_limited_admin_service_account(cluster)
                    
                    # Generate app deployer service account only if cluster needs app deployment
                    if cluster_name in clusters_needing_apps:
                        terraform_config += self.generate_app_deployer_service_account(cluster)
        
        # Determine which clusters to exclude from day2 operations based on deployment method
        # Use the deployment_method already extracted earlier (from yaml_data.get('rosa_deployment'))
        
        # Only skip ROSA clusters if using CLI method, Terraform method supports full lifecycle
        if deployment_method == 'cli':
            # CLI method - skip ROSA clusters for day2 operations
            non_rosa_clusters = [c for c in clusters if c.get('type') not in ['rosa-classic', 'rosa-hcp']]
            skip_message = '''
# =============================================================================
# DAY-2 OPERATIONS SKIPPED FOR ROSA CLI CLUSTERS
# =============================================================================
# ROSA clusters are created via ROSA CLI after Terraform deployment
# Day-2 operations can be configured after cluster creation using:
# - OpenShift Web Console
# - ROSA CLI commands
# - oc CLI after cluster access is established

'''
        else:
            # Terraform method - include all clusters for day2 operations
            non_rosa_clusters = clusters
            skip_message = ''
        
        # Determine if we are in no-credentials mode
        no_credentials_mode = yaml_data.get('no_credentials_mode', 'false') == 'true'
        
        # Generate Day-2 operations only for terraform deployment method and when clusters exist
        # For terraform deployment, wrap Day-2 operations in deployment conditionals
        day2_comment = '''
# =============================================================================
# DAY-2 OPERATIONS (deploy_day2_operations=true)
# =============================================================================
# Deploy operators, applications, and day-2 configurations
# Set deploy_day2_operations=true when clusters are ready and operational

'''
        
        if deployment_method == 'terraform':
            # For terraform method, Day-2 operations should be managed separately
            # They will be applied only when deploy_day2_operations=true AND clusters exist
            terraform_config += '''
# =============================================================================
# DAY-2 OPERATIONS (Conditional Deployment)
# =============================================================================
# Day-2 operations are only deployed when:
# 1. deploy_day2_operations = true
# 2. ROSA clusters are fully operational
# 3. Kubernetes providers are available
#
# Deploy infrastructure first, then clusters, then set deploy_day2_operations=true

'''
            # Generate the actual operators and applications with conditional deployment
            if clusters:
                terraform_config += self.operator_provider.generate_operators(yaml_data, clusters)
                terraform_config += self.security_provider.generate_security_features(yaml_data, clusters)
                terraform_config += self.storage_provider.generate_storage_features(yaml_data, clusters)
                terraform_config += self.networking_provider.generate_networking_features(yaml_data, clusters)
                terraform_config += self.day2_provider.generate_day2_operations(yaml_data, clusters)
                applications_config = self.application_provider.generate_applications_terraform(yaml_data, clusters)
                if applications_config:
                    terraform_config += applications_config
        else:
            # CLI method - skip ROSA clusters for day2 operations as before
            if non_rosa_clusters:
                terraform_config += day2_comment
                terraform_config += self.operator_provider.generate_operators(yaml_data, non_rosa_clusters)
                terraform_config += self.security_provider.generate_security_features(yaml_data, non_rosa_clusters)
                terraform_config += self.storage_provider.generate_storage_features(yaml_data, non_rosa_clusters)
                terraform_config += self.networking_provider.generate_networking_features(yaml_data, non_rosa_clusters)
                terraform_config += self.day2_provider.generate_day2_operations(yaml_data, non_rosa_clusters)
                applications_config = self.application_provider.generate_applications_terraform(yaml_data, non_rosa_clusters)
                if applications_config:
                    terraform_config += applications_config
            elif skip_message:
                terraform_config += skip_message
        
        return terraform_config
    
    def _has_rosa_clusters(self, yaml_data: Dict) -> bool:
        """Check if the configuration contains any ROSA clusters."""
        clusters = yaml_data.get('openshift_clusters', [])
        return any(cluster.get('type') in ['rosa-classic', 'rosa-hcp'] for cluster in clusters)
    
    def _generate_shared_rosa_data_sources(self, yaml_data: Dict) -> str:
        """Generate shared ROSA data sources that reference CLI-created roles."""
        clusters = yaml_data.get('openshift_clusters', [])
        rosa_clusters = [c for c in clusters if c.get('type') in ['rosa-classic', 'rosa-hcp']]
        
        if not rosa_clusters:
            return ""
        
        # Use first ROSA cluster for shared resource generation
        first_cluster = rosa_clusters[0]
        cluster_name = first_cluster.get('name')
        region = first_cluster.get('region')
        guid = self.converter.get_validated_guid(yaml_data)
        
        # Get AWS provider
        aws_provider = self.converter.get_aws_provider()
        
        # Generate shared data sources (reference CLI-created roles) and OIDC config
        oidc_config = aws_provider.generate_rosa_oidc_config(cluster_name, region, guid, yaml_data)
        data_sources_config = aws_provider.generate_rosa_sts_data_sources(yaml_data)
        
        return f'''
# =============================================================================
# SHARED ROSA DATA SOURCES (Reference CLI-Created Roles)
# =============================================================================

{oidc_config}

{data_sources_config}

'''
    
    def generate_rosa_cli_script(self, yaml_data: Dict) -> str:
        """Generate the ROSA CLI setup script for cluster creation."""
        clusters = yaml_data.get('openshift_clusters', [])
        rosa_clusters = [c for c in clusters if c.get('type') in ['rosa-classic', 'rosa-hcp']]
        
        if not rosa_clusters:
            return ""
        
        # Check if we're in no-credentials mode
        no_credentials_mode = getattr(self.converter, 'no_credentials', False) if self.converter else False
        
        script_content = '''#!/bin/bash
# =============================================================================
# ROSA CLI Setup Script - Generated by YamlForge
# =============================================================================
# This script creates ROSA clusters using the ROSA CLI with complete
# end-to-end automation including authentication and cluster provisioning.
#
# Features:
# - Automatic ROSA CLI installation (if not present)
# - Automatic AWS CLI installation (if not present)
# - Automatic ROSA login using environment variables
# - Self-contained with no sudo requirements
# - Complete end-to-end cluster creation
#
# Prerequisites:
# - Red Hat OpenShift token in environment variables:
#   * REDHAT_OPENSHIFT_TOKEN
# - AWS credentials configured (environment variables or AWS CLI profiles)
#
# Usage: ./rosa-setup.sh
# =============================================================================

set -e  # Exit on any error

# Set no-credentials mode flag
NO_CREDENTIALS_MODE="{no_credentials_mode_str}"

echo " Starting ROSA cluster creation with YamlForge..."

# Function to install ROSA CLI if not present
install_rosa_cli() {{
    echo " Installing ROSA CLI..."
    
    # Create local bin directory if it doesn't exist
    mkdir -p ~/.local/bin
    
    # Download and install ROSA CLI
    cd /tmp
    curl -L https://mirror.openshift.com/pub/openshift-v4/amd64/clients/rosa/latest/rosa-linux.tar.gz -o rosa-linux.tar.gz
    tar xzf rosa-linux.tar.gz
    mv rosa ~/.local/bin/
    rm -f rosa-linux.tar.gz
    
    # Add ~/.local/bin to PATH if not already there
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        export PATH="$HOME/.local/bin:$PATH"
        echo " Added ~/.local/bin to PATH for this session"
        echo " To make this permanent, add 'export PATH=\\"\\$HOME/.local/bin:\\$PATH\\"' to your ~/.bashrc or ~/.zshrc"
    fi
    
    echo " ROSA CLI installed successfully"
}}

# Function to install AWS CLI if not present
install_aws_cli() {{
    echo " Installing AWS CLI..."
    
    # Check if unzip is available
    if ! command -v unzip &> /dev/null; then
        echo " unzip is required but not found. Please install unzip first:"
        echo "   • Ubuntu/Debian: apt-get install unzip"
        echo "   • RHEL/CentOS: yum install unzip"
        echo "   • Fedora: dnf install unzip"
        echo "   • Or download AWS CLI manually from: https://aws.amazon.com/cli/"
        exit 1
    fi
    
    # Create local bin directory if it doesn't exist
    mkdir -p ~/.local/bin
    
    # Download and install AWS CLI v2
    cd /tmp
    curl -L "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip -q awscliv2.zip
    ./aws/install --bin-dir ~/.local/bin --install-dir ~/.local/aws-cli --update
    rm -rf awscliv2.zip aws/
    
    # Add ~/.local/bin to PATH if not already there
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        export PATH="$HOME/.local/bin:$PATH"
        echo " Added ~/.local/bin to PATH for this session"
    fi
    
    echo " AWS CLI installed successfully"
}}

# Check if ROSA CLI is available, install if needed
if ! command -v rosa &> /dev/null; then
    install_rosa_cli
else
    echo " ROSA CLI already available"
fi

echo " ROSA CLI version: $(rosa version)"

# Check if AWS CLI is available, install if needed
if ! command -v aws &> /dev/null; then
    install_aws_cli
else
    echo " AWS CLI already available"
fi

echo " AWS CLI version: $(aws --version)"

# Function to automatically login to ROSA
rosa_auto_login() {{
    echo " Checking ROSA authentication..."
    
    # Try to get ROSA token from environment variable
    TOKEN=""
    if [ -n "$REDHAT_OPENSHIFT_TOKEN" ]; then
        TOKEN="$REDHAT_OPENSHIFT_TOKEN"
    fi
    
    if [ -n "$TOKEN" ]; then
        echo " Found ROSA token in environment, logging in automatically..."
        if rosa login --token="$TOKEN"; then
            echo " ROSA login successful"
            return 0
        else
            echo " ROSA login failed with provided token"
            exit 1
        fi
    else
        echo " No ROSA token found in environment variables"
        echo " Please set: REDHAT_OPENSHIFT_TOKEN"
        echo " Get token from: https://console.redhat.com/openshift/token/rosa"
        exit 1
    fi
}}

# Auto-login to ROSA
rosa_auto_login

echo " Prerequisites verified"

# =============================================================================
# STEP 1: Create ROSA Account Roles (Required Prerequisite)
# =============================================================================
echo " Creating ROSA Account Roles (if not already created)"

# Skip account role creation in no-credentials mode
if [ "$NO_CREDENTIALS_MODE" = "true" ]; then
    echo "  NO-CREDENTIALS MODE: Skipping ROSA account role creation"
    echo "  Account roles must be created manually before deployment"
else
    rosa create account-roles --mode auto --yes || echo " Account roles already exist"
fi

# =============================================================================
# STEP 2: Create ROSA Clusters
# =============================================================================
echo " Creating ROSA clusters..."

'''.format(no_credentials_mode_str=str(no_credentials_mode).lower())
        
        # Generate commands for each ROSA cluster
        for cluster in rosa_clusters:
            cluster_name = cluster.get('name')
            cluster_type = cluster.get('type')
            region = cluster.get('region')
            version = cluster.get('version', '4.18.19')
            
            # Get worker configuration
            cluster_size = cluster.get('size')
            if not cluster_size:
                raise ValueError(f"OpenShift cluster '{cluster_name}': Must specify 'size' (e.g., small, medium, large)")
            size_config = self.get_cluster_size_config(cluster_size, cluster_type)
            worker_count = cluster.get('worker_count', size_config.get('worker_count', 2))
            
            # Ensure minimum worker count for multi-AZ
            if worker_count < 3:
                worker_count = 3
                
            machine_type = self.get_openshift_machine_type('aws', size_config['worker_size'], 'worker')
            
            script_content += f'''
# =============================================================================
# Create {cluster_type.upper()} Cluster: {cluster_name}
# =============================================================================

echo " Creating {cluster_type.upper()} cluster: {cluster_name}"

'''
            
            if cluster_type == 'rosa-classic':
                script_content += f'''echo " Creating ROSA-CLASSIC cluster: {cluster_name}"

# Create ROSA Classic cluster with STS
# Note: Using same region as infrastructure and 3 replicas for multi-AZ
rosa create cluster \\
  --cluster-name "{cluster_name}" \\
  --region "{region}" \\
  --version "{version}" \\
  --compute-machine-type "{machine_type}" \\
  --replicas 3 \\
  --sts \\
  --mode auto \\
  --multi-az \\
  --yes

echo " ROSA Classic cluster '{cluster_name}' creation initiated"

'''
            elif cluster_type == 'rosa-hcp':
                script_content += f'''# Get subnet IDs from Terraform state (after terraform apply)
SUBNET_IDS=$(terraform output -json | jq -r 'to_entries[] | select(.key | startswith("public_subnet_ids_{region.replace("-", "_")}_")) | .value.value | join(",")')

if [ -z "$SUBNET_IDS" ] || [ "$SUBNET_IDS" = "null" ]; then
    echo " Could not get subnet IDs from Terraform. Please run 'terraform apply' first."
    exit 1
fi

echo " Using subnet IDs: $SUBNET_IDS"

# Get AWS Account ID for billing
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo " Using AWS Account ID for billing: $AWS_ACCOUNT_ID"

# Create ROSA HCP cluster with STS, billing account, and OIDC config
# Note: Replicas adjusted to be multiple of subnet count (3 subnets = 6 replicas)
rosa create cluster \\
  --cluster-name "{cluster_name}" \\
  --region "{region}" \\
  --version "{version}" \\
  --compute-machine-type "{machine_type}" \\
  --replicas 6 \\
  --hosted-cp \\
  --subnet-ids "$SUBNET_IDS" \\
  --billing-account "$AWS_ACCOUNT_ID" \\
  --oidc-config-id "2hrokq3vnicn25m4v2pkfaodg2e780d5" \\
  --sts \\
  --mode auto \\
  --yes

echo " ROSA HCP cluster '{cluster_name}' creation initiated"

'''
        
        script_content += '''
# =============================================================================
# Wait for all clusters to be ready
# =============================================================================

echo "⏳ Waiting for all ROSA clusters to be ready..."

'''
        
        # Add wait commands for each cluster
        for cluster in rosa_clusters:
            cluster_name = cluster.get('name')
            script_content += f'wait_for_cluster "{cluster_name}"\n'
        
        script_content += '''
# =============================================================================
# Display cluster information
# =============================================================================

echo " All ROSA clusters are ready!"
echo ""

'''
        
        # Add status display for each cluster
        for cluster in rosa_clusters:
            cluster_name = cluster.get('name')
            script_content += f'''echo " Cluster: {cluster_name}"
rosa describe cluster "{cluster_name}"
echo ""

'''

        script_content += '''echo " To access your clusters:"
echo "  1. Get console URLs: rosa describe cluster <cluster-name>"
echo "  2. Create admin user: rosa create admin --cluster=<cluster-name>"
echo "  3. Login via CLI: oc login <api-url> --username=<admin-username> --password=<admin-password>"
echo ""
echo " ROSA cluster setup complete!"
'''
        
        return script_content
    
    def generate_rosa_cleanup_script(self, yaml_data: Dict) -> str:
        """Generate a cleanup script to delete ROSA clusters and optionally account roles."""
        
        # Get cluster information from YAML
        clusters = yaml_data.get('openshift_clusters', [])
        rosa_clusters = [c for c in clusters if c.get('type') in ['rosa-classic', 'rosa-hcp']]
        
        if not rosa_clusters:
            return ""
            
        script_content = '''#!/bin/bash
# =============================================================================
# ROSA Cleanup Script - Generated by YamlForge
# =============================================================================
# This script deletes ROSA clusters and optionally cleans up account roles
#
# Features:
# - Lists all ROSA clusters
# - Safely deletes specified clusters
# - Optional account role cleanup
# - Safety confirmations and dry-run mode
#
# Usage: 
#   ./rosa-cleanup.sh                    # Interactive mode
#   ./rosa-cleanup.sh --delete-all       # Delete all clusters
#   ./rosa-cleanup.sh --cluster <name>   # Delete specific cluster
#   ./rosa-cleanup.sh --dry-run          # Show what would be deleted
#   ./rosa-cleanup.sh --full-cleanup     # Delete clusters + account roles
# =============================================================================

set -e  # Exit on any error

# Default settings
DRY_RUN=false
DELETE_ALL=false
DELETE_ACCOUNT_ROLES=false
SPECIFIC_CLUSTER=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --delete-all)
            DELETE_ALL=true
            shift
            ;;
        --cluster)
            SPECIFIC_CLUSTER="$2"
            shift 2
            ;;
        --full-cleanup)
            DELETE_ALL=true
            DELETE_ACCOUNT_ROLES=true
            shift
            ;;
        --help|-h)
            echo "ROSA Cleanup Script Usage:"
            echo "  ./rosa-cleanup.sh                    # Interactive mode"
            echo "  ./rosa-cleanup.sh --delete-all       # Delete all clusters"
            echo "  ./rosa-cleanup.sh --cluster <name>   # Delete specific cluster"
            echo "  ./rosa-cleanup.sh --dry-run          # Show what would be deleted"
            echo "  ./rosa-cleanup.sh --full-cleanup     # Delete clusters + account roles"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "🧹 ROSA Cleanup Script - Generated by YamlForge"
echo "=============================================="

# Check prerequisites
if ! command -v rosa &> /dev/null; then
    echo " ROSA CLI not found. Please install ROSA CLI first."
    exit 1
fi

if ! rosa whoami &> /dev/null; then
    echo " ROSA CLI not logged in. Please run: rosa login"
    exit 1
fi

echo " ROSA CLI available and authenticated"
echo " Logged in as: $(rosa whoami 2>/dev/null | head -1 || echo 'authenticated user')"
echo ""

# Function to list clusters
list_clusters() {
    echo " Current ROSA clusters:"
    rosa list clusters 2>/dev/null || echo "No clusters found"
    echo ""
}

# Function to delete a specific cluster
delete_cluster() {
    local cluster_name="$1"
    echo "  Deleting cluster: $cluster_name"
    
    if [ "$DRY_RUN" = true ]; then
        echo "   [DRY RUN] Would delete cluster: $cluster_name"
        return 0
    fi
    
    # Check if cluster exists
    if ! rosa describe cluster --cluster "$cluster_name" &>/dev/null; then
        echo "     Cluster '$cluster_name' not found, skipping..."
        return 0
    fi
    
    echo "   ⏳ Deleting cluster '$cluster_name' (this may take 10-15 minutes)..."
    if rosa delete cluster --cluster "$cluster_name" --yes; then
        echo "    Cluster '$cluster_name' deletion initiated successfully"
    else
        echo "    Failed to delete cluster '$cluster_name'"
        return 1
    fi
}

# Function to wait for cluster deletion
wait_for_deletion() {
    local cluster_name="$1"
    echo "   ⏳ Waiting for cluster '$cluster_name' to be fully deleted..."
    
    while rosa describe cluster --cluster "$cluster_name" &>/dev/null; do
        echo "    Cluster '$cluster_name' still exists, checking again in 30 seconds..."
        sleep 30
    done
    
    echo "    Cluster '$cluster_name' has been fully deleted"
}

# Function to delete account roles
delete_account_roles() {
    echo "  Deleting ROSA account roles..."
    
    if [ "$DRY_RUN" = true ]; then
        echo "   [DRY RUN] Would delete account roles:"
        echo "   - ManagedOpenShift-Installer-Role"
        echo "   - ManagedOpenShift-ControlPlane-Role"
        echo "   - ManagedOpenShift-Worker-Role"
        echo "   - ManagedOpenShift-Support-Role"
        echo "   - ManagedOpenShift-HCP-ROSA-Installer-Role"
        echo "   - ManagedOpenShift-HCP-ROSA-Support-Role"
        echo "   - ManagedOpenShift-HCP-ROSA-Worker-Role"
        return 0
    fi
    
    # Delete account roles (both classic and HCP)
    if rosa delete account-roles --mode auto --yes; then
        echo "    Account roles deleted successfully"
    else
        echo "     Some account roles may not have been deleted (this is normal if shared across clusters)"
    fi
}

# Main execution
echo " Scanning for clusters..."
list_clusters

# Get expected clusters from YamlForge configuration
EXPECTED_CLUSTERS=('''

        # Add expected cluster names from YAML
        for cluster in rosa_clusters:
            cluster_name = cluster.get('name', 'unnamed-cluster')
            script_content += f'    "{cluster_name}"\n'
            
        script_content += ''')

if [ "$DRY_RUN" = true ]; then
    echo " DRY RUN MODE - Showing what would be deleted:"
    echo ""
fi

# Handle different execution modes
if [ "$SPECIFIC_CLUSTER" != "" ]; then
    echo " Deleting specific cluster: $SPECIFIC_CLUSTER"
    delete_cluster "$SPECIFIC_CLUSTER"
    
elif [ "$DELETE_ALL" = true ]; then
    echo "  Deleting all expected clusters..."
    
    for cluster_name in "${EXPECTED_CLUSTERS[@]}"; do
        delete_cluster "$cluster_name"
    done
    
    if [ "$DELETE_ACCOUNT_ROLES" = true ]; then
        echo ""
        delete_account_roles
    fi
    
else
    # Interactive mode
    echo "🤔 Interactive mode - Please choose an option:"
    echo "1. Delete all expected clusters"
    echo "2. Delete specific cluster"
    echo "3. Delete all clusters + account roles (full cleanup)"
    echo "4. List clusters only"
    echo "5. Exit"
    echo ""
    read -p "Enter your choice (1-5): " choice
    
    case $choice in
        1)
            echo "  Deleting all expected clusters..."
            for cluster_name in "${EXPECTED_CLUSTERS[@]}"; do
                delete_cluster "$cluster_name"
            done
            ;;
        2)
            echo "Available clusters:"
            rosa list clusters 2>/dev/null | grep -v "ID.*NAME.*STATE" || true
            echo ""
            read -p "Enter cluster name to delete: " cluster_name
            if [ -n "$cluster_name" ]; then
                delete_cluster "$cluster_name"
            fi
            ;;
        3)
            echo "  Full cleanup: Deleting all clusters + account roles..."
            for cluster_name in "${EXPECTED_CLUSTERS[@]}"; do
                delete_cluster "$cluster_name"
            done
            delete_account_roles
            ;;
        4)
            echo " Listing clusters only"
            ;;
        5)
            echo " Exiting without changes"
            exit 0
            ;;
        *)
            echo " Invalid choice"
            exit 1
            ;;
    esac
fi

if [ "$DRY_RUN" = false ]; then
    echo ""
    echo " Cleanup operations completed!"
    echo " Final cluster status:"
    list_clusters
    
    echo " Tips:"
    echo "   - Use 'rosa list clusters' to verify all clusters are deleted"
    echo "   - Use 'terraform destroy' to clean up AWS infrastructure"
    echo "   - Account roles are shared and may be used by other clusters"
fi

echo ""
echo "🧹 ROSA cleanup script completed!"
'''
        
        return script_content
    
    def detect_required_providers(self, yaml_data: Dict) -> Set[str]:
        """Detect which cloud providers are required for OpenShift clusters"""
        
        required_providers = set()
        clusters = yaml_data.get('openshift_clusters', [])
        
        for cluster in clusters:
            cluster_type = cluster.get('type')
            
            # Get cloud provider for cluster type
            cloud_provider = self.OPENSHIFT_PROVIDER_MAP.get(cluster_type)
            if cloud_provider:
                required_providers.add(cloud_provider)
            
            # Handle cluster types that can use multiple providers
            if cluster_type == 'openshift-dedicated':
                dedicated_cloud = cluster.get('provider')
                required_providers.add(dedicated_cloud)
            elif cluster_type == 'self-managed':
                self_managed_provider = cluster.get('provider')
                required_providers.add(self_managed_provider)
            elif cluster_type == 'hypershift':
                hypershift_provider = cluster.get('provider')
                required_providers.add(hypershift_provider)
        
        return required_providers
    



# Export the main provider and all sub-providers
__all__ = [
    'OpenShiftProvider',
    'BaseOpenShiftProvider', 
    'ROSAProvider',
    'AROProvider',
    'SelfManagedOpenShiftProvider',
    'OpenShiftDedicatedProvider',
    'HyperShiftProvider',
    'ApplicationProvider'
] 

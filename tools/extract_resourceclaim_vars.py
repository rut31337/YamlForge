#!/usr/bin/env python3
"""
Extract provision_data from a Kubernetes ResourceClaim and output as bash exports.

Usage:
    python extract_resourceclaim_vars.py --resource-claim <name> --namespace <ns> --kubeconfig <path>

Examples:
    python extract_resourceclaim_vars.py --resource-claim azure-resource-claim-name --namespace my-namespace --kubeconfig ~/.kube/config
    python extract_resourceclaim_vars.py --resource-claim gcp-resource-claim-name --namespace my-namespace --kubeconfig /path/to/kubeconfig
"""

import sys
import os
import json
import subprocess
import argparse


def run_kubectl_command(cmd, kubeconfig):
    """Run kubectl command and return the output."""
    env = os.environ.copy()
    env['KUBECONFIG'] = kubeconfig
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            print(f"Error running kubectl command: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        return result.stdout
    except Exception as e:
        print(f"Error executing command: {e}", file=sys.stderr)
        sys.exit(1)


def get_resourceclaim_data(resource_claim_name, namespace, kubeconfig):
    """Get ResourceClaim data from Kubernetes cluster."""
    cmd = f"kubectl get resourceclaim {resource_claim_name} -n {namespace} -o json"
    output = run_kubectl_command(cmd, kubeconfig)
    
    try:
        return json.loads(output)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON output: {e}", file=sys.stderr)
        sys.exit(1)


def extract_provision_data(resourceclaim_data):
    """Extract provision_data from ResourceClaim status.summary and additional nested data."""
    try:
        provision_data = resourceclaim_data['status']['summary']['provision_data'].copy()
        
        # Extract additional AWS data from job_vars if available
        try:
            job_vars = resourceclaim_data['status']['resources'][0]['state']['spec']['vars']['job_vars']
            
            # Add AWS hosted zone ID if available
            if 'sandbox_hosted_zone_id' in job_vars:
                provision_data['sandbox_hosted_zone_id'] = job_vars['sandbox_hosted_zone_id']
                
        except (KeyError, IndexError):
            # job_vars not available or structure different - that's okay
            pass
            
        return provision_data
    except KeyError as e:
        print(f"Error: Could not find provision_data in ResourceClaim. Missing key: {e}", file=sys.stderr)
        print("Available status keys:", list(resourceclaim_data.get('status', {}).keys()), file=sys.stderr)
        if 'summary' in resourceclaim_data.get('status', {}):
            print("Available summary keys:", list(resourceclaim_data['status']['summary'].keys()), file=sys.stderr)
        sys.exit(1)


def format_bash_exports(provision_data, verbose=False):
    """Convert provision_data to bash export statements."""
    exports = []
    
    # Cloud provider credential mappings to match envvars.example.sh format
    credential_mappings = {
        # AWS mappings
        'aws_access_key_id': 'AWS_ACCESS_KEY_ID',
        'aws_secret_access_key': 'AWS_SECRET_ACCESS_KEY',
        'aws_default_region': 'AWS_DEFAULT_REGION',
        'sandbox_hosted_zone_id': 'AWS_HOSTED_ZONE_ID',
        
        # Azure mappings
        'azure_service_principal_id': 'ARM_CLIENT_ID',
        'azure_service_principal_password': 'ARM_CLIENT_SECRET',
        'azure_subscription': 'ARM_SUBSCRIPTION_ID',
        'azure_tenant_id': 'ARM_TENANT_ID',
        
        # GCP mappings
        'gcp_credentials_file': 'GCP_SERVICE_ACCOUNT_KEY',
        'gcp_project': 'GCP_PROJECT_ID',
        'gcp_service_account': 'GOOGLE_SERVICE_ACCOUNT',
        
        # IBM Cloud mappings (if they exist in future)
        'ibm_api_key': 'IBMCLOUD_API_KEY',
        'ibm_account_id': 'IBMCLOUD_ACCOUNT_ID',
        
        # OCI mappings (if they exist in future)
        'oci_user_ocid': 'OCI_USER_OCID',
        'oci_tenancy_ocid': 'OCI_TENANCY_OCID',
        'oci_fingerprint': 'OCI_FINGERPRINT',
        'oci_region': 'OCI_REGION',
        
        # VMware mappings (if they exist in future)
        'vsphere_user': 'VSPHERE_USER',
        'vsphere_password': 'VSPHERE_PASSWORD',
        'vsphere_server': 'VSPHERE_SERVER',
        
        # Alibaba mappings (if they exist in future)
        'alicloud_access_key': 'ALICLOUD_ACCESS_KEY',
        'alicloud_secret_key': 'ALICLOUD_SECRET_KEY',
        'alicloud_region': 'ALICLOUD_REGION',
    }
    
    # DNS zone patterns to include
    dns_zone_patterns = ['_dns_zone', '_zone', 'domain']
    
    # Variables to exclude
    excluded_vars = ['guid']
    
    for key, value in provision_data.items():
        # Skip excluded variables
        if key.lower() in excluded_vars:
            continue
            
        # Check if this is a cloud provider credential that should be mapped
        mapped_key = credential_mappings.get(key.lower())
        is_dns_zone = any(pattern in key.lower() for pattern in dns_zone_patterns)
        
        # Only export cloud credentials and DNS zones
        if mapped_key or is_dns_zone:
            if mapped_key:
                env_var_name = mapped_key
                comment = f"# Mapped from ResourceClaim: {key}" if verbose else ""
            else:
                env_var_name = key.upper()
                comment = f"# From ResourceClaim: {key}" if verbose else ""
            
            # Handle different value types
            if isinstance(value, dict):
                # For complex objects like gcp_credentials_file, convert to JSON string
                value_str = json.dumps(value, separators=(',', ':'))
                # Escape single quotes in the JSON string
                value_str = value_str.replace("'", "'\"'\"'")
                if comment:
                    exports.append(comment)
                exports.append(f"export {env_var_name}='{value_str}'")
            elif isinstance(value, (list, tuple)):
                # Convert lists to space-separated strings
                value_str = ' '.join(str(item) for item in value)
                if comment:
                    exports.append(comment)
                exports.append(f"export {env_var_name}='{value_str}'")
            else:
                # Handle strings, numbers, booleans
                if comment:
                    exports.append(comment)
                exports.append(f"export {env_var_name}='{value}'")
    
    # Add additional mapped variables for GCP if gcp_credentials_file exists
    if 'gcp_credentials_file' in provision_data:
        # Also set GOOGLE_CREDENTIALS for compatibility
        gcp_creds = provision_data['gcp_credentials_file']
        if isinstance(gcp_creds, dict):
            value_str = json.dumps(gcp_creds, separators=(',', ':'))
            value_str = value_str.replace("'", "'\"'\"'")
            if verbose:
                exports.append("# Mapped from ResourceClaim: gcp_credentials_file")
            exports.append(f"export GOOGLE_CREDENTIALS='{value_str}'")
    
    return exports


def main():
    parser = argparse.ArgumentParser(
        description='Extract provision_data from a Kubernetes ResourceClaim and output as bash exports',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --resource-claim azure-resource-claim-name --namespace my-namespace --kubeconfig ~/.kube/config
  %(prog)s --resource-claim gcp-resource-claim-name --namespace my-namespace --kubeconfig /path/to/kubeconfig --verbose
        """
    )
    
    parser.add_argument('--resource-claim', '-r', required=True, help='Name of the ResourceClaim')
    parser.add_argument('--namespace', '-n', required=True, help='Namespace containing the ResourceClaim')
    parser.add_argument('--kubeconfig', '-k', required=True, help='Path to kubeconfig file')
    parser.add_argument('--verbose', '-v', action='store_true', help='Include comments showing original ResourceClaim variable names')
    
    args = parser.parse_args()
    
    # Get ResourceClaim data
    resourceclaim_data = get_resourceclaim_data(args.resource_claim, args.namespace, args.kubeconfig)
    
    # Extract provision_data
    provision_data = extract_provision_data(resourceclaim_data)
    
    # Generate bash exports
    exports = format_bash_exports(provision_data, verbose=args.verbose)
    
    # Output the export statements
    for export_stmt in exports:
        print(export_stmt)


if __name__ == '__main__':
    main()
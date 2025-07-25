#!/bin/bash
# YamlForge Environment Variables Template
# Copy this file to envvars.sh and customize with your credentials
# 
# Usage: 
#   cp envvars.example.sh envvars.sh
#   # Edit envvars.sh with your credentials
#   source envvars.sh

# =============================================================================
# REQUIRED BASIC CONFIGURATION
# =============================================================================

# Required: Unique 5-character identifier (lowercase alphanumeric)
# Examples: web01, app42, test1, dev99, prod1
export GUID=web01

# SSH Public Key (for instance access)
# Generate with: ssh-keygen -t rsa -b 2048 -f ~/.ssh/yamlforge_key
export SSH_PUBLIC_KEY="ssh-rsa YOUR_PUBLIC_KEY_HERE your-email@example.com"

# =============================================================================
# AWS CREDENTIALS AND CONFIGURATION
# =============================================================================

# AWS Credentials (required for AWS deployments and ROSA clusters)
export AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_KEY
export AWS_DEFAULT_REGION=us-east-1

# AWS Billing Account (optional - for ROSA HCP clusters)
# If not set, defaults to the current AWS account ID
export AWS_BILLING_ACCOUNT_ID=YOUR_AWS_BILLING_ACCOUNT_ID

# Alternative: AWS Profile (if using AWS CLI profiles)
# export AWS_PROFILE=your-profile-name

# =============================================================================
# AZURE CREDENTIALS AND CONFIGURATION
# =============================================================================

# Azure Credentials (required for Azure deployments and ARO clusters)
# NOTE: ARO requires full subscription access, not compatible with shared resource groups
# Get from: az ad sp create-for-rbac --role="Contributor" --scopes="/subscriptions/YOUR_SUBSCRIPTION_ID"
export ARM_CLIENT_ID=YOUR_AZURE_CLIENT_ID
export ARM_CLIENT_SECRET=YOUR_AZURE_CLIENT_SECRET
export ARM_SUBSCRIPTION_ID=YOUR_AZURE_SUBSCRIPTION_ID
export ARM_TENANT_ID=YOUR_AZURE_TENANT_ID

# Azure Resource Management (choose one approach)
# Option 1: Use existing resource group in shared subscription (VMs only, not ARO)
export AZURE_USE_EXISTING_RESOURCE_GROUP=true
export AZURE_EXISTING_RESOURCE_GROUP_NAME=my-existing-rg
export AZURE_EXISTING_RESOURCE_GROUP_LOCATION=eastus

# Option 2: Create new resource groups in subscription (default, required for ARO)
# export AZURE_USE_EXISTING_RESOURCE_GROUP=false

# =============================================================================
# GOOGLE CLOUD PLATFORM CREDENTIALS AND CONFIGURATION
# =============================================================================

# GCP Credentials (required for GCP deployments)
# Download service account JSON from GCP Console
export GCP_SERVICE_ACCOUNT_KEY="$(cat ~/path/to/gcp-service-account.json)"
export GCP_PROJECT_ID=your-gcp-project-id
export GOOGLE_CREDENTIALS="$GCP_SERVICE_ACCOUNT_KEY"
export GOOGLE_PROJECT="$GCP_PROJECT_ID"

# GCP Project Ownership and Organization
export GCP_PROJECT_OWNER_EMAIL=admin@yourdomain.com
export GCP_COMPANY_DOMAIN=yourdomain.com
export GCP_ROOT_ZONE_DOMAIN=yourdomain.com
export GCP_BILLING_ACCOUNT_ID=YOUR_GCP_BILLING_ACCOUNT

# GCP Project Management (choose one approach)
# Option 1: Use existing project (common for users with limited permissions)
export GCP_USE_EXISTING_PROJECT=true
export GCP_EXISTING_PROJECT_ID=my-existing-project-123

# Option 2: Create new project (requires organization/folder permissions)
# export GCP_USE_EXISTING_PROJECT=false
# export GCP_ORGANIZATION_ID=YOUR_ORG_ID     # For new project creation
# export GCP_FOLDER_ID=folders/123456789     # Alternative to organization_id

# =============================================================================
# RED HAT OPENSHIFT CREDENTIALS
# =============================================================================

# Red Hat OpenShift Cluster Manager API (required for ROSA/Managed OpenShift)
# Get from: https://console.redhat.com/openshift/token
export REDHAT_OPENSHIFT_TOKEN=YOUR_REDHAT_TOKEN
export OCM_TOKEN="$REDHAT_OPENSHIFT_TOKEN"
export ROSA_TOKEN="$REDHAT_OPENSHIFT_TOKEN"
export REDHAT_OPENSHIFT_URL="https://api.openshift.com"

# OpenShift Cluster Connection (for existing cluster management)
# export OPENSHIFT_CLUSTER_URL="https://api.cluster.example.com:6443"
# export OPENSHIFT_TOKEN="your_openshift_token"
# export OPENSHIFT_USERNAME="your_username"
# export OPENSHIFT_PASSWORD="your_password"
# export OPENSHIFT_NAMESPACE="default"

# Alternative: Kubeconfig
# export OPENSHIFT_KUBECONFIG="$(cat ~/.kube/config)"

# =============================================================================
# IBM CLOUD CREDENTIALS
# =============================================================================

# IBM Cloud API Key (required for IBM Cloud deployments)
export IC_API_KEY=YOUR_IBM_CLOUD_API_KEY
export IBM_CLOUD_API_KEY=YOUR_IBM_CLOUD_API_KEY
export IBM_CLOUD_REGION=us-south

# Available IBM Cloud Regions:
# - us-south (Dallas), us-east (Washington DC), ca-tor (Toronto)
# - eu-gb (London), eu-de (Frankfurt)
# - jp-tok (Tokyo), jp-osa (Osaka), au-syd (Sydney)
# - br-sao (São Paulo)

# =============================================================================
# ORACLE CLOUD INFRASTRUCTURE (OCI) CREDENTIALS
# =============================================================================

# OCI API Key Authentication
export OCI_USER_OCID="ocid1.user.oc1..aaaaaaaa..."
export OCI_FINGERPRINT="12:34:56:78:90:ab:cd:ef"
export OCI_TENANCY_OCID="ocid1.tenancy.oc1..aaaaaaaa..."
export OCI_REGION="us-ashburn-1"
export OCI_PRIVATE_KEY="$(cat ~/.oci/oci_api_key.pem)"

# Terraform variable format (alternative)
export TF_VAR_tenancy_ocid="$OCI_TENANCY_OCID"
export TF_VAR_user_ocid="$OCI_USER_OCID"
export TF_VAR_fingerprint="$OCI_FINGERPRINT"
export TF_VAR_private_key_path=~/.oci/oci_api_key.pem

# Available OCI Regions:
# - us-ashburn-1, us-phoenix-1, ca-toronto-1, ca-montreal-1
# - eu-frankfurt-1, eu-zurich-1, uk-london-1
# - ap-tokyo-1, ap-osaka-1, ap-sydney-1, ap-melbourne-1

# =============================================================================
# VMWARE VSPHERE CREDENTIALS
# =============================================================================

# VMware vSphere Credentials (required for VMware deployments)
export VSPHERE_USER=administrator@vsphere.local
export VSPHERE_PASSWORD=your-password-here
export VSPHERE_SERVER=vcenter.example.com
export VMWARE_DATACENTER="Datacenter"
export VMWARE_CLUSTER="Cluster"
export VMWARE_DATASTORE="datastore1"
export VMWARE_NETWORK="VM Network"
export VMWARE_ALLOW_UNVERIFIED_SSL=true

# =============================================================================
# ALIBABA CLOUD CREDENTIALS
# =============================================================================

# Alibaba Cloud Credentials (required for Alibaba Cloud deployments)
export ALICLOUD_ACCESS_KEY=YOUR_ALIBABA_ACCESS_KEY
export ALICLOUD_SECRET_KEY=YOUR_ALIBABA_SECRET_KEY
export ALICLOUD_REGION=us-east-1

# Available Alibaba Cloud Regions:
# - us-east-1 (Virginia), us-west-1 (Silicon Valley)
# - cn-hangzhou (Hangzhou), cn-shanghai (Shanghai), cn-beijing (Beijing)
# - ap-southeast-1 (Singapore), eu-central-1 (Frankfurt)

# =============================================================================
# CERT-MANAGER / TLS CERTIFICATE CREDENTIALS
# =============================================================================

# ZeroSSL EAB Credentials (optional - for automated certificate management)
# Get from: https://app.zerossl.com/ → API Access → ACME
# export ZEROSSL_EAB_KID="your_zerossl_eab_kid"
# export ZEROSSL_EAB_HMAC="your_zerossl_eab_hmac"

# SSL.com EAB Credentials (optional - for automated certificate management)
# Contact SSL.com support for ACME v2 access and EAB credentials
# export SSLCOM_EAB_KID="your_sslcom_eab_kid"
# export SSLCOM_EAB_HMAC="your_sslcom_eab_hmac"

# =============================================================================
# SETUP VERIFICATION
# =============================================================================

echo "✅ YamlForge environment variables loaded!"
echo "📍 GUID: $GUID"

# Check which providers are configured
providers=()
[[ -n "$AWS_ACCESS_KEY_ID" ]] && providers+=("AWS")
[[ -n "$ARM_CLIENT_ID" ]] && providers+=("Azure") 
[[ -n "$GCP_SERVICE_ACCOUNT_KEY" ]] && providers+=("GCP")
[[ -n "$IBM_CLOUD_API_KEY" ]] && providers+=("IBM Cloud")
[[ -n "$OCI_USER_OCID" ]] && providers+=("OCI")
[[ -n "$VSPHERE_USER" ]] && providers+=("VMware")
[[ -n "$ALICLOUD_ACCESS_KEY" ]] && providers+=("Alibaba Cloud")
[[ -n "$REDHAT_OPENSHIFT_TOKEN" ]] && providers+=("OpenShift")

if [ ${#providers[@]} -gt 0 ]; then
    echo "🔐 Configured providers: $(IFS=', '; echo "${providers[*]}")"
else
    echo "⚠️  No provider credentials detected - add credentials above"
fi

# =============================================================================
# QUICK SETUP INSTRUCTIONS
# =============================================================================
#
# 1. Copy this template:
#    cp envvars.example.sh envvars.sh
#
# 2. Edit envvars.sh with your actual credentials
#
# 3. Load the environment:
#    source envvars.sh
#
# 4. Test deployment:
#    python yamlforge.py examples/testing/simple_test.yaml -d output/ --auto-deploy
#
# 5. See specific provider setup instructions in docs/
#
# Security: Never commit envvars.sh to version control! 
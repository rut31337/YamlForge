#!/bin/bash
# YamlForge Environment Variables Template
# Copy this file to envvars.sh and customize with your credentials
# 
# Usage: source envvars.sh

# Required: Unique 5-character identifier (lowercase alphanumeric)
export GUID=web01

# AWS Credentials (required for AWS deployments and ROSA clusters)
export AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY
export AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_KEY
export AWS_BILLING_ACCOUNT_ID=YOUR_AWS_BILLING_ACCOUNT_ID

# SSH Public Key (for instance access)
# Generate with: ssh-keygen -t rsa -b 2048 -f ~/.ssh/yamlforge_key
export SSH_PUBLIC_KEY="ssh-rsa YOUR_PUBLIC_KEY_HERE your-email@example.com"

# Red Hat OpenShift Token (required for ROSA/OpenShift deployments)
# Get from: https://console.redhat.com/openshift/token
export REDHAT_OPENSHIFT_TOKEN=YOUR_REDHAT_TOKEN
export OCM_TOKEN="$REDHAT_OPENSHIFT_TOKEN"
export ROSA_TOKEN="$REDHAT_OPENSHIFT_TOKEN"

# GCP Credentials (required for GCP deployments)
# Download service account JSON from GCP Console
export GCP_SERVICE_ACCOUNT_KEY="$(cat ~/path/to/gcp-service-account.json)"
export GCP_PROJECT_ID=your-gcp-project-id
export GOOGLE_CREDENTIALS="$GCP_SERVICE_ACCOUNT_KEY"
export GOOGLE_PROJECT="$GCP_PROJECT_ID"
export GCP_PROJECT_OWNER_EMAIL=your-email@company.com
export GCP_COMPANY_DOMAIN=company.com
export GCP_ROOT_ZONE_DOMAIN=your-domain.com
export GCP_BILLING_ACCOUNT_ID=YOUR_GCP_BILLING_ACCOUNT

# Azure Credentials (required for Azure deployments and ARO clusters)
# Get from: az ad sp create-for-rbac --role="Contributor" --scopes="/subscriptions/YOUR_SUBSCRIPTION_ID"
export ARM_CLIENT_ID=YOUR_AZURE_CLIENT_ID
export ARM_CLIENT_SECRET=YOUR_AZURE_CLIENT_SECRET
export ARM_SUBSCRIPTION_ID=YOUR_AZURE_SUBSCRIPTION_ID
export ARM_TENANT_ID=YOUR_AZURE_TENANT_ID

# IBM Cloud Credentials (required for IBM Cloud deployments)
export IC_API_KEY=YOUR_IBM_CLOUD_API_KEY

# Oracle Cloud Credentials (required for OCI deployments)
export TF_VAR_tenancy_ocid=YOUR_OCI_TENANCY_OCID
export TF_VAR_user_ocid=YOUR_OCI_USER_OCID
export TF_VAR_fingerprint=YOUR_OCI_KEY_FINGERPRINT
export TF_VAR_private_key_path=~/path/to/oci_private_key.pem

# VMware vSphere Credentials (required for VMware deployments)
export VSPHERE_USER=your-vsphere-username
export VSPHERE_PASSWORD=your-vsphere-password
export VSPHERE_SERVER=your-vcenter-server.com

# Alibaba Cloud Credentials (required for Alibaba Cloud deployments)
export ALICLOUD_ACCESS_KEY=YOUR_ALIBABA_ACCESS_KEY
export ALICLOUD_SECRET_KEY=YOUR_ALIBABA_SECRET_KEY
export ALICLOUD_REGION=us-east-1

echo "✅ YamlForge environment variables loaded!"
echo "📍 GUID: $GUID"
echo "🔐 Configured providers: AWS, Azure, GCP, IBM, OCI, VMware, Alibaba" 
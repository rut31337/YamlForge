# Azure Credentials Configuration

This guide explains how to configure Azure credentials for YamlForge deployments.

## Required Environment Variables

YamlForge uses the standard Terraform AzureRM provider authentication method via environment variables:

```bash
export ARM_CLIENT_ID=YOUR_AZURE_CLIENT_ID           # Application (client) ID
export ARM_CLIENT_SECRET=YOUR_AZURE_CLIENT_SECRET   # Client secret value  
export ARM_SUBSCRIPTION_ID=YOUR_AZURE_SUBSCRIPTION_ID  # Azure subscription ID
export ARM_TENANT_ID=YOUR_AZURE_TENANT_ID           # Directory (tenant) ID
```

## Getting Your Azure Credentials

### Step 1: Find Your Subscription ID

```bash
# List all available subscriptions
az account list --output table

# Get current subscription ID
az account show --query "id" --output tsv

# Set specific subscription (if needed)
az account set --subscription "YOUR_SUBSCRIPTION_ID"
```

### Step 2: Create Service Principal

Create a service principal with Contributor access to your subscription:

```bash
# Replace YOUR_SUBSCRIPTION_ID with your actual subscription ID
az ad sp create-for-rbac \
  --role="Contributor" \
  --scopes="/subscriptions/YOUR_SUBSCRIPTION_ID" \
  --name="YamlForge-ServicePrincipal"
```

### Step 3: Extract Credentials

The command above returns JSON like this:

```json
{
  "appId": "12345678-1234-1234-1234-123456789012",        # → ARM_CLIENT_ID
  "displayName": "YamlForge-ServicePrincipal",
  "password": "abcdef~123456789012345678901234567890",    # → ARM_CLIENT_SECRET
  "tenant": "87654321-4321-4321-4321-210987654321"       # → ARM_TENANT_ID
}
```

Map these values to environment variables:
- `appId` → `ARM_CLIENT_ID`
- `password` → `ARM_CLIENT_SECRET`  
- `tenant` → `ARM_TENANT_ID`
- Your subscription ID → `ARM_SUBSCRIPTION_ID`

## Configuration Examples

### Option 1: Environment File (Recommended)

Add to your `envvars.sh`:

```bash
# Azure Credentials
export ARM_CLIENT_ID=12345678-1234-1234-1234-123456789012
export ARM_CLIENT_SECRET=abcdef~123456789012345678901234567890
export ARM_SUBSCRIPTION_ID=87654321-4321-4321-4321-210987654321
export ARM_TENANT_ID=11111111-2222-3333-4444-555555555555

# Source the file
source envvars.sh
```

### Option 2: Direct Export

```bash
export ARM_CLIENT_ID=12345678-1234-1234-1234-123456789012
export ARM_CLIENT_SECRET=abcdef~123456789012345678901234567890
export ARM_SUBSCRIPTION_ID=87654321-4321-4321-4321-210987654321
export ARM_TENANT_ID=11111111-2222-3333-4444-555555555555
```

## How Credentials Work with Resource Group Models

The same Azure credentials work with both YamlForge deployment models:

### Model 1: Entire Subscription (Default)
- Uses `ARM_SUBSCRIPTION_ID` to determine target subscription
- Creates new resource groups in that subscription
- Requires Contributor permissions on subscription
- **Required for ARO clusters** - ARO requires full subscription access

### Model 2: Shared Subscription + Existing Resource Group  
- Uses `ARM_SUBSCRIPTION_ID` to determine target subscription
- Uses existing resource groups in that subscription
- Requires Contributor permissions on resource group(s)
- **Not compatible with ARO clusters** - ARO requires full subscription permissions

## Verification

Test your credentials:

```bash
# Verify authentication
az account show

# Test Terraform authentication
terraform plan  # Should authenticate successfully
```

## Troubleshooting

### Common Issues

1. **Invalid Subscription ID**: Verify with `az account list`
2. **Insufficient Permissions**: Ensure service principal has Contributor role
3. **Expired Secret**: Rotate client secret if needed
4. **Wrong Tenant**: Verify tenant ID matches your Azure AD

### Permission Requirements

- **Entire Subscription Model**: Contributor on subscription (required for ARO)
- **Shared Resource Group Model**: Contributor on specific resource group(s) (VMs only, not ARO)

## Security Best Practices

1. **Rotate Secrets**: Regularly update client secrets
2. **Limit Scope**: Use resource group-level permissions when possible  
3. **Environment Files**: Never commit `envvars.sh` to version control
4. **Monitoring**: Enable Azure activity logging for service principal actions

## Related Documentation

- [Azure Resource Group Models](quickstart.md#azure-configuration)
- [Environment Variables Setup](quickstart.md#step-1-set-up-environment-variables)
- [Examples](../examples/cloud-specific/README.md#azure-examples) 
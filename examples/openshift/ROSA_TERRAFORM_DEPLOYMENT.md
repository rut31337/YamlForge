# ROSA Terraform Deployment - YamlForge

YamlForge supports two deployment methods for ROSA (Red Hat OpenShift Service on AWS) clusters:

1. **ROSA CLI Method** (Traditional) - Uses ROSA CLI commands for cluster creation
2. **RHCS Terraform Provider Method** - Uses the Red Hat Cloud Services Terraform provider for full lifecycle management

## Configuration

The deployment method is configured in `defaults/openshift.yaml`:

```yaml
openshift:
  # ROSA deployment method configuration
  rosa_deployment:
    # Method to use for ROSA cluster creation:
    # - "cli": Use ROSA CLI commands (traditional method)
    # - "terraform": Use RHCS Terraform provider (better lifecycle management)
    method: "terraform"
    
    # Note: When both ROSA Classic and ROSA HCP are deployed together,
    # YamlForge automatically separates them into phases to handle
    # overlapping infrastructure requirements:
    # - Phase 1: Shared infrastructure + ROSA Classic clusters
    # - Phase 2: ROSA HCP clusters (using Phase 1 infrastructure)
```

## Deployment Methods Comparison

### ROSA CLI Method (`method: "cli"`)
- **Pros**: Traditional method, well-documented
- **Cons**: 
  - Limited lifecycle management, clusters created outside Terraform
  - Manual cleanup required (cleanup scripts must be run manually)
  - No automatic state tracking
- **Use case**: Quick testing, environments where Terraform lifecycle management isn't required

### RHCS Terraform Provider Method (`method: "terraform"`)
- **Pros**: 
  - Full lifecycle management including automatic cleanup (`terraform destroy`)
  - Consistent state tracking
  - Better CI/CD integration
  - Complete infrastructure-as-code approach
- **Cons**: Requires RHCS provider configuration
- **Use case**: Production environments, enterprise deployments, automated workflows

## Automatic Deployment Separation

YamlForge **automatically detects** when multiple OpenShift cluster types are present and separates them into deployment groups to handle overlapping Terraform configurations or dependencies. This happens automatically - no configuration required.

> ** Safety First**: All deployment variables default to `false`. You must explicitly enable the deployment groups you want by setting their variables to `true`. This prevents accidental deployments.

**Supported cluster types with automatic deployment separation:**
- **ROSA Classic** clusters (separate from HCP to avoid Terraform configuration conflicts)
- **ROSA HCP** clusters (separate from Classic to avoid Terraform configuration conflicts)
- **HyperShift management** clusters (deployed first, before hosted clusters)
- **HyperShift hosted** clusters (deployed after management clusters are ready)
- **Day-2 operations** (always deployed last, after all clusters are ready)

### Step 1: ROSA Classic Deployment
```bash
terraform apply -var="deploy_rosa_classic=true"
```
- Creates AWS infrastructure (VPC, subnets, etc.)
- Deploys ROSA Classic clusters
- Sets up shared OIDC configuration

### Step 2: ROSA HCP Deployment (if needed)
```bash
terraform apply -var="deploy_rosa_classic=true" -var="deploy_rosa_hcp=true"
```
- Deploys ROSA HCP clusters (avoids Terraform configuration conflicts with ROSA Classic)
- Uses shared infrastructure and configuration

### Step 3: HyperShift Management Deployment (if needed)
```bash
terraform apply -var="deploy_rosa_classic=true" -var="deploy_rosa_hcp=true" -var="deploy_hypershift_mgmt=true"
```
- Deploys HyperShift management clusters (based on ROSA Classic)
- Sets up HyperShift operator and management plane

### Step 4: HyperShift Hosted Deployment (if needed)
```bash
terraform apply -var="deploy_rosa_classic=true" -var="deploy_rosa_hcp=true" -var="deploy_hypershift_mgmt=true" -var="deploy_hypershift_hosted=true"
```
- Deploys HyperShift hosted clusters (requires management clusters to be ready)
- Creates worker infrastructure and hosted control planes

### Step 5: Day-2 Operations (always last)
```bash
terraform apply -var="deploy_rosa_classic=true" -var="deploy_rosa_hcp=true" -var="deploy_hypershift_mgmt=true" -var="deploy_hypershift_hosted=true" -var="deploy_day2_operations=true"
```
- Deploys operators, monitoring, GitOps, etc.
- Configures applications
- Sets up service accounts for cluster management

### Complete Cleanup (Terraform Method Only)
```bash
terraform destroy
```
- **Automatically removes ALL resources**: clusters, infrastructure, day-2 operations
- **No manual scripts needed**: Unlike ROSA CLI method which requires running cleanup scripts manually
- **Guaranteed cleanup**: Terraform tracks all resources and removes them systematically
- **Cost control**: Ensures no orphaned resources are left running

## Example Configuration

See `examples/openshift/rosa_terraform_deployment_example.yaml` for a complete example.

## Benefits of Terraform Method

1. **Complete Lifecycle Management**: Full cluster lifecycle managed through Terraform
   - **Creation**: `terraform apply` creates clusters
   - **Updates**: `terraform apply` handles configuration changes
   - **Cleanup**: `terraform destroy` automatically removes all resources
   - **No manual scripts**: Unlike CLI method which requires manual cleanup scripts

2. **Consistent State Tracking**: Cluster state tracked in Terraform state files
   - Always know what resources exist
   - Detect configuration drift
   - Rollback capabilities

3. **CI/CD Integration**: Seamless integration with automated deployment pipelines
   - GitOps workflows
   - Automated testing and validation
   - Consistent deployments across environments

4. **Multi-cluster Management**: Manage multiple clusters consistently
   - Unified configuration approach
   - Consistent naming and tagging
   - Coordinated deployments

5. **Day-2 Operations**: Full support for operators, monitoring, and applications
   - Integrated with cluster lifecycle
   - Automatic dependency management
   - Complete infrastructure-as-code

## Migration from CLI to Terraform Method

To migrate existing CLI-based deployments:

1. Update `defaults/openshift.yaml` to set `method: "terraform"`
2. Import existing clusters into Terraform state (if needed)
3. Re-run YamlForge to generate new Terraform configuration
4. Apply the new configuration

## Troubleshooting

### Common Issues

1. **OIDC Configuration**: Ensure `rosa_oidc_config_id` variable is set correctly
2. **Deployment Order**: Always deploy Classic group before HCP group
3. **AWS Permissions**: Ensure AWS credentials have ROSA permissions
4. **Resource Cleanup**: 
   - **Terraform method**: Use `terraform destroy` for complete automatic cleanup
   - **CLI method**: Manual cleanup scripts required (generated but must be run manually)

### Variables Reference

- `deploy_rosa_classic`: Deploy ROSA Classic clusters (default: `false`)
- `deploy_rosa_hcp`: Deploy ROSA HCP clusters (default: `false`, separate from Classic to avoid Terraform conflicts)
- `deploy_hypershift_mgmt`: Deploy HyperShift management clusters (default: `false`)
- `deploy_hypershift_hosted`: Deploy HyperShift hosted clusters (default: `false`, requires management clusters)
- `deploy_day2_operations`: Deploy Day-2 operations (default: `false`, always last)
- `rosa_oidc_config_id`: OIDC configuration ID for ROSA clusters

### Credentials Setup

For ROSA clusters using the Terraform method, ensure the following environment variables are set (reference your `~/envvars.sh` setup):

- **AWS Credentials**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` (if using temporary credentials)
- **ROSA Token**: `REDHAT_OPENSHIFT_TOKEN` for Red Hat Cloud Services authentication
- **AWS Account Info**: `AWS_ACCOUNT_ID`, `AWS_ARN` for ROSA cluster creation

The RHCS Terraform provider will use these credentials to create and manage ROSA clusters through the Red Hat Cloud Services API. 

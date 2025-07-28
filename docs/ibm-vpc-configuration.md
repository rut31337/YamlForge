# IBM VPC Configuration

IBM VPC (Virtual Private Cloud) configuration options for YamlForge deployments.

## Configuration Options

### Basic Configuration

```yaml
yamlforge:
  ibm_vpc:
    use_existing_resource_group: false
    create_cloud_user: true
```

### Configuration Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_existing_resource_group` | boolean | `false` | Use an existing IBM Cloud resource group instead of creating new ones |
| `existing_resource_group_name` | string | - | Name of the existing IBM Cloud resource group to use (required if `use_existing_resource_group` is `true`) |
| `create_cloud_user` | boolean | `true` | Create cloud-user account with SSH access instead of using root account |
| `auto_create_outbound_sg` | boolean | `true` | Automatically create outbound security group for internet access if none configured |

## Cloud-User Configuration

### Default Behavior (create_cloud_user: true)

When `create_cloud_user` is set to `true` (default):

- Creates a `cloud-user` account on RHEL instances
- Configures SSH access for the cloud-user account
- Sets up sudo access without password
- Disables root SSH access for security
- SSH username will be `cloud-user`

**Example:**
```yaml
yamlforge:
  ibm_vpc:
    create_cloud_user: true  # Default behavior
```

### Root Account Usage (create_cloud_user: false)

When `create_cloud_user` is set to `false`:

- No user_data script is generated
- Uses the default root account
- SSH username will be `root`
- No system modifications are performed

**Example:**
```yaml
yamlforge:
  ibm_vpc:
    create_cloud_user: false  # Use root account
```

## Outbound Security Group Configuration

### Automatic Outbound Security Group (Default)

When `auto_create_outbound_sg` is set to `true` (default):

- YamlForge automatically creates an outbound security group if no outbound rules are configured
- The auto-created security group allows all outbound traffic (0.0.0.0/0)
- This is essential for RHEL instances to complete their initialization process
- A message is displayed: "INFO: No outbound security group rules found. Creating automatic outbound security group for {region}."

**Example:**
```yaml
yamlforge:
  ibm_vpc:
    auto_create_outbound_sg: true  # Default behavior
```

### Manual Outbound Configuration

When `auto_create_outbound_sg` is set to `false`:

- No automatic outbound security group is created
- You must manually configure outbound rules in your security groups
- Useful when you need specific outbound restrictions

**Example:**
```yaml
yamlforge:
  ibm_vpc:
    auto_create_outbound_sg: false  # Manual configuration required

security_groups:
  - name: "my-security-group"
    rules:
      - direction: "ingress"
        protocol: "tcp"
        port_range: "22"
        source: "0.0.0.0/0"
      - direction: "egress"  # Manual outbound rule
        protocol: "all"
        port_range: "0-65535"
        source: "0.0.0.0/0"
```

## Resource Group Configuration

### Creating New Resource Groups (Default)

```yaml
yamlforge:
  ibm_vpc:
    use_existing_resource_group: false  # Default behavior
```

YamlForge will create a new resource group for each deployment with the naming pattern:
`{deployment-name}-{guid}-vpc-{region}`

### Using Existing Resource Groups

```yaml
yamlforge:
  ibm_vpc:
    use_existing_resource_group: true
    existing_resource_group_name: "my-existing-resource-group"
```

When using existing resource groups:
- All resources will be created in the specified resource group
- The resource group must exist before deployment
- Useful for organizations with centralized resource management

## Complete Example

```yaml
---
guid: "demo01"

yamlforge:
  cloud_workspace:
    name: "ibm-vpc-demo-{guid}"
    description: "IBM VPC deployment example"
  
  ibm_vpc:
    use_existing_resource_group: false
    create_cloud_user: true  # Create cloud-user account with SSH access
    auto_create_outbound_sg: true  # Automatically create outbound security group for internet access
  
  security_groups:
    - name: "ssh-access-{guid}"
      description: "Allow SSH access (ingress only - outbound will be auto-created)"
      rules:
        - direction: "ingress"
          protocol: "tcp"
          port_range: "22"
          source: "0.0.0.0/0"
          description: "SSH access from anywhere"
  
  instances:
    - name: "web-server-{guid}"
      provider: "ibm_vpc"
      size: "medium"
      region: "us-south"
      image: "RHEL9-latest"
      security_groups: ["ssh-access-{guid}"]
      tags:
        environment: "production"
        tier: "web"
  
  tags:
    project: "ibm-vpc-demo"
    managed_by: "yamlforge"
```

**Note**: With `auto_create_outbound_sg: true`, YamlForge will automatically create an outbound security group that allows all protocols (TCP, UDP, ICMP) on ports 1-65535, which is essential for RHEL instances to complete their initialization process.

## SSH Access

### With Cloud-User (Default)
```bash
ssh cloud-user@<public-ip>
```

### With Root Account
```bash
ssh root@<public-ip>
```

## Security Considerations

- **Cloud-User (Recommended)**: More secure, follows security best practices
- **Root Account**: Less secure, but may be required for certain use cases
- **SSH Key Management**: Always use SSH keys instead of passwords
- **Security Groups**: Configure appropriate security group rules for SSH access

## Troubleshooting

### Common Issues and Solutions

#### 1. RHEL Instance Fails to Start (`cannot_start_compute`)

**Problem**: RHEL instances fail to start with `cannot_start_compute` error.

**Cause**: Missing outbound security group rules prevent RHEL instances from completing initialization.

**Solution**: 
- Ensure `auto_create_outbound_sg: true` (default) is set
- Or manually configure outbound rules in your security groups
- The automatic outbound security group allows all protocols (TCP, UDP, ICMP) on ports 1-65535

#### 2. Cloud-User Account Not Created

**Problem**: The `cloud-user` account is not created despite `create_cloud_user: true`.

**Cause**: User data script not executing due to cloud-init configuration issues.

**Solution**:
- YamlForge now passes user data directly without base64 encoding (fixed in v0.99.0a1)
- Ensure `create_cloud_user: true` is set in your configuration
- Check cloud-init logs: `journalctl -u cloud-init --no-pager`

#### 3. SSH Connection Fails
   - Verify the correct username (cloud-user vs root)
   - Check security group rules allow SSH access
   - Ensure SSH key is properly configured

#### 4. Resource Group Errors
   - Verify resource group exists when using `use_existing_resource_group: true`
   - Check permissions for resource group access

#### 5. Security Group Protocol Issues

**Problem**: Security group rules with "all" protocol not working correctly.

**Solution**: 
- YamlForge automatically creates separate rules for TCP, UDP, and ICMP when protocol is "all"
- This ensures compatibility with IBM VPC requirements
- Port ranges are automatically corrected to 1-65535 (IBM VPC doesn't allow port 0) 

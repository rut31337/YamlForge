# IBM Cloud Classic Configuration

## Overview

IBM Cloud Classic provides traditional infrastructure-as-a-service with full account access and datacenter-based deployment.

## Environment Variables

### Required
```bash
# IBM Cloud API Key (required for both Classic and VPC)
export IBMCLOUD_API_KEY=YOUR_IBM_CLOUD_API_KEY

# IBM Cloud Account ID (required for Classic, optional for VPC)
export IBMCLOUD_ACCOUNT_ID=YOUR_IBM_CLOUD_ACCOUNT_ID
```

### Not Required (Configure in YAML Instead)
The following environment variables are **NOT USED** and should be configured in your YAML file:

- ❌ `IBMCLOUD_CLASSIC_DATACENTER` - Use `region` in instance configuration
- ❌ `IBMCLOUD_CLASSIC_DOMAIN` - Use `domain` in `ibm_classic` configuration
- ❌ `IBM_CLOUD_REGION` - Use `region` in instance configuration

## YAML Configuration

### IBM Classic Configuration Section
```yaml
guid: "ibc01"

yamlforge:
  cloud_workspace:
    name: "ibm-classic-config-{guid}"
    description: "IBM Classic configuration example"
  
  ibm_classic:
    domain: "example.com"  # Required: Domain for all IBM Classic instances
    create_cloud_user: true  # Optional: Create cloud-user account (default: true)
    auto_create_outbound_sg: true  # Optional: Auto-create outbound security group (default: true)
  
  instances:
    - name: "example-{guid}"
      provider: "ibm_classic"
      flavor: "medium"
      image: "RHEL9-latest"
      region: "dal10"
```

### Instance Configuration
```yaml
guid: "ibc02"

yamlforge:
  cloud_workspace:
    name: "ibm-classic-instance-{guid}"
    description: "IBM Classic instance configuration example"
  
  instances:
    - name: "web-server-{guid}"
      provider: "ibm_classic"
      region: "dal10"  # IBM Classic datacenter (e.g., dal10, wdc04, lon02)
      flavor: "medium"
      image: "RHEL9-latest"
```

## Available Datacenters

IBM Cloud Classic datacenters (use as `region` in instances):

### North America
- `dal10` - Dallas 10
- `dal12` - Dallas 12
- `wdc04` - Washington DC 4
- `wdc06` - Washington DC 6
- `tor01` - Toronto 1
- `mon01` - Montreal 1

### Europe
- `lon02` - London 2
- `lon04` - London 4
- `lon05` - London 5
- `lon06` - London 6
- `fra02` - Frankfurt 2
- `fra04` - Frankfurt 4
- `fra05` - Frankfurt 5
- `ams01` - Amsterdam 1
- `ams03` - Amsterdam 3
- `par01` - Paris 1

### Asia Pacific
- `tok02` - Tokyo 2
- `tok04` - Tokyo 4
- `tok05` - Tokyo 5
- `osa21` - Osaka 21
- `osa22` - Osaka 22
- `syd01` - Sydney 1
- `syd04` - Sydney 4
- `syd05` - Sydney 5
- `hkg02` - Hong Kong 2
- `seo01` - Seoul 1

### South America
- `sao01` - São Paulo 1

## Features

### Cloud User Creation
IBM Classic can automatically create a `cloud-user` account with SSH access instead of using the root account:

**Configuration in your YamlForge file:**
```yaml
# In the ibm_classic section
ibm_classic:
  create_cloud_user: true  # Default: true
```

### Automatic Outbound Security Groups
IBM Classic can automatically create outbound security groups for internet access:

**Configuration in your YamlForge file:**
```yaml
# In the ibm_classic section
ibm_classic:
  auto_create_outbound_sg: true  # Default: true
```

## Example

See `examples/cloud-specific/ibm_classic_example.yaml` for a complete example.

## Notes

- IBM Classic instances require a domain name (configured globally in `ibm_classic.domain`)
- Datacenters are specified per instance using the `region` field
- IBM Classic provides full account access (no resource group concept)
- Uses tagging for organization instead of resource groups

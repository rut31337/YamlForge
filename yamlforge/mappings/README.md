# YamlForge Mappings

This directory contains all the mapping files that YamlForge uses to translate generic terms into provider-specific resources.

## Directory Structure

```
mappings/
├── images.yaml                    # Operating system image mappings
├── locations.yaml                 # Region/location mappings
├── flavors/                       # Instance flavor mappings
│   ├── aws.yaml
│   ├── azure.yaml
│   ├── gcp.yaml
│   ├── oci.yaml
│   ├── ibm_vpc.yaml
│   ├── ibm_classic.yaml
│   ├── vmware.yaml
│   ├── alibaba.yaml
│   └── cnv.yaml
├── flavors_openshift/             # OpenShift-specific mappings
│   ├── openshift_aws.yaml
│   ├── openshift_azure.yaml
│   ├── openshift_gcp.yaml
│   ├── openshift_oci.yaml
│   ├── openshift_ibm_vpc.yaml
│   ├── openshift_ibm_classic.yaml
│   └── openshift_vmware.yaml
└── gcp/
    └── machine-type-availability.yaml  # GCP machine type availability
```

## Image Mappings (`images.yaml`)

Maps generic image names to provider-specific image identifiers.

### Example Usage

```yaml
# In your YAML configuration
instances:
  - name: "web-server"
    provider: "aws"
    flavor: "medium"
    image: "RHEL9-latest"  # Generic name
    region: "us-east-1"
```

### Mapping Structure

```yaml
# mappings/images.yaml
image_mappings:
  RHEL9-latest:
    aws: "ami-12345678"
    azure: "rhel-9-latest"
    gcp: "rhel-cloud/rhel-9"
    oci: "ocid1.image.oc1..aaaaaaa..."
    ibm_vpc: "rhel-9-latest"
    ibm_classic: "REDHAT_7_64"
    vmware: "rhel-9-latest"
    alibaba: "rhel_9_0_x64_20G_alibase_20200914.vhd"
    cnv: "kubevirt/fedora-cloud-container-disk-demo:latest"
```

## Location Mappings (`locations.yaml`)

Maps universal location names to provider-specific regions.

### Example Usage

```yaml
# In your YAML configuration
instances:
  - name: "web-server"
    provider: "aws"
    flavor: "medium"
    image: "RHEL9-latest"
    region: "us-east"  # Universal location
```

### Mapping Structure

```yaml
# mappings/locations.yaml
location_mappings:
  us-east:
    aws: "us-east-1"
    azure: "eastus"
    gcp: "us-east1"
    oci: "us-ashburn-1"
    ibm_vpc: "us-east"
    ibm_classic: "us-east"
    vmware: "us-east"
    alibaba: "us-east-1"
    cnv: "us-east"  # CNV doesn't use regions
```

## Flavor Mappings (`flavors/`)

Maps generic flavor names to provider-specific instance types.

### Example Usage

```yaml
# In your YAML configuration
instances:
  - name: "web-server"
    provider: "aws"
    flavor: "medium"  # Generic flavor
    image: "RHEL9-latest"
    region: "us-east-1"
```

### Mapping Structure

```yaml
# mappings/flavors/aws.yaml
flavor_mappings:
  small:
    aws-small:
      instance_type: "t3.small"
      vcpus: 2
      memory_gb: 2
      hourly_cost: 0.0208
      description: "Small instance for development"
      suitable_for:
        - "Development environments"
        - "Testing workloads"
        - "Small applications"
  
  medium:
    aws-medium:
      instance_type: "t3.medium"
      vcpus: 2
      memory_gb: 4
      hourly_cost: 0.0416
      description: "Medium instance for general workloads"
      suitable_for:
        - "Web applications"
        - "Small databases"
        - "Development servers"
```

## OpenShift Flavor Mappings (`flavors_openshift/`)

Maps cluster sizes to OpenShift-specific configurations.

### Example Usage

```yaml
# In your YAML configuration
openshift_clusters:
  - name: "my-cluster"
    type: "rosa-classic"
    size: "medium"  # Cluster size (not instance size)
    worker_count: 3
```

### Mapping Structure

```yaml
# mappings/flavors_openshift/openshift_aws.yaml
flavor_mappings:
  small:
    rosa-small:
      controlplane_size: "controlplane_small"
      worker_size: "worker_micro"
      controlplane_count: 3
      worker_count: 3
      hourly_cost: 0.25
      description: "Small ROSA cluster for development"
      suitable_for:
        - "Development environments"
        - "Testing workloads"
        - "Small applications"
  
  medium:
    rosa-medium:
      controlplane_size: "controlplane_medium"
      worker_size: "worker_medium"
      controlplane_count: 3
      worker_count: 6
      hourly_cost: 0.50
      description: "Medium ROSA cluster for production"
      suitable_for:
        - "Production workloads"
        - "Medium applications"
        - "Team development"
```

## GCP Machine Type Availability (`gcp/machine-type-availability.yaml`)

Defines GCP machine type availability by region and region proximity mappings.

### Example Usage

```yaml
# Used internally by YamlForge for GCP machine type selection
gpu_machine_types:
  n1-standard-4-t4:
    regions:
      - "us-east1"
      - "us-east4"
      - "us-west1"
      - "us-west2"
    description: "4 vCPU, T4 GPU machine type"

region_proximity:
  us-central1:
    nearby_regions:
      - "us-east1"
      - "us-west1"
      - "us-east4"
      - "us-west2"
    description: "Central US region"
```

## Customizing Mappings

### Adding New Images

1. **Edit `mappings/images.yaml`**
   ```yaml
   image_mappings:
     MyCustomImage:
       aws: "ami-your-custom-ami"
       azure: "your-custom-image"
       gcp: "your-project/your-image"
   ```

2. **Use in your configuration**
   ```yaml
   instances:
     - name: "custom-server"
       provider: "aws"
       flavor: "medium"
       image: "MyCustomImage"  # Your custom image
       region: "us-east-1"
   ```

### Adding New Flavors

1. **Edit provider-specific flavor file**
   ```yaml
   # mappings/flavors/aws.yaml
   flavor_mappings:
     custom_large:
       aws-custom-large:
         instance_type: "c5.2xlarge"
         vcpus: 8
         memory_gb: 16
         hourly_cost: 0.34
         description: "Custom large instance"
   ```

2. **Use in your configuration**
   ```yaml
   instances:
     - name: "custom-server"
       provider: "aws"
       flavor: "custom_large"  # Your custom flavor
       image: "RHEL9-latest"
       region: "us-east-1"
   ```

### Adding New Locations

1. **Edit `mappings/locations.yaml`**
   ```yaml
   location_mappings:
     my-region:
       aws: "us-my-region-1"
       azure: "myregion"
       gcp: "my-region1"
   ```

2. **Use in your configuration**
   ```yaml
   instances:
     - name: "regional-server"
       provider: "aws"
       flavor: "medium"
       image: "RHEL9-latest"
       region: "my-region"  # Your custom location
   ```

## Best Practices

### 1. Use Generic Names

```yaml
# ✅ Good - Use generic names
flavor: "medium"
image: "RHEL9-latest"
region: "us-east"

# ❌ Avoid - Provider-specific names
flavor: "t3.medium"
image: "ami-12345678"
region: "us-east-1"
```

### 2. Keep Mappings Updated

- Update cost information regularly
- Add new instance types as they become available
- Remove deprecated resources

### 3. Use Descriptive Names

```yaml
# ✅ Good - Descriptive names
flavor: "memory_optimized_large"
image: "Ubuntu2204-latest"

# ❌ Avoid - Unclear names
flavor: "type1"
image: "img1"
```

### 4. Document Custom Mappings

```yaml
# Add descriptions and use cases
flavor_mappings:
  production_large:
    aws-production-large:
      instance_type: "m5.2xlarge"
      vcpus: 8
      memory_gb: 32
      hourly_cost: 0.384
      description: "Production-optimized large instance"
      suitable_for:
        - "Production workloads"
        - "High-performance applications"
        - "Database servers"
```

## Validation

YamlForge validates mappings during configuration analysis:

```bash
# Analyze configuration to see mapped values
python yamlforge.py my-config.yaml --analyze
```

**Sample Output:**
```
Instance Analysis:
- Name: web-server
- Provider: aws
- Flavor: medium (t3.medium)
- Image: RHEL9-latest (ami-12345678)
- Region: us-east (us-east-1)
```

## Troubleshooting

### Common Issues

1. **Missing Mapping**
   ```bash
   # Error: No mapping found for flavor 'invalid-flavor'
   # Solution: Add mapping to appropriate flavor file
   ```

2. **Invalid Provider**
   ```bash
   # Error: Provider 'invalid-provider' not supported
   # Solution: Use supported provider names
   ```

3. **Region Not Available**
   ```bash
   # Error: Region 'invalid-region' not available
   # Solution: Check location mappings
   ```

### Debugging Mappings

```bash
# Use verbose mode to see mapping details
python yamlforge.py my-config.yaml --analyze --verbose
```

## Related Documentation

- [Configuration Guide](../docs/configuration.md)
- [Provider Documentation](../docs/providers/)
- [Examples](../examples/) 

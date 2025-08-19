# Object Storage Documentation

YamlForge provides unified object storage deployment across all major cloud providers. Define storage buckets once and deploy them as native resources (AWS S3, Azure Blob Storage, GCP Cloud Storage, etc.) with consistent configuration patterns.

## Quick Start

```yaml
guid: "demo1"

yamlforge:
  cloud_workspace:
    name: "storage-demo-{guid}"
  
  storage:
    - name: "my-bucket-{guid}"
      provider: "aws"
      location: "us-east"
      public: false
      versioning: true
      encryption: true
```

## Configuration Reference

### Required Fields

| Field | Description | Example |
|-------|-------------|---------|
| `name` | Unique bucket name (supports {guid} placeholder) | `"data-bucket-{guid}"` |
| `provider` | Cloud provider or `cheapest` for cost optimization | `"aws"`, `"azure"`, `"cheapest"` |

### Location Fields (Choose One)

| Field | Description | Example |
|-------|-------------|---------|
| `region` | Direct cloud region specification | `"us-east-1"`, `"eastus"`, `"us-central1"` |
| `location` | Universal location mapping | `"us-east"`, `"eu-west"` |

### Optional Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `public` | boolean | `false` | Enable public read access |
| `versioning` | boolean | `false` | Enable object versioning |
| `encryption` | boolean | `true` | Enable server-side encryption |
| `tags` | object | `{}` | Key-value metadata tags |

## Provider Support

### AWS S3
- **Resources**: S3 bucket, bucket ACL, versioning, encryption configuration
- **Public Access**: ACL-based with public access block management
- **Versioning**: Native S3 versioning support
- **Encryption**: AES256 server-side encryption

```yaml
storage:
  - name: "s3-bucket-{guid}"
    provider: "aws"
    location: "us-east"
    public: false
    versioning: true
    encryption: true
```

### Azure Blob Storage
- **Resources**: Storage account, resource group, blob container
- **Public Access**: Container-level access control
- **Versioning**: Lifecycle management policies
- **Encryption**: Infrastructure encryption

```yaml
storage:
  - name: "azure-storage-{guid}"
    provider: "azure"
    region: "East US"
    public: true
    versioning: false
    encryption: true
```

### GCP Cloud Storage
- **Resources**: Storage bucket with IAM bindings
- **Public Access**: IAM-based public access
- **Versioning**: Native bucket versioning
- **Encryption**: Default Google-managed encryption

```yaml
storage:
  - name: "gcs-bucket-{guid}"
    provider: "gcp"
    region: "us-central1"
    public: false
    versioning: true
```

### Oracle Cloud Infrastructure (OCI)
- **Resources**: Object storage bucket with namespace
- **Public Access**: Bucket-level access control
- **Versioning**: Object versioning support

```yaml
storage:
  - name: "oci-bucket-{guid}"
    provider: "oci"
    region: "us-ashburn-1"
    public: false
    versioning: true
```

### IBM Cloud Object Storage
- **Resources**: COS instance and bucket
- **Public Access**: IAM-controlled access
- **Versioning**: Manual configuration required

```yaml
storage:
  - name: "ibm-bucket-{guid}"
    provider: "ibm_vpc"
    region: "us-south"
    public: false
    versioning: false
```

### Alibaba Cloud OSS
- **Resources**: OSS bucket with ACL
- **Public Access**: ACL-based control
- **Versioning**: Bucket versioning support

```yaml
storage:
  - name: "oss-bucket-{guid}"
    provider: "alibaba"
    region: "oss-us-east-1"
    public: false
    versioning: true
```

## Location Mapping

YamlForge supports universal location mapping for consistent multi-cloud deployments:

| Universal Location | AWS | Azure | GCP | IBM VPC |
|-------------------|-----|-------|-----|---------|
| `us-east` | us-east-1 | East US | us-east1 | us-east |
| `us-west` | us-west-2 | West US 2 | us-west1 | us-south |
| `eu-west` | eu-west-1 | West Europe | europe-west1 | eu-gb |

```yaml
# Uses location mapping
storage:
  - name: "mapped-bucket-{guid}"
    provider: "aws"
    location: "us-east"  # Maps to us-east-1

# Direct region specification
storage:
  - name: "direct-bucket-{guid}"
    provider: "aws"
    location: "us-east"  # Direct region
```

## Cost Optimization

Use the `cheapest` provider for automatic cost optimization:

```yaml
storage:
  - name: "cost-optimized-{guid}"
    provider: "cheapest"
    location: "us-east"
    public: false
    versioning: true
    encryption: true
```

YamlForge analyzes pricing across all providers and selects the most cost-effective option that meets your requirements.

## Multi-Cloud Examples

### Data Lake Architecture
```yaml
guid: "lake1"

yamlforge:
  cloud_workspace:
    name: "data-lake-{guid}"
  
  storage:
    # Raw data ingestion
    - name: "raw-data-{guid}"
      provider: "aws"
      location: "us-east"
      public: false
      versioning: true
      tags:
        Purpose: "data-ingestion"
        Tier: "raw"
    
    # Processed data storage
    - name: "processed-data-{guid}"
      provider: "azure"
      location: "us-east"
      public: false
      versioning: true
      tags:
        Purpose: "processed-data"
        Tier: "curated"
    
    # Archive storage (cost-optimized)
    - name: "archive-{guid}"
      provider: "cheapest"
      location: "us-east"
      public: false
      versioning: false
      tags:
        Purpose: "long-term-archive"
```

### Content Distribution
```yaml
guid: "cdn01"

yamlforge:
  cloud_workspace:
    name: "content-distribution-{guid}"
  
  storage:
    # Primary content storage
    - name: "primary-content-{guid}"
      provider: "aws"
      location: "us-east"
      public: true
      versioning: true
      tags:
        Purpose: "primary-content"
        CDN: "enabled"
    
    # Regional mirrors
    - name: "eu-mirror-{guid}"
      provider: "gcp"
      region: "europe-west1"
      public: true
      versioning: false
      tags:
        Purpose: "regional-mirror"
        Region: "europe"
    
    # Backup storage
    - name: "backup-{guid}"
      provider: "cheapest"
      location: "us-west"
      public: false
      versioning: true
      tags:
        Purpose: "backup"
```

## Advanced Configuration

### Tagging Strategy
```yaml
storage:
  - name: "production-data-{guid}"
    provider: "aws"
    location: "us-east"
    tags:
      Environment: "production"
      Owner: "data-engineering"
      CostCenter: "1234"
      Compliance: "sox-required"
      Backup: "daily"
      Retention: "7-years"
```

### Security Configuration
```yaml
# Private bucket with strict security
storage:
  - name: "secure-bucket-{guid}"
    provider: "aws"
    location: "us-east"
    public: false          # No public access
    versioning: true       # Enable versioning for audit
    encryption: true       # Server-side encryption
    tags:
      Security: "confidential"
      Access: "restricted"

# Public assets bucket
storage:
  - name: "public-assets-{guid}"
    provider: "aws"
    location: "us-east"
    public: true           # Public read access
    versioning: false      # No versioning needed
    encryption: true       # Still encrypt at rest
    tags:
      Purpose: "static-assets"
      Public: "read-only"
```

## Deployment

### Generate and Review
```bash
# Analyze storage configuration
python yamlforge.py storage-config.yaml --analyze

# Generate Terraform
python yamlforge.py storage-config.yaml -d output/

# Review generated Terraform
cat output/main.tf
```

### Deploy
```bash
# Deploy infrastructure
cd output/
terraform init
terraform plan
terraform apply

# Or use auto-deploy
python yamlforge.py storage-config.yaml -d output/ --auto-deploy
```

### Cleanup
```bash
# Destroy infrastructure
cd output/
terraform destroy
```

## Best Practices

### Naming Conventions
- Use descriptive bucket names with purpose
- Include GUID placeholder for uniqueness
- Follow cloud provider naming restrictions

```yaml
# Good naming examples
storage:
  - name: "app-data-{guid}"           # Clear purpose
  - name: "user-uploads-{guid}"       # Descriptive
  - name: "logs-archive-{guid}"       # Purpose and type
```

### Security
- Default to private buckets (`public: false`)
- Enable encryption for sensitive data
- Use versioning for audit trails
- Apply appropriate tags for compliance

### Cost Optimization
- Use `cheapest` provider for development/testing
- Consider regional costs for data transfer
- Enable versioning selectively based on requirements
- Use appropriate storage classes (handled by provider)

### Multi-Cloud Strategy
- Distribute data based on access patterns
- Use regional storage for performance
- Implement backup strategies across providers
- Consider compliance and data sovereignty requirements

## Troubleshooting

### Common Issues

**Bucket name conflicts:**
```yaml
# Solution: Use unique names with GUID
storage:
  - name: "unique-bucket-{guid}"  # GUID ensures uniqueness
```

**Region specification errors:**
```yaml
# Error: Both region and location specified
storage:
  - name: "bucket-{guid}"
    location: "us-east"
    location: "us-east"     # Remove one

# Solution: Use either region OR location
storage:
  - name: "bucket-{guid}"
    location: "us-east"     # Direct region
```

**Provider-specific naming:**
- AWS S3: Globally unique names, lowercase, no underscores
- Azure: Storage account names must be lowercase, no hyphens
- GCP: Globally unique names, DNS-compliant

YamlForge automatically handles naming restrictions for each provider.

## Related Documentation

- [Examples: storage-example.yaml](../examples/storage-example.yaml)
- [Core Configuration](configuration/core-configuration.md)
- [Cost Optimization](features/cost-optimization.md)
- [YamlForge Schema](yamlforge-schema.json)
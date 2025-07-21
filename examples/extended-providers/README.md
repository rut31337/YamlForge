# Extended Provider Support: OCI, VMware vSphere, and Alibaba Cloud

This directory contains examples and documentation for YamlForge's extended cloud and hybrid infrastructure providers:

- **Oracle Cloud Infrastructure (OCI)**
- **VMware vSphere (On-premises/Hybrid)**  
- **Alibaba Cloud**

## 🚀 **Extended Provider Features**

### **🏢 Oracle Cloud Infrastructure (OCI)**
- **Compute Instances**: VM.Standard, VM.DenseIO, VM.GPU shapes
- **High-Performance Computing**: Bare metal and GPU instances
- **Networking**: Virtual Cloud Networks (VCNs), security lists
- **Storage**: Block volumes, object storage
- **DNS Integration**: Oracle Cloud DNS for certificate management

### **🏭 VMware vSphere (Hybrid Cloud)**
- **Virtual Machines**: Full vSphere integration with datacenters/clusters
- **Resource Pools**: Automatic resource allocation and management
- **Storage**: Datastore management and provisioning
- **Networking**: Distributed virtual switches and port groups
- **Hybrid Deployments**: Seamless cloud-to-on-premises integration

### **🌏 Alibaba Cloud**
- **Elastic Compute Service (ECS)**: Full range of instance families
- **Networking**: Virtual Private Cloud (VPC), security groups
- **Storage**: Block storage, object storage service (OSS)
- **Regions**: Global presence across China and international markets
- **DNS Integration**: Alibaba Cloud DNS for domain management

## 📋 **Configuration Examples**

### **Oracle Cloud Infrastructure**
```yaml
yamlforge:
  providers:
    - oci
  instances:
    - name: oci-compute
      provider: oci
      size: "small"               # Maps to VM.Standard.E4.Flex
      image: "RHEL9-latest"            # Auto-resolves to latest RHEL 9
      region: "us-ashburn-1"
```

### **VMware vSphere**
```yaml
yamlforge:
  providers:
    - vmware
  instances:
    - name: vsphere-vm
      provider: vmware
      size: "medium"               # 4 vCPU, 8GB RAM
      image: "RHEL9-latest"           # Uses rhel9-template
      datacenter: "datacenter1"
      cluster: "cluster1"
```

### **Alibaba Cloud**
```yaml
yamlforge:
  providers:
    - alibaba
  instances:
    - name: alibaba-ecs
      provider: alibaba
      size: "large"                # Maps to ecs.g6.2xlarge
      image: "RHEL9-latest"           # RHEL 9 on Alibaba Cloud
      region: "cn-hangzhou"
```

## 🌍 **Multi-Cloud Deployment**

The **"cheapest"** meta-provider includes all extended providers and supports **policy-based exclusions**:

```yaml
yamlforge:
  core:
    exclude_providers:
      - "vmware"  # Exclude on-premises for cloud-only deployment
  instances:
    - name: cost-optimized
      provider: "cheapest"  # Compares AWS, Azure, GCP, OCI, Alibaba
      size: "medium"
      image: "RHEL9-latest"
```

### **🚫 Provider Exclusions**

Control which providers participate in cost optimization:

```yaml
yamlforge:
  core:
    exclude_providers:
      - "oci"       # Exclude Oracle Cloud
      - "alibaba"   # Exclude Alibaba Cloud  
      - "vmware"    # Exclude VMware vSphere
  instances:
    - name: limited-cloud-options
      provider: "cheapest"  # Only considers AWS, Azure, GCP
```

## 🏗️ **Generated Terraform**

The extended providers generate clean, production-ready Terraform:

### **OCI Resources**
```hcl
# Oracle Cloud Infrastructure
resource "oci_core_instance" "oci_compute" {
  availability_domain = "uocm:US-ASHBURN-AD-1"
  compartment_id      = var.oci_compartment_id
  shape               = "VM.Standard.E4.Flex"
  
  source_details {
    source_type = "image"
    source_id   = data.oci_core_images.rhel9.images[0].id
  }
}
```

### **VMware vSphere Resources**
```hcl
# VMware vSphere
resource "vsphere_virtual_machine" "vsphere_vm" {
  name             = "vsphere-vm"
  resource_pool_id = data.vsphere_compute_cluster.cluster.resource_pool_id
  datastore_id     = data.vsphere_datastore.datastore.id
  num_cpus         = 4
  memory           = 8192
  
  clone {
    template_uuid = data.vsphere_virtual_machine.rhel9_template.id
  }
}
```

### **Alibaba Cloud Resources**
```hcl
# Alibaba Cloud ECS
resource "alicloud_instance" "alibaba_ecs" {
  instance_name   = "alibaba-ecs"
  image_id        = data.alicloud_images.rhel9.images[0].id
  instance_type   = "ecs.g6.2xlarge"
  security_groups = [alicloud_security_group.default.id]
}
```

## 📚 **Provider Documentation**

### **Setup Guides**
- **Oracle Cloud**: Configure OCI credentials and compartments
- **VMware vSphere**: Set up vCenter connection and templates  
- **Alibaba Cloud**: Configure AccessKey and region settings

### **Credential Configuration**
```bash
# Oracle Cloud
export OCI_USER_OCID="ocid1.user.oc1.."
export OCI_TENANCY_OCID="ocid1.tenancy.oc1.."
export OCI_FINGERPRINT="12:34:56:78:90:ab:cd:ef"

# VMware vSphere  
export VSPHERE_SERVER="vcenter.company.com"
export VSPHERE_USER="administrator@vsphere.local"
export VSPHERE_PASSWORD="password"

# Alibaba Cloud
export ALICLOUD_ACCESS_KEY="your_access_key"
export ALICLOUD_SECRET_KEY="your_secret_key"
```

### **Terraform Providers**
# All extended providers
terraform {
  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 5.0"
    }
    vsphere = {
      source  = "hashicorp/vsphere"
      version = "~> 2.0"
    }
    alicloud = {
      source  = "aliyun/alicloud"
      version = "~> 1.0"
    }
  }
}

## 🌟 **Complete Infrastructure Platform Support**

With these extended providers, yamlforge supports **8 different infrastructure platforms**:

1. **☁️ Amazon Web Services (AWS)** - Global cloud leader
2. **☁️ Microsoft Azure** - Enterprise cloud platform  
3. **☁️ Google Cloud Platform (GCP)** - AI/ML optimized cloud
4. **☁️ Oracle Cloud Infrastructure (OCI)** - High-performance cloud
5. **☁️ Alibaba Cloud** - Leading cloud in Asia-Pacific
6. **🏭 VMware vSphere** - On-premises virtualization
7. **☁️ IBM Cloud Classic** - Traditional infrastructure
8. **☁️ IBM Cloud VPC** - Modern cloud architecture

This provides unmatched flexibility for multi-cloud, hybrid, and on-premises deployments across the entire spectrum of infrastructure platforms. 
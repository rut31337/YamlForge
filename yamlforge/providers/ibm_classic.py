"""
IBM Classic Provider Module

Contains IBM Classic-specific implementations for VM generation and networking.
"""

import os


class IBMClassicProvider:
    """IBM Classic-specific provider implementation."""

    def __init__(self, converter):
        """Initialize the instance."""
        self.converter = converter
        self.config = self.load_config()

    def load_config(self):
        """Load IBM Classic configuration from environment variables."""
        # IBM Classic always has full account access (like AWS)
        # No resource group concept - uses tagging for organization
        return {
            'account_id': os.environ.get('IBMCLOUD_ACCOUNT_ID', ''),
            'default_datacenter': os.environ.get('IBMCLOUD_CLASSIC_DATACENTER', 'dal10'),
            'default_domain': os.environ.get('IBMCLOUD_CLASSIC_DOMAIN', 'example.com')
        }

    def generate_ibm_classic_vm(self, instance, index, clean_name, size, yaml_data=None):
        """Generate IBM Classic virtual guest."""
        instance_name = instance.get("name", f"instance_{index}")
        # Replace {guid} placeholder in instance name
        instance_name = self.converter.replace_guid_placeholders(instance_name)

        # Get datacenter
        datacenter = self.converter.resolve_instance_region(instance, "ibm_classic")
        
        # Get image and resolve using centralized mappings
        image = instance.get("image", "RHEL8-latest")
        ibm_image = self.get_ibm_classic_image(image)
        
        # Show resolved image in standardized format
        print(f"Dynamic image search for {instance_name} on ibm_classic for {image} in {datacenter} results in {ibm_image}")
        
        # Get instance specs from size
        cores, memory = self.get_ibm_classic_specs(size)
        
        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})

        # Generate SSH key resource if SSH key is provided
        ssh_key_resources = ""
        key_name_ref = "null"
        
        if ssh_key_config and ssh_key_config.get('public_key'):
            ssh_key_name = f"{clean_name}_ssh_key_{self.converter.get_validated_guid(yaml_data)}"
            ssh_key_resources = f'''
# IBM Cloud Classic SSH Key for {instance_name}
resource "ibm_compute_ssh_key" "{ssh_key_name}" {{
  label      = "{instance_name}-key"
  public_key = "{ssh_key_config['public_key']}"
}}

'''
            key_name_ref = f"ibm_compute_ssh_key.{ssh_key_name}.id"

        # Generate the Classic instance
        vm_config = ssh_key_resources + f'''
# IBM Cloud Classic Instance: {instance_name}
resource "ibm_compute_vm_instance" "{clean_name}_{self.converter.get_validated_guid(yaml_data)}" {{
  hostname                 = "{instance_name}"
  domain                   = "{self.config['default_domain']}"
  os_reference_code        = "{ibm_image}"
  datacenter               = "{datacenter}"
  network_speed            = 100
  hourly_billing           = true
  private_network_only     = false
  cores                    = {cores}
  memory                   = {memory}
  disks                    = [25]
  local_disk               = false
  ssh_key_ids              = [{key_name_ref}]
  
  tags = [
    "environment:agnosticd",
    "managed-by:yamlforge",
    "yamlforge-workspace:{yaml_data.get('yamlforge', {}).get('cloud_workspace', {}).get('name', 'default')}-{self.converter.get_validated_guid(yaml_data)}"
  ]
}}
'''
        return vm_config

    def get_ibm_classic_image(self, image):
        """Get IBM Classic OS reference code from centralized mappings."""
        # Use centralized image mappings (images are loaded directly, not under 'images' key)
        image_config = self.converter.images.get(image, {})
        
        ibm_classic_config = image_config.get('ibm_classic', {})
        print(f"[DEBUG] IBM Classic Debug - IBM Classic config: {ibm_classic_config}")
        
        if ibm_classic_config and 'os_reference_code' in ibm_classic_config:
            return ibm_classic_config['os_reference_code']
        
        # No fallbacks - all mappings should be in mappings/images.yaml
        raise ValueError(f"No IBM Classic image mapping found for '{image}'. "
                       f"Please add mapping to mappings/images.yaml under '{image}: ibm_classic: os_reference_code'")
    
    def get_ibm_classic_specs(self, size_or_instance_type):
        """Get cores and memory for IBM Classic from centralized flavor mappings.
        
        Args:
            size_or_instance_type: Either a generic size ('medium', 'large') or 
                                 specific IBM instance type ('B1.4x8x100')
        """
        ibm_flavors = self.converter.flavors.get('ibm_classic', {}).get('flavor_mappings', {})
        
        # First, try as a generic size (medium, large, etc.)
        if size_or_instance_type in ibm_flavors:
            size_mapping = ibm_flavors[size_or_instance_type]
            # Get the first (preferred) instance profile for this size
            first_profile = list(size_mapping.values())[0]
            cores = first_profile.get('vcpus', 2)
            memory_mb = first_profile.get('memory_gb', 4) * 1024  # Convert GB to MB
            return (cores, memory_mb)
        
        # Next, search for the specific instance type across all sizes
        for size_name, instance_types in ibm_flavors.items():
            if size_or_instance_type in instance_types:
                profile = instance_types[size_or_instance_type]
                cores = profile.get('vcpus', 2)
                memory_mb = profile.get('memory_gb', 4) * 1024  # Convert GB to MB
                print(f"IBM Classic size mapping: '{size_name}' -> '{size_or_instance_type}' ({cores} vCPU, {memory_mb//1024}GB)")
                return (cores, memory_mb)
        
        # No mapping found
        available_sizes = list(ibm_flavors.keys())
        raise ValueError(f"No IBM Classic mapping found for '{size_or_instance_type}'. "
                       f"Available sizes: {available_sizes}. "
                       f"Please add to mappings/flavors/ibm_classic.yaml")

    def generate_ibm_classic_networking(self, deployment_name, deployment_config, region, yaml_data=None):
        """Generate IBM Classic networking resources."""
        return f'''
# IBM Cloud Classic SSH Key (Global)
resource "ibm_compute_ssh_key" "main_key_{self.converter.get_validated_guid(yaml_data)}" {{
  label      = "{deployment_name}-key"
  public_key = var.ssh_public_key
  
  tags = [
    "environment:agnosticd",
    "managed-by:yamlforge"
  ]
}}
'''


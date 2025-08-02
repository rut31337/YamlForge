"""
VMware vSphere Provider Module

Contains VMware vSphere-specific implementations for VM generation,
networking, and resource management for on-premises virtualization.
"""

import yaml
from pathlib import Path


class VMwareProvider:
    """VMware vSphere-specific provider implementation."""

    def __init__(self, converter):
        """Initialize the instance."""
        self.converter = converter

    def get_vmware_vm_size(self, flavor_or_instance_type):
        """Get VMware VM size configuration from flavor or instance type."""
        # Handle VMware-specific suffixes
        base_size = flavor_or_instance_type.replace('-vm', '') if flavor_or_instance_type.endswith('-vm') else flavor_or_instance_type
        
        # Load VMware flavors
        vmware_flavors = self.converter.flavors.get('vmware', {}).get('flavor_mappings', {})
        size_mapping = vmware_flavors.get(base_size, {})
        
        if size_mapping:
            # Return the first (usually cheapest) option
            return next(iter(size_mapping.keys()))
        
        # Check machine types
        machine_types = self.converter.flavors.get('vmware', {}).get('machine_types', {})
        if flavor_or_instance_type in machine_types:
            return flavor_or_instance_type
        
        # Check if it's a direct configuration
        if isinstance(flavor_or_instance_type, dict):
            return flavor_or_instance_type
        
        # No mapping found
        available_sizes = list(vmware_flavors.keys())
        raise ValueError(f"No VMware VM size mapping found for flavor '{flavor_or_instance_type}'. "
                        f"Available flavors: {', '.join(available_sizes)}")

    def get_vmware_template(self, image_name):
        """Get VMware template reference from image mapping or direct reference."""
        
        # Check the centralized image mappings
        images = self.converter.images.get(image_name, {})
        vmware_image = images.get('vmware', {})
        
        if isinstance(vmware_image, dict):
            # Return the template from mapping
            return vmware_image.get('template', image_name)
        elif isinstance(vmware_image, str):
            # Direct template name mapping
            return vmware_image
        
        # Check VMware-specific template mappings
        vmware_templates = self.converter.flavors.get('vmware', {}).get('templates', {})
        if image_name in vmware_templates:
            return image_name
        
        # Default fallback
        return "rhel9-template"

    def generate_vmware_vm(self, instance, index, clean_name, flavor, available_subnets=None, yaml_data=None, has_guid_placeholder=False):
        """Generate VMware vSphere virtual machine."""
        instance_name = instance.get("name", f"instance_{index}")
        # Replace {guid} placeholder in instance name
        instance_name = self.converter.replace_guid_placeholders(instance_name)
        image = instance.get("image")
        if not image:
            raise ValueError(f"Instance '{instance_name}' requires an 'image' field")

        # Get VM size configuration
        vm_size = self.get_vmware_vm_size(flavor)
        
        # Extract CPU, memory, and disk from size configuration
        if isinstance(vm_size, dict):
            num_cpus = vm_size.get('cpus', 2)
            memory = vm_size.get('memory', 4096)
            disk_size = vm_size.get('disk', 40)
        else:
            # Fallback defaults
            num_cpus = 2
            memory = 4096
            disk_size = 40

        # Get template reference
        vmware_template = self.get_vmware_template(image)

        # Get user data script
        user_data_script = instance.get('user_data_script')

        # Get domain from instance config first, then fall back to VMware config (defaults to "local")
        instance_domain = instance.get('domain')
        vmware_config = yaml_data.get('yamlforge', {}).get('vmware', {}) if yaml_data else {}
        global_domain = vmware_config.get('domain', 'local') if vmware_config else 'local'
        
        domain = instance_domain or global_domain

        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})
        
        # Get GUID for consistent naming
        guid = self.converter.get_validated_guid(yaml_data)
        
        # Use clean_name directly if GUID is already present, otherwise add GUID
        resource_name = clean_name if has_guid_placeholder else f"{clean_name}_{guid}"

        # Generate customization script for cloud-init if SSH key is provided
        customization_script = ""
        if ssh_key_config and ssh_key_config.get('public_key'):
            ssh_username = ssh_key_config.get('username', 'vmware-user')
            customization_script = f'''
  # Cloud-init customization
  customize {{
    linux_options {{
      host_name = "{instance_name}"
      domain    = "{domain}"
    }}

    network_interface {{
      ipv4_address = "dhcp"
    }}
  }}

  # Custom attributes for SSH key
  custom_attributes = {{
    "ssh_authorized_keys" = "{ssh_key_config['public_key']}"
    "ssh_username" = "{ssh_username}"
  }}'''

        vm_config = f'''
# VMware vSphere Data Sources
data "vsphere_datacenter" "datacenter" {{
  name = var.vmware_datacenter
}}

data "vsphere_datastore" "datastore" {{
  name          = var.vmware_datastore
  datacenter_id = data.vsphere_datacenter.datacenter.id
}}

data "vsphere_compute_cluster" "cluster" {{
  name          = var.vmware_cluster
  datacenter_id = data.vsphere_datacenter.datacenter.id
}}

data "vsphere_network" "network" {{
  name          = var.vmware_network
  datacenter_id = data.vsphere_datacenter.datacenter.id
}}

data "vsphere_virtual_machine" "template" {{
  name          = "{vmware_template}"
  datacenter_id = data.vsphere_datacenter.datacenter.id
}}

# VMware vSphere Virtual Machine: {instance_name}
resource "vsphere_virtual_machine" "{resource_name}" {{
  name             = "{instance_name}"
  resource_pool_id = data.vsphere_compute_cluster.cluster.resource_pool_id
  datastore_id     = data.vsphere_datastore.datastore.id

  num_cpus = {num_cpus}
  memory   = {memory}
  guest_id = data.vsphere_virtual_machine.template.guest_id

  scsi_type = data.vsphere_virtual_machine.template.scsi_type

  network_interface {{
    network_id   = data.vsphere_network.network.id
    adapter_type = data.vsphere_virtual_machine.template.network_interface_types[0]
  }}

  disk {{
    label            = "disk0"
    size             = {disk_size}
    eagerly_scrub    = data.vsphere_virtual_machine.template.disks.0.eagerly_scrub
    thin_provisioned = data.vsphere_virtual_machine.template.disks.0.thin_provisioned
  }}

  clone {{
    template_uuid = data.vsphere_virtual_machine.template.id{customization_script}
  }}'''

        # Add user data via extra configuration if provided
        if user_data_script:
            vm_config += f'''

  extra_config = {{
    "guestinfo.userdata"          = base64encode(<<-EOF
{user_data_script}
EOF
    )
    "guestinfo.userdata.encoding" = "base64"
  }}'''

        vm_config += f'''

  # Tags for resource management
  tags = ["environment:agnosticd", "managed-by:yamlforge"]
}}
'''

        return vm_config

    def generate_vmware_networking(self, deployment_name, deployment_config, region, yaml_data=None):
        """Generate VMware vSphere networking resources for specific datacenter."""
        network_config = deployment_config.get('network', {})
        network_name = network_config.get('name', f"{deployment_name}-network")

        clean_datacenter = datacenter.replace("-", "_").replace(".", "_")

        return f'''
# VMware vSphere Networking: {network_name} (Datacenter: {datacenter})
# Note: VMware networking is typically pre-configured
# This is a placeholder for potential vSphere distributed switch configuration

# VMware Distributed Virtual Switch (if needed)
# resource "vsphere_distributed_virtual_switch" "main_dvs_{clean_datacenter}" {{
#   name          = "{network_name}-dvs-{datacenter}"
#   datacenter_id = data.vsphere_datacenter.datacenter.id
#   uplinks       = ["uplink1", "uplink2"]
#   active_uplinks = ["uplink1"]
#   standby_uplinks = ["uplink2"]
# }}

# VMware Distributed Port Group (if needed)
# resource "vsphere_distributed_port_group" "main_pg_{clean_datacenter}" {{
#   name                            = "{network_name}-pg-{datacenter}"
#   distributed_virtual_switch_uuid = vsphere_distributed_virtual_switch.main_dvs_{clean_datacenter}.id
#   vlan_id                         = 100
# }}

# Most VMware environments use pre-existing networks
# Configure network references in variables instead
'''





 
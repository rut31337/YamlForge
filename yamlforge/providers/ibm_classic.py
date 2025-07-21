"""
IBM Classic Provider Module

Contains IBM Classic-specific implementations for VM generation and networking.
"""


class IBMClassicProvider:
    """IBM Classic-specific provider implementation."""

    def __init__(self, converter):
        """Initialize the instance."""
        self.converter = converter

    def generate_ibm_classic_vm(self, instance, index, clean_name, size, yaml_data=None):
        """Generate IBM Classic virtual guest."""
        instance_name = instance.get("name", f"instance_{index}")

        # Get datacenter
        datacenter = self.converter.resolve_instance_region(instance, "ibm_classic")
        
        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})

        # Generate SSH key resource if configured
        ssh_key_resources = ""
        ssh_key_ids_config = ""
        
        if ssh_key_config and ssh_key_config.get('public_key'):
            ssh_key_name = f"{clean_name}_ssh_key"
            ssh_key_resources = f'''
# IBM Classic SSH Key for {instance_name}
resource "ibm_compute_ssh_key" "{ssh_key_name}" {{
  label      = "{instance_name}-ssh-key"
  public_key = "{ssh_key_config['public_key']}"
  
  tags = ["environment:agnosticd", "managed-by:yamlforge"]
}}

'''
            ssh_key_ids_config = f"ssh_key_ids = [ibm_compute_ssh_key.{ssh_key_name}.id]"

        vm_config = ssh_key_resources + f'''
# IBM Classic Virtual Guest: {instance_name}
resource "ibm_compute_vm_instance" "{clean_name}" {{
  hostname          = "{instance_name}"
  domain            = "example.com"
  os_reference_code = "RHEL_9_64"
  datacenter        = "{datacenter}"
  cores             = 2
  memory            = 4096
  network_speed     = 100
  hourly_billing    = true'''

        # Add SSH key IDs if configured
        if ssh_key_ids_config:
            vm_config += f'''
  {ssh_key_ids_config}'''

        vm_config += '''

  tags = ["environment:agnosticd", "managed-by:yamlforge"]
}}
'''
        return vm_config

    def generate_ibm_classic_networking(self, deployment_name, deployment_config):
        """Generate IBM Classic networking resources."""
        return f'''
# IBM Classic SSH Key
resource "ibm_compute_ssh_key" "main_key" {{
  label      = "main-ssh-key"
  public_key = var.ssh_public_key
}}
'''

    def format_ibm_tags(self, tags):
        """Format tags for IBM (key:value format)."""
        if not tags:
            return ""

        tag_items = []
        for key, value in tags.items():
            tag_items.append(f'"{key}:{value}"')

        return f'''
  tags = [{", ".join(tag_items)}]'''
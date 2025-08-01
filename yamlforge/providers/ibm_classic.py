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
            'auto_create_outbound_sg': True,  # Default to True for automatic outbound access
            'create_cloud_user': True  # Default to True for automatic cloud-user creation
        }

    def generate_ibm_classic_vm(self, instance, index, clean_name, flavor, yaml_data=None, has_guid_placeholder=False):
        """Generate IBM Classic virtual guest."""
        instance_name = instance.get("name", f"instance_{index}")
        # Replace {guid} placeholder in instance name
        instance_name = self.converter.replace_guid_placeholders(instance_name)

        # Get datacenter and convert to lowercase (IBM Classic requires lowercase)
        datacenter = self.converter.resolve_instance_region(instance, "ibm_classic").lower()
        
        # Get domain from instance config first, then fall back to IBM Classic config
        instance_domain = instance.get('domain')
        ibm_classic_config = yaml_data.get('yamlforge', {}).get('ibm_classic', {})
        global_domain = ibm_classic_config.get('domain')
        
        domain = instance_domain or global_domain
        if not domain:
            raise ValueError(f"Domain is required for IBM Classic instances. Please specify 'domain' in the ibm_classic configuration or override it per instance.")
        
        # Get image and resolve using centralized mappings
        image = instance.get("image", "RHEL8-latest")
        ibm_image = self.get_ibm_classic_image(image)
        
        # Show resolved image in standardized format
        self.converter.print_instance_output(instance_name, 'ibm_classic', f"Dynamic image search for {image} in {datacenter} results in {ibm_image}")
        
        # Get instance specs from size
        cores, memory = self.get_ibm_classic_specs(flavor)
        
        # Get user_data script if provided
        user_data_script = instance.get('user_data_script')
        
        # Check if cloud-user creation is enabled in IBM Classic config
        ibm_classic_config = yaml_data.get('yamlforge', {}).get('ibm_classic', {})
        create_cloud_user = ibm_classic_config.get('create_cloud_user', True)  # Default to True
        
        # Generate cloud-user creation script for RHEL images if enabled
        if create_cloud_user and "rhel" in image.lower():
            cloud_user_script = self.generate_rhel_user_data_script(instance, yaml_data)
            
            if user_data_script:
                # Combine user-provided script with cloud-user creation
                user_data_script = f"{user_data_script}\n\n{cloud_user_script}"
            else:
                # Use only cloud-user creation script
                user_data_script = cloud_user_script
        
        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})

        # Get the global SSH key reference (created in networking)
        guid = self.converter.get_validated_guid(yaml_data)
        resource_name = clean_name if has_guid_placeholder else f"{clean_name}_{guid}"
        global_ssh_key_ref = f"ibm_compute_ssh_key.main_key_{guid}.id"
        
        # Check if instance specifies a different SSH key than the global one
        instance_ssh_key = instance.get('ssh_key')
        global_ssh_key_config = self.converter.get_default_ssh_key(yaml_data or {})
        
        # Only create instance-specific key if:
        # 1. Instance specifies a different SSH key name, AND
        # 2. The SSH key content is actually different from global
        should_create_instance_key = (
            instance_ssh_key and 
            instance_ssh_key != 'default' and
            ssh_key_config and 
            ssh_key_config.get('public_key') and
            global_ssh_key_config and
            global_ssh_key_config.get('public_key') and
            ssh_key_config.get('public_key') != global_ssh_key_config.get('public_key')
        )
        
        ssh_key_resources = ""
        if should_create_instance_key:
            # Instance has a different SSH key - create it
            ssh_key_name = clean_name if has_guid_placeholder else f"{clean_name}_ssh_key_{guid}"
            ssh_key_resources = f'''
# IBM Cloud Classic SSH Key for {instance_name}
resource "ibm_compute_ssh_key" "{ssh_key_name}" {{
  label      = "{instance_name}-key"
  public_key = "{ssh_key_config['public_key']}"
}}

'''
            key_name_ref = f"ibm_compute_ssh_key.{ssh_key_name}.id"
        else:
            # Use the global SSH key
            key_name_ref = global_ssh_key_ref

        # Get security group references
        ibm_sg_refs = []
        sg_names = instance.get('security_groups', [])
        for sg_name in sg_names:
            sg_name = self.converter.replace_guid_placeholders(sg_name)
            clean_sg = sg_name.replace("-", "_").replace(".", "_")
            clean_region = datacenter.replace("-", "_").replace(".", "_")
            sg_resource_name = f"{clean_sg}_{clean_region}_{guid}"
            ibm_sg_refs.append(f"ibm_security_group.{sg_resource_name}.id")
        ibm_sg_refs_str = "[" + ", ".join(ibm_sg_refs) + "]" if ibm_sg_refs else "[]"

        # Generate the Classic instance
        newline = chr(10)
        user_metadata_block = ("user_metadata = <<-EOF" + newline + user_data_script + newline + "EOF") if user_data_script else ""
        
        vm_config = ssh_key_resources + '''
# IBM Cloud Classic Instance: {instance_name}
resource "ibm_compute_vm_instance" "{resource_name}" {{
  hostname                 = "{instance_name}"
  domain                   = "{domain}"
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
  
  {user_metadata_block}
  
  tags = [
    "environment:agnosticd",
    "managed-by:yamlforge"
  ]
}}
'''.format(
            instance_name=instance_name,
            resource_name=resource_name,
            domain=domain,
            ibm_image=ibm_image,
            datacenter=datacenter,
            cores=cores,
            memory=memory,
            key_name_ref=key_name_ref,
            user_metadata_block=user_metadata_block
        )
        return vm_config

    def get_ibm_classic_image(self, image):
        """Get IBM Classic OS reference code from centralized mappings."""
        # Check for no-credentials mode first
        if getattr(self.converter, 'no_credentials', False):
            self.converter.print_provider_output('ibm_classic', f"NO-CREDENTIALS MODE: Skipping image lookup for {image}, using placeholder OS reference code.")
            return "PLACEHOLDER-IBM-CLASSIC-OS-REFERENCE-CODE"
        
        # Use centralized image mappings (images are loaded directly, not under 'images' key)
        image_config = self.converter.images.get(image, {})
        
        ibm_classic_config = image_config.get('ibm_classic', {})
        
        if ibm_classic_config and 'os_reference_code' in ibm_classic_config:
            return ibm_classic_config['os_reference_code']
        
        # No fallbacks - all mappings should be in mappings/images.yaml
        raise ValueError(f"No IBM Classic image mapping found for '{image}'. "
                       f"Please add mapping to mappings/images.yaml under '{image}: ibm_classic: os_reference_code'")
    
    def get_ibm_classic_specs(self, flavor_or_instance_type):
        """Get IBM Classic instance specifications from flavor or instance type.
        
        Args:
            flavor_or_instance_type: Either a generic flavor ('medium', 'large') or
                                    a specific IBM Classic instance type.
        
        Returns:
            tuple: (cores, memory_mb) where memory_mb is in MB
        """
        # Load IBM Classic flavors
        ibm_flavors = self.converter.flavors.get('ibm_classic', {}).get('flavor_mappings', {})
        
        # Check if it's a generic flavor
        if flavor_or_instance_type in ibm_flavors:
            size_mapping = ibm_flavors[flavor_or_instance_type]
            # Get the first (usually cheapest) option
            instance_type = next(iter(size_mapping.keys()))
            profile = size_mapping[instance_type]
            cores = profile.get('vcpus', 1)
            memory_mb = profile.get('memory_gb', 1) * 1024
            return cores, memory_mb
        
        # Check if it's a specific instance type
        for size_name, instance_types in ibm_flavors.items():
            if flavor_or_instance_type in instance_types:
                profile = instance_types[flavor_or_instance_type]
                cores = profile.get('vcpus', 1)
                memory_mb = profile.get('memory_gb', 1) * 1024
                self.converter.print_provider_output('ibm_classic', f"Flavor mapping: '{size_name}' -> '{flavor_or_instance_type}' ({cores} vCPU, {memory_mb//1024}GB)")
                return cores, memory_mb
        
        # No mapping found
        available_sizes = list(ibm_flavors.keys())
        raise ValueError(f"No IBM Classic mapping found for '{flavor_or_instance_type}'. "
                        f"Available flavors: {', '.join(available_sizes)}")

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

    def generate_ibm_classic_security_group(self, sg_name, rules, region, yaml_data=None):
        """Generate IBM Classic security group rules.
        
        Note: IBM Classic uses ibm_security_group and ibm_security_group_rule resources
        for managing security groups and their rules.
        """
        # Replace {guid} placeholder in security group name
        sg_name = self.converter.replace_guid_placeholders(sg_name)
        clean_name = sg_name.replace("-", "_").replace(".", "_")
        clean_region = region.replace("-", "_").replace(".", "_")
        regional_sg_name = f"{clean_name}_{clean_region}"
        
        # Get the validated GUID for resource naming
        guid = self.converter.get_validated_guid(yaml_data)
        resource_name = f"{regional_sg_name}_{guid}"

        security_group_config = f'''
# IBM Cloud Classic Security Group: {sg_name} (Region: {region})
resource "ibm_security_group" "{resource_name}" {{
  name = "{sg_name}-{region}"
}}

'''

        # Generate security group rules
        for i, rule in enumerate(rules):
            rule_data = self.converter.generate_native_security_group_rule(rule, 'ibm_classic')
            direction = rule_data['direction']  # 'ingress' or 'egress'
            protocol = rule_data['protocol']
            
            # Map direction to IBM Classic format
            ibm_direction = "ingress" if direction == "ingress" else "egress"

            # Handle different protocols for IBM Classic
            if protocol == 'all':
                # For "all" protocol, create separate rules for TCP, UDP, and ICMP
                protocols = ['tcp', 'udp', 'icmp']
                for proto in protocols:
                    if proto == 'icmp':
                        # ICMP doesn't use port ranges
                        rule_config = f'''
# IBM Classic Security Group Rule: {sg_name} Rule {i+1} ({proto.upper()}) (Region: {region})
resource "ibm_security_group_rule" "{resource_name}_rule_{i+1}_{proto}" {{
  security_group_id = ibm_security_group.{resource_name}.id
  direction         = "{ibm_direction}"
  remote_ip         = "{rule_data['source_cidr_blocks'][0] if rule_data['source_cidr_blocks'] else '0.0.0.0/0'}"
  protocol          = "{proto}"
}}
'''
                    else:
                        # TCP and UDP rules - IBM Classic may not support port ranges
                        rule_config = f'''
# IBM Classic Security Group Rule: {sg_name} Rule {i+1} ({proto.upper()}) (Region: {region})
resource "ibm_security_group_rule" "{resource_name}_rule_{i+1}_{proto}" {{
  security_group_id = ibm_security_group.{resource_name}.id
  direction         = "{ibm_direction}"
  remote_ip         = "{rule_data['source_cidr_blocks'][0] if rule_data['source_cidr_blocks'] else '0.0.0.0/0'}"
  protocol          = "{proto}"
}}
'''
                    security_group_config += rule_config
            else:
                # Single protocol rule
                if protocol == 'icmp':
                    # ICMP doesn't use port ranges
                    rule_config = f'''
# IBM Classic Security Group Rule: {sg_name} Rule {i+1} (Region: {region})
resource "ibm_security_group_rule" "{resource_name}_rule_{i+1}" {{
  security_group_id = ibm_security_group.{resource_name}.id
  direction         = "{ibm_direction}"
  remote_ip         = "{rule_data['source_cidr_blocks'][0] if rule_data['source_cidr_blocks'] else '0.0.0.0/0'}"
  protocol          = "{protocol}"
}}
'''
                else:
                    # TCP and UDP rules - IBM Classic may not support port ranges
                    rule_config = f'''
# IBM Classic Security Group Rule: {sg_name} Rule {i+1} (Region: {region})
resource "ibm_security_group_rule" "{resource_name}_rule_{i+1}" {{
  security_group_id = ibm_security_group.{resource_name}.id
  direction         = "{ibm_direction}"
  remote_ip         = "{rule_data['source_cidr_blocks'][0] if rule_data['source_cidr_blocks'] else '0.0.0.0/0'}"
  protocol          = "{protocol}"
}}
'''
                    security_group_config += rule_config

        return security_group_config

    def generate_rhel_user_data_script(self, instance, yaml_data=None):
        """Generate user_data script for RHEL instances to create cloud-user account."""
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})
        public_key = ssh_key_config.get('public_key', '') if ssh_key_config else ''
        
        # Get the SSH username that should be created
        ssh_username = self.converter.get_instance_ssh_username(instance, yaml_data or {})
        
        user_data_script = '''#!/bin/bash
# User data script for RHEL instance
# This script creates the {ssh_username} user and configures SSH access

set -e

# Create {ssh_username} user if it doesn't exist
if ! id "{ssh_username}" &>/dev/null; then
    useradd -m -s /bin/bash {ssh_username}
    echo "Created {ssh_username} user"
fi

# Create .ssh directory and set permissions
mkdir -p /home/{ssh_username}/.ssh
chmod 700 /home/{ssh_username}/.ssh

# Add SSH public key to authorized_keys
if [ -n "{public_key}" ]; then
    echo "{public_key}" >> /home/{ssh_username}/.ssh/authorized_keys
    chmod 600 /home/{ssh_username}/.ssh/authorized_keys
    echo "Added SSH key for {ssh_username}"
fi

# Set ownership
chown -R {ssh_username}:{ssh_username} /home/{ssh_username}/.ssh

# Configure sudo access for {ssh_username}
echo "{ssh_username} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/{ssh_username}
chmod 440 /etc/sudoers.d/{ssh_username}

# Disable root SSH access for security
sed -i 's/#PermitRootLogin yes/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config

# Restart SSH service
systemctl restart sshd

echo "User data script completed successfully"
'''.format(ssh_username=ssh_username, public_key=public_key)
        
        return user_data_script

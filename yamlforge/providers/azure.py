"""
Azure Provider Module

Contains Azure-specific implementations for VM generation, networking,
security groups, and other Azure cloud resources.
"""

import base64
import os


class AzureProvider:
    """Azure-specific provider implementation."""

    def __init__(self, converter):
        """Initialize the instance."""
        self.converter = converter
        self.config = self.load_config()

    def load_config(self):
        """Load Azure configuration from credentials and environment variables."""
        # Check if credentials are available
        has_credentials = self.converter.credentials and hasattr(self.converter.credentials, 'azure_config')

        # Get Azure resource management configuration
        use_existing_resource_group = False
        existing_resource_group_name = ""
        existing_resource_group_location = ""
        
        if has_credentials:
            azure_creds = self.converter.credentials.get_azure_credentials()
            if azure_creds:
                use_existing_resource_group = azure_creds.get('use_existing_resource_group', False)
                existing_resource_group_name = azure_creds.get('existing_resource_group_name', '')
                existing_resource_group_location = azure_creds.get('existing_resource_group_location', '')

        # Fall back to environment variables if not in credentials
        if not use_existing_resource_group:
            use_existing_rg_str = os.environ.get('AZURE_USE_EXISTING_RESOURCE_GROUP', '').lower()
            use_existing_resource_group = use_existing_rg_str in ['true', '1', 'yes']
        
        if not existing_resource_group_name:
            existing_resource_group_name = os.environ.get('AZURE_EXISTING_RESOURCE_GROUP_NAME', '')
        
        if not existing_resource_group_location:
            existing_resource_group_location = os.environ.get('AZURE_EXISTING_RESOURCE_GROUP_LOCATION', '')

        return {
            'use_existing_resource_group': use_existing_resource_group,
            'existing_resource_group_name': existing_resource_group_name,
            'existing_resource_group_location': existing_resource_group_location,
            'has_credentials': has_credentials
        }

    def get_azure_vm_size(self, flavor_or_instance_type):
        """Get Azure VM size from flavor or instance type."""
        # If it's already an Azure VM size, return it directly
        if any(prefix in flavor_or_instance_type for prefix in ['Standard_', 'Basic_']):
            return flavor_or_instance_type
        
        # Load Azure flavors
        azure_flavors = self.converter.flavors.get('azure', {}).get('flavor_mappings', {})
        size_mapping = azure_flavors.get(flavor_or_instance_type, {})
        
        if size_mapping:
            # Return the first (usually cheapest) option
            return next(iter(size_mapping.keys()))
        
        # Check machine types
        machine_types = self.converter.flavors.get('azure', {}).get('machine_types', {})
        if flavor_or_instance_type in machine_types:
            return flavor_or_instance_type
        
        raise ValueError(f"No Azure VM size mapping found for flavor '{flavor_or_instance_type}'. "
                        f"Available flavors: {list(azure_flavors.keys())}")

    def get_azure_image_reference(self, image_name):
        """Get Azure image reference for a given image name."""
        # Default to RHEL 9 if not found in mappings
        default_image = {
            "publisher": "RedHat",
            "offer": "RHEL",
            "sku": "9-lvm-gen2",
            "version": "latest"
        }

        # Try to get from image mappings
        if image_name in self.converter.images:
            azure_config = self.converter.images[image_name].get('azure', {})
            if azure_config:
                return azure_config

        # Check for RHEL patterns
        if "RHEL" in image_name.upper():
            if "8" in image_name:
                return {
                    "publisher": "RedHat",
                    "offer": "RHEL",
                    "sku": "8-lvm-gen2",
                    "version": "latest"
                }
            elif "9" in image_name:
                return {
                    "publisher": "RedHat",
                    "offer": "RHEL",
                    "sku": "9-lvm-gen2",
                    "version": "latest"
                }

        # Check for other OS patterns
        if "UBUNTU" in image_name.upper():
            return {
                "publisher": "Canonical",
                "offer": "0001-com-ubuntu-server-focal",
                "sku": "20_04-lts-gen2",
                "version": "latest"
            }

        return default_image

    def generate_azure_security_group(self, sg_name, rules, region, yaml_data=None):  # noqa: vulture
        """Generate Azure network security group with rules for specific region."""
        # Replace {guid} placeholder in security group name
        sg_name = self.converter.replace_guid_placeholders(sg_name)
        clean_name = sg_name.replace("-", "_").replace(".", "_")
        clean_region = region.lower().replace(" ", "_").replace("-", "_").replace(".", "_")
        regional_sg_name = f"{clean_name}_{clean_region}"


        security_group_config = f'''
# Azure Network Security Group: {sg_name} (Region: {region})
resource "azurerm_network_security_group" "{regional_sg_name}_{self.converter.get_validated_guid(yaml_data)}" {{
  name                = "{sg_name}-{clean_region}"
  location            = local.resource_group_location_{clean_region}_{self.converter.get_validated_guid(yaml_data)}
  resource_group_name = local.resource_group_name_{clean_region}_{self.converter.get_validated_guid(yaml_data)}

'''

        # Generate security rules
        rule_priority = 100
        for i, rule in enumerate(rules):
            rule_data = self.converter.generate_native_security_group_rule(rule, 'azure')
            direction = rule_data['direction']  # Already converted by converter
            
            # Determine port range string
            from_port = rule_data['from_port']
            to_port = rule_data['to_port']
            if from_port != to_port:
                port_range = f"{from_port}-{to_port}"
            else:
                port_range = str(from_port)
            
            # Determine source address
            if rule_data['is_source_cidr']:
                source_address = rule_data['source_cidr_blocks'][0] if rule_data['source_cidr_blocks'] else '*'
            else:
                # For now, Azure only supports CIDR blocks in the generic approach
                # Provider-specific sources would need custom handling
                source_address = '*'

            # Determine destination address
            if rule_data['destination'] and rule_data['is_destination_cidr']:
                destination_address = rule_data['destination_cidr_blocks'][0] if rule_data['destination_cidr_blocks'] else '*'
            else:
                # Default destination for Azure
                destination_address = '*'

            rule_block = f'''  security_rule {{
    name                       = "{sg_name}-rule-{i+1}"
    priority                   = {rule_priority + i * 10}
    direction                  = "{direction}"
    access                     = "Allow"
    protocol                   = "{rule_data['protocol'].capitalize()}"
    source_port_range          = "*"
    destination_port_range     = "{port_range}"
    source_address_prefix      = "{source_address}"
    destination_address_prefix = "{destination_address}"
  }}

'''
            security_group_config += rule_block

        security_group_config += f'''  tags = {{
    Environment = "agnosticd"
    Region = "{region}"
  }}
}}

'''
        return security_group_config

    def generate_azure_vm(self, instance, index, clean_name, flavor, available_subnets=None, yaml_data=None, has_guid_placeholder=False):  # noqa: vulture
        """Generate native Azure virtual machine."""
        instance_name = instance.get("name", f"instance_{index}")
        # Replace {guid} placeholder in instance name
        instance_name = self.converter.replace_guid_placeholders(instance_name)
        image = instance.get("image")
        if not image:
            raise ValueError(f"Instance '{instance_name}' requires an 'image' field")

        # Resolve region using region/location logic
        azure_region = self.converter.resolve_instance_region(instance, "azure")
        
        # Check if user specified a zone (only valid with region-based configuration)
        user_specified_zone = instance.get('zone')
        has_region = 'region' in instance
        
        if user_specified_zone and has_region:
            # Azure zones are just numbers (1, 2, 3), validate the zone is valid
            if not user_specified_zone.isdigit() or int(user_specified_zone) not in [1, 2, 3]:
                raise ValueError(f"Instance '{instance_name}': Azure zones must be '1', '2', or '3'. Got: '{user_specified_zone}'")
            
            print(f"Using user-specified zone '{user_specified_zone}' for instance '{instance_name}' in region '{azure_region}'")
            azure_zone = user_specified_zone
            
        elif user_specified_zone and not has_region:
            raise ValueError(f"Instance '{instance_name}': Zone '{user_specified_zone}' can only be specified when using 'region' (not 'location'). "
                           f"Either remove 'zone' or change 'location' to 'region'.")
        else:
            # Let Terraform automatically select the best available zone
            azure_zone = None
        
        azure_vm_size = self.get_azure_vm_size(flavor)

        # Get Azure NSG references with regional awareness
        azure_nsg_refs = []
        sg_names = instance.get('security_groups', [])
        clean_region = azure_region.lower().replace(" ", "_").replace("-", "_").replace(".", "_")
        for sg_name in sg_names:
            # Replace {guid} placeholder in security group name first
            resolved_sg_name = self.converter.replace_guid_placeholders(sg_name)
            clean_sg = resolved_sg_name.replace("-", "_").replace(".", "_")
            azure_nsg_refs.append(f"azurerm_network_security_group.{clean_sg}_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.id")

        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})
        
        # Get the SSH username for this instance
        ssh_username = self.converter.get_instance_ssh_username(instance, 'azure', yaml_data or {})
        
        # Get GUID for consistent naming
        guid = self.converter.get_validated_guid(yaml_data)
        
        # Use clean_name directly if GUID is already present, otherwise add GUID
        resource_name = clean_name if has_guid_placeholder else f"{clean_name}_{guid}"
        
        # Generate Azure SSH public key resource if SSH key is provided
        ssh_key_resources = ""
        ssh_key_reference = "null"
        
        if ssh_key_config and ssh_key_config.get('public_key'):
            # Use clean_name directly if GUID is already present, otherwise add GUID
            ssh_key_name = clean_name if has_guid_placeholder else f"{clean_name}_ssh_key_{guid}"
            ssh_key_resources = f'''
# Azure SSH Public Key: {instance_name}
resource "azurerm_ssh_public_key" "{ssh_key_name}" {{
  name                = "{instance_name}-ssh-key"
  resource_group_name = local.resource_group_name_{clean_region}_{guid}
  location            = local.resource_group_location_{clean_region}_{guid}
  public_key          = "{ssh_key_config['public_key']}"

  tags = {{
    Environment = "agnosticd"
    ManagedBy = "yamlforge"
  }}
}}

'''
            ssh_key_reference = f"azurerm_ssh_public_key.{ssh_key_name}.public_key"
        
        # Get Azure image configuration
        azure_image = self.get_azure_image_reference(image)

        vm_config = ssh_key_resources + f'''
# Azure Public IP: {instance_name}
resource "azurerm_public_ip" "{resource_name}_ip" {{
  name                = "{instance_name}-ip"
  location            = local.resource_group_location_{clean_region}_{guid}
  resource_group_name = local.resource_group_name_{clean_region}_{guid}
  allocation_method   = "Static"

  tags = {{
    Environment = "agnosticd"
    ManagedBy = "yamlforge"
  }}
}}

# Azure Network Interface: {instance_name}
resource "azurerm_network_interface" "{resource_name}_nic" {{
  name                = "{instance_name}-nic"
  location            = local.resource_group_location_{clean_region}_{guid}
  resource_group_name = local.resource_group_name_{clean_region}_{guid}

  ip_configuration {{
    name                          = "internal"
    subnet_id                     = azurerm_subnet.main_subnet_{clean_region}_{guid}.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.{resource_name}_ip.id
  }}

  tags = {{
    Environment = "agnosticd"
    ManagedBy = "yamlforge"
  }}
}}'''

        # Add security group association if security groups exist
        if azure_nsg_refs:
            vm_config += f'''

# Azure NSG Association: {instance_name}
resource "azurerm_network_interface_security_group_association" "{resource_name}_nsg_assoc" {{
  network_interface_id      = azurerm_network_interface.{resource_name}_nic.id
  network_security_group_id = {azure_nsg_refs[0]}
}}'''

        vm_config += f'''

# Azure Linux Virtual Machine: {instance_name}
resource "azurerm_linux_virtual_machine" "{resource_name}" {{
  name                = "{instance_name}"
  resource_group_name = local.resource_group_name_{clean_region}_{guid}
  location            = local.resource_group_location_{clean_region}_{guid}
  size                = "{azure_vm_size}"
  admin_username      = "{ssh_username}"
  disable_password_authentication = {str(bool(ssh_key_config and ssh_key_config.get('public_key'))).lower()}'''

        # Add zone if user specified one
        if azure_zone:
            vm_config += f'''
  zone                = "{azure_zone}"'''

        vm_config += f'''

  network_interface_ids = [
    azurerm_network_interface.{resource_name}_nic.id,
  ]'''

        # Add SSH key block only if SSH key is available
        if ssh_key_config and ssh_key_config.get('public_key'):
            vm_config += f'''

  admin_ssh_key {{
    username   = "{ssh_username}"
    public_key = {ssh_key_reference}
  }}'''

        vm_config += f'''

  os_disk {{
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }}

  source_image_reference {{
    publisher = "{azure_image['publisher']}"
    offer     = "{azure_image['offer']}"
    sku       = "{azure_image['sku']}"
    version   = "{azure_image['version']}"
  }}'''

        # Get user data script if provided
        user_data_script = instance.get('user_data_script', '')
        
        # Get the SSH username for this instance
        ssh_username = self.converter.get_instance_ssh_username(instance, 'azure', yaml_data or {})
        
        # Get the default username from core configuration
        default_username = self.converter.core_config.get('security', {}).get('default_username', 'cloud-user')
        
        # Generate cloud-user creation script if needed (Azure doesn't have native cloud-user)
        custom_username_script = ""
        if ssh_username == default_username:
            # Create user data script to set up the configurable default account
            public_key = ssh_key_config.get('public_key', '') if ssh_key_config else ''
            custom_username_script = '''#!/bin/bash
# User data script for Azure instance
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
        elif ssh_username != 'azureuser':
            # Create user data script to set up other custom usernames
            public_key = ssh_key_config.get('public_key', '') if ssh_key_config else ''
            custom_username_script = '''#!/bin/bash
# User data script for Azure instance
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
        
        # Combine custom username script with user-provided script
        if custom_username_script:
            if user_data_script:
                # Prepend custom username script to user-provided script
                user_data_script = custom_username_script + "\n\n" + user_data_script
            else:
                user_data_script = custom_username_script
        
        # Add cloud-init if provided
        if user_data_script:
            # Base64 encode for Azure
            encoded_script = base64.b64encode(user_data_script.encode()).decode()
            vm_config += f'''

  custom_data = "{encoded_script}"'''

        vm_config += f'''

  tags = {{
    Environment = "agnosticd"
    ManagedBy   = "yamlforge"
  }}
}}
'''
        return vm_config

    def generate_azure_networking(self, deployment_name, deployment_config, region, yaml_data=None):  # noqa: vulture
        """Generate Azure networking resources for specific region."""
        network_config = deployment_config.get('network', {})
        network_name = network_config.get('name', f"{deployment_name}-vnet")
        cidr_block = network_config.get('cidr_block', '10.0.0.0/16')

        clean_region = region.lower().replace(" ", "_").replace("-", "_").replace(".", "_")

        # Get Azure configuration from YAML (override environment/defaults)
        yaml_azure_config = yaml_data.get('yamlforge', {}).get('azure', {}) if yaml_data else {}
        
        # Get configuration with YAML overrides
        use_existing_resource_group = yaml_azure_config.get('use_existing_resource_group', self.config['use_existing_resource_group'])
        existing_resource_group_name = yaml_azure_config.get('existing_resource_group_name', self.config['existing_resource_group_name'])
        existing_resource_group_location = yaml_azure_config.get('existing_resource_group_location', self.config['existing_resource_group_location'])

        guid = self.converter.get_validated_guid(yaml_data)
        
        if use_existing_resource_group and existing_resource_group_name:
            # Use existing resource group
            networking_config = f'''
# Using existing Azure Resource Group: {existing_resource_group_name}
data "azurerm_resource_group" "main_{clean_region}_{guid}" {{
  name = "{existing_resource_group_name}"
}}

# Local value to reference resource group
locals {{
  resource_group_name_{clean_region}_{guid} = data.azurerm_resource_group.main_{clean_region}_{guid}.name
  resource_group_location_{clean_region}_{guid} = data.azurerm_resource_group.main_{clean_region}_{guid}.location
}}

'''
        else:
            # Create new resource group (default behavior)
            # Sanitize region name for resource group name (no spaces)
            sanitized_region = region.replace(" ", "-").replace("_", "-")
            networking_config = f'''
# Azure Resource Group: {network_name} (Region: {region})
resource "azurerm_resource_group" "main_{clean_region}_{guid}" {{
  name     = "{network_name}-{sanitized_region}"
  location = "{region}"

  tags = {{
    Environment = "agnosticd"
    ManagedBy = "yamlforge"
  }}
}}

# Local value to reference resource group
locals {{
  resource_group_name_{clean_region}_{guid} = azurerm_resource_group.main_{clean_region}_{guid}.name
  resource_group_location_{clean_region}_{guid} = azurerm_resource_group.main_{clean_region}_{guid}.location
}}

'''

        networking_config += f'''
# Azure Virtual Network: {network_name}
resource "azurerm_virtual_network" "main_vnet_{clean_region}_{guid}" {{
  name                = "{network_name}-vnet"
  address_space       = ["{cidr_block}"]
  location            = local.resource_group_location_{clean_region}_{guid}
  resource_group_name = local.resource_group_name_{clean_region}_{guid}

  tags = {{
    Environment = "agnosticd"
    ManagedBy = "yamlforge"
  }}
}}

# Azure Subnet: {network_name} subnet
resource "azurerm_subnet" "main_subnet_{clean_region}_{guid}" {{
  name                 = "{network_name}-subnet"
  resource_group_name  = local.resource_group_name_{clean_region}_{guid}
  virtual_network_name = azurerm_virtual_network.main_vnet_{clean_region}_{guid}.name
  address_prefixes     = ["{cidr_block}"]
}}
'''
        
        return networking_config

    def generate_storage_account(self, bucket, yaml_data):
        """Generate Azure Storage Account configuration."""
        bucket_name = bucket.get('name', 'my-bucket')
        region = self.converter.resolve_bucket_region(bucket, 'azure')
        guid = self.converter.get_validated_guid(yaml_data)

        # Replace GUID placeholders and clean for Azure naming requirements
        final_bucket_name = self.converter.replace_guid_placeholders(bucket_name)
        # Azure storage account names must be lowercase, no hyphens, 3-24 chars
        clean_bucket_name = final_bucket_name.lower().replace('-', '').replace('_', '')[:24]
        clean_tf_name, _ = self.converter.clean_name(final_bucket_name)
        
        # Bucket configuration
        public = bucket.get('public', False)
        versioning = bucket.get('versioning', False)
        encryption = bucket.get('encryption', True)
        tags = bucket.get('tags', {})

        terraform_config = f'''
# Azure Storage Account: {final_bucket_name}
resource "azurerm_resource_group" "storage_{clean_tf_name}_{guid}" {{
  name     = "rg-{final_bucket_name}"
  location = "{region}"

  tags = {{
    Name = "{final_bucket_name}"
    ManagedBy = "YamlForge"
    GUID = "{guid}"'''

        # Add custom tags
        for key, value in tags.items():
            terraform_config += f'''
    {key} = "{value}"'''

        terraform_config += f'''
  }}
}}

resource "azurerm_storage_account" "{clean_tf_name}_{guid}" {{
  name                     = "{clean_bucket_name}"
  resource_group_name      = azurerm_resource_group.storage_{clean_tf_name}_{guid}.name
  location                 = azurerm_resource_group.storage_{clean_tf_name}_{guid}.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  
  # Public access configuration
  public_network_access_enabled = {str(public).lower()}
  
  # Encryption configuration
  infrastructure_encryption_enabled = {str(encryption).lower()}
  
  tags = {{
    Name = "{final_bucket_name}"
    ManagedBy = "YamlForge"
    GUID = "{guid}"'''

        # Add custom tags
        for key, value in tags.items():
            terraform_config += f'''
    {key} = "{value}"'''

        terraform_config += '''
  }
}

'''

        # Create container (equivalent to S3 bucket)
        terraform_config += f'''
resource "azurerm_storage_container" "{clean_tf_name}_container_{guid}" {{
  name                  = "data"
  storage_account_name  = azurerm_storage_account.{clean_tf_name}_{guid}.name
  container_access_type = "{"blob" if public else "private"}"
}}

'''

        # Versioning configuration (blob versioning)
        if versioning:
            terraform_config += f'''
resource "azurerm_storage_management_policy" "{clean_tf_name}_versioning_{guid}" {{
  storage_account_id = azurerm_storage_account.{clean_tf_name}_{guid}.id

  rule {{
    name    = "versioning-rule"
    enabled = true
    filters {{
      blob_types = ["blockBlob"]
    }}
    actions {{
      version {{
        delete_after_days_since_creation = 365
      }}
    }}
  }}
}}

'''

        return terraform_config

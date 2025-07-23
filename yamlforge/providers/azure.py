"""
Azure Provider Module

Contains Azure-specific implementations for VM generation, networking,
security groups, and other Azure cloud resources.
"""

import base64


class AzureProvider:
    """Azure-specific provider implementation."""

    def __init__(self, converter):
        """Initialize the instance."""
        self.converter = converter

    def get_azure_vm_size(self, size_or_instance_type):
        """Get Azure VM size from size mapping or return direct instance type."""
        # If it looks like a direct Azure VM size, return it as-is
        if any(prefix in size_or_instance_type for prefix in ['Standard_', 'Basic_']):
            return size_or_instance_type
        
        # Check for advanced flavor mappings
        azure_flavors = self.converter.flavors.get('azure', {}).get('flavor_mappings', {})
        size_mapping = azure_flavors.get(size_or_instance_type, {})

        if size_mapping:
            # Return the first (preferred) VM size for this size
            return list(size_mapping.keys())[0]

        # No mapping found for this size
        raise ValueError(f"No Azure VM size mapping found for size '{size_or_instance_type}'. "
                       f"Available sizes: {list(azure_flavors.keys())}")

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

    def generate_azure_security_group(self, sg_name, rules, region, yaml_data=None):
        """Generate Azure network security group with rules for specific region."""
        clean_name = sg_name.replace("-", "_").replace(".", "_")
        clean_region = region.replace("-", "_").replace(".", "_")
        regional_sg_name = f"{clean_name}_{clean_region}"
        regional_rg_ref = f"azurerm_resource_group.main_{clean_region}"

        security_group_config = f'''
# Azure Network Security Group: {sg_name} (Region: {region})
resource "azurerm_network_security_group" "{regional_sg_name}_{self.converter.get_validated_guid(yaml_data)}" {{
  name                = "{sg_name}-{region}"
  location            = azurerm_resource_group.main_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.location
  resource_group_name = azurerm_resource_group.main_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.name

'''

        # Generate security rules
        rule_priority = 100
        for i, rule in enumerate(rules):
            rule_data = self.converter.generate_native_security_group_rule(rule, 'azure')
            direction = "Inbound" if rule_data['direction'] == 'ingress' else "Outbound"

            rule_block = f'''  security_rule {{
    name                       = "{sg_name}-rule-{i+1}"
    priority                   = {rule_priority + i * 10}
    direction                  = "{direction}"
    access                     = "Allow"
    protocol                   = "{rule_data['protocol'].upper()}"
    source_port_range          = "*"
    destination_port_range     = "{rule_data['from_port']}-{rule_data['to_port']}" if {rule_data['from_port']} != {rule_data['to_port']} else "{rule_data['from_port']}"
    source_address_prefix      = "{rule_data['cidr_blocks'][0] if rule_data['cidr_blocks'] else '*'}"
    destination_address_prefix = "*"
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

    def generate_azure_vm(self, instance, index, clean_name, size, available_subnets=None, yaml_data=None):
        """Generate native Azure virtual machine."""
        instance_name = instance.get("name", f"instance_{index}")
        image = instance.get("image", "RHEL9-latest")

        # Resolve region using region/location logic
        azure_region = self.converter.resolve_instance_region(instance, "azure")
        azure_vm_size = self.get_azure_vm_size(size)

        # Get Azure NSG references with regional awareness
        azure_nsg_refs = []
        sg_names = instance.get('security_groups', [])
        for sg_name in sg_names:
            clean_sg = sg_name.replace("-", "_").replace(".", "_")
            azure_nsg_refs.append(f"azurerm_network_security_group.{clean_sg}_{azure_region.replace('-', '_').replace(' ', '_')}_{self.converter.get_validated_guid(yaml_data)}.id")

        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})
        
        # Get Azure image configuration
        azure_image = self.get_azure_image_reference(image)

        vm_config = f'''
# Azure Public IP: {instance_name}
resource "azurerm_public_ip" "{clean_name}_ip_{self.converter.get_validated_guid(yaml_data)}" {{
  name                = "{instance_name}-ip"
  location            = azurerm_resource_group.main_{azure_region.replace("-", "_").replace(" ", "_")}_{self.converter.get_validated_guid(yaml_data)}.location
  resource_group_name = azurerm_resource_group.main_{azure_region.replace("-", "_").replace(" ", "_")}_{self.converter.get_validated_guid(yaml_data)}.name
  allocation_method   = "Static"

  tags = {{
    Environment = "agnosticd"
    ManagedBy = "yamlforge"
  }}
}}

# Azure Network Interface: {instance_name}
resource "azurerm_network_interface" "{clean_name}_nic_{self.converter.get_validated_guid(yaml_data)}" {{
  name                = "{instance_name}-nic"
  location            = azurerm_resource_group.main_{azure_region.replace("-", "_").replace(" ", "_")}_{self.converter.get_validated_guid(yaml_data)}.location
  resource_group_name = azurerm_resource_group.main_{azure_region.replace("-", "_").replace(" ", "_")}_{self.converter.get_validated_guid(yaml_data)}.name

  ip_configuration {{
    name                          = "internal"
    subnet_id                     = azurerm_subnet.main_subnet_{azure_region.replace("-", "_").replace(" ", "_")}_{self.converter.get_validated_guid(yaml_data)}.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.{clean_name}_ip_{self.converter.get_validated_guid(yaml_data)}.id
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
resource "azurerm_network_interface_security_group_association" "{clean_name}_nsg_assoc_{self.converter.get_validated_guid(yaml_data)}" {{
  network_interface_id      = azurerm_network_interface.{clean_name}_nic_{self.converter.get_validated_guid(yaml_data)}.id
  network_security_group_id = {azure_nsg_refs[0]}
}}'''

        vm_config += f'''

# Azure Linux Virtual Machine: {instance_name}
resource "azurerm_linux_virtual_machine" "{clean_name}_{self.converter.get_validated_guid(yaml_data)}" {{
  name                = "{instance_name}"
  resource_group_name = azurerm_resource_group.main_{azure_region.replace("-", "_").replace(" ", "_")}_{self.converter.get_validated_guid(yaml_data)}.name
  location            = azurerm_resource_group.main_{azure_region.replace("-", "_").replace(" ", "_")}_{self.converter.get_validated_guid(yaml_data)}.location
  size                = "{azure_vm_size}"
  admin_username      = "azureuser"
  disable_password_authentication = true

  network_interface_ids = [
    azurerm_network_interface.{clean_name}_nic_{self.converter.get_validated_guid(yaml_data)}.id,
  ]

  admin_ssh_key {{
    username   = "azureuser"
    public_key = "{ssh_key_config.get('public_key', 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC...')}"
  }}

  os_disk {{
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
  }}}}

    source_image_reference {{{{
    publisher = f"{azure_image['publisher']}"
    offer     = f"{azure_image['offer']}"
    sku       = f"{azure_image['sku']}"
    version   = f"{azure_image['version']}"
  }}}}'''

        # Get user data script if provided
        user_data_script = instance.get('user_data_script', '')
        
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

    def generate_azure_networking(self, deployment_name, deployment_config, region, yaml_data=None):
        """Generate Azure networking resources for specific region."""
        network_config = deployment_config.get('network', {})
        network_name = network_config.get('name', f"{deployment_name}-vnet")
        cidr_block = network_config.get('cidr_block', '10.0.0.0/16')

        clean_network_name = self.converter.clean_name(network_name)
        clean_region = region.replace("-", "_").replace(".", "_")

        return f'''
# Azure Resource Group: {network_name} (Region: {region})
resource "azurerm_resource_group" "main_{clean_region}_{self.converter.get_validated_guid(yaml_data)}" {{
  name     = "{network_name}-{region}"
  location = "{region}"

  tags = {{
    Environment = "agnosticd"
    ManagedBy = "yamlforge"
  }}
}}

# Azure Virtual Network: {network_name}
resource "azurerm_virtual_network" "main_vnet_{clean_region}_{self.converter.get_validated_guid(yaml_data)}" {{
  name                = "{network_name}-vnet"
  address_space       = ["{cidr_block}"]
  location            = azurerm_resource_group.main_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.location
  resource_group_name = azurerm_resource_group.main_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.name

  tags = {{
    Environment = "agnosticd"
    ManagedBy = "yamlforge"
  }}
}}

# Azure Subnet: {network_name} subnet
resource "azurerm_subnet" "main_subnet_{clean_region}_{self.converter.get_validated_guid(yaml_data)}" {{
  name                 = "{network_name}-subnet"
  resource_group_name  = azurerm_resource_group.main_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.name
  virtual_network_name = azurerm_virtual_network.main_vnet_{clean_region}_{self.converter.get_validated_guid(yaml_data)}.name
  address_prefixes     = ["{cidr_block}"]
}}
'''

    def format_azure_tags(self, tags):
        """Format tags for Azure (key-value pairs)."""
        if not tags:
            return ""

        tag_items = []
        for key, value in tags.items():
            # Azure tag keys cannot contain spaces, convert to camelCase or use underscores
            azure_key = key.replace(' ', '_')
            tag_items.append(f'    {azure_key} = "{value}"')

        return f'''
  tags = {{
{chr(10).join(tag_items)}
  }}'''

    def generate_azure_resource_group(self, resource_group_name, location, tags=None):
        """Generate Azure resource group configuration."""
        tag_block = self.format_azure_tags(tags) if tags else '''
  tags = {
    Environment = "agnosticd"
    ManagedBy   = "yamlforge"
  }'''

        return f'''
# Azure Resource Group
resource "azurerm_resource_group" "main" {{
  name     = "{resource_group_name}"
  location = "{location}"
{tag_block}
}}

'''

    def generate_azure_resource_group_from_config(self, workspace_config):
        """Generate Azure resource group from cloud-agnostic workspace config."""
        # Generate a clean resource group name
        rg_name = workspace_config['name'].replace('_', '-').replace(' ', '-')

        # Merge tags
        all_tags = {
            'environment': 'agnosticd',
            'managed-by': 'yamlforge',
            'description': workspace_config['description']
        }

        # Add custom tags
        all_tags.update(workspace_config.get('tags', {}))

        # Get location (default to East US if not specified)
        location = workspace_config.get('location', 'East US')

        return f'''
# Azure Resource Group - {workspace_config['name']}
resource "azurerm_resource_group" "main" {{
  name     = "{rg_name}"
  location = "{location}"

  tags = {{
    environment  = "{all_tags['environment']}"
    managed_by   = "{all_tags['managed-by']}"
    description  = "{all_tags['description']}"
{chr(10).join([f'    {k} = "{v}"' for k, v in workspace_config.get('tags', {}).items()])}
  }}
}}

'''
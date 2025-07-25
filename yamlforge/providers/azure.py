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
            vm_size = list(size_mapping.keys())[0]
            return vm_size

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
  location            = local.resource_group_location_{clean_region}_{self.converter.get_validated_guid(yaml_data)}
  resource_group_name = local.resource_group_name_{clean_region}_{self.converter.get_validated_guid(yaml_data)}

'''

        # Generate security rules
        rule_priority = 100
        for i, rule in enumerate(rules):
            rule_data = self.converter.generate_native_security_group_rule(rule, 'azure')
            direction = "Inbound" if rule_data['direction'] == 'ingress' else "Outbound"
            
            # Determine port range string
            from_port = rule_data['from_port']
            to_port = rule_data['to_port']
            if from_port != to_port:
                port_range = f"{from_port}-{to_port}"
            else:
                port_range = str(from_port)
            
            # Determine source address
            source_address = rule_data['cidr_blocks'][0] if rule_data['cidr_blocks'] else '*'

            rule_block = f'''  security_rule {{
    name                       = "{sg_name}-rule-{i+1}"
    priority                   = {rule_priority + i * 10}
    direction                  = "{direction}"
    access                     = "Allow"
    protocol                   = "{rule_data['protocol'].capitalize()}"
    source_port_range          = "*"
    destination_port_range     = "{port_range}"
    source_address_prefix      = "{source_address}"
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
        
        azure_vm_size = self.get_azure_vm_size(size)

        # Get Azure NSG references with regional awareness
        azure_nsg_refs = []
        sg_names = instance.get('security_groups', [])
        for sg_name in sg_names:
            clean_sg = sg_name.replace("-", "_").replace(".", "_")
            azure_nsg_refs.append(f"azurerm_network_security_group.{clean_sg}_{azure_region.replace('-', '_').replace(' ', '_')}_{self.converter.get_validated_guid(yaml_data)}.id")

        # Get SSH key configuration for this instance
        ssh_key_config = self.converter.get_instance_ssh_key(instance, yaml_data or {})
        
        # Generate SSH key resource if SSH key is provided
        ssh_key_resources = ""
        ssh_key_reference = "null"
        
        if ssh_key_config and ssh_key_config.get('public_key'):
            ssh_key_name = f"{clean_name}_ssh_key_{self.converter.get_validated_guid(yaml_data)}"
            ssh_key_resources = f'''
# Azure SSH Public Key: {instance_name}
resource "azurerm_ssh_public_key" "{ssh_key_name}" {{
  name                = "{instance_name}-ssh-key"
  resource_group_name = local.resource_group_name_{azure_region.replace("-", "_").replace(" ", "_")}_{self.converter.get_validated_guid(yaml_data)}
  location            = local.resource_group_location_{azure_region.replace("-", "_").replace(" ", "_")}_{self.converter.get_validated_guid(yaml_data)}
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
resource "azurerm_public_ip" "{clean_name}_ip_{self.converter.get_validated_guid(yaml_data)}" {{
  name                = "{instance_name}-ip"
  location            = local.resource_group_location_{azure_region.replace("-", "_").replace(" ", "_")}_{self.converter.get_validated_guid(yaml_data)}
  resource_group_name = local.resource_group_name_{azure_region.replace("-", "_").replace(" ", "_")}_{self.converter.get_validated_guid(yaml_data)}
  allocation_method   = "Static"

  tags = {{
    Environment = "agnosticd"
    ManagedBy = "yamlforge"
  }}
}}

# Azure Network Interface: {instance_name}
resource "azurerm_network_interface" "{clean_name}_nic_{self.converter.get_validated_guid(yaml_data)}" {{
  name                = "{instance_name}-nic"
  location            = local.resource_group_location_{azure_region.replace("-", "_").replace(" ", "_")}_{self.converter.get_validated_guid(yaml_data)}
  resource_group_name = local.resource_group_name_{azure_region.replace("-", "_").replace(" ", "_")}_{self.converter.get_validated_guid(yaml_data)}

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
  resource_group_name = local.resource_group_name_{azure_region.replace("-", "_").replace(" ", "_")}_{self.converter.get_validated_guid(yaml_data)}
  location            = local.resource_group_location_{azure_region.replace("-", "_").replace(" ", "_")}_{self.converter.get_validated_guid(yaml_data)}
  size                = "{azure_vm_size}"
  admin_username      = "azureuser"
  disable_password_authentication = {str(bool(ssh_key_config and ssh_key_config.get('public_key'))).lower()}'''

        # Add zone if user specified one
        if azure_zone:
            vm_config += f'''
  zone                = "{azure_zone}"'''

        vm_config += f'''

  network_interface_ids = [
    azurerm_network_interface.{clean_name}_nic_{self.converter.get_validated_guid(yaml_data)}.id,
  ]'''

        # Add SSH key block only if SSH key is available
        if ssh_key_config and ssh_key_config.get('public_key'):
            vm_config += f'''

  admin_ssh_key {{
    username   = "azureuser"
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
            networking_config = f'''
# Azure Resource Group: {network_name} (Region: {region})
resource "azurerm_resource_group" "main_{clean_region}_{guid}" {{
  name     = "{network_name}-{region}"
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
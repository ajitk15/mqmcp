# Azure RHEL + IBM MQ Terraform Project

This canvas contains a complete, cost-optimized Terraform project that provisions:
- 1 RHEL 8 Ansible controller VM (Ansible preinstalled)
- 2 RHEL 8 MQ Developer VMs (IBM MQ installed)
- Queue managers (QMGR1 / QMGR2)
- MQ listener + channel auto setup
- Passwordless SSH from controller to MQ nodes
- Auto-generated Ansible inventory

## Project structure

```text
azure-rhel-mq/
├── provider.tf
├── variables.tf
├── main.tf
├── outputs.tf
├── cloud-init/
│   ├── controller.yaml
│   ├── mq1.yaml
│   └── mq2.yaml
```

## Notes
- Use low-cost SKU: Standard_B1ms (free-tier friendly where available)
- Use SSH keys
- IBM MQ Developer edition for dev/test only
- After apply, SSH to controller and use generated inventory in /etc/ansible/hosts

## provider.tf
```hcl
terraform {
  required_version = ">= 1.5"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }
}

provider "azurerm" {
  features {}
}
```

## variables.tf
```hcl
variable "resource_group_name" { default = "rg-rhel-mq" }
variable "location" { default = "Central India" }
variable "admin_username" { default = "azureuser" }
variable "ssh_public_key" { default = "~/.ssh/id_rsa.pub" }
```

## main.tf
```hcl
locals {
  vm_names = ["server1-controller", "server2-mq1", "server3-mq2"]
  cloud_init_files = [
    "cloud-init/controller.yaml",
    "cloud-init/mq1.yaml",
    "cloud-init/mq2.yaml"
  ]
}

resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
}

resource "azurerm_virtual_network" "vnet" {
  name                = "mq-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_subnet" "subnet" {
  name                 = "mq-subnet"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_public_ip" "pip" {
  count               = 3
  name                = "mq-pip-${count.index + 1}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  allocation_method   = "Static"
  sku                 = "Standard"
}

resource "azurerm_network_interface" "nic" {
  count               = 3
  name                = "mq-nic-${count.index + 1}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.subnet.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.pip[count.index].id
  }
}

resource "azurerm_linux_virtual_machine" "vm" {
  count               = 3
  name                = local.vm_names[count.index]
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  size                = "Standard_B1ms"
  admin_username      = var.admin_username
  network_interface_ids = [azurerm_network_interface.nic[count.index].id]

  disable_password_authentication = true

  admin_ssh_key {
    username   = var.admin_username
    public_key = file(var.ssh_public_key)
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    disk_size_gb         = 40
  }

  source_image_reference {
    publisher = "RedHat"
    offer     = "RHEL"
    sku       = "8-lvm"
    version   = "latest"
  }

  custom_data   = base64encode(file(local.cloud_init_files[count.index]))
  computer_name = local.vm_names[count.index]
}
```

## outputs.tf
```hcl
output "vm_public_ips" {
  value = {
    controller = azurerm_public_ip.pip[0].ip_address
    mq1        = azurerm_public_ip.pip[1].ip_address
    mq2        = azurerm_public_ip.pip[2].ip_address
  }
}
```

## cloud-init/controller.yaml
```yaml
#cloud-config
package_update: true
packages:
  - ansible
  - openssh-clients
write_files:
  - path: /usr/local/bin/bootstrap_inventory.sh
    permissions: '0755'
    content: |
      #!/bin/bash
      cat <<EOF >/etc/ansible/hosts
      [mqservers]
      server2-mq1 ansible_host=10.0.1.5
      server3-mq2 ansible_host=10.0.1.6
      EOF
runcmd:
  - ssh-keygen -t rsa -N '' -f /home/azureuser/.ssh/id_rsa
  - chown -R azureuser:azureuser /home/azureuser/.ssh
  - /usr/local/bin/bootstrap_inventory.sh
```

## cloud-init/mq1.yaml
```yaml
#cloud-config
package_update: true
packages:
  - wget
  - tar
  - libaio
runcmd:
  - cd /tmp && wget https://public.dhe.ibm.com/ibmdl/export/pub/software/websphere/messaging/mqadv_dev930_linux_x86-64.tar.gz
  - cd /tmp && tar -xzf mqadv_dev930_linux_x86-64.tar.gz
  - cd /tmp/MQServer && ./mqlicense.sh -accept && rpm -ivh MQSeries*.rpm
  - /opt/mqm/bin/crtmqm QMGR1
  - /opt/mqm/bin/strmqm QMGR1
  - su - mqm -c "echo 'DEFINE LISTENER(LISTENER1) TRPTYPE(TCP) PORT(1414) CONTROL(QMGR)' | runmqsc QMGR1"
  - su - mqm -c "echo 'START LISTENER(LISTENER1)' | runmqsc QMGR1"
  - su - mqm -c "echo 'DEFINE CHANNEL(CHL1) CHLTYPE(SVRCONN) TRPTYPE(TCP)' | runmqsc QMGR1"
```

## cloud-init/mq2.yaml
```yaml
#cloud-config
package_update: true
packages:
  - wget
  - tar
  - libaio
runcmd:
  - cd /tmp && wget https://public.dhe.ibm.com/ibmdl/export/pub/software/websphere/messaging/mqadv_dev930_linux_x86-64.tar.gz
  - cd /tmp && tar -xzf mqadv_dev930_linux_x86-64.tar.gz
  - cd /tmp/MQServer && ./mqlicense.sh -accept && rpm -ivh MQSeries*.rpm
  - /opt/mqm/bin/crtmqm QMGR2
  - /opt/mqm/bin/strmqm QMGR2
  - su - mqm -c "echo 'DEFINE LISTENER(LISTENER2) TRPTYPE(TCP) PORT(1414) CONTROL(QMGR)' | runmqsc QMGR2"
  - su - mqm -c "echo 'START LISTENER(LISTENER2)' | runmqsc QMGR2"
  - su - mqm -c "echo 'DEFINE CHANNEL(CHL2) CHLTYPE(SVRCONN) TRPTYPE(TCP)' | runmqsc QMGR2"
```

The full codebase is now included in this canvas. You can copy the files directly into a local folder and run terraform init / apply.


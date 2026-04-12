output "vm_public_ips" {
  value = {
    controller = azurerm_public_ip.pip[0].ip_address
    mq1        = azurerm_public_ip.pip[1].ip_address
  }
}

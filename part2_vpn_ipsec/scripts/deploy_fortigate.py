import getpass
from netmiko import Netmiko


def configure_fortigate(
    host="192.168.0.251", username="admin", password=None, log_callback=print
):
  if not password:
    password = getpass.getpass(f"Senha SSH para FortiGate ({host}): ")

  device = {
      "device_type": "fortinet",
      "host": host,
      "username": username,
      "password": password,
      "timeout": 40,
  }

  commands = [
      "config system interface",
      "edit port2",
      "set mode static",
      "set ip 100.100.100.2 255.255.255.252",
      "set allowaccess ping",
      "next",
      "end",
      "config vpn ipsec phase1-interface",
      "edit VPN_TO_PALOALTO",
      "set interface port2",
      "set ike-version 2",
      "set peertype any",
      "set net-device disable",
      "set proposal aes256-sha256",
      "set dhgrp 14",
      "set remote-gw 200.200.200.2",
      "set psksecret ML_Secured_Key_2026!",
      "set keylife 86400",
      "next",
      "end",
      "config vpn ipsec phase2-interface",
      "edit VPN_TO_PALOALTO_P2",
      "set phase1name VPN_TO_PALOALTO",
      "set proposal aes256-sha256",
      "set dhgrp 14",
      "set keylifeseconds 28800",
      "set src-subnet 10.0.0.0 255.255.0.0",
      "set dst-subnet 20.0.0.0 255.255.0.0",
      "next",
      "end",
      "config firewall address",
      "edit NET_LOCAL_10",
      "set subnet 10.0.10.0 255.255.255.0",
      "next",
      "edit NET_LOCAL_20",
      "set subnet 10.0.20.0 255.255.255.0",
      "next",
      "edit NET_LOCAL_50",
      "set subnet 10.0.50.0 255.255.255.0",
      "next",
      "edit NET_REMOTE_10",
      "set subnet 20.0.10.0 255.255.255.0",
      "next",
      "edit NET_REMOTE_20",
      "set subnet 20.0.20.0 255.255.255.0",
      "next",
      "edit NET_REMOTE_50",
      "set subnet 20.0.50.0 255.255.255.0",
      "next",
      "end",
      "config firewall addrgrp",
      "edit GRP_LOCAL_VLANS",
      "set member NET_LOCAL_10 NET_LOCAL_20 NET_LOCAL_50",
      "next",
      "edit GRP_REMOTE_VLANS",
      "set member NET_REMOTE_10 NET_REMOTE_20 NET_REMOTE_50",
      "next",
      "end",
      "config router static",
      "edit 1",
      "set dst 0.0.0.0 0.0.0.0",
      "set gateway 100.100.100.1",
      "set device port2",
      "next",
      "edit 2",
      "set dst 20.0.0.0 255.255.0.0",
      "set device VPN_TO_PALOALTO",
      "next",
      "end",
      "config firewall policy",
      "edit 10",
      "set name OUTBOUND_TO_PALOALTO",
      "set srcintf port3",
      "set dstintf VPN_TO_PALOALTO",
      "set srcaddr GRP_LOCAL_VLANS",
      "set dstaddr GRP_REMOTE_VLANS",
      "set action accept",
      "set schedule always",
      "set service ALL",
      "next",
      "edit 11",
      "set name INBOUND_FROM_PALOALTO",
      "set srcintf VPN_TO_PALOALTO",
      "set dstintf port3",
      "set srcaddr GRP_REMOTE_VLANS",
      "set dstaddr GRP_LOCAL_VLANS",
      "set action accept",
      "set schedule always",
      "set service ALL",
      "next",
      "end",
  ]

  log_callback(f"[*] Conectando ao FortiGate ({host})...")
  try:
    net_connect = Netmiko(**device)
    log_callback(
        "[*] Aplicando configurações de interface, VPN IPsec, rotas e políticas..."
    )
    output = net_connect.send_config_set(commands)
    log_callback(output)

    log_callback("[*] Validando status do túnel IKE...")
    status = net_connect.send_command("get vpn ipsec tunnel summary")
    log_callback(status)

    net_connect.disconnect()
    log_callback("[+] Configuração do FortiGate concluída com sucesso!")
    return True, output + "\n" + status
  except Exception as e:
    err_msg = f"[-] Erro ao configurar FortiGate: {e}"
    log_callback(err_msg)
    return False, err_msg
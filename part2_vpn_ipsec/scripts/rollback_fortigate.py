import getpass
from netmiko import Netmiko


def rollback_fortigate(
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
      "config firewall policy",
      "purge",
      "end",
      "config router static",
      "edit 2",
      "set status disable",
      "next",
      "end",
      "config vpn ipsec phase2-interface",
      "delete VPN_TO_PALOALTO_P2",
      "end",
      "config vpn ipsec phase1-interface",
      "delete VPN_TO_PALOALTO",
      "end",
      "config firewall addrgrp",
      "delete GRP_LOCAL_VLANS",
      "delete GRP_REMOTE_VLANS",
      "end",
      "config firewall address",
      "delete NET_LOCAL_10",
      "delete NET_LOCAL_20",
      "delete NET_LOCAL_50",
      "delete NET_REMOTE_10",
      "delete NET_REMOTE_20",
      "delete NET_REMOTE_50",
      "end",
  ]

  log_callback(f"[*] Iniciando ROLLBACK no FortiGate ({host})...")
  try:
    net_connect = Netmiko(**device)
    output = net_connect.send_config_set(commands)
    log_callback(output)
    net_connect.disconnect()
    log_callback("[+] Rollback do FortiGate concluído com sucesso!")
    return True, output
  except Exception as e:
    err_msg = f"[-] Erro no rollback do FortiGate: {e}"
    log_callback(err_msg)
    return False, err_msg
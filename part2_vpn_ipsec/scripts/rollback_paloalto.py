import getpass
from netmiko import Netmiko


def rollback_paloalto(
    host="192.168.0.252", username="admin", password=None, log_callback=print
):
  if not password:
    password = getpass.getpass(f"Senha SSH para Palo Alto ({host}): ")

  device = {
      "device_type": "paloalto_panos",
      "host": host,
      "username": username,
      "password": password,
      "timeout": 90,
  }

  commands = [
      "delete rulebase security rules ALLOW_VPN_TRAFFIC",
      "delete network tunnel ipsec VPN_TO_FORTIGATE",
      "delete network ike gateway GW_FORTIGATE",
      (
          "delete network ike crypto-profiles ipsec-crypto-profiles"
          " IPSEC_ML_PROFILE"
      ),
      (
          "delete network ike crypto-profiles ike-crypto-profiles"
          " IKE_ML_PROFILE"
      ),
      (
          "delete network virtual-router default routing-table ip static-route"
          " TO_FORTIGATE"
      ),
      "delete network interface tunnel units tunnel.1",
  ]

  log_callback(f"[*] Iniciando ROLLBACK no Palo Alto ({host})...")
  try:
    net_connect = Netmiko(**device)
    output = net_connect.send_config_set(commands)
    log_callback(output)

    log_callback("[*] Executando COMMIT do rollback no Palo Alto...")
    commit_out = net_connect.commit()
    log_callback(commit_out)

    net_connect.disconnect()
    log_callback(
        "[+] Rollback do Palo Alto concluído e commitado com sucesso!"
    )
    return True, output + "\n" + commit_out
  except Exception as e:
    err_msg = f"[-] Erro no rollback do Palo Alto: {e}"
    log_callback(err_msg)
    return False, err_msg
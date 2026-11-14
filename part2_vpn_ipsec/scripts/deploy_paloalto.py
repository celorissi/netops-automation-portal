import getpass
from netmiko import Netmiko


def configure_paloalto(
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
      "set network interface ethernet ethernet1/2 layer3 ip 200.200.200.2/30",
      "set network interface tunnel units tunnel.1",
      "set zone WAN network layer3 ethernet1/2",
      "set zone VPN network layer3 tunnel.1",
      "set zone LAN network layer3 ethernet1/3",
      (
          "set network virtual-router default interface [ ethernet1/2"
          " ethernet1/3 tunnel.1 ]"
      ),
      (
          "set network virtual-router default routing-table ip static-route"
          " DEFAULT_WAN destination 0.0.0.0/0 interface ethernet1/2 nexthop"
          " ip-address 200.200.200.1"
      ),
      (
          "set network virtual-router default routing-table ip static-route"
          " TO_FORTIGATE destination 10.0.0.0/16 interface tunnel.1"
      ),
      (
          "set network ike crypto-profiles ike-crypto-profiles IKE_ML_PROFILE"
          " hash sha256"
      ),
      (
          "set network ike crypto-profiles ike-crypto-profiles IKE_ML_PROFILE"
          " dh-group group14"
      ),
      (
          "set network ike crypto-profiles ike-crypto-profiles IKE_ML_PROFILE"
          " encryption aes-256-cbc"
      ),
      (
          "set network ike crypto-profiles ike-crypto-profiles IKE_ML_PROFILE"
          " lifetime seconds 86400"
      ),
      (
          "set network ike crypto-profiles ipsec-crypto-profiles"
          " IPSEC_ML_PROFILE esp encryption aes-256-cbc"
      ),
      (
          "set network ike crypto-profiles ipsec-crypto-profiles"
          " IPSEC_ML_PROFILE esp authentication sha256"
      ),
      (
          "set network ike crypto-profiles ipsec-crypto-profiles"
          " IPSEC_ML_PROFILE dh-group group14"
      ),
      (
          "set network ike crypto-profiles ipsec-crypto-profiles"
          " IPSEC_ML_PROFILE lifetime seconds 28800"
      ),
      (
          "set network ike gateway GW_FORTIGATE protocol version ikev2"
      ),
      (
          "set network ike gateway GW_FORTIGATE protocol ikev2"
          " ike-crypto-profile IKE_ML_PROFILE"
      ),
      (
          "set network ike gateway GW_FORTIGATE authentication pre-shared-key"
          " key ML_Secured_Key_2026!"
      ),
      (
          "set network ike gateway GW_FORTIGATE local-address interface"
          " ethernet1/2 ip 200.200.200.2/30"
      ),
      (
          "set network ike gateway GW_FORTIGATE peer-address ip 100.100.100.2"
      ),
      (
          "set network tunnel ipsec VPN_TO_FORTIGATE auto-key ike-gateway"
          " GW_FORTIGATE"
      ),
      (
          "set network tunnel ipsec VPN_TO_FORTIGATE auto-key"
          " ipsec-crypto-profile IPSEC_ML_PROFILE"
      ),
      ("set network tunnel ipsec VPN_TO_FORTIGATE tunnel-interface tunnel.1"),
      (
          "set network tunnel ipsec VPN_TO_FORTIGATE auto-key proxy-id PROXY_ML"
          " local 20.0.0.0/16"
      ),
      (
          "set network tunnel ipsec VPN_TO_FORTIGATE auto-key proxy-id PROXY_ML"
          " remote 10.0.0.0/16"
      ),
      (
          "set rulebase security rules ALLOW_VPN_TRAFFIC from [ LAN VPN ] to ["
          " LAN VPN ] source [ 10.0.0.0/16 20.0.0.0/16 ] destination ["
          " 10.0.0.0/16 20.0.0.0/16 ] application any service any action allow"
      ),
  ]

  log_callback(f"[*] Conectando ao Palo Alto ({host})...")
  try:
    net_connect = Netmiko(**device)
    log_callback("[*] Enviando comandos de configuração PAN-OS...")
    output = net_connect.send_config_set(commands)
    log_callback(output)

    log_callback("[*] Executando COMMIT no Palo Alto (aguarde ~30-60s)...")
    commit_out = net_connect.commit()
    log_callback(commit_out)

    log_callback("[*] Validando status do túnel IPsec...")
    status = net_connect.send_command("show vpn ipsec-sa")
    log_callback(status)

    net_connect.disconnect()
    log_callback(
        "[+] Configuração do Palo Alto concluída e commitada com sucesso!"
    )
    return True, output + "\n" + commit_out + "\n" + status
  except Exception as e:
    err_msg = f"[-] Erro ao configurar Palo Alto: {e}"
    log_callback(err_msg)
    return False, err_msg
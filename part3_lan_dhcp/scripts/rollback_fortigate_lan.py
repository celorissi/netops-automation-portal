from netmiko import Netmiko


def rollback_fortigate_lan(host, username, password, log_callback):
    device = {
        "device_type": "fortinet",
        "host": host,
        "username": username,
        "password": password,
        "timeout": 30,
    }

    commands = [
        # 1. Remover a entrada do servidor DHCP (deve ocorrer antes de mexer no IP da interface)
        "config system dhcp server",
            "delete 1",
        "end",
        # 2. Limpar IP e protocolos liberados na port3
        "config system interface",
            "edit port3",
                "unset ip",
                "unset allowaccess",
                "set mode static",
            "next",
        "end",
    ]

    try:
        log_callback(f"[*] Conectando ao FortiGate LAN para ROLLBACK ({host})...")
        net_connect = Netmiko(**device)
        log_callback("[*] Removendo escopo DHCP (ID 1) e limpando IP da port3...")
        output = net_connect.send_config_set(commands)
        log_callback(output)
        net_connect.disconnect()
        log_callback("[+] Rollback do FortiGate LAN executado com sucesso!")
        return True, ""
    except Exception as e:
        log_callback(f"❌ Erro no Rollback do FortiGate LAN: {str(e)}")
        return False, str(e)
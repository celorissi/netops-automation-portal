from netmiko import Netmiko

def configure_fortigate_lan(host, username, password, log_callback):
    device = {
        "device_type": "fortinet",
        "host": host,
        "username": username,
        "password": password,
        "timeout": 30,
    }
    
    commands = [
        # Configurar IP e acesso administrativo na port3 (direta para a LAN 10.0.10.0/24)
        "config system interface",
            "edit port3",
                "set mode static",
                "set ip 10.0.10.1 255.255.255.0",
                "set allowaccess ping http https ssh",
            "next",
        "end",
        
        # Configurar o Servidor DHCP na port3 para atender os hosts locais
        "config system dhcp server",
            "edit 1",
                "set status enable",
                "set interface port3",
                "set default-gateway 10.0.10.1",
                "set netmask 255.255.255.0",
                "config ip-range",
                    "edit 1",
                        "set start-ip 10.0.10.10",
                        "set end-ip 10.0.10.100",
                    "next",
                "end",
                "set dns-server1 8.8.8.8",
            "next",
        "end"
    ]

    try:
        log_callback(f"[*] Conectando ao FortiGate LAN ({host})...")
        net_connect = Netmiko(**device)
        log_callback("[*] Aplicando IP na port3 e habilitando escopo DHCP...")
        output = net_connect.send_config_set(commands)
        log_callback(output)
        net_connect.disconnect()
        log_callback("[+] FortiGate LAN & DHCP configurado com sucesso na port3!")
        return True, ""
    except Exception as e:
        log_callback(f"❌ Erro no FortiGate LAN: {str(e)}")
        return False, str(e)
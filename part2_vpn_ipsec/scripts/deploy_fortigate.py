import logging
import sys
from netmiko import ConnectHandler

def configure_fortigate(host, username, password, log_callback=print):
    try:
        log_callback(f"[*] [SSH] Conectando ao FortiGate {host}:22 (User: {username})...")
        device = {
            'device_type': 'fortinet',
            'host': host,
            'username': username,
            'password': password,
            'port': 22,
            'secret': password,
            'timeout': 30
        }
        
        net_connect = ConnectHandler(**device)
        log_callback("[+] [SSH] Conexão estabelecida com sucesso!")
        
        commands = [
            "config vpn ipsec phase1-interface",
            "edit \"FGT-TO-PA-VPN\"",
            "set interface \"port2\"",
            "set remote-gw 200.200.200.2",
            "set psksecret MySecurePSK123456",
            "set proposal aes128gcm-prfsha256",
            "set dhgrp 14",
            "next",
            "end",
            
            "config system interface",
            "edit \"FGT-TO-PA-VPN\"",
            "set mode static",
            "set ip 169.254.100.1 255.255.255.255",
            "set remote-ip 169.254.100.2 255.255.255.255",
            "next",
            "end",
            
            "config vpn ipsec phase2-interface",
            "edit \"FGT-TO-PA-VPN\"",
            "set phase1name \"FGT-TO-PA-VPN\"",
            "set proposal aes128gcm-sha256",
            "set pfs enable",
            "set dhgrp 14",
            "next",
            "end",
            
            "config router static",
            "edit 0",
            "set dst 10.0.20.0 255.255.255.0",
            "set device \"FGT-TO-PA-VPN\"",
            "next",
            "end",
            
            "config firewall policy",
            "edit 0",
            "set name \"FGT_TO_PA_OUT\"",
            "set srcintf \"port3\"",
            "set dstintf \"FGT-TO-PA-VPN\"",
            "set srcaddr \"all\"",
            "set dstaddr \"all\"",
            "set action accept",
            "set schedule \"always\"",
            "set service \"ALL\"",
            "next",
            "edit 0",
            "set name \"FGT_TO_PA_IN\"",
            "set srcintf \"FGT-TO-PA-VPN\"",
            "set dstintf \"port3\"",
            "set srcaddr \"all\"",
            "set dstaddr \"all\"",
            "set action accept",
            "set schedule \"always\"",
            "set service \"ALL\"",
            "next",
            "end"
        ]
        
        log_callback("[*] [SSH] Aplicando comandos CLI do túnel IPsec no FortiGate...")
        output = net_connect.send_config_set(commands)
        log_callback(f"[+] [SSH] Retorno da CLI:\n{output}")
        
        net_connect.disconnect()
        log_callback("[+] Deploy via SSH concluído com SUCESSO!")
        return True, ""
        
    except Exception as e:
        err = str(e)
        log_callback(f"[-] [SSH] Erro crítico na execução: {err}")
        return False, err

def rollback_fortigate(host, username, password, log_callback=print):
    try:
        log_callback(f"[*] [SSH] Executando Rollback no FortiGate {host}...")
        device = {
            'device_type': 'fortinet',
            'host': host,
            'username': username,
            'password': password,
            'port': 22,
            'timeout': 30
        }
        net_connect = ConnectHandler(**device)
        
        commands = [
            "config vpn ipsec phase2-interface",
            "delete \"FGT-TO-PA-VPN\"",
            "end",
            "config vpn ipsec phase1-interface",
            "delete \"FGT-TO-PA-VPN\"",
            "end"
        ]
        output = net_connect.send_command_timing(commands) if isinstance(commands, str) else net_connect.send_config_set(commands)
        log_callback(f"[+] [SSH] Retorno do Rollback:\n{output}")
        net_connect.disconnect()
        log_callback("[+] Rollback via SSH executado com sucesso!")
        return True, ""
    except Exception as e:
        err = str(e)
        log_callback(f"[-] [SSH] Erro no Rollback: {err}")
        return False, err
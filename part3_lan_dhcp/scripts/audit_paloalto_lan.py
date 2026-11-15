import re
from netmiko import ConnectHandler

CLI_ERRORS = re.compile(
    r"Invalid syntax|Unknown command|Validation Error|Server error|Error:", re.I
)

LAN_IFACE = "ethernet1/1"
LAN_IP = "10.0.20.1"
LAN_ZONE = "LAN-ZONE"
VR_NAME = "default"


def _open_ssh(host, username, password):
    return ConnectHandler(
        device_type="paloalto_panos",
        host=host,
        username=username,
        password=password,
        timeout=120,
        session_timeout=300,
    )


def audit_paloalto_lan(host, username, password, log_callback):
    """Audita o estado atual da LAN no Palo Alto (Interface, Zona, VR e DHCP)

    garantindo total conformidade com a baseline do NetOps.
    """
    net_connect = None
    try:
        log_callback(f"[*] Conectando ao Palo Alto ({host}) para AUDITORIA da LAN...")
        net_connect = _open_ssh(host, username, password)
        
        divergencias = []

        # 1. Auditoria da Interface Layer 3 e IP
        log_callback(f"[*] Verificando interface {LAN_IFACE}...")
        out_int = net_connect.send_command(f"show interface {LAN_IFACE}", read_timeout=30)
        log_callback(out_int)
        
        if LAN_IP not in out_int:
            divergencias.append(f"Interface {LAN_IFACE} não contém o IP esperado ({LAN_IP}/24).")
        else:
            log_callback("[OK] IP da interface validado.")

        # 2. Auditoria da Zona de Segurança
        log_callback(f"[*] Verificando zona '{LAN_ZONE}'...")
        out_zone = net_connect.send_command(f"show zone {LAN_ZONE}", read_timeout=30)
        log_callback(out_zone)
        
        if LAN_IFACE not in out_zone:
            divergencias.append(f"Interface {LAN_IFACE} não está associada à zona {LAN_ZONE}.")
        else:
            log_callback("[OK] Associação com a zona validada.")

        # 3. Auditoria do Virtual Router
        log_callback(f"[*] Verificando Virtual Router '{VR_NAME}'...")
        out_vr = net_connect.send_command(f"show network virtual-router {VR_NAME}", read_timeout=30)
        log_callback(out_vr)
        
        if LAN_IFACE not in out_vr:
            divergencias.append(f"Interface {LAN_IFACE} não está associada ao Virtual Router {VR_NAME}.")
        else:
            log_callback("[OK] Associação com o Virtual Router validada.")

        # 4. Auditoria do Servidor DHCP
        log_callback("[*] Verificando configurações do servidor DHCP...")
        out_dhcp = net_connect.send_command("show dhcp server allocation", read_timeout=30)
        log_callback(out_dhcp)
        
        if LAN_IFACE not in out_dhcp and "10.0.20" not in out_dhcp:
            divergencias.append("Servidor DHCP não ativo ou escopo 10.0.20.x não encontrado.")
        else:
            log_callback("[OK] Servidor DHCP validado na interface.")

        # Resultado final da Auditoria
        if divergencias:
            log_callback("\n🚨 DIVERGÊNCIAS ENCONTRADAS NA AUDITORIA:")
            for div in divergencias:
                log_callback(f"   ⚠️ {div}")
            return False, f"{len(divergencias)} divergência(s) encontrada(s)."
        else:
            log_callback("\n✅ AUDITORIA CONCLUÍDA: 100% em conformidade com a baseline!")
            return True, ""

    except Exception as e:
        log_callback(f"[ERRO] Auditoria do Palo Alto LAN: {e}")
        return False, str(e)
    finally:
        if net_connect:
            try:
                net_connect.disconnect()
            except Exception:
                pass
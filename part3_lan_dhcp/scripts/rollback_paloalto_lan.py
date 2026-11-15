import re
from netmiko import ConnectHandler

CLI_ERRORS = re.compile(
    r"Invalid syntax|Unknown command|Validation Error|Server error|Error:", re.I
)

LAN_IFACE = "ethernet1/1"
LAN_ZONE = "LAN-ZONE"
VR_NAME = "default"
PROFILE_NAME = "PERMITE_PING"


def _open_ssh(host, username, password):
    return ConnectHandler(
        device_type="paloalto_panos",
        host=host,
        username=username,
        password=password,
        timeout=120,
        session_timeout=300,
    )


def rollback_paloalto_lan(host, username, password, log_callback):
    net_connect = None
    try:
        log_callback(f"[*] Conectando ao Palo Alto ({host}) para ROLLBACK da LAN...")
        net_connect = _open_ssh(host, username, password)
        net_connect.config_mode()

        # PASSO 0: Desliga a interface para liberar o IP do Dataplane imediatamente (mata o ping)
        log_callback(f"[*] Desativando logicamente a interface {LAN_IFACE}...")
        net_connect.send_command_timing(f"set network interface ethernet {LAN_IFACE} state down", read_timeout=30)
        
        # Comita o desligamento para o ping parar na hora
        net_connect.send_command("commit", expect_string=r"#", read_timeout=180)

        # PASSO 1: Remove o DHCP e desassocia do Virtual Router
        log_callback("[*] Removendo DHCP e desassociando do Virtual Router...")
        commands_step1 = [
            f"delete network dhcp interface {LAN_IFACE}",
            f"delete network virtual-router {VR_NAME} interface {LAN_IFACE}",
        ]
        for cmd in commands_step1:
            log_callback(f">>> {cmd}")
            out = net_connect.send_command_timing(cmd, read_timeout=30)
            if out.strip():
                log_callback(out)

        # Commit da Etapa 1
        log_callback("[*] Comitando liberação (Etapa 1)...")
        c1 = net_connect.send_command("commit", expect_string=r"#", read_timeout=180)
        log_callback(c1)

        # PASSO 2: Remove a Zona, a Interface Layer 3 e o Perfil
        log_callback("[*] Removendo Zona, Interface Layer 3 e Perfil...")
        commands_step2 = [
            f"delete zone {LAN_ZONE}",
            f"delete network interface ethernet {LAN_IFACE} layer3",
            f"delete network profiles interface-management-profile {PROFILE_NAME}",
        ]
        for cmd in commands_step2:
            log_callback(f">>> {cmd}")
            out = net_connect.send_command_timing(cmd, read_timeout=30)
            if out.strip():
                log_callback(out)

        # Commit final do Rollback
        log_callback("[*] Executando commit final do rollback...")
        commit_out = net_connect.send_command("commit", expect_string=r"#", read_timeout=180)
        log_callback(commit_out)

        if CLI_ERRORS.search(commit_out) and "is not a valid reference" not in commit_out:
            raise RuntimeError(f"Commit final do rollback falhou:\n{commit_out}")

        net_connect.exit_config_mode()
        log_callback("[+] Rollback do Palo Alto LAN concluído com sucesso!")
        return True, ""

    except Exception as e:
        log_callback(f"[ERRO] Rollback do Palo Alto LAN: {e}")
        return False, str(e)
    finally:
        if net_connect:
            try:
                net_connect.disconnect()
            except Exception:
                pass
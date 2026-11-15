import re
from netmiko import ConnectHandler

CLI_ERRORS = re.compile(
    r"Invalid syntax|Unknown command|Validation Error|Server error|Error:", re.I
)

LAN_IFACE = "ethernet1/1"
LAN_IP = "10.0.20.1/24"
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


def _run_config_commands(net_connect, commands, log_callback):
    """Executa comandos em config mode validando a saída linha por linha.

    Em caso de erro de sintaxe ou referência, aborta e reverte.
    """
    for cmd in commands:
        log_callback(f">>> {cmd}")
        out = net_connect.send_command_timing(cmd, read_timeout=30)
        if out.strip():
            log_callback(out)
        if CLI_ERRORS.search(out):
            try:
                net_connect.send_command_timing("revert config", read_timeout=30)
            except Exception:
                pass
            raise RuntimeError(f"Falha em '{cmd}':\n{out}")


# ---------------------------------------------------------------------------
# DEPLOY
# ---------------------------------------------------------------------------
def configure_paloalto_lan(host, username, password, log_callback):
    net_connect = None
    try:
        log_callback(f"[*] Conectando ao Palo Alto ({host}) para DEPLOY da LAN...")
        net_connect = _open_ssh(host, username, password)
        net_connect.config_mode()

        deploy_commands = [
            # 1. Perfil de gerenciamento
            f"set network profiles interface-management-profile {PROFILE_NAME} ping yes",
            # 2. Interface Layer 3, IP e perfil
            f"set network interface ethernet {LAN_IFACE} layer3 ip {LAN_IP}",
            f"set network interface ethernet {LAN_IFACE} layer3 interface-management-profile {PROFILE_NAME}",
            # 3. Zona de segurança
            f"set zone {LAN_ZONE} network layer3 [ {LAN_IFACE} ]",
            # 4. Virtual Router
            f"set network virtual-router {VR_NAME} interface [ {LAN_IFACE} ]",
            # 5. Servidor DHCP
            f"set network dhcp interface {LAN_IFACE} server ip-pool 10.0.20.50-10.0.20.150",
            f"set network dhcp interface {LAN_IFACE} server option gateway 10.0.20.1",
            f"set network dhcp interface {LAN_IFACE} server option subnet-mask 255.255.255.0",
            f"set network dhcp interface {LAN_IFACE} server mode auto",
        ]

        log_callback("[*] Aplicando comandos de configuração da LAN...")
        _run_config_commands(net_connect, deploy_commands, log_callback)

        log_callback("[*] Executando validate full...")
        validate = net_connect.send_command_timing("validate full", read_timeout=120)
        log_callback(validate)
        if CLI_ERRORS.search(validate) and "failed" in validate.lower():
            raise RuntimeError(f"Validação falhou:\n{validate}")

        log_callback("[*] Executando commit das alterações (aguarde até 2 min)...")
        commit_out = net_connect.send_command("commit", expect_string=r"#", read_timeout=180)
        log_callback(commit_out)

        if CLI_ERRORS.search(commit_out) and "failed" in commit_out.lower():
            raise RuntimeError(f"Commit falhou:\n{commit_out}")

        net_connect.exit_config_mode()
        log_callback("[+] Deploy LAN (IP, Perfil Ping, Zona, VR, DHCP) concluído com sucesso!")
        return True, ""

    except Exception as e:
        log_callback(f"[ERRO] Deploy do Palo Alto LAN: {e}")
        return False, str(e)
    finally:
        if net_connect:
            try:
                net_connect.disconnect()
            except Exception:
                pass
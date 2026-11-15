import os
import sys
import socket
import logging
from datetime import datetime
import markdown
from flask import (
    Flask,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
    jsonify,
)
import urllib3
from flask_socketio import SocketIO
from netmiko import (
    Netmiko,
    NetMikoTimeoutException,
    NetMikoAuthenticationException,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- DEFINIÇÃO DO DIRETÓRIO BASE E IMPORTS DE MÓDULOS ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Caminho para os módulos da Parte 2 (VPN IPsec)
sys.path.append(os.path.abspath(os.path.join(BASE_DIR, "../part2_vpn_ipsec")))
sys.path.append(os.path.abspath(os.path.join(BASE_DIR, "../part2_vpn_ipsec/scripts")))

# Importações da API REST / SDK
from deploy_fortigate_vpn import configurar_vpn_fortigate
from deploy_paloalto_vpn import configurar_vpn_paloalto

# Importações dos scripts legados via SSH (Com fallback automático de caminho)
try:
    from deploy_fortigate import configure_fortigate
    from deploy_paloalto import configure_paloalto
    from rollback_fortigate import rollback_fortigate
    from rollback_paloalto import rollback_paloalto
except ImportError:
    try:
        from scripts.deploy_fortigate import configure_fortigate
        from scripts.deploy_paloalto import configure_paloalto
        from scripts.rollback_fortigate import rollback_fortigate
        from scripts.rollback_paloalto import rollback_paloalto
    except ImportError:
        # Funções de segurança caso os arquivos SSH não existam no disco
        def configure_fortigate(*args, **kwargs): return False, "Script SSH FortiGate não encontrado."
        def configure_paloalto(*args, **kwargs): return False, "Script SSH Palo Alto não encontrado."
        def rollback_fortigate(*args, **kwargs): return False, "Script Rollback FortiGate não encontrado."
        def rollback_paloalto(*args, **kwargs): return False, "Script Rollback Palo Alto não encontrado."

# Caminho para os módulos da Parte 3 (LAN / DHCP)
sys.path.append(os.path.abspath(os.path.join(BASE_DIR, "../part3_lan_dhcp")))
from scripts.deploy_fortigate_lan import configure_fortigate_lan
from scripts.deploy_paloalto_lan import configure_paloalto_lan
from scripts.rollback_fortigate_lan import rollback_fortigate_lan
from scripts.rollback_paloalto_lan import rollback_paloalto_lan

# --- CORREÇÃO DEFINITIVA DE CRIPTOGRAFIA/KEX PARA CISCO IOL LEGADO ---
try:
    import paramiko
    from paramiko.transport import Transport
    from paramiko.kex_gex import KexGex, KexGroup14, KexGroup1

    if "diffie-hellman-group-exchange-sha1" not in Transport._kex_info:
        Transport._kex_info["diffie-hellman-group-exchange-sha1"] = KexGex
    if "diffie-hellman-group14-sha1" not in Transport._kex_info:
        Transport._kex_info["diffie-hellman-group14-sha1"] = KexGroup14
    if "diffie-hellman-group1-sha1" not in Transport._kex_info:
        Transport._kex_info["diffie-hellman-group1-sha1"] = KexGroup1
except Exception:
    pass

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger("netmiko")
logger.setLevel(logging.INFO)

app = Flask(__name__)
app.secret_key = "netops-automation-portal-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

PORTAL_IP = os.getenv("PORTAL_IP", "127.0.0.1")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

VPN_DOCS_PATH = os.path.abspath(
    os.path.join(BASE_DIR, "../part2_vpn_ipsec/vpn_architecture.md")
)

DEFAULT_CONFIG = {
    "fortigate": {
        "host": "192.168.0.251",
        "wan_ip": "100.100.100.2",
    },
    "paloalto": {
        "host": "192.168.0.252",
        "user": "admin",
        "wan_ip": "200.200.200.2",
    },
}

LEGACY_SSH_DISABLED_ALGOS = {
    "kex": [
        "mlkem768x25519-sha256",
        "curve25519-sha256",
        "curve25519-sha256@libssh.org",
        "ecdh-sha2-nistp256",
        "ecdh-sha2-nistp384",
        "ecdh-sha2-nistp521",
        "diffie-hellman-group16-sha512",
        "diffie-hellman-group-exchange-sha256",
        "diffie-hellman-group14-sha256",
    ]
}


def testar_porta_ssh(host: str, porta: int = 22, timeout: int = 3) -> bool:
    """Validação pré-voo (Pre-flight Check) para garantir que a porta TCP 22 está acessível."""
    try:
        with socket.create_connection((host, porta), timeout=timeout):
            return True
    except (socket.timeout, socket.error, OSError):
        return False


def build_cisco_device(
    host: str,
    username: str,
    password: str,
    enable_password: str,
    ssh_profile: str = "legacy",
) -> dict:
    """Constrói o dicionário de conexão do Netmiko respeitando o perfil criptográfico."""
    device = {
        "device_type": "cisco_ios",
        "host": host,
        "username": username,
        "password": password,
        "secret": enable_password,
        "timeout": 30,
        "banner_timeout": 30,
        "auth_timeout": 30,
        "ssh_strict": False,
    }
    if ssh_profile == "legacy":
        device["disabled_algorithms"] = LEGACY_SSH_DISABLED_ALGOS
    return device


def auditar_conformidade_switch(
    net_connect,
    target_hostname: str,
    vlans: dict,
    port_mappings: dict,
    send_log,
) -> list:
    """Audita o estado atual do switch Cisco comparando Hostname, VLANs e mapeamento de portas."""
    send_log("\n[*] --- INICIANDO AUDITORIA DE CONFORMIDADE (CISCO) ---")
    divergencias = []

    current_hostname_out = net_connect.send_command(
        "show running-config | include ^hostname"
    ).strip()
    hostname_atual = (
        current_hostname_out.replace("hostname ", "").strip()
        if current_hostname_out
        else "DESCONHECIDO"
    )
    if hostname_atual != target_hostname:
        divergencias.append(
            f"Hostname fora do padrão: esperado '{target_hostname}', encontrado '{hostname_atual}'."
        )
    else:
        send_log(f"[OK] Hostname validado: {hostname_atual}")

    vlan_brief = net_connect.send_command("show vlan brief")
    send_log("[*] Saída atual do 'show vlan brief':\n" + vlan_brief)

    for vlan_id, vlan_name in vlans.items():
        vlan_encontrada = False
        for line in vlan_brief.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == vlan_id and parts[1] == vlan_name:
                vlan_encontrada = True
                break
        if not vlan_encontrada:
            divergencias.append(
                f"VLAN {vlan_id} ({vlan_name}) ausente ou com nome divergente."
            )
        else:
            send_log(f"[OK] VLAN {vlan_id} ({vlan_name}) ativa e validada.")

    for interface, expected_vlan in port_mappings.items():
        int_status = net_connect.send_command(
            f"show running-config interface {interface}"
        )
        if "switchport mode access" not in int_status:
            divergencias.append(
                f"Interface {interface}: modo 'switchport mode access' não configurado."
            )
        elif f"switchport access vlan {expected_vlan}" not in int_status:
            divergencias.append(
                f"Interface {interface}: não está associada à VLAN {expected_vlan}."
            )
        else:
            send_log(
                f"[OK] Interface {interface} validada em modo access na VLAN {expected_vlan}."
            )

    send_log("[*] --- FIM DA AUDITORIA DE CONFORMIDADE ---\n")
    return divergencias


# ==========================================
# ROTAS WEB (FRONTEND)
# ==========================================
@app.route("/")
def index():
    return render_template("index.html", portal_ip=PORTAL_IP)


@app.route("/configure-page")
def configure_page():
    return render_template("configure.html", portal_ip=PORTAL_IP)


@app.route("/lan-dhcp")
def lan_dhcp_page():
    return render_template("lan_dhcp.html", portal_ip=PORTAL_IP)


@app.route("/backups")
def list_backups():
    files = []
    message = request.args.get("message")
    error = request.args.get("error")

    if os.path.exists(BACKUP_DIR):
        all_files = os.listdir(BACKUP_DIR)
        cfgs = [f for f in all_files if f.endswith(".cfg")]
        cfgs.sort(
            key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)),
            reverse=True,
        )
        for filename in cfgs[:20]:
            file_path = os.path.join(BACKUP_DIR, filename)
            file_size = os.path.getsize(file_path)
            file_date = datetime.fromtimestamp(
                os.path.getmtime(file_path)
            ).strftime("%Y-%m-%d %H:%M:%S")
            files.append({"name": filename, "date": file_date, "size": file_size})

    return render_template(
        "backups.html", backups=files, message=message, error=error
    )


@app.route("/vpn-docs")
def vpn_docs():
    html_content = ""
    if os.path.exists(VPN_DOCS_PATH):
        with open(VPN_DOCS_PATH, "r", encoding="utf-8") as f:
            md_text = f.read()
            html_content = markdown.markdown(
                md_text, extensions=["fenced_code", "tables"]
            )
    else:
        html_content = (
            "<p class='text-danger'>Arquivo de documentação da VPN não encontrado"
            f" em: {VPN_DOCS_PATH}</p>"
        )

    return render_template("vpn_docs.html", content=html_content)


@app.route("/backup-now", methods=["POST"])
def backup_now():
    host = request.form.get("host", "").strip()
    username = request.form.get("username", "admin").strip()
    password = request.form.get("password", "")
    enable_password = request.form.get("enable_password", "")
    target_hostname = request.form.get("hostname", "SWITCH").strip()
    ssh_profile = request.form.get("ssh_profile", "legacy")

    if not host or not testar_porta_ssh(host):
        return redirect(
            url_for(
                "list_backups",
                error=f"Falha de Pré-Voo: Host {host} inacessível na porta 22.",
            )
        )

    device = build_cisco_device(
        host, username, password, enable_password, ssh_profile
    )

    try:
        net_connect = Netmiko(**device)
        if enable_password:
            net_connect.enable()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{target_hostname}_manual_{timestamp}.cfg"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)

        running_config = net_connect.send_command("show running-config")
        with open(backup_path, "w") as f:
            f.write(running_config)

        net_connect.disconnect()

        all_cfgs = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".cfg")]
        if len(all_cfgs) > 20:
            all_cfgs.sort(key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)))
            for old_file in all_cfgs[: len(all_cfgs) - 20]:
                os.remove(os.path.join(BACKUP_DIR, old_file))

        return redirect(
            url_for(
                "list_backups",
                message=f"Backup manual realizado com sucesso: {backup_filename}",
            )
        )

    except NetMikoAuthenticationException:
        return redirect(
            url_for(
                "list_backups",
                error="Falha de Autenticação: Usuário ou senha inválidos.",
            )
        )
    except NetMikoTimeoutException:
        return redirect(
            url_for(
                "list_backups",
                error=f"Tempo limite esgotado ao conectar em {host}.",
            )
        )
    except Exception as e:
        return redirect(
            url_for("list_backups", error=f"Erro ao realizar backup: {str(e)}")
        )


@app.route("/clear-backups", methods=["POST"])
def clear_backups():
    try:
        if os.path.exists(BACKUP_DIR):
            files = os.listdir(BACKUP_DIR)
            deleted_count = 0
            for filename in files:
                if filename.endswith(".cfg"):
                    file_path = os.path.join(BACKUP_DIR, filename)
                    os.remove(file_path)
                    deleted_count += 1
            return redirect(
                url_for(
                    "list_backups",
                    message=(
                        f"Todos os backups foram limpos com sucesso! ({deleted_count}"
                        " arquivos removidos)"
                    ),
                )
            )
        else:
            return redirect(
                url_for("list_backups", message="Nenhum diretório de backup encontrado.")
            )
    except Exception as e:
        return redirect(
            url_for("list_backups", error=f"Erro ao limpar backups: {str(e)}")
        )


@app.route("/download/<filename>")
def download_backup(filename):
    return send_from_directory(BACKUP_DIR, filename, as_attachment=True)


# ==========================================
# WEBSOCKET 1: Switches Cisco (Router-on-a-Stick / SVIs / DHCP)
# ==========================================
@socketio.on("start_config")
def handle_config(data):
    host = data.get("host", "").strip()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    enable_password = data.get("enable_password", "")
    target_hostname = data.get("hostname", "SWITCH_AUTOMATIZADO").strip()
    action = data.get("action", "apply")
    ssh_profile = data.get("ssh_profile", "legacy")

    def send_log(msg):
        socketio.emit("log_message", {"data": msg})

    if not host:
        send_log("❌ Erro de Pré-Voo: O endereço IP do dispositivo não foi informado.")
        socketio.emit("config_finished", {"success": False})
        return

    send_log(f"[*] Executando validação pré-voo (TCP/22) em {host}...")
    if not testar_porta_ssh(host):
        send_log(
            f"❌ Erro de Pré-Voo: A porta 22 do host {host} está fechada ou inacessível."
        )
        socketio.emit("config_finished", {"success": False})
        return

    vlans = {
        "10": "VLAN_DADOS",
        "20": "VLAN_VOZ",
        "50": "VLAN_SEGURANCA",
    }

    port_mappings = {
        "Ethernet0/1": "10",
        "Ethernet0/2": "20",
        "Ethernet0/3": "50",
    }

    device = build_cisco_device(
        host, username, password, enable_password, ssh_profile
    )

    try:
        send_log(
            f"[*] Conectando ao dispositivo {host} via SSH (Perfil: {ssh_profile.upper()})..."
        )
        net_connect = Netmiko(**device)
        if enable_password:
            send_log("[*] Autenticando com senha Enable...")
            net_connect.enable()

        if action == "audit":
            send_log(
                f"[*] Modo AUDITORIA ativo: verificando conformidade contra baseline '{target_hostname}'..."
            )
            divergencias = auditar_conformidade_switch(
                net_connect, target_hostname, vlans, port_mappings, send_log
            )
            net_connect.disconnect()

            if divergencias:
                send_log("🚨 DIVERGÊNCIAS DE CONFIGURAÇÃO DETECTADAS:")
                for div in divergencias:
                    send_log(f"   ⚠️ {div}")
                socketio.emit(
                    "config_finished",
                    {
                        "success": False,
                        "message": f"Auditoria reprovada: {len(divergencias)} divergência(s).",
                    },
                )
            else:
                send_log(
                    "✅ AUDITORIA APROVADA: 100% da configuração está em conformidade!"
                )
                socketio.emit(
                    "config_finished",
                    {
                        "success": True,
                        "message": "Auditoria aprovada com sucesso!",
                    },
                )
            return

        config_commands = []
        if action == "apply":
            send_log(f"[*] Aplicando Hostname: {target_hostname}")
            config_commands.append(f"hostname {target_hostname}")

            for vlan_id, vlan_name in vlans.items():
                send_log(f"[*] Criando VLAN {vlan_id} ({vlan_name})...")
                config_commands.extend([f"vlan {vlan_id}", f"name {vlan_name}"])

            for interface, vlan_id in port_mappings.items():
                vlan_desc = vlans[vlan_id]
                send_log(
                    f"[*] Configurando interface {interface} na VLAN {vlan_id} ({vlan_desc})..."
                )
                config_commands.extend([
                    f"interface {interface}",
                    f"description ACCESS-{vlan_desc}",
                    "switchport mode access",
                    f"switchport access vlan {vlan_id}",
                    "no shutdown",
                ])

        elif action == "remove":
            send_log("[*] Executando Rollback: limpando portas e VLANs...")
            config_commands.append("hostname Switch")
            for interface in port_mappings.keys():
                config_commands.append(f"default interface {interface}")
            for vlan_id in vlans.keys():
                config_commands.append(f"no vlan {vlan_id}")

        send_log("[*] Enviando comandos de configuração para o switch...")
        output = net_connect.send_config_set(config_commands)
        send_log(output)

        net_connect.set_base_prompt()
        send_log("[*] Salvando alterações na NVRAM (write memory)...")
        net_connect.save_config()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{target_hostname}_{action}_{timestamp}.cfg"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)

        send_log(f"[*] Capturando running-config para backup automático ({backup_filename})...")
        running_config = net_connect.send_command("show running-config")
        with open(backup_path, "w") as f:
            f.write(running_config)

        all_cfgs = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".cfg")]
        if len(all_cfgs) > 20:
            all_cfgs.sort(key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)))
            for old_file in all_cfgs[: len(all_cfgs) - 20]:
                os.remove(os.path.join(BACKUP_DIR, old_file))

        net_connect.disconnect()
        send_log(f"[+] Processo de {action.upper()} concluído com SUCESSO!")
        socketio.emit(
            "config_finished",
            {"success": True, "message": f"Processo de {action.upper()} concluído com sucesso!"},
        )

    except Exception as e:
        send_log(f"❌ Erro crítico durante a execução: {str(e)}")
        socketio.emit("config_finished", {"success": False})


# ==========================================
# WEBSOCKET 2: Automação VPN IPsec (Parte 2 - SSH Legado)
# ==========================================
@socketio.on("start_vpn_action")
def handle_vpn_action(data):
    firewall = data.get("firewall", "")
    action = data.get("action", "")
    mode = data.get("mode", "api")  # 'api' ou 'ssh'
    host = data.get("host", "").strip()
    username = data.get("username", "").strip()
    secret = data.get("password", "")  # Recebe Senha SSH ou API Token

    def send_log(msg):
        socketio.emit("vpn_log_message", {"data": msg})

    if not host:
        send_log(f"❌ Erro: IP do {firewall.capitalize()} não informado.")
        socketio.emit("vpn_finished", {"success": False})
        return

    try:
        success = False
        send_log(f"[*] Iniciando {action.upper()} via {mode.upper()} no {firewall.capitalize()} ({host})...")

        if mode == "api":
            if action == "deploy":
                if firewall == "fortigate":
                    send_log("[*] Autenticando via Bearer Token na API REST do FortiGate...")
                    res = configurar_vpn_fortigate(host=host, token=secret)
                    send_log(f"[+] Resposta API FortiGate (HTTP Status): {res}")
                    success = all(code in [200, 201] for code in res.values())
                elif firewall == "paloalto":
                    send_log("[*] Conectando via SDK pan-os-python no Palo Alto e realizando Commit...")
                    res = configurar_vpn_paloalto(host=host, user=username, password=secret)
                    send_log(f"[+] Resultado SDK Palo Alto: {res}")
                    success = res.get("status") == "Sucesso"
            else:
                send_log(f"⚠️ Rollback via API não mapeado. Utilize o Modo SSH.")
                success = False

        elif mode == "ssh":
            if not testar_porta_ssh(host):
                send_log(f"❌ Erro de Pré-Voo: Firewall {firewall.capitalize()} ({host}) inacessível na porta 22.")
                socketio.emit("vpn_finished", {"success": False})
                return

            err_msg = ""
            if firewall == "fortigate":
                if "configure_fortigate" in globals() and callable(configure_fortigate):
                    if action == "deploy":
                        success, err_msg = configure_fortigate(host=host, username=username, password=secret, log_callback=send_log)
                    else:
                        success, err_msg = rollback_fortigate(host=host, username=username, password=secret, log_callback=send_log)
                else:
                    send_log("❌ Erro: O script SSH do FortiGate não foi encontrado no diretório do projeto.")
                    success, err_msg = False, "Script SSH do FortiGate não encontrado no diretório"
            elif firewall == "paloalto":
                if "configure_paloalto" in globals() and callable(configure_paloalto):
                    if action == "deploy":
                        success, err_msg = configure_paloalto(host=host, username=username, password=secret, log_callback=send_log)
                    else:
                        success, err_msg = rollback_paloalto(host=host, username=username, password=secret, log_callback=send_log)
                else:
                    send_log("❌ Erro: O script SSH do Palo Alto não foi encontrado no diretório do projeto.")
                    success, err_msg = False, "Script SSH do Palo Alto não encontrado no diretório"

            if not success and err_msg:
                send_log(f"❌ Detalhe do Erro SSH: {err_msg}")

        socketio.emit("vpn_finished", {"success": success})
    except Exception as e:
        send_log(f"❌ Erro crítico: {str(e)}")
        socketio.emit("vpn_finished", {"success": False})

# ==========================================
# WEBSOCKET 3: Automação LAN & DHCP (Parte 3)
# ==========================================
@socketio.on("start_lan_action")
def handle_lan_action(data):
    firewall = data.get("firewall", "")
    action = data.get("action", "")
    host = data.get("host", "").strip()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    def send_log(msg):
        socketio.emit("lan_log_message", {"data": msg})

    if not host or not testar_porta_ssh(host):
        send_log(f"❌ Erro de Pré-Voo: Firewall {firewall.capitalize()} ({host}) inacessível na porta 22.")
        socketio.emit("lan_finished", {"success": False})
        return

    try:
        success = False
        if firewall == "fortigate":
            if action == "deploy":
                success, _ = configure_fortigate_lan(host=host, username=username, password=password, log_callback=send_log)
            elif action == "audit":
                send_log(f"[*] Conectando ao FortiGate LAN ({host}) para Auditoria da port3 e DHCP...")
                net_connect = Netmiko(device_type="fortinet", host=host, username=username, password=password, timeout=30)

                send_log("\n--- [AUDITORIA] Estado da Interface port3 ---")
                out_int = net_connect.send_command("show system interface port3")
                send_log(out_int)

                send_log("\n--- [AUDITORIA] Estado dos Servidores DHCP ---")
                out_dhcp = net_connect.send_command("show system dhcp server")
                send_log(out_dhcp)

                net_connect.disconnect()
                send_log("\n[+] Auditoria da LAN concluída com sucesso!")
                success = True
            else:
                success, _ = rollback_fortigate_lan(host=host, username=username, password=password, log_callback=send_log)

        elif firewall == "paloalto":
            if action == "deploy":
                success, _ = configure_paloalto_lan(host=host, username=username, password=password, log_callback=send_log)
            elif action == "audit":
                send_log(f"[*] Conectando ao Palo Alto LAN ({host}) para Auditoria da eth1/1...")
                net_connect = Netmiko(device_type="paloalto_panos", host=host, username=username, password=password, timeout=30)

                send_log("\n--- [AUDITORIA] Estado da Interface ethernet1/1 ---")
                out_int = net_connect.send_command("show interface ethernet1/1")
                send_log(out_int)

                net_connect.disconnect()
                send_log("\n[+] Auditoria da LAN do Palo Alto concluída com sucesso!")
                success = True
            else:
                success, _ = rollback_paloalto_lan(host=host, username=username, password=password, log_callback=send_log)

        socketio.emit("lan_finished", {"success": success})
    except Exception as e:
        send_log(f"❌ Erro crítico: {str(e)}")
        socketio.emit("lan_finished", {"success": False})


# ==========================================
# NOVA ROTA: API REST / SDK PARA VPN IPSEC ENTRE FIREWALLS
# ==========================================
@app.route("/api/vpn/deploy", methods=["POST"])
def api_deploy_vpn():
    """
    Endpoint unificado via API REST (FortiGate) e SDK (Palo Alto) para
    subida do túnel VPN IPsec Site-to-Site utilizando os parâmetros oficiais:
    - FortiGate WAN: 100.100.100.2 (port2)
    - Palo Alto WAN: 200.200.200.2 (ethernet1/2)
    """
    data = request.json or {}

    fgt_ip = data.get("fgt_ip", DEFAULT_CONFIG["fortigate"]["host"])
    fgt_token = data.get("fgt_token")

    pa_ip = data.get("pa_ip", DEFAULT_CONFIG["paloalto"]["host"])
    pa_user = data.get("pa_user", DEFAULT_CONFIG["paloalto"]["user"])
    pa_pass = data.get("pa_pass")

    if not fgt_token or not pa_pass:
        return jsonify({
            "status": "error",
            "message": "Token de API do FortiGate e senha administrativa do Palo Alto são obrigatórios.",
        }), 400

    try:
        res_fgt = configurar_vpn_fortigate(fgt_ip, fgt_token)
        res_pa = configurar_vpn_paloalto(pa_ip, pa_user, pa_pass)

        return jsonify({
            "status": "success",
            "message": "Deploy da VPN IPsec processado via API REST / SDK em ambos os firewalls.",
            "fortigate_result": res_fgt,
            "palo_alto_result": res_pa,
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Falha crítica ao orquestrar a VPN IPsec: {str(e)}",
        }), 500


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=True,
        log_output=True,
        allow_unsafe_werkzeug=True,
    )
import os
import sys
from datetime import datetime
import markdown
from flask import (
    Flask,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_socketio import SocketIO
from netmiko import Netmiko
import logging
import sys

import paramiko
# Força o Paramiko a registrar e aceitar o grupo 14 do IOL globalmente
try:
    from paramiko.transport import Transport
    # Adiciona explicitamente o suporte caso não esteja presente na lista ativa
    if "diffie-hellman-group14-sha1" not in Transport._kex_info:
        from paramiko.kex_gex import KexGroup14
        Transport._kex_info["diffie-hellman-group14-sha1"] = KexGroup14
except Exception:
    pass

# Ativa o log detalhado do Netmiko no console para ver o que o switch está respondendo
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger("netmiko")
logger.setLevel(logging.DEBUG)


# Garante que o Python encontre os scripts da parte 2
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), "../part2_vpn_ipsec"))
)
from scripts.deploy_fortigate import configure_fortigate
from scripts.deploy_paloalto import configure_paloalto
from scripts.rollback_fortigate import rollback_fortigate
from scripts.rollback_paloalto import rollback_paloalto

app = Flask(__name__)
app.secret_key = "netops-automation-portal-secret"
socketio = SocketIO(app, cors_allowed_origins="*")

PORTAL_IP = os.getenv("PORTAL_IP", "127.0.0.1")
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

VPN_DOCS_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), "../part2_vpn_ipsec/vpn_architecture.md"
    )
)


@app.route("/")
def index():
    return render_template("index.html", portal_ip=PORTAL_IP)


@app.route("/configure-page")
def configure_page():
    return render_template("configure.html", portal_ip=PORTAL_IP)


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
        # Limite estrito de 20 arquivos
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
    host = request.form.get("host")
    username = request.form.get("username", "admin")
    password = request.form.get("password")
    enable_password = request.form.get("enable_password", "")
    target_hostname = request.form.get("hostname", "SWITCH")

    device = {
        "device_type": "cisco_ios",
        "host": host,
        "username": username,
        "password": password,
        "secret": enable_password,
        "timeout": 30,
        "ssh_strict": False,
        "look_for_keys": False,
        "allow_agent": False,
        # Força o Paramiko a rejeitar os KEX modernos e usar o group14-sha1 do IOL
        "disabled_algorithms": {
            "kex": [
                "curve25519-sha256",
                "curve25519-sha256@libssh.org",
                "ecdh-sha2-nistp256",
                "ecdh-sha2-nistp384",
                "ecdh-sha2-nistp521",
                "diffie-hellman-group16-sha512",
                "diffie-hellman-group-exchange-sha256",
                "diffie-hellman-group14-sha256",
            ]
        },
    }

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

        # Aplica política de retenção de 20 arquivos
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
# WEBSOCKET: Configuração de Switches Cisco (Parte 1)
# ==========================================
@socketio.on("start_config")
def handle_config(data):
    host = data.get("host")
    username = data.get("username")
    password = data.get("password")
    enable_password = data.get("enable_password", "")
    target_hostname = data.get("hostname", "SWITCH_AUTOMATIZADO")
    action = data.get("action", "apply")

    vlans = {
        "10": "VLAN_DADOS",
        "20": "VLAN_VOZ",
        "50": "VLAN_SEGURANCA",
    }

    # Mapeamento atualizado para interfaces GigabitEthernet do vIOS
    port_mappings = {
        "Ethernet0/1": "10",  # VLAN_DADOS
        "Ethernet0/2": "20",  # VLAN_VOZ
        "Ethernet0/3": "50",  # VLAN_SEGURANCA
    }

    device = {
        "device_type": "cisco_ios",
        "host": host,
        "username": username,
        "password": password,
        "secret": enable_password,
        "timeout": 30,
        "ssh_strict": False,
        
    }

    def send_log(msg):
        socketio.emit("log_message", {"data": msg})

    try:
        send_log(f"[*] Conectando ao dispositivo {host} via SSH...")
        net_connect = Netmiko(**device)
        if enable_password:
            send_log("[*] Autenticando com senha Enable...")
            net_connect.enable()

        config_commands = []
        if action == "apply":
            send_log(f"[*] Aplicando Hostname: {target_hostname}")
            config_commands.append(f"hostname {target_hostname}")

            # 1. Criação das VLANs
            for vlan_id, vlan_name in vlans.items():
                send_log(f"[*] Criando VLAN {vlan_id} ({vlan_name})...")
                config_commands.extend([f"vlan {vlan_id}", f"name {vlan_name}"])

            # 2. Configuração das portas de acesso GigabitEthernet
            for interface, vlan_id in port_mappings.items():
                vlan_desc = vlans[vlan_id]
                send_log(f"[*] Configurando interface {interface} na VLAN {vlan_id} ({vlan_desc})...")
                config_commands.extend([
                    f"interface {interface}",
                    f"description ACCESS-{vlan_desc}",
                    "switchport mode access",
                    f"switchport access vlan {vlan_id}",
                    "no shutdown",
                ])

        elif action == "remove":
            send_log("[*] Executando Rollback: revertendo portas, removendo VLANs e restaurando Hostname...")
            config_commands.append("hostname Switch")

            # 1. Restaura as interfaces ao padrão de fábrica
            for interface in port_mappings.keys():
                send_log(f"[*] Restaurando interface {interface} para configuração padrão...")
                config_commands.append(f"default interface {interface}")

            # 2. Remove as VLANs
            for vlan_id in vlans.keys():
                send_log(f"[*] Removendo VLAN {vlan_id}...")
                config_commands.append(f"no vlan {vlan_id}")

        send_log("[*] Enviando comandos de configuração para o switch...")
        output = net_connect.send_config_set(config_commands)
        send_log(output)

        send_log("[*] Salvando alterações na NVRAM (write memory)...")
        net_connect.save_config()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{target_hostname}_{action}_{timestamp}.cfg"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)

        send_log(
            f"[*] Capturando running-config para backup automático ({backup_filename})..."
        )
        running_config = net_connect.send_command("show running-config")
        with open(backup_path, "w") as f:
            f.write(running_config)

        # Mantém limite estrito de 20 arquivos de backup
        all_cfgs = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".cfg")]
        if len(all_cfgs) > 20:
            all_cfgs.sort(key=lambda x: os.path.getmtime(os.path.join(BACKUP_DIR, x)))
            for old_file in all_cfgs[: len(all_cfgs) - 20]:
                os.remove(os.path.join(BACKUP_DIR, old_file))

        send_log("[*] Executando validação pós-configuração (show vlan brief)...")
        vlan_brief = net_connect.send_command("show vlan brief")
        send_log(vlan_brief)

        alerts = []
        if action == "apply":
            current_hostname_out = net_connect.send_command(
                "show running-config | include hostname"
            )
            if target_hostname not in current_hostname_out:
                alerts.append("Alerta: Hostname não confere.")
            for vlan_id, vlan_name in vlans.items():
                if vlan_id not in vlan_brief or vlan_name not in vlan_brief:
                    alerts.append(f"Alerta: VLAN {vlan_id} ({vlan_name}) não encontrada!")
            for interface, vlan_id in port_mappings.items():
                short_int = interface.replace("GigabitEthernet", "Gi")
                if short_int not in vlan_brief:
                    alerts.append(f"Alerta: Interface {interface} não associada à VLAN {vlan_id}!")
        elif action == "remove":
            for vlan_id in vlans.keys():
                if vlan_id in vlan_brief:
                    alerts.append(f"Alerta: VLAN {vlan_id} ainda presente após rollback!")

        if alerts:
            for alert in alerts:
                send_log(f"⚠️ {alert}")
        else:
            send_log(f"[+] Processo de {action.upper()} concluído com SUCESSO!")

        net_connect.disconnect()
        socketio.emit("config_finished", {"success": len(alerts) == 0})

    except Exception as e:
        send_log(f"❌ Erro crítico durante a execução: {str(e)}")
        socketio.emit("config_finished", {"success": False})


# ==========================================
# WEBSOCKET: Automação VPN IPsec (Parte 2)
# ==========================================
@socketio.on("start_vpn_action")
def handle_vpn_action(data):
    firewall = data.get("firewall")
    action = data.get("action")
    host = data.get("host")
    username = data.get("username")
    password = data.get("password")

    def send_log(msg):
        socketio.emit("vpn_log_message", {"data": msg})

    try:
        success = False
        send_log(
            f"[*] Iniciando {action.upper()} no {firewall.capitalize()} ({host})..."
        )

        if firewall == "fortigate":
            if action == "deploy":
                success, _ = configure_fortigate(
                    host=host, username=username, password=password, log_callback=send_log
                )
            else:
                success, _ = rollback_fortigate(
                    host=host, username=username, password=password, log_callback=send_log
                )
        elif firewall == "paloalto":
            if action == "deploy":
                success, _ = configure_paloalto(
                    host=host, username=username, password=password, log_callback=send_log
                )
            else:
                success, _ = rollback_paloalto(
                    host=host, username=username, password=password, log_callback=send_log
                )

        if success:
            send_log(
                f"[+] Ação de {action.upper()} no {firewall.capitalize()}"
                " finalizada com SUCESSO!"
            )
        else:
            send_log(
                f"[-] Falha na execução de {action.upper()} no"
                f" {firewall.capitalize()}."
            )

        socketio.emit("vpn_finished", {"success": success})

    except Exception as e:
        send_log(f"❌ Erro crítico: {str(e)}")
        socketio.emit("vpn_finished", {"success": False})


if __name__ == "__main__":
    socketio.run(
        app, host="0.0.0.0", port=5000, debug=True, log_output=True
    )
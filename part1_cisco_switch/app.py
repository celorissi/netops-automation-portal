import os
import sys
import socket
import logging
from datetime import datetime
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- CORREÇÃO DE CRIPTOGRAFIA/KEX PARA CISCO IOL LEGADO ---
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


def salvar_backup_retencao(device_name: str, running_config: str) -> str:
    """Salva o snapshot .cfg e mantém no máximo os 20 arquivos mais recentes."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in device_name)
    filename = f"{safe_name}_{timestamp}.cfg"
    filepath = os.path.join(BACKUP_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(running_config)

    # Aplica retenção máxima de 20 arquivos .cfg
    cfgs = [
        os.path.join(BACKUP_DIR, f)
        for f in os.listdir(BACKUP_DIR)
        if f.endswith(".cfg")
    ]
    cfgs.sort(key=os.path.getmtime, reverse=True)
    for old_file in cfgs[20:]:
        try:
            os.remove(old_file)
        except OSError:
            pass

    return filename


# ==========================================
# ROTAS WEB (FRONTEND)
# ==========================================
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


@app.route("/download/<filename>")
def download_backup(filename):
    return send_from_directory(BACKUP_DIR, filename, as_attachment=True)


@app.route("/delete-backup/<filename>", methods=["POST"])
def delete_backup(filename):
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(BACKUP_DIR, safe_filename)
    if os.path.exists(file_path) and safe_filename.endswith(".cfg"):
        os.remove(file_path)
        return redirect(url_for("list_backups", message=f"Backup {safe_filename} removido."))
    return redirect(url_for("list_backups", error="Arquivo não encontrado."))


# ==========================================
# WEBSOCKET: Switches Cisco (Parte 1)
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

    if not host or not testar_porta_ssh(host):
        send_log(f"❌ Erro de Pré-Voo: Host {host} inacessível na porta 22.")
        socketio.emit("config_finished", {"success": False})
        return

    vlans = {"10": "VLAN_DADOS", "20": "VLAN_VOZ", "50": "VLAN_SEGURANCA"}
    port_mappings = {"Ethernet0/1": "10", "Ethernet0/2": "20", "Ethernet0/3": "50"}
    device = build_cisco_device(host, username, password, enable_password, ssh_profile)

    try:
        send_log(f"[*] Conectando via SSH em {host}...")
        net_connect = Netmiko(**device)
        if enable_password:
            net_connect.enable()

        config_commands = []
        expected_hostname = target_hostname

        if action == "apply":
            config_commands.append(f"hostname {target_hostname}")
            for vlan_id, vlan_name in vlans.items():
                config_commands.extend([f"vlan {vlan_id}", f"name {vlan_name}"])
            for interface, vlan_id in port_mappings.items():
                config_commands.extend([
                    f"interface {interface}",
                    f"description ACCESS-{vlans[vlan_id]}",
                    "switchport mode access",
                    f"switchport access vlan {vlan_id}",
                    "no shutdown",
                ])
        elif action == "remove":
            expected_hostname = "Switch"
            config_commands.append("hostname Switch")
            for interface in port_mappings.keys():
                config_commands.append(f"default interface {interface}")
            for vlan_id in vlans.keys():
                config_commands.append(f"no vlan {vlan_id}")

        # 1. Envia comandos sem sair automaticamente (evita erro de regex ao mudar hostname)
        output = net_connect.send_config_set(config_commands, exit_config_mode=False)
        send_log(output)

        # 2. Sai do modo config e atualiza o novo prompt no Netmiko
        net_connect.send_command_timing("end")
        net_connect.set_base_prompt()

        # 3. Salva a configuração na NVRAM
        send_log("\n[*] Salvando configuração (write memory)...")
        net_connect.save_config()

        # 4. VALIDAÇÃO PÓS-DEPLOY (Hostname + VLANs)
        send_log("\n🔍 Iniciando Validação Pós-Deploy...")
        validation_ok = True

        run_host = net_connect.send_command("show running-config | include ^hostname")
        if f"hostname {expected_hostname}" in run_host:
            send_log(f"  ✅ Hostname validado: {expected_hostname}")
        else:
            send_log(f"  ❌ Falha na validação do Hostname (esperado: {expected_hostname})")
            validation_ok = False

        vlan_brief = net_connect.send_command("show vlan brief")
        if action == "apply":
            for vlan_id, vlan_name in vlans.items():
                if vlan_id in vlan_brief and vlan_name in vlan_brief:
                    send_log(f"  ✅ VLAN {vlan_id} ({vlan_name}) ativa e validada!")
                else:
                    send_log(f"  ❌ VLAN {vlan_id} ({vlan_name}) NÃO encontrada!")
                    validation_ok = False
        elif action == "remove":
            for vlan_id, vlan_name in vlans.items():
                if vlan_name not in vlan_brief:
                    send_log(f"  ✅ VLAN {vlan_id} ({vlan_name}) removida com sucesso!")
                else:
                    send_log(f"  ⚠️ VLAN {vlan_id} ({vlan_name}) ainda presente!")
                    validation_ok = False

        # 5. Gera backup automático da running-config validada
        if action == "apply" and validation_ok:
            full_run = net_connect.send_command("show running-config")
            bkp_file = salvar_backup_retencao(expected_hostname, full_run)
            send_log(f"\n📦 Backup automático salvo: {bkp_file}")

        net_connect.disconnect()

        if validation_ok:
            send_log("\n[+] Processo e validações executados com SUCESSO!")
            socketio.emit("config_finished", {"success": True})
        else:
            send_log("\n⚠️ Configuração aplicada, mas houve alertas na validação.")
            socketio.emit("config_finished", {"success": False})

    except Exception as e:
        send_log(f"\n❌ Erro crítico: {str(e)}")
        socketio.emit("config_finished", {"success": False})

@app.route("/backup-now", methods=["POST"])
def backup_now():
    host = request.form.get("host", "").strip()
    hostname_input = request.form.get("hostname", "switch").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    enable_password = request.form.get("enable_password", password)

    if not host or not testar_porta_ssh(host):
        return redirect(
            url_for("list_backups", error=f"Host {host} inacessível na porta 22.")
        )

    device = build_cisco_device(
        host=host,
        username=username,
        password=password,
        enable_password=enable_password,
        ssh_profile="legacy",
    )

    try:
        net_connect = Netmiko(**device)
        if enable_password:
            net_connect.enable()

        # Captura o hostname real configurado no switch (ou usa o digitado no form)
        run_host = net_connect.send_command("show running-config | include ^hostname")
        if "hostname " in run_host:
            real_hostname = run_host.strip().split()[-1]
        else:
            real_hostname = hostname_input or "switch"

        full_run = net_connect.send_command("show running-config")
        net_connect.disconnect()

        saved_file = salvar_backup_retencao(real_hostname, full_run)
        return redirect(
            url_for("list_backups", message=f"Backup manual '{saved_file}' salvo com sucesso!")
        )
    except Exception as e:
        return redirect(
            url_for("list_backups", error=f"Falha ao gerar backup de {host}: {str(e)}")
        )

if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=True,
        log_output=True,
        allow_unsafe_werkzeug=True,
    )
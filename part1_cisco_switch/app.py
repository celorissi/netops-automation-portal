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
        net_connect = Netmiko(**device)
        if enable_password:
            net_connect.enable()

        config_commands = []
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
            config_commands.append("hostname Switch")
            for interface in port_mappings.keys():
                config_commands.append(f"default interface {interface}")
            for vlan_id in vlans.keys():
                config_commands.append(f"no vlan {vlan_id}")

        output = net_connect.send_config_set(config_commands)
        send_log(output)
        net_connect.save_config()
        net_connect.disconnect()

        send_log("[+] Processo executado com SUCESSO!")
        socketio.emit("config_finished", {"success": True})
    except Exception as e:
        send_log(f"❌ Erro crítico: {str(e)}")
        socketio.emit("config_finished", {"success": False})


if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=True,
        log_output=True,
        allow_unsafe_werkzeug=True,
    )
import os
import warnings
from datetime import datetime
from netmiko import Netmiko
from tqdm import tqdm

warnings.filterwarnings("ignore", category=DeprecationWarning)

# ==============================================================================
# PARÂMETROS
# ==============================================================================
FGT_HOST = "192.168.0.251"
FGT_USER = "admin"
FGT_PASS = "Admin@123"

DEST_DIR = os.path.expanduser("/home/marcelo/lab/netops-automation-portal/part2_vpn_ipsec/backup")

def backup_fortigate(host=FGT_HOST, username=FGT_USER, password=FGT_PASS, log_callback=None):
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            tqdm.write(msg)

    os.makedirs(DEST_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"fortigate_running_{timestamp}.conf"
    local_path = os.path.join(DEST_DIR, backup_filename)

    log(f"\n📦 Iniciando Backup do FortiGate ({host})...\n")

    try:
        with tqdm(total=3, desc="Backup FortiGate", ncols=90, colour="green") as pbar:
            pbar.set_postfix_str("Conectando via SSH...")
            net_connect = Netmiko(
                device_type="fortinet",
                host=host,
                username=username,
                password=password,
                timeout=30,
                fast_cli=False,
            )
            pbar.update(1)

            pbar.set_postfix_str("Coletando full-configuration...")
            config_data = net_connect.send_command("show full-configuration", delay_factor=5)
            pbar.update(1)

            pbar.set_postfix_str("Salvando arquivo local...")
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(config_data)

            net_connect.disconnect()
            pbar.update(1)
            pbar.set_postfix_str("Concluído!")

        log(f"\n✅ Backup do FortiGate salvo com sucesso em:\n   {local_path}\n")
        return True, local_path
    except Exception as e:
        err = f"Erro no backup do FortiGate: {str(e)}"
        log(f"\n❌ {err}\n")
        return False, err

if __name__ == "__main__":
    backup_fortigate()

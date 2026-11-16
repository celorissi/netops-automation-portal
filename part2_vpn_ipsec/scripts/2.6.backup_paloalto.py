import os
import time
from datetime import datetime
import paramiko
from tqdm import tqdm

PA_HOST = "192.168.0.252"
PA_USER = "admin"
PA_PASS = "Admin@123"

DEST_DIR = os.path.expanduser("/home/marcelo/lab/netops-automation-portal/part2_vpn_ipsec/backup")

def backup_paloalto(host=PA_HOST, username=PA_USER, password=PA_PASS, log_callback=None):
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            tqdm.write(msg)

    os.makedirs(DEST_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"paloalto_running_{timestamp}.xml"
    local_path = os.path.join(DEST_DIR, backup_filename)

    log(f"\n📦 Iniciando Backup do Palo Alto via Paramiko ({host})...\n")

    try:
        with tqdm(total=3, desc="Backup Palo Alto", ncols=90, colour="green") as pbar:
            pbar.set_postfix_str("Conectando via SSH...")
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=host, username=username, password=password, timeout=30, look_for_keys=False, allow_agent=False)
            pbar.update(1)

            pbar.set_postfix_str("Coletando XML...")
            shell = client.invoke_shell()
            time.sleep(1)
            shell.send("set cli config-output-format xml\n")
            time.sleep(1)
            shell.send("show configuration running\n")
            
            output = ""
            time.sleep(5)
            while shell.recv_ready():
                output += shell.recv(65535).decode("utf-8", errors="ignore")
                time.sleep(1)
            pbar.update(1)

            pbar.set_postfix_str("Salvando arquivo local...")
            with open(local_path, "w", encoding="utf-8") as f:
                f.write(output)

            client.close()
            pbar.update(1)
            pbar.set_postfix_str("Concluído!")

        log(f"\n✅ Backup do Palo Alto salvo com sucesso em:\n   {local_path}\n")
        return True, local_path
    except Exception as e:
        err = f"Erro no backup do Palo Alto: {str(e)}"
        log(f"\n❌ {err}\n")
        return False, err

if __name__ == "__main__":
    backup_paloalto()

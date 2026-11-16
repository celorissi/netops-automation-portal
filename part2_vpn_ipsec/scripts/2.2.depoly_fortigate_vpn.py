import os
import warnings
from netmiko import Netmiko
from tqdm import tqdm

warnings.filterwarnings("ignore", category=DeprecationWarning)

# ==============================================================================
# PARÂMETROS DO LABORATÓRIO
# ==============================================================================
FGT_HOST = "192.168.0.251"
FGT_USER = "admin"
FGT_PASS = "Admin@123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.abspath(os.path.join(BASE_DIR, "../config/2.2.config_fgt_vpn.cfg"))


def configure_fortigate(host=FGT_HOST, username=FGT_USER, password=FGT_PASS, log_callback=None):
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            tqdm.write(msg)

    if not os.path.exists(CONFIG_FILE):
        err = f"Arquivo de configuração não encontrado: {CONFIG_FILE}"
        log(f"❌ {err}")
        return False, err

    commands = []
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                commands.append(stripped)

    total_steps = len(commands) + 1
    log(f"\n🚀 Iniciando Deploy VPN no FortiGate ({host})...\n")

    try:
        with tqdm(total=total_steps, desc="Deploy FGT VPN", ncols=90, colour="green") as pbar:
            pbar.set_postfix_str("Conectando via SSH...")
            net_connect = Netmiko(
                device_type="fortinet",
                host=host,
                username=username,
                password=password,
                timeout=30,
            )
            pbar.update(1)

            for cmd in commands:
                pbar.set_postfix_str(f"CLI: {cmd[:32]}...")
                log(f"  >>> {cmd}")
                output = net_connect.send_config_set([cmd])
                if output.strip() and not output.strip().endswith("#"):
                    for out_line in output.splitlines():
                        if out_line.strip():
                            log(f"      {out_line.strip()}")
                pbar.update(1)

            pbar.set_postfix_str("Concluído!")

        net_connect.disconnect()
        log("\n✅ Deploy do FortiGate concluído com sucesso!\n")
        return True, ""
    except Exception as e:
        err = f"Erro no deploy do FortiGate: {str(e)}"
        log(f"\n❌ {err}\n")
        return False, err


if __name__ == "__main__":
    configure_fortigate()
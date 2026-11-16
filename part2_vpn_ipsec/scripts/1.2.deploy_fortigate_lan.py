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
FGT_PASS = "Admin@123"  # Ajuste conforme a senha do seu lab

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.abspath(os.path.join(BASE_DIR, "../config/1.2.config_fgt_lan.cfg"))


def deploy_fortigate_lan():
    if not os.path.exists(CONFIG_FILE):
        print(f"[ERRO] Arquivo de configuração não encontrado: {CONFIG_FILE}")
        return

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        commands = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    net_connect = None
    total_steps = len(commands) + 1

    print(f"\n🚀 Iniciando Deploy LAN & DHCP no FortiGate ({FGT_HOST})...\n")

    try:
        with tqdm(total=total_steps, desc="Deploy FGT LAN", ncols=90, colour="green") as pbar:
            pbar.set_postfix_str("Conectando via SSH...")
            net_connect = Netmiko(
                device_type="fortinet",
                host=FGT_HOST,
                username=FGT_USER,
                password=FGT_PASS,
                timeout=30,
            )
            pbar.update(1)

            for cmd in commands:
                pbar.set_postfix_str(f"CLI: {cmd[:35]}")
                tqdm.write(f"  >>> {cmd}")
                out = net_connect.send_command_timing(cmd)
                if out.strip() and not out.strip().endswith("#"):
                    tqdm.write(f"      {out.strip()}")
                pbar.update(1)

            pbar.set_postfix_str("Concluído!")

        print("\n✅ Deploy LAN & DHCP no FortiGate finalizado com sucesso!\n")

    except Exception as e:
        print(f"\n❌ Erro durante o Deploy FGT LAN: {e}\n")
    finally:
        if net_connect:
            net_connect.disconnect()


if __name__ == "__main__":
    deploy_fortigate_lan()
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
DELETE_FILE = os.path.abspath(os.path.join(BASE_DIR, "../config/1.4.delete_fgt_lan.cfg"))


def rollback_fortigate_lan(host=FGT_HOST, username=FGT_USER, password=FGT_PASS, log_callback=None):
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            tqdm.write(msg)

    if not os.path.exists(DELETE_FILE):
        err = f"Arquivo de delete não encontrado: {DELETE_FILE}"
        log(f"❌ {err}")
        return False, err

    with open(DELETE_FILE, "r", encoding="utf-8") as f:
        commands = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    net_connect = None
    total_steps = 3
    log(f"\n⏪ Iniciando Rollback LAN & DHCP no FortiGate ({host})...\n")

    try:
        with tqdm(total=total_steps, desc="Rollback FGT LAN", ncols=90, colour="yellow") as pbar:
            pbar.set_postfix_str("Conectando via SSH...")
            net_connect = Netmiko(
                device_type="fortinet",
                host=host,
                username=username,
                password=password,
                timeout=30,
                fast_cli=True,
            )
            pbar.update(1)

            pbar.set_postfix_str(f"Removendo em lote ({len(commands)} cmds)...")
            log("  [*] Executando comandos de remoção no FortiGate em lote...")
            output = net_connect.send_config_set(commands, cmd_verify=False)
            if output.strip():
                log(f"      {output.strip()}")
            pbar.update(1)

            pbar.set_postfix_str("Finalizando...")
            net_connect.disconnect()
            net_connect = None
            pbar.update(1)
            pbar.set_postfix_str("Concluído!")

        log("\n✅ Rollback LAN no FortiGate concluído com sucesso!\n")
        return True, ""

    except Exception as e:
        err = f"Erro durante o Rollback FGT LAN: {str(e)}"
        log(f"\n❌ {err}\n")
        return False, err
    finally:
        if net_connect:
            net_connect.disconnect()


if __name__ == "__main__":
    rollback_fortigate_lan()
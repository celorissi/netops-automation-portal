import os
import warnings
from netmiko import Netmiko
from tqdm import tqdm

warnings.filterwarnings("ignore", category=DeprecationWarning)

# ==============================================================================
# PARÂMETROS DO LABORATÓRIO
# ==============================================================================
PA_HOST = "192.168.0.252"
PA_USER = "admin"
PA_PASS = "Admin@123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.abspath(os.path.join(BASE_DIR, "../config/2.1.config_palo_alto_vpn.cfg"))


def configure_paloalto(host=PA_HOST, username=PA_USER, password=PA_PASS, log_callback=None):
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            tqdm.write(msg)

    if not os.path.exists(CONFIG_FILE):
        err = f"Arquivo de configuração não encontrado: {CONFIG_FILE}"
        log(f"❌ {err}")
        return False, err

    commands = ["configure"]
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                if stripped.lower() != "configure":
                    commands.append(stripped)

    if not any("commit" in c.lower() for c in commands):
        commands.append("commit")

    total_steps = 3
    log(f"\n🚀 Iniciando Deploy VPN no Palo Alto ({host})...\n")

    try:
        with tqdm(total=total_steps, desc="Deploy PA VPN", ncols=90, colour="cyan") as pbar:
            pbar.set_postfix_str("Conectando via SSH...")
            net_connect = Netmiko(
                device_type="paloalto_panos",
                host=host,
                username=username,
                password=password,
                timeout=60,
            )
            pbar.update(1)

            pbar.set_postfix_str(f"Enviando {len(commands)} comandos em lote...")
            log("  [*] Aplicando lote de comandos VPN e executando commit no Palo Alto...")
            output = net_connect.send_config_set(commands, cmd_verify=False, read_timeout=120)
            if output.strip():
                for out_line in output.splitlines():
                    if out_line.strip():
                        log(f"      {out_line.strip()}")
            pbar.update(1)

            pbar.set_postfix_str("Finalizando...")
            net_connect.disconnect()
            pbar.update(1)
            pbar.set_postfix_str("Concluído!")

        log("\n✅ Deploy e commit do Palo Alto concluídos com sucesso!\n")
        return True, ""
    except Exception as e:
        err = f"Erro no deploy do Palo Alto: {str(e)}"
        log(f"\n❌ {err}\n")
        return False, err


if __name__ == "__main__":
    configure_paloalto()
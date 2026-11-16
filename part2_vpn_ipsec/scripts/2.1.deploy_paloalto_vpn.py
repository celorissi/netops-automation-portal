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
PA_PASS = "Admin@123"  # Ajuste conforme a senha do seu lab

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

    total_steps = len(commands) + 1
    log(f"\n🚀 Iniciando Deploy VPN no Palo Alto ({host})...\n")

    try:
        with tqdm(total=total_steps, desc="Deploy PA VPN", ncols=90, colour="cyan") as pbar:
            pbar.set_postfix_str("Conectando via SSH...")
            net_connect = Netmiko(
                device_type="paloalto_panos",
                host=host,
                username=username,
                password=password,
                timeout=40,
            )
            pbar.update(1)

            for cmd in commands:
                pbar.set_postfix_str(f"CLI: {cmd[:32]}...")
                log(f"  >>> {cmd}")
                # Envia comando individualmente para acompanhar o progresso visual
                output = net_connect.send_config_set([cmd], cmd_verify=False)
                if output.strip():
                    for out_line in output.splitlines():
                        if out_line.strip():
                            log(f"      {out_line.strip()}")
                pbar.update(1)

            pbar.set_postfix_str("Concluído!")

        net_connect.disconnect()
        log("\n✅ Deploy e commit do Palo Alto concluídos com sucesso!\n")
        return True, ""
    except Exception as e:
        err = f"Erro no deploy do Palo Alto: {str(e)}"
        log(f"\n❌ {err}\n")
        return False, err


if __name__ == "__main__":
    configure_paloalto()
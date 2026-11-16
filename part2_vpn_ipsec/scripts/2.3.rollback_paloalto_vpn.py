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
DELETE_FILE = os.path.abspath(os.path.join(BASE_DIR, "../config/2.3.delete_palo_alto_vpn.cfg"))


def rollback_paloalto(host=PA_HOST, username=PA_USER, password=PA_PASS, log_callback=None):
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            tqdm.write(msg)

    # Fallback para o nome antigo caso ainda não tenha sido renomeado
    target_file = DELETE_FILE
    if not os.path.exists(target_file):
        alt_file = os.path.abspath(os.path.join(BASE_DIR, "../config/2.3.delete_palo_alto.cfg"))
        if os.path.exists(alt_file):
            target_file = alt_file
        else:
            err = f"Arquivo de delete não encontrado: {DELETE_FILE}"
            log(f"❌ {err}")
            return False, err

    commands = ["configure"]
    with open(target_file, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                if stripped.lower() != "configure":
                    commands.append(stripped)

    if not any("commit" in c.lower() for c in commands):
        commands.append("commit")

    total_steps = 3
    log(f"\n⏪ Iniciando Rollback VPN no Palo Alto ({host})...\n")

    try:
        with tqdm(total=total_steps, desc="Rollback PA VPN", ncols=90, colour="yellow") as pbar:
            pbar.set_postfix_str("Conectando via SSH...")
            net_connect = Netmiko(
                device_type="paloalto_panos",
                host=host,
                username=username,
                password=password,
                timeout=60,
            )
            pbar.update(1)

            pbar.set_postfix_str(f"Removendo em lote ({len(commands)} cmds)...")
            log("  [*] Executando lote de remoção VPN e commit no Palo Alto...")
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

        log("\n✅ Rollback e commit do Palo Alto executados com sucesso!\n")
        return True, ""
    except Exception as e:
        err = f"Erro no rollback do Palo Alto: {str(e)}"
        log(f"\n❌ {err}\n")
        return False, err


if __name__ == "__main__":
    rollback_paloalto()
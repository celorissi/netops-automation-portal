import os
import re
import warnings
from netmiko import ConnectHandler
from tqdm import tqdm

warnings.filterwarnings("ignore", category=DeprecationWarning)

# ==============================================================================
# PARÂMETROS DO LABORATÓRIO
# ==============================================================================
PA_HOST = "192.168.0.252"
PA_USER = "admin"
PA_PASS = "Admin@123"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DELETE_FILE = os.path.abspath(os.path.join(BASE_DIR, "../config/1.5.delete_palo_alto_lan.cfg"))

CLI_ERRORS = re.compile(
    r"Invalid syntax|Unknown command|Validation Error|Server error|Error:", re.I
)


def rollback_paloalto_lan(host=PA_HOST, username=PA_USER, password=PA_PASS, log_callback=None):
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

    # Separa em etapas lógicas para commit seguro sem perder velocidade
    step0 = [c for c in commands if "state down" in c]
    step1 = [c for c in commands if "dhcp" in c or "virtual-router" in c]
    step2 = [c for c in commands if c not in step0 and c not in step1]

    net_connect = None
    total_steps = 4
    log(f"\n⏪ Iniciando Rollback LAN no Palo Alto ({host})...\n")

    try:
        with tqdm(total=total_steps, desc="Rollback PA LAN", ncols=90, colour="yellow") as pbar:
            pbar.set_postfix_str("Conectando via SSH...")
            net_connect = ConnectHandler(
                device_type="paloalto_panos",
                host=host,
                username=username,
                password=password,
                timeout=120,
                session_timeout=300,
                fast_cli=True,
            )
            pbar.update(1)

            # Etapa 0: Desativa interface e comita
            pbar.set_postfix_str("Desativando interface...")
            log("  [*] Desativando interface e comitando liberação...")
            net_connect.send_config_set(step0, exit_config_mode=False, cmd_verify=False)
            net_connect.send_command("commit", expect_string=r"#", read_timeout=180)
            pbar.update(1)

            # Etapa 1: Remove DHCP/VR e comita
            pbar.set_postfix_str("Removendo DHCP e VR...")
            log("  [*] Removendo DHCP e Virtual Router em lote...")
            net_connect.send_config_set(step1, exit_config_mode=False, cmd_verify=False)
            net_connect.send_command("commit", expect_string=r"#", read_timeout=180)
            pbar.update(1)

            # Etapa 2: Remove Zona, Layer 3 e Perfil + Commit final
            pbar.set_postfix_str("Removendo Zona/L3 e commit final...")
            log("  [*] Removendo Zona, Layer 3, Perfil e executando commit final...")
            net_connect.send_config_set(step2, exit_config_mode=False, cmd_verify=False)
            commit_out = net_connect.send_command("commit", expect_string=r"#", read_timeout=180)
            if CLI_ERRORS.search(commit_out) and "is not a valid reference" not in commit_out:
                raise RuntimeError(f"Commit final falhou:\n{commit_out}")
            pbar.update(1)
            pbar.set_postfix_str("Concluído!")

        net_connect.exit_config_mode()
        log("\n✅ Rollback LAN no Palo Alto concluído com sucesso!\n")
        return True, ""

    except Exception as e:
        err = f"Erro durante o Rollback PA LAN: {str(e)}"
        log(f"\n❌ {err}\n")
        return False, err
    finally:
        if net_connect:
            net_connect.disconnect()


if __name__ == "__main__":
    rollback_paloalto_lan()
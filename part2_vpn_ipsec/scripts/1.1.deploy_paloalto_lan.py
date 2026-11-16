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
PA_PASS = "Admin@123"  # Ajuste conforme a senha do seu lab

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.abspath(os.path.join(BASE_DIR, "../config/1.1.config_palo_alto_lan.cfg"))

CLI_ERRORS = re.compile(
    r"Invalid syntax|Unknown command|Validation Error|Server error|Error:", re.I
)


def deploy_paloalto_lan(host=PA_HOST, username=PA_USER, password=PA_PASS, log_callback=None):
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            tqdm.write(msg)

    if not os.path.exists(CONFIG_FILE):
        err = f"Arquivo de configuração não encontrado: {CONFIG_FILE}"
        log(f"❌ {err}")
        return False, err

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        commands = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    net_connect = None
    # Etapas macro: 1. Conexão, 2. Envio em lote, 3. Validate, 4. Commit
    total_steps = 4
    log(f"\n🚀 Iniciando Deploy LAN no Palo Alto ({host})...\n")

    try:
        with tqdm(total=total_steps, desc="Deploy PA LAN", ncols=90, colour="cyan") as pbar:
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

            pbar.set_postfix_str(f"Enviando {len(commands)} comandos em lote...")
            log(f"  [*] Aplicando {len(commands)} comandos de LAN/DHCP em lote...")
            out = net_connect.send_config_set(commands, exit_config_mode=False, cmd_verify=False)
            if CLI_ERRORS.search(out):
                net_connect.send_command_timing("revert config", read_timeout=30)
                raise RuntimeError(f"Falha na aplicação do lote:\n{out}")
            pbar.update(1)

            pbar.set_postfix_str("Executando validate full...")
            log("  [*] Validando configuração (validate full)...")
            validate = net_connect.send_command_timing("validate full", read_timeout=120)
            if CLI_ERRORS.search(validate) and "failed" in validate.lower():
                raise RuntimeError(f"Validação falhou:\n{validate}")
            pbar.update(1)

            pbar.set_postfix_str("Executando commit (aguarde)...")
            log("  [*] Comitando alterações no Palo Alto...")
            commit_out = net_connect.send_command("commit", expect_string=r"#", read_timeout=180)
            if CLI_ERRORS.search(commit_out) and "failed" in commit_out.lower():
                raise RuntimeError(f"Commit falhou:\n{commit_out}")
            pbar.update(1)
            pbar.set_postfix_str("Concluído!")

        net_connect.exit_config_mode()
        log("\n✅ Deploy LAN no Palo Alto finalizado com sucesso!\n")
        return True, ""

    except Exception as e:
        err = f"Erro durante o Deploy PA LAN: {str(e)}"
        log(f"\n❌ {err}\n")
        return False, err
    finally:
        if net_connect:
            net_connect.disconnect()


if __name__ == "__main__":
    deploy_paloalto_lan()
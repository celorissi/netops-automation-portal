import os
import re
import warnings
from netmiko import ConnectHandler
from tqdm import tqdm

# Suprime avisos antigos de criptografia do Paramiko no terminal
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


def deploy_paloalto_lan():
    if not os.path.exists(CONFIG_FILE):
        print(f"[ERRO] Arquivo de configuração não encontrado: {CONFIG_FILE}")
        return

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        commands = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    net_connect = None
    # Etapas: Conexão (1) + Comandos (N) + Validate (1) + Commit (1)
    total_steps = len(commands) + 3

    print(f"\n🚀 Iniciando Deploy LAN no Palo Alto ({PA_HOST})...\n")

    try:
        with tqdm(total=total_steps, desc="Deploy PA LAN", ncols=90, colour="cyan") as pbar:
            pbar.set_postfix_str("Conectando via SSH...")
            net_connect = ConnectHandler(
                device_type="paloalto_panos",
                host=PA_HOST,
                username=PA_USER,
                password=PA_PASS,
                timeout=120,
                session_timeout=300,
            )
            net_connect.config_mode()
            pbar.update(1)

            for cmd in commands:
                pbar.set_postfix_str(f"Enviando: {cmd[:32]}...")
                tqdm.write(f"  >>> {cmd}")
                out = net_connect.send_command_timing(cmd, read_timeout=30)
                if out.strip():
                    tqdm.write(f"      {out.strip()}")
                if CLI_ERRORS.search(out):
                    net_connect.send_command_timing("revert config", read_timeout=30)
                    raise RuntimeError(f"Falha no comando '{cmd}': {out}")
                pbar.update(1)

            pbar.set_postfix_str("Executando validate full...")
            tqdm.write("  [*] Validando configuração (validate full)...")
            validate = net_connect.send_command_timing("validate full", read_timeout=120)
            if CLI_ERRORS.search(validate) and "failed" in validate.lower():
                raise RuntimeError(f"Validação falhou:\n{validate}")
            pbar.update(1)

            pbar.set_postfix_str("Comitando alterações (aguarde)...")
            tqdm.write("  [*] Executando commit no Palo Alto...")
            commit_out = net_connect.send_command("commit", expect_string=r"#", read_timeout=180)
            if CLI_ERRORS.search(commit_out) and "failed" in commit_out.lower():
                raise RuntimeError(f"Commit falhou:\n{commit_out}")
            pbar.update(1)
            pbar.set_postfix_str("Concluído!")

        net_connect.exit_config_mode()
        print("\n✅ Deploy LAN no Palo Alto finalizado com sucesso!\n")

    except Exception as e:
        print(f"\n❌ Erro durante o Deploy PA LAN: {e}\n")
    finally:
        if net_connect:
            net_connect.disconnect()


if __name__ == "__main__":
    deploy_paloalto_lan()
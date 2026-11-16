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


def rollback_paloalto_lan():
    if not os.path.exists(DELETE_FILE):
        print(f"[ERRO] Arquivo de delete não encontrado: {DELETE_FILE}")
        return

    with open(DELETE_FILE, "r", encoding="utf-8") as f:
        commands = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    net_connect = None
    # Conexão (1) + Comandos (N) + 2 Commits intermediários + 1 Commit final
    total_steps = len(commands) + 4

    print(f"\n⏪ Iniciando Rollback LAN no Palo Alto ({PA_HOST})...\n")

    try:
        with tqdm(total=total_steps, desc="Rollback PA LAN", ncols=90, colour="yellow") as pbar:
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
                pbar.set_postfix_str(f"Removendo: {cmd[:30]}...")
                tqdm.write(f"  >>> {cmd}")
                out = net_connect.send_command_timing(cmd, read_timeout=30)
                if out.strip():
                    tqdm.write(f"      {out.strip()}")
                pbar.update(1)

                if "state down" in cmd or "delete network dhcp" in cmd:
                    pbar.set_postfix_str("Commit intermediário...")
                    tqdm.write("  [*] Executando commit intermediário de liberação...")
                    net_connect.send_command("commit", expect_string=r"#", read_timeout=180)
                    pbar.update(1)

            pbar.set_postfix_str("Commit final...")
            tqdm.write("  [*] Executando commit final do rollback...")
            commit_out = net_connect.send_command("commit", expect_string=r"#", read_timeout=180)
            if CLI_ERRORS.search(commit_out) and "is not a valid reference" not in commit_out:
                raise RuntimeError(f"Commit final falhou:\n{commit_out}")
            pbar.update(1)
            pbar.set_postfix_str("Concluído!")

        net_connect.exit_config_mode()
        print("\n✅ Rollback LAN no Palo Alto concluído com sucesso!\n")

    except Exception as e:
        print(f"\n❌ Erro durante o Rollback PA LAN: {e}\n")
    finally:
        if net_connect:
            net_connect.disconnect()


if __name__ == "__main__":
    rollback_paloalto_lan()
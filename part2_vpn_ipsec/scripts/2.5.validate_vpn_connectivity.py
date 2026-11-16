import warnings
from netmiko import Netmiko
from tqdm import tqdm

warnings.filterwarnings("ignore", category=DeprecationWarning)

# ==============================================================================
# PARÂMETROS DO LABORATÓRIO
# ==============================================================================
PA_HOST = "192.168.0.252"
PA_USER = "admin"
PA_PASS = "Admin@123"  # Ajuste se a senha do PA for diferente

FGT_HOST = "192.168.0.251"
FGT_USER = "admin"
FGT_PASS = "Admin@123"


def validate_vpn_connectivity(log_callback=None):
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            tqdm.write(msg)

    results = {
        "pa_ike_sa": False,
        "pa_ipsec_sa": False,
        "pa_ping": False,
        "fgt_tunnel": False,
        "fgt_ping": False,
    }

    log("\n🔍 Iniciando Validação de Túnel IPsec e Conectividade Fim-a-Fim...\n")

    try:
        with tqdm(total=4, desc="Validando VPN", ncols=90, colour="cyan") as pbar:
            # ------------------------------------------------------------------
            # 1. VALIDAÇÃO NO PALO ALTO (Control Plane & Data Plane)
            # ------------------------------------------------------------------
            pbar.set_postfix_str("Conectando no Palo Alto...")
            pa_conn = Netmiko(
                device_type="paloalto_panos",
                host=PA_HOST,
                username=PA_USER,
                password=PA_PASS,
                timeout=30,
                fast_cli=False,
            )
            pbar.update(1)

            pbar.set_postfix_str("Checando SAs e Ping no Palo Alto...")
            log("  [1/2] Verificando Palo Alto (192.168.0.252):")

            ike_out = pa_conn.send_command("show vpn ike-sa gateway Fortinet")
            if "Established" in ike_out:
                results["pa_ike_sa"] = True
                log("    ✅ Fase 1 (IKEv2 SA): Established")
            else:
                log("    ❌ Fase 1 (IKEv2 SA): NÃO estabelecida")

            ipsec_out = pa_conn.send_command("show vpn ipsec-sa tunnel Fortinet")
            if "Mature" in ipsec_out or "Fortinet" in ipsec_out:
                results["pa_ipsec_sa"] = True
                log("    ✅ Fase 2 (IPsec SA): Ativa")
            else:
                log("    ❌ Fase 2 (IPsec SA): Inativa")

            pa_ping_out = pa_conn.send_command("ping count 3 source 10.0.20.1 host 10.0.10.1")
            if "0% packet loss" in pa_ping_out:
                results["pa_ping"] = True
                log("    ✅ Ping LAN PA (10.0.20.1) -> LAN FGT (10.0.10.1): 0% perda")
            else:
                log("    ❌ Ping LAN PA -> LAN FGT: Falhou ou com perda de pacotes")

            pa_conn.disconnect()
            pbar.update(1)

            # ------------------------------------------------------------------
            # 2. VALIDAÇÃO NO FORTIGATE (Control Plane & Data Plane)
            # ------------------------------------------------------------------
            pbar.set_postfix_str("Conectando no FortiGate...")
            fgt_conn = Netmiko(
                device_type="fortinet",
                host=FGT_HOST,
                username=FGT_USER,
                password=FGT_PASS,
                timeout=30,
                fast_cli=False,
            )
            pbar.update(1)

            pbar.set_postfix_str("Checando Túnel e Ping no FortiGate...")
            log("\n  [2/2] Verificando FortiGate (192.168.0.251):")

            fgt_vpn_out = fgt_conn.send_command("get vpn ipsec tunnel summary")
            if "palo-alto" in fgt_vpn_out and "selectors(total,up): 1/1" in fgt_vpn_out:
                results["fgt_tunnel"] = True
                log("    ✅ Túnel IPsec 'palo-alto': UP (selectors 1/1)")
            else:
                log("    ❌ Túnel IPsec 'palo-alto': DOWN ou seletores inativos")

            fgt_ping_cmd = (
                "execute ping-options source 10.0.10.1\n"
                "execute ping-options repeat-count 3\n"
                "execute ping 10.0.20.1"
            )
            fgt_ping_out = fgt_conn.send_command_timing(fgt_ping_cmd, delay_factor=2)
            if "0% packet loss" in fgt_ping_out:
                results["fgt_ping"] = True
                log("    ✅ Ping LAN FGT (10.0.10.1) -> LAN PA (10.0.20.1): 0% perda")
            else:
                log("    ❌ Ping LAN FGT -> LAN PA: Falhou ou com perda de pacotes")

            fgt_conn.disconnect()
            pbar.update(1)
            pbar.set_postfix_str("Concluído!")

        # ----------------------------------------------------------------------
        # RESUMO FINAL
        # ----------------------------------------------------------------------
        all_passed = all(results.values())
        if all_passed:
            log("\n🎉 SUCESSO TOTAL: Túnel IPsec operacional e tráfego bidirecional validado!\n")
            return True, results
        else:
            log("\n⚠️ ATENÇÃO: Uma ou mais verificações falharam. Revise os logs acima.\n")
            return False, results

    except Exception as e:
        err = f"Erro durante a validação de conectividade: {str(e)}"
        log(f"\n❌ {err}\n")
        return False, err


if __name__ == "__main__":
    validate_vpn_connectivity()
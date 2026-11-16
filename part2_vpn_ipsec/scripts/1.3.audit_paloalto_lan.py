import warnings
from netmiko import ConnectHandler
from tqdm import tqdm

warnings.filterwarnings("ignore", category=DeprecationWarning)

# ==============================================================================
# PARÂMETROS E BASELINE DE AUDITORIA
# ==============================================================================
PA_HOST = "100.64.100.2"
PA_USER = "admin"
PA_PASS = "Admin@123"

LAN_IFACE = "ethernet1/1"
LAN_IP = "10.0.20.1"
LAN_ZONE = "LAN-ZONE"
VR_NAME = "default"


def audit_paloalto_lan():
    net_connect = None
    divergencias = []

    print(f"\n🔍 Iniciando Auditoria de Conformidade LAN no Palo Alto ({PA_HOST})...\n")

    try:
        with tqdm(total=5, desc="Auditoria PA LAN", ncols=90, colour="blue") as pbar:
            pbar.set_postfix_str("Conectando via SSH...")
            net_connect = ConnectHandler(
                device_type="paloalto_panos",
                host=PA_HOST,
                username=PA_USER,
                password=PA_PASS,
                timeout=120,
            )
            pbar.update(1)

            # 1. Interface e IP
            pbar.set_postfix_str(f"Checando {LAN_IFACE}...")
            out_int = net_connect.send_command(f"show interface {LAN_IFACE}", read_timeout=30)
            if LAN_IP not in out_int:
                divergencias.append(f"Interface {LAN_IFACE} sem o IP {LAN_IP}/24.")
                tqdm.write(f"  ⚠️  [FALHA] Interface {LAN_IFACE} não possui o IP {LAN_IP}")
            else:
                tqdm.write(f"  ✅ [OK] Interface {LAN_IFACE} configurada com {LAN_IP}/24")
            pbar.update(1)

            # 2. Zona
            pbar.set_postfix_str(f"Checando Zona {LAN_ZONE}...")
            out_zone = net_connect.send_command(f"show zone {LAN_ZONE}", read_timeout=30)
            if LAN_IFACE not in out_zone:
                divergencias.append(f"Interface {LAN_IFACE} fora da zona {LAN_ZONE}.")
                tqdm.write(f"  ⚠️  [FALHA] {LAN_IFACE} não associada à {LAN_ZONE}")
            else:
                tqdm.write(f"  ✅ [OK] Zona {LAN_ZONE} vinculada à {LAN_IFACE}")
            pbar.update(1)

            # 3. Virtual Router
            pbar.set_postfix_str(f"Checando VR {VR_NAME}...")
            out_vr = net_connect.send_command(f"show network virtual-router {VR_NAME}", read_timeout=30)
            if LAN_IFACE not in out_vr:
                divergencias.append(f"Interface {LAN_IFACE} fora do VR {VR_NAME}.")
                tqdm.write(f"  ⚠️  [FALHA] {LAN_IFACE} ausente no Virtual Router {VR_NAME}")
            else:
                tqdm.write(f"  ✅ [OK] Virtual Router {VR_NAME} associado corretamente")
            pbar.update(1)

            # 4. Servidor DHCP
            pbar.set_postfix_str("Checando DHCP Server...")
            out_dhcp = net_connect.send_command("show dhcp server allocation", read_timeout=30)
            if LAN_IFACE not in out_dhcp and "10.0.20" not in out_dhcp:
                divergencias.append("Escopo DHCP 10.0.20.x inativo ou não encontrado.")
                tqdm.write("  ⚠️  [FALHA] Servidor DHCP não encontrado na interface")
            else:
                tqdm.write("  ✅ [OK] Servidor DHCP ativo na faixa 10.0.20.x")
            pbar.update(1)
            pbar.set_postfix_str("Auditoria Finalizada!")

        if divergencias:
            print(f"\n🚨 AUDITORIA REPROVADA: {len(divergencias)} divergência(s) encontrada(s).\n")
        else:
            print("\n🏆 AUDITORIA APROVADA: 100% em conformidade com a baseline!\n")

    except Exception as e:
        print(f"\n❌ Erro durante a Auditoria: {e}\n")
    finally:
        if net_connect:
            net_connect.disconnect()


if __name__ == "__main__":
    audit_paloalto_lan()
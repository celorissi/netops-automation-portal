import os
import getpass
from netmiko import ConnectHandler

CONFIG_DIR = "/home/marcelo/lab/netops-automation-portal/part2_vpn_ipsec/config"

fortigate = {
    'device_type': 'fortinet',
    'host': '192.168.0.251',
    'username': 'admin',
    'password': getpass.getpass('Senha do FortiGate: '),
}

paloalto = {
    'device_type': 'paloalto_panos',
    'host': '192.168.0.252',
    'username': 'admin',
    'password': getpass.getpass('Senha do Palo Alto: '),
}

def ler_arquivo_cfg(nome_arquivo):
    caminho = os.path.join(CONFIG_DIR, nome_arquivo)
    with open(caminho, 'r', encoding='utf-8') as f:
        return [linha.strip('\n') for linha in f if (linha.strip() and not linha.strip().startswith('#'))]

def executar_rollback():
    print("\n--- Iniciando ROLLBACK (Remoção) dos Túneis VPN ---")
    
    # 1. FortiGate
    try:
        print("\n[FortiGate] Aplicando comandos de remoção...")
        comandos_fgt = ler_arquivo_cfg("delete_fgt_vpn.cfg")
        conn_fgt = ConnectHandler(**fortigate)
        
        # read_timeout estendido para aguardar o término do bloco
        output_fgt = conn_fgt.send_config_set(comandos_fgt, read_timeout=60)
        print(output_fgt)
        conn_fgt.disconnect()
    except Exception as e:
        print(f"[Erro - FortiGate]: {e}")

    # 2. Palo Alto
    try:
        print("\n[Palo Alto] Aplicando comandos de remoção...")
        comandos_pa = ler_arquivo_cfg("delete_palo_alto.cfg")
        
        # No Palo Alto, adicionamos configure no início e commit no final
        comandos_pa_completos = ["configure"] + comandos_pa + ["commit"]
        conn_pa = ConnectHandler(**paloalto)
        
        # read_timeout estendido para aguardar o commit e processamento das regras
        output_pa = conn_pa.send_config_set(comandos_pa_completos, read_timeout=60)
        print(output_pa)
        conn_pa.disconnect()
    except Exception as e:
        print(f"[Erro - Palo Alto]: {e}")

    print("\nProcesso de rollback finalizado!")

if __name__ == "__main__":
    confirmacao = input("Tem certeza que deseja executar o ROLLBACK nos firewalls? (s/n): ").strip().lower()
    if confirmacao == 's':
        executar_rollback()
    else:
        print("Rollback cancelado pelo usuário.")
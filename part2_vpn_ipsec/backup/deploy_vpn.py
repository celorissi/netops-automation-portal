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

def validar_vpn(conn_fgt, conn_pa):
    print("\n--- Validando o Status do Túnel IPsec nos Firewalls ---")
    
    print("[FortiGate] Verificando IKE Gateway...")
    out_fgt = conn_fgt.send_command("get vpn ike gateway name FGT-TO-PA-VPN")
    print(out_fgt)
    
    print("\n[Palo Alto] Verificando IPsec SAs...")
    out_pa = conn_pa.send_command("show vpn ike-sa")
    print(out_pa)

def executar_deploy():
    print("\n--- Iniciando DEPLOY dos Túneis VPN ---")
    
    # 1. FortiGate
    try:
        print("\n[FortiGate] Aplicando configurações de deploy...")
        comandos_fgt = ler_arquivo_cfg("config_fgt_vpn.cfg")
        conn_fgt = ConnectHandler(**fortigate)
        
        output_fgt = conn_fgt.send_config_set(
            comandos_fgt, 
            enter_config_mode=False, 
            read_timeout=60
        )
        print(output_fgt)
    except Exception as e:
        print(f"[Erro - FortiGate]: {e}")
        return

    # 2. Palo Alto
    try:
        print("\n[Palo Alto] Aplicando configurações de deploy...")
        comandos_pa = ler_arquivo_cfg("config_palo_alto_vpn.cfg")
        
        # Remove o 'commit' do final da lista se houver, pois faremos de forma controlada
        if comandos_pa and comandos_pa[-1].lower() == "commit":
            comandos_pa.pop()

        conn_pa = ConnectHandler(**paloalto)
        
        output_pa = conn_pa.send_config_set(comandos_pa, read_timeout=60)
        print(output_pa)
        
        print("[Palo Alto] Executando commit das alterações...")
        output_commit = conn_pa.commit(read_timeout=120)
        print(output_commit)
    except Exception as e:
        print(f"[Erro - Palo Alto]: {e}")
        conn_fgt.disconnect()
        return

    # Validação automática pós-deploy
    validar_vpn(conn_fgt, conn_pa)

    conn_fgt.disconnect()
    conn_pa.disconnect()
    print("\nDeploy e validação finalizados com sucesso!")

if __name__ == "__main__":
    executar_deploy()
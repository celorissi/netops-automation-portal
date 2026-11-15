import requests
import config_vpn

def criar_ou_atualizar_phase1(conexao):
    url = f"{conexao['base_url']}/cmdb/vpn.ipsec/phase1-interface/{config_vpn.TUNNEL_NAME}"
    proposta = config_vpn.PHASE1_PROPOSAL

    payload = {
        "name": config_vpn.TUNNEL_NAME,
        "interface": "port2",
        "ike-version": proposta["ike_version"],
        "remote-gw": config_vpn.PALOALTO_WAN_IP,
        "psksecret": config_vpn.IPSEC_PSK,
        "proposal": f"{proposta['encryption']}-{proposta['hash']}",
        "dhgrp": proposta["dh_group"],
        "keylife": proposta["lifetime_seconds"],
    }

    # Tenta atualizar (PUT) caso já exista, senão cria (POST)
    resp = requests.put(url, headers=conexao["headers"], json=payload, verify=False)
    if resp.status_code not in [200, 201]:
        url_post = f"{conexao['base_url']}/cmdb/vpn.ipsec/phase1-interface"
        resp = requests.post(url_post, headers=conexao["headers"], json=payload, verify=False)
    return resp

def configurar_ip_interface_tunel(conexao):
    url = f"{conexao['base_url']}/cmdb/system/interface/{config_vpn.TUNNEL_NAME}"
    payload = {
        "mode": "static",
        "ip": f"{config_vpn.FORTIGATE_TUNNEL_IP} 255.255.255.255",
        "remote-ip": f"{config_vpn.PALOALTO_TUNNEL_IP} 255.255.255.255",
    }
    return requests.put(url, headers=conexao["headers"], json=payload, verify=False)

def criar_ou_atualizar_phase2(conexao):
    url = f"{conexao['base_url']}/cmdb/vpn.ipsec/phase2-interface/{config_vpn.TUNNEL_NAME}"
    proposta = config_vpn.PHASE2_PROPOSAL

    payload = {
        "name": config_vpn.TUNNEL_NAME,
        "phase1name": config_vpn.TUNNEL_NAME,
        "proposal": f"{proposta['encryption']}-{proposta['authentication']}",
        "pfs": "enable",
        "dhgrp": proposta["pfs_group"],
        "keylifeseconds": proposta["lifetime_seconds"],
        "src-subnet": "0.0.0.0 0.0.0.0",
        "dst-subnet": "0.0.0.0 0.0.0.0",
    }

    resp = requests.put(url, headers=conexao["headers"], json=payload, verify=False)
    if resp.status_code not in [200, 201]:
        url_post = f"{conexao['base_url']}/cmdb/vpn.ipsec/phase2-interface"
        resp = requests.post(url_post, headers=conexao["headers"], json=payload, verify=False)
    return resp

def criar_rota_estatica(conexao):
    # Usa identificador único ou cria rota para a LAN do Palo Alto
    url = f"{conexao['base_url']}/cmdb/router/static"
    payload = {
        "dst": "10.0.20.0 255.255.255.0",
        "device": config_vpn.TUNNEL_NAME,
    }
    # Tenta cadastrar a rota (se já existir, o FortiGate retorna erro tratado ou ignorável)
    return requests.post(url, headers=conexao["headers"], json=payload, verify=False)

def criar_politica_firewall(conexao):
    url = f"{conexao['base_url']}/cmdb/firewall/policy"

    # Tráfego da LAN (port3) para a VPN
    payload_saida = {
        "name": f"{config_vpn.TUNNEL_NAME}_OUT",
        "srcintf": [{"name": "port3"}],
        "dstintf": [{"name": config_vpn.TUNNEL_NAME}],
        "srcaddr": [{"name": "all"}],
        "dstaddr": [{"name": "all"}],
        "action": "accept",
        "schedule": "always",
        "service": [{"name": "ALL"}],
    }

    # Tráfego da VPN para a LAN (port3)
    payload_entrada = {
        "name": f"{config_vpn.TUNNEL_NAME}_IN",
        "srcintf": [{"name": config_vpn.TUNNEL_NAME}],
        "dstintf": [{"name": "port3"}],
        "srcaddr": [{"name": "all"}],
        "dstaddr": [{"name": "all"}],
        "action": "accept",
        "schedule": "always",
        "service": [{"name": "ALL"}],
    }

    resp_s = requests.post(url, headers=conexao["headers"], json=payload_saida, verify=False)
    resp_e = requests.post(url, headers=conexao["headers"], json=payload_entrada, verify=False)
    return resp_s, resp_e

def configurar_vpn_fortigate(host, token):
    conexao = {
        "base_url": f"https://{host}/api/v2",
        "headers": {"Authorization": f"Bearer {token}"},
    }

    resultados = {}
    
    # 1. Phase 1
    res_p1 = criar_ou_atualizar_phase1(conexao)
    resultados["phase1"] = res_p1.status_code

    # 2. IP da Interface do Túnel
    res_ip = configurar_ip_interface_tunel(conexao)
    resultados["ip_interface"] = res_ip.status_code

    # 3. Phase 2
    res_p2 = criar_ou_atualizar_phase2(conexao)
    resultados["phase2"] = res_p2.status_code

    # 4. Rota Estática
    res_rt = criar_rota_estatica(conexao)
    resultados["rota"] = res_rt.status_code

    # 5. Políticas de Segurança (port3 <-> Túnel)
    saida, entrada = criar_politica_firewall(conexao)
    resultados["policy_out"] = saida.status_code
    resultados["policy_in"] = entrada.status_code

    return resultados
# Parâmetros gerais da VPN IPsec Site-to-Site (FortiGate x Palo Alto)
TUNNEL_NAME = "FGT-TO-PA-VPN"
IPSEC_PSK = "SuaSenhaSeguraCompartilhada123!"

# Endereços WAN dos Firewalls
FORTIGATE_WAN_IP = "100.100.100.2"
PALOALTO_WAN_IP = "200.200.200.2"

# Redes de Túnel P2P (/30)
FORTIGATE_TUNNEL_IP = "169.254.100.1"
PALOALTO_TUNNEL_IP = "169.254.100.2"

# Redes Locais (LANs de cada ponta)
FORTIGATE_LOCAL_NETWORK = "10.0.10.0/24"
PALOALTO_LOCAL_NETWORK = "10.0.20.0/24"

# Propostas de Criptografia (IKEv2 / Phase 1)
PHASE1_PROPOSAL = {
    "ike_version": "2",
    "encryption": "aes256",
    "hash": "sha256",
    "dh_group": "14",
    "lifetime_seconds": 28800,
}

# Propostas de Criptografia (IPsec / Phase 2)
PHASE2_PROPOSAL = {
    "encryption": "aes256",
    "authentication": "sha256",
    "pfs_group": "14",
    "lifetime_seconds": 3600,
}
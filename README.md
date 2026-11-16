# 🚀 NetOps Automation Portal

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/Flask-SocketIO-green.svg" alt="Flask SocketIO">
  <img src="https://img.shields.io/badge/Netmiko%20%7C%20Paramiko-Network%20Automation-orange.svg" alt="Netmiko & Paramiko">
  <img src="https://img.shields.io/badge/Environment-Homelab%20%7C%20Multi--Vendor-critical" alt="Homelab">
</p>

---

## 📋 Visão Geral do Projeto

Portal web e esteira de automação desenvolvidos em **Python**, **Flask** e **WebSockets** para orquestração de redes e segurança corporativa multi-vendor, estruturados em ambiente de laboratório virtualizado com rede de gerência dedicada (`192.168.0.0/24`).

- **Parte 1 — Automação de Switches Cisco:** Provisionamento dinâmico de Hostname, criação de VLANs padronizadas (`10 - VLAN_DADOS`, `20 - VLAN_VOZ`, `50 - VLAN_SEGURANÇA`), validações pós-deploy e sistema automatizado de backup da `running-config` com retenção estrita de até **20 arquivos `.cfg`** (com opção de limpeza manual e download).



- **Parte 2 — Automação de Túneis VPN IPsec / IKEv2 (Multi-Vendor):** Esteira completa de provisionamento de infraestrutura LAN, deploy de túneis VPN IPsec *Route-Based*, rollback transacional ordenado, validação de conectividade (*Control Plane* e *Data Plane*) e backup automatizado para firewalls **FortiGate (FortiOS)** e **Palo Alto (PAN-OS)**.
- **Console em Tempo Real:** Streaming bidirecional de logs via `Flask-SocketIO` e `Gevent`, permitindo monitorar cada comando SSH e capturar saídas de execução instantaneamente no navegador.

---

## 🖼️ Interface do Portal

<p align="center">
  <img src="docs/images/portal-web.png" alt="Interface do NetOps Automation Portal" width="100%">
</p>

---

## 🛠️ Arquitetura e Tecnologias

- **Backend & Automação:** Python 3.11+, Flask, Flask-SocketIO, Gevent, Netmiko, Paramiko, TQDM
- **Frontend:** Bootstrap 5, Console dinâmico em tempo real via WebSockets
- **Infraestrutura:** Ambiente virtualizado conectado à rede de gerência *Out-of-Band* `192.168.0.0/24`

<p align="center">
  <img src="docs/images/topologia.png" alt="Topologia do Projeto" width="450px">
</p>
---

## 🚀 Como Executar Localmente

Clone o repositório e execute o script automatizado de inicialização (`start.sh`). Ele detecta dinamicamente o IP local da máquina (`PORTAL_IP`), configura o ambiente virtual (`venv`), instala as dependências do `requirements.txt` e inicia o servidor web:

```bash
git clone <url-do-seu-repositorio>
cd netops-automation-portal
chmod +x start.sh
./start.sh
```

O portal estará acessível em: `http://<IP_DO_SERVER>:5000`

### Execução Direta da Esteira VPN (Parte 2)

Para executar os scripts da esteira de VPN IPsec diretamente via linha de comando:

```bash
source venv/bin/activate
cd part2_vpn_ipsec/scripts

# Deploy VPN IPsec (Palo Alto e FortiGate)
python 2.1.deploy_paloalto_vpn.py
python 2.2.depoly_fortigate_vpn.py

# Validação de SAs e conectividade fim-a-fim
python 2.5.validate_vpn_connectivity.py

# Backup das configurações ativas (.xml e .conf)
python 2.6.backup_paloalto.py
python 2.7.backup_fortigate.py
```

---

## 🎥 Demonstração em Vídeo

<!-- Para player nativo do GitHub: edite este arquivo no navegador e arraste o arquivo .mp4 para a linha abaixo -->
<!-- https://github.com/user-attachments/assets/SEU-ASSET-ID -->

- **Parte 1 (Cisco Switches & Backups):** Provisionamento de Hostname, criação de VLANs (`10`, `20`, `50`), backup automático/manual com limite de 20 arquivos e rollback.


https://github.com/user-attachments/assets/965a2d18-5b0e-4d5b-9cd1-cc743f71bd7a


- **Parte 2 (FortiGate & Palo Alto VPN IPsec):** Orquestração de túneis IPsec multi-vendor, políticas de segurança, rotas estáticas, validação de conectividade e backups automatizados.

#### Configuração (Deploy)
https://github.com/user-attachments/assets/e022e8fa-9a7f-4285-8938-bd49c634a7b8

#### Rollback 

https://github.com/user-attachments/assets/d4980b07-02cc-4ac3-930a-21473d7a194c

---

## 📂 Estrutura do Repositório

```text
.
├── docs/
│   └── images/
│       ├── portal-web.png               # Captura de tela da interface web do portal
│       └── topologia-homelab.png        # Diagrama de arquitetura do laboratório
├── git-update.sh                        # Script auxiliar para commit e push rápido no GitHub
├── part1_cisco_switch/
│   ├── app.py                           # Aplicação Flask unificada (WebSockets + Rotas)
│   ├── backups/                         # Repositório de snapshots .cfg (Limite de 20 arquivos)
│   ├── config/
│   │   ├── SWITCH_AUTO_01.cfg
│   │   └── SWITCH_AUTO_02.cfg
│   └── templates/
│       ├── backups.html                 # Gerenciamento, download e limpeza de backups
│       ├── configure.html               # Configuração dinâmica de switches via WebSockets
│       └── index.html                   # Página inicial e visão geral do portal
├── part2_vpn_ipsec/
│   ├── backup/                          # Snapshots .xml (Palo Alto) e .conf (FortiGate)
│   ├── config/                          # Templates declarativos de configuração e remoção
│   │   ├── 1.1.config_palo_alto_lan.cfg
│   │   ├── 1.2.config_fgt_lan.cfg
│   │   ├── 1.4.delete_fgt_lan.cfg
│   │   ├── 1.5.delete_palo_alto_lan.cfg
│   │   ├── 2.1.config_palo_alto_vpn.cfg
│   │   ├── 2.2.config_fgt_vpn.cfg
│   │   ├── 2.3.delete_palo_alto_vpn.cfg
│   │   └── 2.4.delete_fgt_vpn.cfg
│   ├── scripts/                         # Orquestradores Python (Deploy, Rollback, Audit e Backup)
│   │   ├── 1.1.deploy_paloalto_lan.py
│   │   ├── 1.2.deploy_fortigate_lan.py
│   │   ├── 1.3.audit_paloalto_lan.py
│   │   ├── 1.4.rollback_fortigate_lan.py
│   │   ├── 1.5.rollback_paloalto_lan.py
│   │   ├── 2.1.deploy_paloalto_vpn.py
│   │   ├── 2.2.depoly_fortigate_vpn.py
│   │   ├── 2.3.rollback_paloalto_vpn.py
│   │   ├── 2.4.rollback_fortigate_vpn.py
│   │   ├── 2.5.validate_vpn_connectivity.py
│   │   ├── 2.6.backup_paloalto.py
│   │   └── 2.7.backup_fortigate.py
│   └── vpn_architecture.md              # Documentação técnica e arquitetura da Parte 2
├── README.md                            # Documentação oficial do projeto
├── requirements.txt                     # Dependências Python do projeto
├── setup_env.sh                         # Script de preparação do ambiente virtual
└── start.sh                             # Script de inicialização automatizada (IP dinâmico + venv)
```

### 🖥️ Imagens e Plataformas do Laboratório

| Dispositivo | Função na Topologia | Imagem / Versão Utilizada |
| :--- | :--- | :--- |
| **FW-Fortigate** | Firewall / VPN Peer A (`192.168.0.251`) | FortiOS `v6.2.3` |
| **FW-PaloAlto** | Firewall / VPN Peer B (`192.168.0.252`) | PAN-OS `10.0.0` |
| **SWITCH_AUTOMATIZADO** | Switch de Acesso L2 (`192.168.0.248`) | Cisco IOL `i86bi_linux_l2_ipbasek9-ms.high_iron_aug9_2017b.bin` |
| **SW-01 / SW-02** | Comutação LAN Interna (Sites A e B) | Cisco IOL `i86bi_linux_l2_ipbasek9-ms.high_iron_aug9_2017b.bin` |
| **2x VPCS** | Endpoints de Teste DHCP / Ping (LANs) | Virtual PC Simulator (VPCS) |

### 🧪 Topologia Pronta para Importação (PNETLab / EVE-NG)

O pacote exportado do laboratório utilizado neste projeto está disponível para importação direta no **PNETLab**:

- 📦 **[Download da Topologia PNETLab (`netops-automation-lab.zip`)](docs/laboratorio/netops-automation-lab.zip)**

> **Nota:** No PNETLab, utilize a opção **Import** selecionando o arquivo `.zip` acima. Após importar, certifique-se de associar as imagens listadas na tabela e conectar a nuvem de gerência (*Cloud0 / Management*) à rede `192.168.0.0/24`.
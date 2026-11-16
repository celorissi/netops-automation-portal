# 🚀 NetOps Automation Portal — Mercado Libre Challenge

<p align="center">
  <img src="docs/images/topologia-homelab.png" alt="Topologia do Homelab PNETLab" width="100%">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.13-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/Flask-SocketIO-green.svg" alt="Flask SocketIO">
  <img src="https://img.shields.io/badge/Netmiko-Network%20Automation-orange.svg" alt="Netmiko">
  <img src="https://img.shields.io/badge/Environment-Raspberry%20Pi%204%20%7C%20PNETLab-critical" alt="Homelab">
</p>

---

## 📋 Visão Geral do Projeto

Portal web unificado desenvolvido em **Flask** e **WebSockets** para automação de redes e segurança corporativa, estruturado em ambiente de homelab (PNETLab) e executado em um **Raspberry Pi** (`raspi-automation`). O projeto atende integralmente aos requisitos do desafio técnico:

* **Parte 1 — Automação de Switches Cisco:** Provisionamento dinâmico de Hostname, criação de VLANs obrigatórias (`10 - VLAN_DADOS`, `20 - VLAN_VOZ`, `50 - VLAN_SEGURANÇA`), validações pós-deploy, e sistema automatizado de backup da `running-config` com retenção estrita de até **20 arquivos `.cfg`** (com opção de limpeza manual e download).
* **Parte 2 — Automação de Túneis VPN IPsec (Multi-Vendor):** Orquestração de deploy, rollback e validação de SAs em firewalls **FortiGate** e **Palo Alto (PAN-OS)**.
* **Console em Tempo Real:** Streaming bidirecional de logs via `Flask-SocketIO` e `Gevent`, permitindo monitorar cada comando SSH e capturar erros de script instantaneamente no navegador.

---

## 🛠️ Arquitetura e Tecnologias

* **Backend:** Python, Flask, Flask-SocketIO, Gevent, Netmiko, Markdown
* **Frontend:** Bootstrap 5, Console dinâmico em tempo real via WebSockets
* **Infraestrutura:** Homelab PNETLab conectado à rede de gerência `192.168.0.0/24`

---

## 🚀 Como Executar Localmente

Clone o repositório e execute o script automatizado de inicialização (`start.sh`). Ele detecta dinamicamente o IP local da máquina (`PORTAL_IP`), configura o ambiente virtual (`venv`), instala as dependências do `requirements.txt` e inicia o servidor web:

```bash
git clone <url-do-seu-repositorio>
cd ml-networking-automation-challenge
chmod +x start.sh
./start.sh
```

O portal estará acessível em: `http://<IP_DO_SERVER>:5000`

---

## 🎥 Demonstração em Vídeo

*(Arraste e solte seu arquivo `.mp4` diretamente aqui no editor web do GitHub para gerar o player nativo, ou utilize a thumbnail do YouTube abaixo)*

[![Assistir Demonstração Completa](https://img.youtube.com/vi/SEU_ID_DO_VIDEO/maxresdefault.jpg)](https://www.youtube.com/watch?v=SEU_ID_DO_VIDEO)

* **Parte 1 (Cisco Switches & Backups):** Provisionamento de Hostname, criação de VLANs (`10`, `20`, `50`), backup automático/manual com limite de 20 arquivos e rollback.
* **Parte 2 (FortiGate & Palo Alto VPN IPsec):** Orquestração de túneis IPsec multi-vendor, políticas de segurança, rotas estáticas e validação de SAs.

---

## 📂 Estrutura do Repositório

```text
.
├── docs/
│   └── images/
│       └── topologia-homelab.png   # Diagrama de arquitetura do laboratório
├── part1_cisco_switch/
│   ├── app.py                      # Aplicação Flask unificada (WebSockets + Rotas)
│   ├── backups/                    # Repositório de snapshots .cfg (Limite de 20 arquivos)
│   └── templates/
│       ├── backups.html            # Gerenciamento, download e limpeza de backups
│       ├── configure.html          # Configuração dinâmica de switches via WebSockets
│       ├── index.html              # Página inicial e visão geral do portal
│       └── vpn_docs.html           # Documentação e orquestração VPN IPsec
├── part2_vpn_ipsec/
│   ├── configs/                    # Arquivos e templates de configuração VPN
│   ├── scripts/
│   │   ├── deploy_fortigate.py
│   │   ├── deploy_paloalto.py
│   │   ├── rollback_fortigate.py
│   │   └── rollback_paloalto.py
│   └── vpn_architecture.md         # Documentação técnica e arquitetura da Parte 2
├── git-update.sh                   # Script auxiliar para commit e push rápido no GitHub
├── README.md                       # Documentação oficial do projeto
├── requirements.txt                # Dependências Python do projeto
└── start.sh                        # Script de inicialização automatizada (IP dinâmico + venv)
```

---


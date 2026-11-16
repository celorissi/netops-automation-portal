# Arquitetura e Plano de Automação — VPN IPsec Site-to-Site (Palo Alto e FortiGate)

## 1. Visão Geral e Objetivo

Este documento detalha o desenho técnico, o planejamento lógico e as lições aprendidas durante o desenvolvimento da esteira de automação em Python para provisionamento, reversão (*rollback*), validação de conectividade e backup de uma **VPN IPsec Route-Based (IKEv2)** entre um firewall **Palo Alto (PAN-OS)** e um firewall **Fortinet FortiGate (FortiOS)**.

Diferente de abordagens baseadas puramente em chamadas REST/XML via SDKs externos, a solução implementada neste projeto adota uma arquitetura desacoplada baseada em **CLI declarativa via SSH (`Netmiko` e `Paramiko`)**, separando os arquivos de configuração base (`.cfg`) da lógica de orquestração em Python. Essa estrutura garante transparência total dos comandos executados, facilidade de auditoria e reversibilidade determinística.

---

## 2. Topologia de Referência do Laboratório

O ambiente foi estruturado em laboratório virtualizado (EVE-NG/KVM), isolando o tráfego de gerência (*Out-of-Band*) dos enlaces de trânsito WAN e das sub-redes LAN protegidas.

![[arquitetura_e_plano_de_automa_o_vpn_ipsec.png]]
### 2.1 Matriz de Endereçamento e Interfaces

| Camada / Função | Parâmetro | FortiGate (`192.168.0.251`) | Palo Alto (`192.168.0.252`) |
| :--- | :--- | :--- | :--- |
| **Gerência (OOB)** | Interface / IP | `port1` (`192.168.0.251/24`) | `mgmt` (`192.168.0.252/24`) |
| **Trânsito WAN** | Interface / IP | `port2` (`172.16.100.1/30`) | `ethernet1/2` (`172.16.100.2/30`) |
| **Sub-rede LAN** | Interface / Rede | `port3` (`10.0.10.0/24` - GW `.1`) | `ethernet1/1` (`10.0.20.0/24` - GW `.1`) |
| **Túnel Lógico** | Interface Virtual | `palo-alto` (gerada pela Phase 1) | `tunnel.1` (associada à `zone-vpn`) |
| **Roteamento** | Destino Remoto | `10.0.20.0/24` via `palo-alto` | `10.0.10.0/24` via `tunnel.1` (`nh: 172.16.100.1`) |

---

## 3. Parâmetros Criptográficos e Negociação (IKEv2 / IPsec)

Para assegurar interoperabilidade estrita entre os dois fabricantes sem falhas de negociação de propostas (*Proposal Mismatch*), ambos os lados foram padronizados com os parâmetros abaixo:

### 3.1 Fase 1 — IKE Gateway (`IKEv2`)
* **Versão do Protocolo:** IKEv2 nativo.
* **Método de Autenticação:** Chave Pré-Compartilhada (*Pre-Shared Key* - PSK) em texto claro nos templates de automação.
* **Criptografia:** `DES` (adequado às restrições de imagem de avaliação/laboratório sem licença de criptografia forte).
* **Integridade (Hash):** `SHA-256`.
* **Grupo Diffie-Hellman:** `Group 14` (2048-bit).
* **Tempo de Vida (Lifetime):** `28800 segundos` (8 horas).
* **Dead Peer Detection (DPD):** Habilitado.

### 3.2 Fase 2 — IPsec Tunnel & Seletores (`Proxy-IDs`)
* **Protocolo de Encapsulamento:** ESP (*Encapsulating Security Payload*).
* **Criptografia / Autenticação:** `DES` / `SHA-256`.
* **PFS (Perfect Forward Secrecy):** Habilitado — `Group 14`.
* **Tempo de Vida (Lifetime):** `3600 segundos` (1 hora).
* **Seletores de Tráfego (Proxy-IDs):** Explicitamente amarrados às sub-redes locais e remotas (`10.0.10.0/24` $\leftrightarrow$ `10.0.20.0/24`) em ambos os equipamentos, garantindo simetria exata na tabela de SAs.

---

## 4. Arquitetura da Esteira de Automação

A solução foi dividida em **modelos declarativos de configuração (`config/`)** e **orquestradores em Python (`scripts/`)**, permitindo evolução independente dos comandos de rede e da lógica de execução.

### 4.1 Tecnologias e Bibliotecas Utilizadas
* **Python 3.11+:** Linguagem base para toda a orquestração e tratamento de exceções.
* **Netmiko (`paloalto_panos` e `fortinet`):** Utilizado para envio de lotes de configuração (`send_config_set`), commits transacionais no PAN-OS, rollbacks e execução de comandos operacionais.
* **Paramiko (SSH Channel Direto):** Adotado especificamente no módulo de backup do Palo Alto (`2.6.backup_paloalto.py`) para contornar limitações de driver de transferência de arquivos no PAN-OS, capturando o fluxo XML bruto da *running-configuration*.
* **TQDM:** Feedback visual em tempo real com barras de progresso e telemetria de etapas no terminal.

### 4.2 Fluxo de Execução Modular

1. **Provisionamento Base LAN (`1.1` e `1.2` + Auditoria `1.3`):** Configura interfaces físicas, zonas de segurança (`zone-lan`, `zone_wan`), perfis de gerenciamento (`PERMITE_PING`) e valida a conformidade inicial.
2. **Deploy VPN IPsec (`2.1.deploy_paloalto_vpn.py` e `2.2.depoly_fortigate_vpn.py`):** Injeta os perfis criptográficos, gateways IKE, túneis IPsec, rotas estáticas (incluindo rota *blackhole* de contingência com distância `254` no FortiGate) e políticas de segurança bidirecionais.
3. **Rollback Transacional (`2.3.rollback_paloalto_vpn.py` e `2.4.rollback_fortigate_vpn.py`):** Remove cirurgicamente toda a configuração de VPN em ordem inversa de dependência, devolvendo os firewalls ao estado limpo sem afetar o acesso de gerência.
4. **Validação de Saúde Fim-a-Fim (`2.5.validate_vpn_connectivity.py`):** Audita o *Control Plane* (SAs IKEv2 estabelecidas e túneis ativos) e o *Data Plane* (disparo real de pacotes ICMP originados das interfaces LAN `10.0.10.1` e `10.0.20.1`).
5. **Persistência e Backup (`2.6.backup_paloalto.py` e `2.7.backup_fortigate.py`):** Extrai snapshots completos das configurações ativas em formatos nativos (`.xml` para Palo Alto e `.conf` para FortiGate), versionados por *timestamp* no diretório `part2_vpn_ipsec/backup/`.

---

## 5. Desafios Técnicos e Soluções de Interoperabilidade (Lições Aprendidas)

Durante os testes de integração entre o código Python e as instâncias virtuais no laboratório, foram identificados comportamentos críticos específicos de cada sistema operacional que exigiram ajustes na arquitetura dos scripts:

### 5.1 Particularidades do FortiGate (FortiOS)
* **Criação Implícita da Interface de Túnel:** No FortiOS, não se deve declarar manualmente uma interface com `set type tunnel` dentro de `config system interface` (o que gera erro de sintaxe exigindo `vlanid`). Ao configurar o bloco `config vpn ipsec phase1-interface`, o sistema cria automaticamente a interface lógica homônima (`palo-alto`).
* **Tratamento de PSK em Texto Claro vs. Hash:** Ao reutilizar trechos de backups `.conf` para automação, strings criptografadas longas (`ENC ...`) ultrapassam o limite de caracteres aceito pela CLI para senhas em texto plano, causando falha silenciosa (`Command fail. Return code -56`). A automação foi padronizada para injetar a chave limpa em texto plano.
* **Prompts Interativos no Rollback (`purge`):** O uso do comando `purge` dentro de tabelas como `config firewall policy` dispara uma confirmação interativa (`Do you want to continue? (y/n)`), desalinhando o buffer do Netmiko e gerando erros de dependência em cascata (`Return code -23`). O rollback foi refatorado para excluir regras por ID específico (`delete 1`, `delete 2`) e seguir a ordem estrita de baixo para cima (Políticas $\rightarrow$ Rotas $\rightarrow$ Fase 2 $\rightarrow$ Fase 1 $\rightarrow$ Grupos $\rightarrow$ Endereços) com `fast_cli=False`.

### 5.2 Particularidades do Palo Alto (PAN-OS)
* **Referência CIDR no `local-address` do IKE Gateway:** O PAN-OS rejeita a configuração de `local-address ip 172.16.100.2` se o endereço não incluir exatamente a máscara configurada na interface física (`172.16.100.2/30`), retornando `Server error: local-address -> ip is not a valid reference`.
* **Sincronismo de Buffer e Commits:** O envio acelerado de comandos (`fast_cli=True`) fazia o parser avaliar dependências antes da indexação interna do XML candidato. Desativar o `fast_cli` e utilizar o método dedicado `net_connect.commit()` garantiu 100% de consistência nas aplicações.
* **Extração de Backup XML sem SCP Nativo:** Como o driver `paloalto_panos` do Netmiko não implementa o método `file_transfer` via SCP, o script `2.6.backup_paloalto.py` foi arquitetado diretamente sobre o **Paramiko** (`invoke_shell`), forçando `set cli config-output-format xml` e capturando o *running-config* completo diretamente do buffer SSH.

---

## 6. Estratégia de Validação e Diagnóstico

A validação automatizada (`2.5.validate_vpn_connectivity.py`) atua em duas camadas complementares para evitar falsos positivos:

1. **Verificação do Plano de Controle (Control Plane):**
   * **Palo Alto:** Executa `show vpn ike-sa gateway Fortinet` e `show vpn ipsec-sa tunnel Fortinet`, validando o estado `Established` na Fase 1 e a presença de SAs ativas (`Mature`) na Fase 2.
   * **FortiGate:** Executa `get vpn ipsec tunnel summary`, confirmando que o túnel `palo-alto` está ativo com seletores operacionais (`selectors(total,up): 1/1`).
2. **Verificação do Plano de Dados (Data Plane):**
   * Força o tráfego ICMP a sair especificamente pelas sub-redes internas protegidas (`10.0.20.1` $\rightarrow$ `10.0.10.1` e vice-versa via `execute ping-options source 10.0.10.1`), garantindo que os pacotes atravessem o encapsulamento IPsec e validando **0% de perda de pacotes**.
#!/bin/bash

echo "=================================================="
echo "  NetOps Portal - Inicializador do Laboratório    "
echo "=================================================="

# 1. Detecta o IP local ativo na rede (Raspberry Pi / Linux)
LOCAL_IP=$(hostname -I | awk '{print $1}')
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="127.0.0.1"
fi

export PORTAL_IP="$LOCAL_IP"
export PORTAL_PORT="5000"

echo "[*] IP Detectado para o Portal: http://$LOCAL_IP:$PORTAL_PORT"

# 2. Verifica se o ambiente virtual (venv) existe
if [ ! -d "venv" ]; then
    echo "[*] Criando ambiente virtual 'venv'..."
    python3 -m venv venv
fi

# 3. Ativa o ambiente virtual e instala dependências
echo "[*] Ativando ambiente virtual e verificando dependências..."
source venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1
pip install flask flask-socketio netmiko markdown gevent simple-websocket > /dev/null 2>&1

# 4. Garante a existência da pasta de backups
mkdir -p part1_cisco_switch/backups

# 5. Inicia a aplicação Flask
echo "--------------------------------------------------"
echo "[+] Servidor rodando! Acesse: http://$LOCAL_IP:$PORTAL_PORT"
echo "--------------------------------------------------"

python part1_cisco_switch/app.py
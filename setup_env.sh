#!/bin/bash

echo "=================================================="
echo "  NetOps Portal - Configuração do Ambiente Ubuntu "
echo "=================================================="

# Garante que o python3-venv e pip estão instalados no sistema
echo "[*] Verificando pacotes do sistema Python..."
sudo apt update && sudo apt install -y python3-venv python3-pip python3-dev

# Cria o ambiente virtual se ele não existir
if [ ! -d "venv" ]; then
    echo "[*] Criando o ambiente virtual (venv)..."
    python3 -m venv venv
else
    echo "[+] Ambiente virtual 'venv' já existe."
fi

# Ativa o venv e instala as dependências
echo "[*] Ativando o venv e instalando dependências..."
source venv/bin/activate

pip install --upgrade pip
pip install flask flask-socketio netmiko markdown

echo "--------------------------------------------------"
echo "[+] Ambiente configurado com sucesso!"
echo "[+] Para iniciar o portal, execute: ./start.sh"
echo "--------------------------------------------------"
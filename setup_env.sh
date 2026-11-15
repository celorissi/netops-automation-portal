#!/bin/bash
set -e

echo "=================================================="
echo "  NetOps Portal - Setup Automatizado de Ambiente  "
echo "=================================================="

# Verifica se python3.11 está disponível, senão usa python3 padrão
if command -v python3.11 &> /dev/null; then
    PYTHON_BIN="python3.11"
else
    PYTHON_BIN="python3"
fi

echo "[*] Usando interpretador: $($PYTHON_BIN --version)"

if [ -d "venv" ]; then
    echo "[*] Removendo ambiente virtual antigo..."
    rm -rf venv
fi

echo "[*] Criando ambiente virtual (venv)..."
$PYTHON_BIN -m venv venv
source venv/bin/activate

echo "[*] Atualizando pip e instalando dependências homologadas..."
pip install --upgrade pip
pip install "paramiko==3.4.0" "netmiko>=4.3.0" flask flask-socketio markdown

chmod +x start.sh setup_env.sh

echo "=================================================="
echo "[+] Ambiente configurado com sucesso!"
echo "[+] Para iniciar o portal, execute: ./start.sh"
echo "=================================================="
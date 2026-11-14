#!/bin/bash

echo "=================================================="
echo "  Git Auto-Update - Enviando alterações          "
echo "=================================================="

# 1. Exibe o status atual dos arquivos
echo "[*] Verificando alterações no repositório..."
git status
echo "--------------------------------------------------"

# 2. Solicita a mensagem do commit ao usuário (ou usa uma padrão se vazio)
read -p "Digite a mensagem do commit (Padrão: 'update: atualiza automações e portal'): " COMMIT_MSG

if [ -z "$COMMIT_MSG" ]; then
    COMMIT_MSG="update: atualiza automações e portal"
fi

# 3. Adiciona todos os arquivos modificados/novos
echo "[*] Adicionando arquivos (git add .)..."
git add .

# 4. Realiza o commit
echo "[*] Realizando commit: \"$COMMIT_MSG\"..."
git commit -m "$COMMIT_MSG"

# 5. Envia para o repositório remoto (detectando a branch atual)
CURRENT_BRANCH=$(git branch --show-current)
if [ -z "$CURRENT_BRANCH" ]; then
    CURRENT_BRANCH="main"
fi

echo "[*] Enviando para o GitHub (branch: $CURRENT_BRANCH)..."
git push origin "$CURRENT_BRANCH"

echo "--------------------------------------------------"
echo "[+] Repositório atualizado com sucesso no GitHub!"
echo "=================================================="
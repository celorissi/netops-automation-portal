#!/bin/bash
echo "=================================================="
echo "  Git Auto-Update - Enviando alterações           "
echo "=================================================="
echo "[*] Sincronizando com o GitHub (git pull)..."
git pull origin main --no-rebase --no-edit || { echo "❌ Erro ao sincronizar. Resolva os conflitos antes de continuar."; exit 1; }

echo "[*] Verificando alterações no repositório..."
git status
echo "--------------------------------------------------"
read -p "Digite a mensagem do commit (Padrão: 'update: atualiza automações e portal'): " MSG
MSG=${MSG:-"update: atualiza automações e portal"}

echo "[*] Adicionando arquivos (git add .)..."
git add .

if ! git diff-index --quiet HEAD --; then
    echo "[*] Realizando commit: \"$MSG\"..."
    git commit -m "$MSG"
else
    echo "[*] Nenhuma alteração nova para commitar."
fi

echo "[*] Enviando para o GitHub (branch: main)..."
git push origin main || { echo "❌ Erro ao enviar para o GitHub!"; exit 1; }

echo "--------------------------------------------------"
echo "[+] Repositório atualizado com sucesso no GitHub!"
echo "=================================================="

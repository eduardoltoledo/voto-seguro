#!/bin/bash
# Restauração manual (desastre):  docker compose run --rm --entrypoint /restaurar.sh backup /backups/voto-AAAAMMDDTHHMMSSZ.dump
# Restaura em um banco NOVO ("voto_restaurado"); depois aponte a API para ele ou promova-o conforme o plano de contingência.
set -euo pipefail
[ $# -eq 1 ] || { echo "uso: $0 <arquivo.dump>"; exit 1; }
export PGPASSWORD="${POSTGRES_PASSWORD}"
sha256sum -c "$1.sha256"
psql -h db-primary -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE voto_restaurado"
pg_restore -h db-primary -U "$POSTGRES_USER" -d voto_restaurado --no-owner "$1"
echo "OK: banco voto_restaurado criado. Verifique a integridade com a API (/auditoria/verificar) antes de usar."

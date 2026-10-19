#!/bin/bash
# Backup automático com TESTE DE RESTAURAÇÃO a cada ciclo.
#  1. pg_dump (formato custom) do primário
#  2. restaura o dump em um banco temporário
#  3. compara a contagem de linhas das tabelas críticas com a origem
#  4. descarta o banco temporário e aplica retenção
set -uo pipefail
export PGPASSWORD="${POSTGRES_PASSWORD}"
HOST=db-primary; U="${POSTGRES_USER}"; DB="${POSTGRES_DB}"
INTERVALO="${BACKUP_INTERVAL_SECONDS:-3600}"; RETENCAO="${BACKUP_RETENTION:-24}"
DIR=/backups; mkdir -p "$DIR"
TABELAS="voto log_auditoria eleitor token_votacao candidato sessao_votacao"

contar() { psql -h "$HOST" -U "$U" -d "$1" -Atc "SELECT count(*) FROM $2" 2>/dev/null; }

ciclo() {
  local ts arq tmp="restore_check"
  ts=$(date -u +%Y%m%dT%H%M%SZ); arq="$DIR/voto-$ts.dump"
  echo "[backup] $ts: gerando $arq"
  pg_dump -h "$HOST" -U "$U" -d "$DB" -Fc -f "$arq.parcial" || { echo "[backup] FALHA no pg_dump"; rm -f "$arq.parcial"; return 1; }
  mv "$arq.parcial" "$arq"; sha256sum "$arq" > "$arq.sha256"

  echo "[backup] testando restauração em banco temporário"
  psql -h "$HOST" -U "$U" -d postgres -qc "DROP DATABASE IF EXISTS $tmp" -c "CREATE DATABASE $tmp" || return 1
  pg_restore -h "$HOST" -U "$U" -d "$tmp" --no-owner "$arq" >/dev/null 2>&1
  local ok=1 t a b
  for t in $TABELAS; do
    a=$(contar "$DB" "$t"); b=$(contar "$tmp" "$t")
    if [ "$a" != "$b" ]; then echo "[backup] DIVERGÊNCIA em $t: origem=$a restaurado=$b"; ok=0; fi
  done
  psql -h "$HOST" -U "$U" -d postgres -qc "DROP DATABASE IF EXISTS $tmp"
  if [ $ok = 1 ]; then echo "[backup] restauração verificada: OK"; echo "$ts OK" > "$DIR/ULTIMO_TESTE"
  else echo "[backup] RESTAURAÇÃO INVÁLIDA"; echo "$ts FALHOU" > "$DIR/ULTIMO_TESTE"; fi
  ls -1t "$DIR"/voto-*.dump 2>/dev/null | tail -n +$((RETENCAO + 1)) | while read -r velho; do rm -f "$velho" "$velho.sha256"; done
}

until pg_isready -h "$HOST" -U "$U" -q; do sleep 2; done
sleep 20   # deixa o init-db criar o esquema
while true; do ciclo; sleep "$INTERVALO"; done

#!/bin/bash
# Standby: clona o primário (pg_basebackup -R) e sobe em modo hot_standby (somente leitura).
set -e
export PGDATA="${PGDATA:-/var/lib/postgresql/data}"
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  echo "[replica] aguardando o primário..."
  until pg_isready -h db-primary -p 5432 -U replicator -q; do sleep 2; done
  mkdir -p "$PGDATA" && chown postgres:postgres "$PGDATA" && chmod 700 "$PGDATA"
  echo "[replica] clonando o primário (pg_basebackup)..."
  PGPASSWORD="$REPLICATION_PASSWORD" gosu postgres pg_basebackup \
      -h db-primary -p 5432 -U replicator -D "$PGDATA" -X stream -R -S replica1_slot -P
fi
exec docker-entrypoint.sh postgres -c hot_standby=on -c listen_addresses='*'

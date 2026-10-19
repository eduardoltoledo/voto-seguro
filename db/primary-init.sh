#!/bin/bash
# Executado uma vez, na criação do banco primário (docker-entrypoint-initdb.d).
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<SQL
-- conta usada pela replicação
CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '${REPLICATION_PASSWORD}';
SELECT pg_create_physical_replication_slot('replica1_slot');
-- conta da API: sem superusuário, sem CREATE; privilégios finos são aplicados pelo init-db
CREATE ROLE ${APP_DB_USER} LOGIN PASSWORD '${APP_DB_PASSWORD}' NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${APP_DB_USER};
SQL
echo "host replication replicator all scram-sha-256" >> "$PGDATA/pg_hba.conf"

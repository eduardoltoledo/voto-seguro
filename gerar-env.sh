#!/bin/sh
# Gera .env com segredos aleatórios. Usa só /dev/urandom, base64 e tr (funciona no Git Bash, Linux e macOS; não precisa de Python).
# Não sobrescreve um .env existente: apague-o antes se quiser gerar de novo.
set -e
cd "$(dirname "$0")"
if [ -e .env ]; then
  if grep -E '^(POSTGRES_PASSWORD|REPLICATION_PASSWORD|APP_DB_PASSWORD|AES_KEY|INDEX_KEY|JWT_KEY|BOLETIM_KEY)=$' .env >/dev/null 2>&1; then
    echo "O .env existente está INCOMPLETO (segredos vazios). Guardando como .env.quebrado e gerando um novo."
    mv .env .env.quebrado
  else
    echo ".env já existe e está preenchido; nada a fazer (apague-o com 'rm .env' para gerar outro)."
    exit 0
  fi
fi

chave() { head -c 32 /dev/urandom | base64 | tr -d '\n'; }                  # 32 bytes em base64
senha() { LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32; }       # alfanumérica (segura em URLs)

for v in AES_KEY INDEX_KEY JWT_KEY BOLETIM_KEY; do eval "$v=\$(chave)"; done
PG=$(senha); REPL=$(senha); APP=$(senha)
[ -n "$AES_KEY" ] && [ -n "$PG" ] || { echo "ERRO: não foi possível gerar segredos (/dev/urandom ou base64 indisponíveis)."; exit 1; }

cat > .env <<EOT
POSTGRES_USER=voto_owner
POSTGRES_PASSWORD=$PG
POSTGRES_DB=votacao
REPLICATION_PASSWORD=$REPL
APP_DB_USER=voto_app
APP_DB_PASSWORD=$APP
AES_KEY=$AES_KEY
INDEX_KEY=$INDEX_KEY
JWT_KEY=$JWT_KEY
BOLETIM_KEY=$BOLETIM_KEY
SEED_DEMO=true
HTTPS_PORT=8443
HTTP_PORT=8080
BACKUP_INTERVAL_SECONDS=3600
EOT
chmod 600 .env 2>/dev/null || true
echo ".env criado. Agora: docker compose up --build"

#!/bin/sh
# Gera um certificado AUTOASSINADO para demonstração, se nenhum for montado em /etc/nginx/certs.
# Em produção: monte um certificado real (ex.: Let's Encrypt) em /etc/nginx/certs/{server.crt,server.key}.
set -e
mkdir -p /etc/nginx/certs
if [ ! -s /etc/nginx/certs/server.crt ]; then
  echo "[edge] gerando certificado autoassinado (somente demonstração)"
  openssl req -x509 -newkey rsa:3072 -nodes -days 365 -sha256 \
    -keyout /etc/nginx/certs/server.key -out /etc/nginx/certs/server.crt \
    -subj "/CN=localhost/O=Voto Seguro (demo)" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
  chmod 600 /etc/nginx/certs/server.key
fi

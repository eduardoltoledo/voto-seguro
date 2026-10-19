# --- build do frontend React
FROM node:22-alpine AS build
WORKDIR /app
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- Nginx: balanceador, TLS 1.3, cabeçalhos de segurança, rate limiting e arquivos estáticos
FROM nginx:1.27-alpine
RUN apk add --no-cache openssl
COPY edge/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY edge/proxy_api.conf edge/seguranca.conf /etc/nginx/
COPY --chmod=755 edge/10-gerar-certificado.sh /docker-entrypoint.d/10-gerar-certificado.sh
RUN sed -i 's/\r$//' /docker-entrypoint.d/10-gerar-certificado.sh /etc/nginx/*.conf /etc/nginx/templates/*.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80 443

# Voto Seguro – Eleições Presidenciais 2026

Sistema de votação eletrônica web (projeto acadêmico de **Segurança e Auditoria de Sistemas – UNOESC**).
Candidatos, eleitores e a base "TSE" são **fictícios**. Documentação completa: [`docs/DOCUMENTACAO_TECNICA.md`](docs/DOCUMENTACAO_TECNICA.md).

**Stack:** React (SPA) · FastAPI (Python) · PostgreSQL com streaming replication · JWT curto + refresh + MFA (TOTP) · Docker · Nginx (TLS 1.3, balanceador).

## Como executar (Docker)

Requisitos: **Docker Desktop** (Windows/Mac) ou Docker Engine + Compose. Não precisa de Python nem Node na sua máquina.
No Windows, rode os comandos no **Git Bash** (ou WSL). Se o Docker Desktop pedir, ative o backend WSL 2.


```bash
./gerar-env.sh                 # cria .env com segredos aleatórios (se já existir um .env quebrado: rm .env)
docker compose up --build      # sobe tudo (primeira vez demora: build do frontend)
```

Abra **https://localhost:8443** (certificado autoassinado: aceite o aviso do navegador).
Documentação interativa da API: https://localhost:8443/api/docs

Subiram: `edge` (Nginx + SPA), `backend1` e `backend2` (API), `db-primary` e `db-replica` (PostgreSQL),
`init-db` (cria esquema/privilégios e termina) e `backup` (backup + teste de restauração a cada hora).

### Contas de demonstração (`SEED_DEMO=true`)

Senha de todas: `Demo@Seguro2026!`. O segredo TOTP é **fixo e público de propósito** (só na demo) para dispensar celular:

| Perfil | Login | Segredo TOTP (base32) |
|---|---|---|
| Eleitores 0, 1, 2 | CPFs da tabela abaixo | `MFRGGZDFMZTWQ2LKMFRGGZDFMZTWQ2LK` |
| Mesário (ADMIN) | `mesario` | `JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP` |
| Fiscal (AUDITOR) | `fiscal` | `KRSXG5CTMVRXEZLUKRSXG5CTMVRXEZLU` |

Para gerar o código de 6 dígitos sem aplicativo (a partir da raiz do projeto):

```bash
docker compose exec backend1 python -c "from app import totp; print(totp.codigo_atual('JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP'))"
```

Base TSE simulada:

| i | CPF | Título | Situação |
|---|---|---|---|
| 0 | `111.222.330-43` | `100000000000` | cadastrado |
| 1 | `111.222.331-24` | `100000000001` | cadastrado |
| 2 | `111.222.332-05` | `100000000002` | cadastrado |
| 3 | `111.222.333-96` | `100000000003` | livre para cadastrar |
| 4 | `111.222.334-77` | `100000000004` | livre para cadastrar |
| 5 | `111.222.335-58` | `100000000005` | livre para cadastrar |
| 6 | `111.222.336-39` | `100000000006` | livre para cadastrar |
| 7 | `111.222.337-10` | `100000000007` | SUSPENSO (cadastro recusado) |

Os eleitores `3..6` podem usar a tela **Cadastro** (informando CPF + título + uma senha nova).
Em produção real use `SEED_DEMO=false` e `docker compose run --rm backend1 python -m scripts.criar_admin ...`.

### Demonstração de fraude (seminário)

```bash
docker compose --profile demo run --rm demo-fraude
```

Mostra: voto duplicado recusado e registrado, reuso de token recusado, **adulteração direta no banco detectada** pela
recontagem de hashes (com a posição exata) e a restauração. Detalhes na seção 6 da documentação.

### Redundância

```bash
docker compose stop backend1            # a API segue respondendo via backend2 (veja Monitoramento)
docker compose stop db-replica          # leituras voltam automaticamente para o primário
docker compose exec backup ls /backups  # dumps; cat /backups/ULTIMO_TESTE mostra o resultado do teste de restauração
```

## Testes

```bash
cd backend && python3 -m unittest tests.test_core -v          # núcleo (sem dependências além de `cryptography`)
docker compose run --rm --no-deps backend1 python -m unittest tests.test_api -v   # integração da API
```

## Estrutura

```
backend/    API FastAPI (app/), scripts operacionais (scripts/), testes (tests/)
frontend/   SPA React (Vite)
edge/       Nginx: TLS 1.3, balanceamento, rate limiting, CSP/HSTS (+ build do frontend)
db/         inicialização do primário e do standby (streaming replication)
backup/     backup automático + teste de restauração + restauração manual
docs/       documentação técnica
```

## Status de validação

Validado neste repositório: testes do núcleo criptográfico/cadeias de hash (inclui vetor oficial da RFC 6238),
compilação de todo o Python, compilação e execução da SPA em Chromium (telas de eleitor/mesário/fiscal/monitor com API simulada),
validação sintática do `docker-compose.yml` e dos scripts shell.
**Não foi possível executar `docker compose up` nem os testes de integração da API no ambiente em que o código foi escrito**
(sem daemon Docker nem acesso ao PyPI). Rode o passo a passo acima e os testes de integração; se algo falhar, os logs
(`docker compose logs <serviço>`) indicam a causa.

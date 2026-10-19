"""Demonstração de detecção de fraude para o seminário.

Cenários (rodar com a API no ar e SEED_DEMO=true; DATABASE_URL aponta para o banco):
  1. voto duplicado     -> a API recusa e registra TENTATIVA_VOTO_DUPLICADO
  2. reuso de token     -> recusado e registrado
  3. adulteração no BD  -> um DBA malicioso troca o candidato de um voto; a verificação aponta a posição
  4. restauração        -> desfaz a adulteração e a cadeia volta a ficar íntegra

Uso: python -m scripts.demo_fraude [URL_DA_API]   (padrão http://backend1:8000)
"""
import sys

import httpx
from sqlalchemy import text

from app import totp
from app.database import engine
from app.seed import SEGREDO_AUDITOR, SEGREDO_ELEITORES, SENHA_DEMO, cpf_demo

API = (sys.argv[1] if len(sys.argv) > 1 else "http://backend1:8000").rstrip("/")
http = httpx.Client(base_url=API, timeout=10, follow_redirects=False)


def titulo(t):
    print(f"\n=== {t} ===")


def login(perfil, ident, segredo):
    r = http.post("/auth/login", json={"perfil": perfil, "identificador": ident, "senha": SENHA_DEMO})
    r.raise_for_status()
    # evita o anti-replay: espera o próximo passo de 30 s se o código atual já foi usado
    import time
    for _ in range(2):
        r2 = http.post("/auth/mfa", json={"mfa_token": r.json()["mfa_token"], "codigo": totp.codigo_atual(segredo)})
        if r2.status_code == 200:
            return {"Authorization": "Bearer " + r2.json()["access_token"]}
        time.sleep(31)
    r2.raise_for_status()


def verificar(h):
    v = http.get("/auditoria/verificar", headers=h).json()
    for s in v["sessoes"]:
        c = s["cadeia_votos"]
        print(f"  sessão {s['sessao_id']}: cadeia de votos {'ÍNTEGRA' if c['ok'] else 'QUEBRADA em seq=' + str(c['quebra_em_seq'])}"
              f" ({c['motivo'] or 'ok'}), total={c['total']}")
    print("  cadeia de logs:", "ÍNTEGRA" if v["cadeia_logs"]["ok"] else "QUEBRADA")
    return v


h_el = login("eleitor", cpf_demo(0), SEGREDO_ELEITORES)
h_fiscal = login("admin", "fiscal", SEGREDO_AUDITOR)

titulo("1. Eleitor vota normalmente")
tok = http.post("/votacao/token", headers=h_el)
print("  token:", tok.status_code)
if tok.status_code == 200:
    cands = http.get("/votacao/candidatos").json()["candidatos"]
    rv = http.post("/votacao/votar", json={"token": tok.json()["token"], "tipo": "candidato", "candidato_id": cands[0]["id"]})
    print("  voto:", rv.status_code, "posição", rv.json().get("posicao"))
    token_usado = tok.json()["token"]
else:
    token_usado = None
    print("  (eleitor demo já votou antes; seguindo)")

titulo("2. Fraude: o mesmo eleitor tenta votar de novo")
r = http.post("/votacao/token", headers=h_el)
print("  resposta:", r.status_code, r.json().get("detail"))

titulo("3. Fraude: reutilizar o token já consumido")
if token_usado:
    r = http.post("/votacao/votar", json={"token": token_usado, "tipo": "branco"})
    print("  resposta:", r.status_code, r.json().get("detail"))

titulo("4. Eventos registrados no log de auditoria")
for e in http.get("/auditoria/logs?limite=6", headers=h_fiscal).json():
    print(f"  #{e['seq']} {e['evento']} {e['detalhes']}")

titulo("5. Integridade ANTES da adulteração")
verificar(h_fiscal)

titulo("6. Adulteração direta no banco (atacante com acesso privilegiado)")
with engine.begin() as c:
    alvo = c.execute(text("SELECT id, seq, candidato_id FROM voto ORDER BY seq LIMIT 1")).first()
    if alvo is None:
        raise SystemExit("sem votos para adulterar")
    if engine.dialect.name == "postgresql":
        c.execute(text("ALTER TABLE voto DISABLE TRIGGER voto_append_only"))  # exige ser dono da tabela
    else:
        c.execute(text("DROP TRIGGER IF EXISTS voto_no_update"))
    c.execute(text("UPDATE voto SET candidato_id = (SELECT id FROM candidato WHERE id <> :a LIMIT 1) WHERE id = :i"),
              {"a": alvo.candidato_id or -1, "i": alvo.id})
print(f"  voto na posição {alvo.seq} alterado direto no banco")

titulo("7. Integridade DEPOIS da adulteração")
verificar(h_fiscal)

titulo("8. Restaurando o estado original")
with engine.begin() as c:
    c.execute(text("UPDATE voto SET candidato_id = :c WHERE id = :i"), {"c": alvo.candidato_id, "i": alvo.id})
    if engine.dialect.name == "postgresql":
        c.execute(text("ALTER TABLE voto ENABLE TRIGGER voto_append_only"))
    else:
        c.execute(text("CREATE TRIGGER IF NOT EXISTS voto_no_update BEFORE UPDATE ON voto "
                       "BEGIN SELECT RAISE(ABORT, 'tabela voto é append-only'); END"))
verificar(h_fiscal)

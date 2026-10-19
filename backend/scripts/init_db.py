"""Cria o esquema (uma vez) e, se SEED_DEMO=true, os dados de demonstração.
Executado pelo serviço `init-db` do docker compose antes das instâncias do backend."""
import os
import sys
import time
import traceback

from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal, engine
from app.schema import inicializar


def etapa(nome, fn):
    print(f"[init-db] {nome}...", flush=True)
    try:
        fn()
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        print(f"[init-db] ERRO na etapa '{nome}': {type(e).__name__}: {e}", flush=True)
        sys.exit(1)
    print(f"[init-db] {nome}: ok", flush=True)


def aguardar_banco():
    ultimo = None
    for tentativa in range(90):
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            return
        except Exception as e:  # noqa: BLE001
            ultimo = e
            if tentativa % 5 == 0:
                print(f"[init-db] aguardando banco ({tentativa + 1}/90): {type(e).__name__}", flush=True)
            time.sleep(2)
    raise RuntimeError(f"banco indisponível (último erro: {ultimo})")


def seed():
    from app.seed import popular_demo
    with SessionLocal() as db:
        popular_demo(db)


etapa("conectar ao banco", aguardar_banco)
etapa("criar esquema, gatilhos append-only e privilégios", lambda: inicializar(engine, os.getenv("APP_DB_USER") or None))
if settings.SEED_DEMO:
    etapa("carregar dados de demonstração", seed)
print("[init-db] concluído", flush=True)

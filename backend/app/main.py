from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .config import settings
from .database import SessionLocal, engine
from .routers import admin, auditoria, auth, monitor, votacao


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Em PostgreSQL o esquema é criado uma única vez pelo serviço `init-db` (evita corrida entre instâncias).
    if settings.DATABASE_URL.startswith("sqlite"):
        from .schema import inicializar
        inicializar(engine)
        if settings.SEED_DEMO:
            from .seed import popular_demo
            with SessionLocal() as db:
                popular_demo(db)
    yield


app = FastAPI(title="Voto Seguro - API", version="1.0.0", lifespan=lifespan, root_path="/api",
              description="Sistema de votação eletrônica (projeto acadêmico - Segurança e Auditoria de Sistemas).")


@app.middleware("http")
async def cabecalhos_seguranca(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("Cache-Control", "no-store")
    resp.headers["X-Instance-Id"] = settings.INSTANCE_ID  # útil para demonstrar o balanceamento
    return resp


@app.exception_handler(Exception)
async def erro_generico(request: Request, exc: Exception):
    # Nunca vazar stack trace/detalhes internos ao cliente.
    return JSONResponse({"detail": "Erro interno. Tente novamente."}, status_code=500)


@app.get("/saude", tags=["Monitoramento"])
def saude():
    """Health check usado pelo balanceador (consulta o banco)."""
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        return JSONResponse({"status": "indisponivel", "instancia": settings.INSTANCE_ID}, status_code=503)
    return {"status": "ok", "instancia": settings.INSTANCE_ID}


for r in (auth.router, votacao.router, admin.router, auditoria.router, monitor.router):
    app.include_router(r)

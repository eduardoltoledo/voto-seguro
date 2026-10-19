from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .config import settings


def _engine(url: str, **kw):
    if url.startswith("sqlite"):
        kw["connect_args"] = {"check_same_thread": False}
    return create_engine(url, pool_pre_ping=True, **kw)


engine = _engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

engine_ro = _engine(settings.DATABASE_REPLICA_URL) if settings.DATABASE_REPLICA_URL else None
SessionRO = sessionmaker(bind=engine_ro, autoflush=False) if engine_ro else None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_ro():
    """Leituras que toleram pequeno atraso usam a réplica; se ela cair, volta para a primária."""
    db = None
    if SessionRO is not None:
        try:
            db = SessionRO()
            db.execute(text("SELECT 1"))
        except Exception:
            if db is not None:
                db.close()
            db = None
    if db is None:
        db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def travar_cadeia(db, chave: int) -> None:
    """Serializa a escrita nas cadeias de hash (lock consultivo no PostgreSQL)."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": chave})


LOCK_VOTOS = 1001
LOCK_LOGS = 1002

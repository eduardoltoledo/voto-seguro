import os

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import text

from ..config import settings
from ..database import SessionLocal, SessionRO
from ..deps import Principal, exigir

router = APIRouter(prefix="/monitor", tags=["Monitoramento"])


def _sonda(fabrica, papel_esperado: str) -> dict:
    if fabrica is None:
        return {"configurado": False}
    try:
        with fabrica() as db:
            db.execute(text("SELECT 1"))
            out = {"configurado": True, "online": True}
            if db.get_bind().dialect.name == "postgresql":
                out["em_recuperacao"] = bool(db.scalar(text("SELECT pg_is_in_recovery()")))
                if papel_esperado == "primaria":
                    linhas = db.execute(text("SELECT application_name, state, "
                                             "COALESCE(EXTRACT(EPOCH FROM replay_lag),0) FROM pg_stat_replication")).all()
                    out["replicas"] = [{"nome": r[0], "estado": r[1], "atraso_s": round(float(r[2]), 3)} for r in linhas]
                else:
                    out["atraso_s"] = float(db.scalar(text(
                        "SELECT COALESCE(EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())),0)")) or 0)
            return out
    except Exception as e:  # noqa: BLE001
        return {"configurado": True, "online": False, "erro": type(e).__name__}


@router.get("/status")
def status(p: Principal = Depends(exigir("ADMIN", "AUDITOR"))):
    nos = []
    for url in [u.strip() for u in os.getenv("BACKEND_NODES", "").split(",") if u.strip()]:
        try:
            r = httpx.get(f"{url}/saude", timeout=2.0)
            nos.append({"url": url, "online": r.status_code == 200, **(r.json() if r.status_code == 200 else {})})
        except Exception as e:  # noqa: BLE001
            nos.append({"url": url, "online": False, "erro": type(e).__name__})
    return {"instancia_atual": settings.INSTANCE_ID, "nos_backend": nos,
            "banco_primario": _sonda(SessionLocal, "primaria"),
            "banco_replica": _sonda(SessionRO, "replica")}

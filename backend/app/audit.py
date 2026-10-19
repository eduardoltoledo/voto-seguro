"""Trilha de auditoria append-only com hash encadeado."""
import json
from datetime import datetime, timezone

from sqlalchemy import select

from . import chain
from .database import LOCK_LOGS, travar_cadeia
from .models import LogAuditoria


def registrar(db, evento: str, ator_tipo: str | None = None, ator_id: int | None = None,
              ip: str | None = None, detalhes: dict | None = None, commit: bool = True) -> None:
    """Acrescenta um evento à cadeia. NUNCA receber conteúdo de voto aqui.

    Faz commit por padrão: eventos de falha precisam persistir mesmo quando a requisição
    termina em erro HTTP. Chamadores com transação pendente que não deve ser confirmada
    devem fazer rollback() antes.
    """
    travar_cadeia(db, LOCK_LOGS)
    ultimo = db.scalar(select(LogAuditoria).order_by(LogAuditoria.seq.desc()).limit(1))
    seq = 1 if ultimo is None else ultimo.seq + 1
    prev = chain.GENESIS_LOGS if ultimo is None else ultimo.hash
    ts = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    det = json.dumps(detalhes or {}, sort_keys=True, ensure_ascii=False)
    h = chain.hash_log(seq, ts, evento, ator_tipo, ator_id, ip, det, prev)
    db.add(LogAuditoria(seq=seq, ts=ts, evento=evento, ator_tipo=ator_tipo, ator_id=ator_id,
                        ip=ip, detalhes=det, prev_hash=prev, hash=h))
    db.flush()
    if commit:
        db.commit()

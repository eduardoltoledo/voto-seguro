from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from .. import integridade
from ..database import get_db_ro
from ..deps import Principal, exigir
from ..models import Eleitor, LogAuditoria, SessaoVotacao, Voto

router = APIRouter(prefix="/auditoria", tags=["Auditoria"])
PODE_AUDITAR = exigir("AUDITOR", "ADMIN")


@router.get("/logs")
def logs(limite: int = Query(50, ge=1, le=500), antes_de_seq: int | None = None, evento: str | None = None,
         p: Principal = Depends(PODE_AUDITAR), db=Depends(get_db_ro)):
    q = select(LogAuditoria).order_by(LogAuditoria.seq.desc()).limit(limite)
    if antes_de_seq:
        q = q.where(LogAuditoria.seq < antes_de_seq)
    if evento:
        q = q.where(LogAuditoria.evento == evento)
    return [{"seq": x.seq, "ts": x.ts, "evento": x.evento, "ator_tipo": x.ator_tipo, "ator_id": x.ator_id,
             "ip": x.ip, "detalhes": x.detalhes, "hash": x.hash} for x in db.scalars(q)]


@router.get("/verificar")
def verificar(p: Principal = Depends(PODE_AUDITAR), db=Depends(get_db_ro)):
    """Recontagem de hashes: votos, logs, conciliação e âncora de fechamento."""
    return integridade.verificar_tudo(db)


@router.get("/relatorio")
def relatorio(p: Principal = Depends(PODE_AUDITAR), db=Depends(get_db_ro)):
    """Relatório para fiscais: totais por sessão, contagem de eventos e integridade."""
    eventos = dict(db.execute(select(LogAuditoria.evento, func.count()).group_by(LogAuditoria.evento)).all())
    sessoes = []
    for s in db.scalars(select(SessaoVotacao).order_by(SessaoVotacao.id)).all():
        total = db.scalar(select(func.count()).select_from(Voto).where(Voto.sessao_id == s.id))
        sessoes.append({"sessao_id": s.id, "titulo": s.titulo, "status": s.status,
                        "aberta_em": s.aberta_em.isoformat(),
                        "fechada_em": s.fechada_em.isoformat() if s.fechada_em else None,
                        "total_votos": total})
    return {"eleitores_cadastrados": db.scalar(select(func.count()).select_from(Eleitor)),
            "sessoes": sessoes, "eventos": eventos, "integridade": integridade.verificar_tudo(db)}

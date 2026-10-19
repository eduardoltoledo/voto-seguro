"""Verificação de integridade: cadeias de votos e de logs, conciliação e âncoras."""
import json

from sqlalchemy import func, select

from . import chain
from .models import Eleitor, LogAuditoria, SessaoVotacao, TokenVotacao, Voto


def _dict_voto(v: Voto) -> dict:
    return dict(seq=v.seq, sessao_id=v.sessao_id, candidato_id=v.candidato_id, nonce=v.nonce,
                recibo_hash=v.recibo_hash, prev_hash=v.prev_hash, hash=v.hash)


def _dict_log(x: LogAuditoria) -> dict:
    return dict(seq=x.seq, ts=x.ts, evento=x.evento, ator_tipo=x.ator_tipo, ator_id=x.ator_id,
                ip=x.ip, detalhes=x.detalhes, prev_hash=x.prev_hash, hash=x.hash)


def verificar_votos(db, sessao_id: int) -> chain.Resultado:
    q = select(Voto).where(Voto.sessao_id == sessao_id).order_by(Voto.seq)
    return chain.verificar_cadeia((_dict_voto(v) for v in db.scalars(q).yield_per(1000)),
                                  chain.calcular_voto, chain.genesis_votos(sessao_id))


def verificar_logs(db) -> chain.Resultado:
    q = select(LogAuditoria).order_by(LogAuditoria.seq)
    return chain.verificar_cadeia((_dict_log(x) for x in db.scalars(q).yield_per(1000)),
                                  chain.calcular_log, chain.GENESIS_LOGS)


def conciliar(db, sessao_id: int) -> dict:
    """Confere contagens SEM ligar identidade a voto: votos == tokens usados."""
    votos = db.scalar(select(func.count()).select_from(Voto).where(Voto.sessao_id == sessao_id))
    emitidos = db.scalar(select(func.count()).select_from(TokenVotacao).where(TokenVotacao.sessao_id == sessao_id))
    usados = db.scalar(select(func.count()).select_from(TokenVotacao)
                       .where(TokenVotacao.sessao_id == sessao_id, TokenVotacao.usado.is_(True)))
    ja_votaram = db.scalar(select(func.count()).select_from(Eleitor).where(Eleitor.ja_votou.is_(True)))
    return {"votos": votos, "tokens_emitidos": emitidos, "tokens_usados": usados,
            "eleitores_marcados": ja_votaram,
            "ok": votos == usados and usados <= emitidos and emitidos == ja_votaram}


def verificar_ancora(db, sessao: SessaoVotacao, res_votos: chain.Resultado) -> dict | None:
    """Ao fechar a sessão, a cabeça da cadeia de votos é gravada no log de auditoria.
    Isso detecta truncamento (remoção dos últimos votos), que a cadeia sozinha não vê."""
    if sessao.status != "FECHADA":
        return None
    eventos = db.scalars(select(LogAuditoria).where(LogAuditoria.evento == "SESSAO_FECHADA")
                         .order_by(LogAuditoria.seq.desc())).all()
    for e in eventos:
        d = json.loads(e.detalhes)
        if d.get("sessao_id") == sessao.id:
            ok = d.get("total_votos") == res_votos.total and d.get("hash_final") == res_votos.ultimo_hash
            return {"ok": ok, "esperado": {"total": d.get("total_votos"), "hash": d.get("hash_final")},
                    "atual": {"total": res_votos.total, "hash": res_votos.ultimo_hash}}
    return {"ok": False, "erro": "âncora de fechamento não encontrada no log"}


def verificar_tudo(db) -> dict:
    logs = verificar_logs(db)
    ultima = db.scalar(select(func.max(SessaoVotacao.id)))
    sessoes = []
    for s in db.scalars(select(SessaoVotacao).order_by(SessaoVotacao.id)).all():
        rv = verificar_votos(db, s.id)
        sessoes.append({"sessao_id": s.id, "titulo": s.titulo, "status": s.status,
                        "cadeia_votos": rv.como_dict(),
                        "conciliacao": conciliar(db, s.id) if s.id == ultima else None,
                        "ancora": verificar_ancora(db, s, rv)})
    ok = logs.ok and all(x["cadeia_votos"]["ok"] and (x["ancora"] is None or x["ancora"]["ok"])
                         and (x["conciliacao"] is None or x["conciliacao"]["ok"]) for x in sessoes)
    return {"ok": ok, "cadeia_logs": logs.como_dict(), "sessoes": sessoes}

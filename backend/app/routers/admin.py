import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update

from .. import audit, integridade
from ..config import settings
from ..database import LOCK_VOTOS, get_db, travar_cadeia
from ..deps import Principal, exigir
from ..models import Candidato, Eleitor, SessaoVotacao, Voto, agora
from ..ratelimit import ip_cliente

router = APIRouter(prefix="/admin", tags=["Administração / Apuração"])


class AbrirIn(BaseModel):
    titulo: str = Field(default="Eleição Presidencial 2026 - 1º turno", min_length=3, max_length=120)


def _assinar(corpo: dict) -> str:
    bruto = json.dumps(corpo, sort_keys=True, ensure_ascii=False).encode()
    return hmac.new(settings.BOLETIM_KEY, bruto, hashlib.sha256).hexdigest()


def contar(db, sessao_id: int) -> dict:
    linhas = db.execute(select(Voto.candidato_id, func.count()).where(Voto.sessao_id == sessao_id)
                        .group_by(Voto.candidato_id)).all()
    por_cand = {cid: n for cid, n in linhas}
    cands = db.scalars(select(Candidato).order_by(Candidato.numero)).all()
    resultado = [{"numero": c.numero, "nome": c.nome, "partido": c.partido, "votos": por_cand.get(c.id, 0)}
                 for c in cands]
    brancos = por_cand.get(None, 0)
    validos = sum(r["votos"] for r in resultado)
    total = validos + brancos
    for r in resultado:
        r["percentual_validos"] = round(100 * r["votos"] / validos, 2) if validos else 0.0
    resultado.sort(key=lambda r: (-r["votos"], r["numero"]))
    return {"candidatos": resultado, "brancos": brancos, "votos_validos": validos, "total_votos": total}


@router.get("/painel")
def painel(p: Principal = Depends(exigir("ADMIN")), db=Depends(get_db)):
    # Parciais por candidato NÃO são expostos enquanto a sessão está aberta.
    s = db.scalar(select(SessaoVotacao).order_by(SessaoVotacao.id.desc()).limit(1))
    eleitores = db.scalar(select(func.count()).select_from(Eleitor))
    ja = db.scalar(select(func.count()).select_from(Eleitor).where(Eleitor.ja_votou.is_(True)))
    votos = db.scalar(select(func.count()).select_from(Voto).where(Voto.sessao_id == s.id)) if s else 0
    return {"sessao": None if not s else {"id": s.id, "titulo": s.titulo, "status": s.status,
            "aberta_em": s.aberta_em.isoformat(), "fechada_em": s.fechada_em.isoformat() if s.fechada_em else None},
            "eleitores_cadastrados": eleitores, "eleitores_que_votaram": ja, "votos_registrados": votos}


@router.post("/sessao/abrir", status_code=201)
def abrir(body: AbrirIn, request: Request, p: Principal = Depends(exigir("ADMIN")), db=Depends(get_db)):
    atual = db.scalar(select(SessaoVotacao).order_by(SessaoVotacao.id.desc()).limit(1))
    if atual and atual.status == "ABERTA":
        raise HTTPException(409, "Já existe uma sessão aberta")
    s = SessaoVotacao(titulo=body.titulo, status="ABERTA")
    db.add(s)
    db.flush()
    db.execute(update(Eleitor).values(ja_votou=False))  # nova sessão: todos podem votar uma vez
    db.commit()
    audit.registrar(db, "SESSAO_ABERTA", "admin", p.id, ip_cliente(request), {"sessao_id": s.id, "titulo": s.titulo})
    return {"sessao_id": s.id, "status": s.status}


@router.post("/sessao/fechar")
def fechar(request: Request, p: Principal = Depends(exigir("ADMIN")), db=Depends(get_db)):
    s = db.scalar(select(SessaoVotacao).order_by(SessaoVotacao.id.desc()).limit(1))
    if not s or s.status != "ABERTA":
        raise HTTPException(409, "Não há sessão aberta")
    travar_cadeia(db, LOCK_VOTOS)  # nenhum voto entra entre a verificação e o commit do fechamento
    db.refresh(s)
    if s.status != "ABERTA":
        db.rollback()
        raise HTTPException(409, "A sessão já foi encerrada")
    s.status, s.fechada_em = "FECHADA", agora()
    db.flush()
    cadeia = integridade.verificar_votos(db, s.id)
    if not cadeia.ok:
        db.rollback()
        audit.registrar(db, "FECHAMENTO_ABORTADO", "admin", p.id, ip_cliente(request),
                        {"sessao_id": s.id, "motivo": cadeia.motivo, "quebra_em_seq": cadeia.quebra_em_seq})
        raise HTTPException(500, "Cadeia de votos corrompida: fechamento abortado. Acione a auditoria.")
    conc = integridade.conciliar(db, s.id)
    resultado = contar(db, s.id)
    corpo = {"sessao_id": s.id, "titulo": s.titulo, "fechada_em": s.fechada_em.isoformat(),
             "total_votos": cadeia.total, "hash_final": cadeia.ultimo_hash, "resultado": resultado,
             "conciliacao": conc}
    s.boletim_json = json.dumps({**corpo, "assinatura_hmac": _assinar(corpo)}, ensure_ascii=False)
    db.commit()
    # âncora: a cabeça da cadeia fica registrada também na cadeia de logs (detecta truncamento)
    audit.registrar(db, "SESSAO_FECHADA", "admin", p.id, ip_cliente(request),
                    {"sessao_id": s.id, "total_votos": cadeia.total, "hash_final": cadeia.ultimo_hash})
    return json.loads(s.boletim_json)


@router.get("/boletim/{sessao_id}")
def boletim(sessao_id: int, p: Principal = Depends(exigir("ADMIN", "AUDITOR")), db=Depends(get_db)):
    s = db.get(SessaoVotacao, sessao_id)
    if not s:
        raise HTTPException(404, "Sessão não encontrada")
    if s.status != "FECHADA" or not s.boletim_json:
        raise HTTPException(409, "O boletim só existe após o fechamento da sessão")
    b = json.loads(s.boletim_json)
    assinatura = b.pop("assinatura_hmac")
    return {**b, "assinatura_hmac": assinatura, "assinatura_valida": hmac.compare_digest(assinatura, _assinar(b))}

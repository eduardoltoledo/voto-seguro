import secrets
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, update

from .. import audit, chain
from ..crypto import sha256_hex
from ..database import LOCK_VOTOS, get_db, get_db_ro, travar_cadeia
from ..deps import Principal, exigir
from ..models import Candidato, Eleitor, SessaoVotacao, TokenVotacao, Voto
from ..ratelimit import ip_cliente, limitar_publico, limitar_voto

router = APIRouter(prefix="/votacao", tags=["Votação"])


def sessao_atual(db) -> SessaoVotacao | None:
    return db.scalar(select(SessaoVotacao).order_by(SessaoVotacao.id.desc()).limit(1))


class VotoIn(BaseModel):
    token: str = Field(min_length=20, max_length=100)
    tipo: Literal["candidato", "branco"]
    candidato_id: int | None = None

    @model_validator(mode="after")
    def _coerente(self):
        if (self.tipo == "candidato") != (self.candidato_id is not None):
            raise ValueError("candidato_id é obrigatório para 'candidato' e proibido para 'branco'")
        return self


class ReciboIn(BaseModel):
    recibo: str = Field(min_length=20, max_length=100)


@router.get("/candidatos")
def candidatos(db=Depends(get_db_ro), _=Depends(limitar_publico)):
    s = sessao_atual(db)
    lista = db.scalars(select(Candidato).where(Candidato.ativo.is_(True)).order_by(Candidato.numero)).all()
    return {"sessao": {"id": s.id, "titulo": s.titulo, "status": s.status} if s else None,
            "candidatos": [{"id": c.id, "numero": c.numero, "nome": c.nome, "partido": c.partido} for c in lista]}


@router.get("/situacao")
def situacao(p: Principal = Depends(exigir("ELEITOR")), db=Depends(get_db)):
    s = sessao_atual(db)
    el = db.get(Eleitor, p.id)
    return {"sessao_aberta": bool(s and s.status == "ABERTA"), "ja_votou": bool(el and el.ja_votou),
            "elegivel": bool(el and el.elegivel)}


@router.post("/token")
def emitir_token(request: Request, p: Principal = Depends(exigir("ELEITOR")), db=Depends(get_db),
                 _=Depends(limitar_voto)):
    """Passo 1 (autenticado): marca o eleitor como 'já votou' e entrega um token descartável.
    O token é guardado só como hash, sem ligação com o eleitor: aqui termina a identidade."""
    ip = ip_cliente(request)
    s = sessao_atual(db)
    if not s or s.status != "ABERTA":
        raise HTTPException(409, "Não há sessão de votação aberta")
    el = db.scalar(select(Eleitor).where(Eleitor.id == p.id).with_for_update())  # trava a linha
    if el is None or not el.elegivel:
        db.rollback()
        raise HTTPException(403, "Eleitor não elegível")
    if el.ja_votou:
        db.rollback()
        audit.registrar(db, "TENTATIVA_VOTO_DUPLICADO", "eleitor", p.id, ip)
        raise HTTPException(409, "Você já votou nesta sessão")
    token = secrets.token_urlsafe(32)
    db.add(TokenVotacao(sessao_id=s.id, token_hash=sha256_hex(token)))
    el.ja_votou = True
    db.commit()
    audit.registrar(db, "TOKEN_EMITIDO", "eleitor", p.id, ip)
    return {"token": token}


@router.post("/votar", status_code=201)
def votar(body: VotoIn, request: Request, db=Depends(get_db), _=Depends(limitar_voto)):
    """Passo 2 (SEM autenticação, só o token): registra o voto na cadeia de hashes."""
    ip = ip_cliente(request)
    s = sessao_atual(db)
    if not s or s.status != "ABERTA":
        raise HTTPException(409, "A sessão de votação não está aberta")
    if body.tipo == "candidato":
        cand = db.scalar(select(Candidato).where(Candidato.id == body.candidato_id, Candidato.ativo.is_(True)))
        if cand is None:
            raise HTTPException(422, "Candidato inválido")
    travar_cadeia(db, LOCK_VOTOS)
    # rechecagem DENTRO do lock: o mesário pode ter fechado a sessão enquanto esperávamos
    if db.scalar(select(SessaoVotacao.status).where(SessaoVotacao.id == s.id)) != "ABERTA":
        db.rollback()
        raise HTTPException(409, "A sessão de votação foi encerrada")
    consumido = db.execute(update(TokenVotacao).where(
        TokenVotacao.token_hash == sha256_hex(body.token), TokenVotacao.sessao_id == s.id,
        TokenVotacao.usado.is_(False)).values(usado=True)).rowcount  # atômico: um uso só
    if consumido != 1:
        db.rollback()
        audit.registrar(db, "TENTATIVA_VOTO_REJEITADA", None, None, ip, {"motivo": "token inválido ou já usado"})
        raise HTTPException(403, "Token de votação inválido ou já utilizado")
    ultimo = db.scalar(select(Voto).where(Voto.sessao_id == s.id).order_by(Voto.seq.desc()).limit(1))
    seq = 1 if ultimo is None else ultimo.seq + 1
    prev = chain.genesis_votos(s.id) if ultimo is None else ultimo.hash
    nonce, segredo = secrets.token_hex(16), secrets.token_urlsafe(24)
    recibo_hash = sha256_hex(segredo)
    h = chain.hash_voto(seq, s.id, body.candidato_id, nonce, recibo_hash, prev)
    db.add(Voto(sessao_id=s.id, seq=seq, candidato_id=body.candidato_id, nonce=nonce,
                recibo_hash=recibo_hash, prev_hash=prev, hash=h))
    db.commit()  # token consumido + voto gravado na mesma transação
    # Sem log por voto com ator/horário: evita correlação temporal token<->voto.
    return {"recibo": segredo, "recibo_hash": recibo_hash, "posicao": seq, "hash": h}


@router.post("/recibo/verificar")
def verificar_recibo(body: ReciboIn, db=Depends(get_db), _=Depends(limitar_publico)):
    """O eleitor confere que o voto foi contado. Não revela em quem votou."""
    v = db.scalar(select(Voto).where(Voto.recibo_hash == sha256_hex(body.recibo)))
    if v is None:
        return {"encontrado": False}
    return {"encontrado": True, "sessao_id": v.sessao_id, "posicao": v.seq, "hash": v.hash,
            "hash_anterior": v.prev_hash}


@router.get("/ledger/{sessao_id}")
def ledger(sessao_id: int, inicio: int = 1, limite: int = 200, db=Depends(get_db), _=Depends(limitar_publico)):
    """Livro público: posição, hash do recibo e hash encadeado (sem candidato)."""
    limite = max(1, min(limite, 1000))
    q = select(Voto).where(Voto.sessao_id == sessao_id, Voto.seq >= inicio).order_by(Voto.seq).limit(limite)
    return [{"posicao": v.seq, "recibo_hash": v.recibo_hash, "hash": v.hash} for v in db.scalars(q)]

import hmac
import secrets
from datetime import timedelta
from typing import Literal

import jwt
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from .. import audit, cpf as cpfmod, totp
from ..config import settings
from ..crypto import cifrar, decifrar, indice_cego, sha256_hex
from ..database import get_db
from ..deps import Principal, principal_atual
from ..models import Eleitor, RefreshToken, TseSimulado, UsuarioAdmin, agora
from ..ratelimit import ip_cliente, limitar_cadastro, limitar_login, limitar_mfa
from ..security import (criar_access_token, criar_mfa_token, decodificar, hash_senha,
                        novo_refresh, senha_forte, verificar_senha)

router = APIRouter(prefix="/auth", tags=["Autenticação"])
DUMMY_HASH = hash_senha("Senha-Falsa-Para-Tempo-Constante-1!")
MSG_CRED = "Credenciais inválidas ou conta temporariamente bloqueada"


class CadastroIn(BaseModel):
    cpf: str = Field(min_length=11, max_length=14)
    titulo: str = Field(min_length=12, max_length=14)
    senha: str = Field(min_length=10, max_length=128)


class LoginIn(BaseModel):
    perfil: Literal["eleitor", "admin"]
    identificador: str = Field(min_length=3, max_length=40)  # CPF (eleitor) ou usuário (admin)
    senha: str = Field(min_length=1, max_length=128)


class MfaIn(BaseModel):
    mfa_token: str = Field(max_length=2000)
    codigo: str = Field(pattern=r"^\d{6}$")


def _sujeito(db, perfil: str, ident: str):
    if perfil == "eleitor":
        c = cpfmod.normalizar(ident)
        if not cpfmod.validar(c):
            return None
        return db.scalar(select(Eleitor).where(Eleitor.cpf_hash == indice_cego(settings.INDEX_KEY, c)))
    return db.scalar(select(UsuarioAdmin).where(UsuarioAdmin.usuario == ident, UsuarioAdmin.ativo.is_(True)))


def _sujeito_por_id(db, perfil: str, sid: int):
    return db.get(Eleitor if perfil == "eleitor" else UsuarioAdmin, sid)


def _papel(perfil: str, s) -> str:
    return "ELEITOR" if perfil == "eleitor" else s.papel


def _registrar_falha(s) -> bool:
    s.tentativas_falhas += 1
    if s.tentativas_falhas >= settings.MAX_FALHAS:
        s.bloqueado_ate = agora() + timedelta(minutes=settings.BLOQUEIO_MIN)
        s.tentativas_falhas = 0
        return True
    return False


def _cookies(response: Response, refresh: str):
    csrf = secrets.token_urlsafe(24)
    opts = dict(max_age=settings.REFRESH_HORAS * 3600, secure=settings.COOKIE_SECURE,
                samesite="strict", path="/api/auth")
    response.set_cookie("refresh_token", refresh, httponly=True, **opts)
    # CSRF (double-submit): legível pelo JS, por isso path "/" (cookies só são visíveis ao JS no path da página)
    response.set_cookie("csrf_token", csrf, httponly=False, **{**opts, "path": "/"})


def _emitir_sessao(db, response, perfil, s, familia=None):
    refresh, rh = novo_refresh()
    db.add(RefreshToken(token_hash=rh, perfil=perfil, sujeito_id=s.id,
                        familia=familia or secrets.token_hex(8),
                        expira_em=agora() + timedelta(hours=settings.REFRESH_HORAS)))
    _cookies(response, refresh)
    nome = decifrar(settings.AES_KEY, s.nome_enc, "nome").split()[0] if perfil == "eleitor" else s.nome
    return {"access_token": criar_access_token(perfil, s.id, _papel(perfil, s)),
            "expira_em_s": settings.ACCESS_MIN * 60, "perfil": perfil,
            "papel": _papel(perfil, s), "nome": nome}


@router.post("/cadastro", status_code=201)
def cadastro(body: CadastroIn, request: Request, db=Depends(get_db), _=Depends(limitar_cadastro)):
    """Valida o eleitor na base (simulada) do TSE e cria a conta com MFA."""
    ip = ip_cliente(request)
    c, t = cpfmod.normalizar(body.cpf), "".join(ch for ch in body.titulo if ch.isdigit())
    if not cpfmod.validar(c) or len(t) != 12:
        raise HTTPException(422, "CPF ou título com formato inválido")
    if not senha_forte(body.senha):
        raise HTTPException(422, "Senha fraca: use 10+ caracteres com maiúscula, minúscula, número e símbolo")
    tse = db.scalar(select(TseSimulado).where(TseSimulado.cpf == c, TseSimulado.titulo == t))
    if tse is None or tse.situacao != "REGULAR":
        audit.registrar(db, "CADASTRO_RECUSADO", "eleitor", None, ip, {"motivo": "TSE"})
        raise HTTPException(403, "Dados não conferem com a base do TSE ou situação irregular")
    chave_cpf = indice_cego(settings.INDEX_KEY, c)
    if db.scalar(select(Eleitor.id).where(Eleitor.cpf_hash == chave_cpf)):
        raise HTTPException(409, "Eleitor já cadastrado")
    segredo = totp.gerar_segredo()
    el = Eleitor(cpf_hash=chave_cpf, cpf_enc=cifrar(settings.AES_KEY, c, "cpf"),
                 titulo_hash=indice_cego(settings.INDEX_KEY, t), titulo_enc=cifrar(settings.AES_KEY, t, "titulo"),
                 nome_enc=cifrar(settings.AES_KEY, tse.nome, "nome"), senha_hash=hash_senha(body.senha),
                 totp_secret_enc=cifrar(settings.AES_KEY, segredo, "totp"))
    db.add(el)
    db.flush()
    audit.registrar(db, "ELEITOR_CADASTRADO", "eleitor", el.id, ip)
    return {"mfa_segredo": segredo, "mfa_uri": totp.uri_provisionamento(segredo, f"eleitor-{el.id}")}


@router.post("/login")
def login(body: LoginIn, request: Request, db=Depends(get_db), _=Depends(limitar_login)):
    ip = ip_cliente(request)
    s = _sujeito(db, body.perfil, body.identificador)
    bloqueado = s is not None and s.bloqueado_ate is not None and s.bloqueado_ate > agora()
    # a verificação sempre roda: o tempo de resposta não revela se a conta existe
    ok = verificar_senha(s.senha_hash if s else DUMMY_HASH, body.senha) and s is not None and not bloqueado
    if not ok:
        travou = False
        if s is not None and not bloqueado:
            travou = _registrar_falha(s)
        audit.registrar(db, "LOGIN_FALHA", body.perfil, s.id if s else None, ip,
                        {"bloqueado": bool(bloqueado or travou)})
        raise HTTPException(401, MSG_CRED)
    audit.registrar(db, "LOGIN_SENHA_OK", body.perfil, s.id, ip)
    return {"mfa_token": criar_mfa_token(body.perfil, s.id)}


@router.post("/mfa")
def mfa(body: MfaIn, request: Request, response: Response, db=Depends(get_db), _=Depends(limitar_mfa)):
    ip = ip_cliente(request)
    try:
        d = decodificar(body.mfa_token, "mfa")
    except jwt.PyJWTError:
        raise HTTPException(401, "Etapa de senha expirada. Entre novamente.")
    perfil = d["perfil"]
    s = _sujeito_por_id(db, perfil, int(d["sub"]))
    if s is None or (s.bloqueado_ate and s.bloqueado_ate > agora()):
        raise HTTPException(401, MSG_CRED)
    segredo = decifrar(settings.AES_KEY, s.totp_secret_enc, "totp")
    passo = totp.verificar(segredo, body.codigo, ultimo_passo=s.totp_ultimo_passo)
    if passo is None:
        travou = _registrar_falha(s)
        audit.registrar(db, "MFA_FALHA", perfil, s.id, ip, {"bloqueado": travou})
        raise HTTPException(401, "Código inválido ou expirado")
    s.totp_ultimo_passo, s.tentativas_falhas, s.bloqueado_ate = passo, 0, None
    sessao = _emitir_sessao(db, response, perfil, s)
    audit.registrar(db, "LOGIN_SUCESSO", perfil, s.id, ip, {"papel": _papel(perfil, s)})
    return sessao


@router.post("/refresh")
def refresh(request: Request, response: Response, db=Depends(get_db),
            refresh_token: str | None = Cookie(default=None), csrf_token: str | None = Cookie(default=None),
            x_csrf_token: str | None = Header(default=None)):
    """Renova a sessão. Exige cookie HttpOnly + cabeçalho CSRF (double-submit) e rotaciona o token."""
    if not (refresh_token and csrf_token and x_csrf_token and hmac.compare_digest(csrf_token, x_csrf_token)):
        raise HTTPException(403, "Verificação CSRF falhou")
    ip = ip_cliente(request)
    rt = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == sha256_hex(refresh_token)))
    if rt is None:
        raise HTTPException(401, "Sessão inválida")
    if rt.revogado:  # reutilização de token já rotacionado => possível roubo: derruba a família
        db.execute(update(RefreshToken).where(RefreshToken.familia == rt.familia).values(revogado=True))
        db.commit()
        audit.registrar(db, "REFRESH_REUTILIZADO", rt.perfil, rt.sujeito_id, ip)
        raise HTTPException(401, "Sessão inválida")
    s = _sujeito_por_id(db, rt.perfil, rt.sujeito_id)
    if rt.expira_em < agora() or s is None or (rt.perfil == "admin" and not s.ativo):
        raise HTTPException(401, "Sessão expirada")
    rt.revogado = True
    out = _emitir_sessao(db, response, rt.perfil, s, familia=rt.familia)
    db.commit()
    return out


@router.post("/logout", status_code=204)
def logout(response: Response, db=Depends(get_db), refresh_token: str | None = Cookie(default=None)):
    if refresh_token:
        db.execute(update(RefreshToken).where(RefreshToken.token_hash == sha256_hex(refresh_token))
                   .values(revogado=True))
        db.commit()
    response.delete_cookie("refresh_token", path="/api/auth")
    response.delete_cookie("csrf_token", path="/")


@router.get("/me")
def me(p: Principal = Depends(principal_atual)):
    return {"perfil": p.perfil, "papel": p.papel}

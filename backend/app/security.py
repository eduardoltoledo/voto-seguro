"""Senhas (Argon2id), JWT de curta duração e refresh tokens opacos."""
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from .config import settings
from .crypto import sha256_hex

_ph = PasswordHasher()  # Argon2id com parâmetros padrão da biblioteca


def hash_senha(senha: str) -> str:
    return _ph.hash(senha)


def verificar_senha(hash_: str, senha: str) -> bool:
    try:
        return _ph.verify(hash_, senha)
    except (VerifyMismatchError, InvalidHashError):
        return False


def senha_forte(senha: str) -> bool:
    return bool(len(senha) >= 10 and re.search(r"[a-z]", senha) and re.search(r"[A-Z]", senha)
                and re.search(r"\d", senha) and re.search(r"[^\w\s]", senha))


def _emitir(typ: str, perfil: str, sub: int, papel: str, minutos: int) -> str:
    agora = datetime.now(timezone.utc)
    return jwt.encode(
        {"iss": settings.ISSUER, "typ": typ, "perfil": perfil, "sub": str(sub), "papel": papel,
         "iat": agora, "exp": agora + timedelta(minutes=minutos), "jti": uuid.uuid4().hex},
        settings.JWT_KEY, algorithm="HS256")


def criar_access_token(perfil: str, sub: int, papel: str) -> str:
    return _emitir("access", perfil, sub, papel, settings.ACCESS_MIN)


def criar_mfa_token(perfil: str, sub: int) -> str:
    """Token intermediário: prova que a senha foi aceita, mas NÃO dá acesso a nada."""
    return _emitir("mfa", perfil, sub, "PENDENTE", settings.MFA_TOKEN_MIN)


def decodificar(token: str, typ_esperado: str) -> dict:
    dados = jwt.decode(token, settings.JWT_KEY, algorithms=["HS256"], issuer=settings.ISSUER,
                       options={"require": ["exp", "iat", "sub", "typ"]})
    if dados["typ"] != typ_esperado:
        raise jwt.InvalidTokenError("tipo de token inválido")
    return dados


def novo_refresh() -> tuple[str, str]:
    bruto = secrets.token_urlsafe(48)
    return bruto, sha256_hex(bruto)  # só o hash vai para o banco

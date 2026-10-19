from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .security import decodificar

_bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    perfil: str   # eleitor | admin
    id: int
    papel: str    # ELEITOR | ADMIN | AUDITOR


def principal_atual(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Principal:
    if cred is None:
        raise HTTPException(401, "Autenticação necessária", headers={"WWW-Authenticate": "Bearer"})
    try:
        d = decodificar(cred.credentials, "access")
    except jwt.PyJWTError:
        raise HTTPException(401, "Sessão expirada ou inválida", headers={"WWW-Authenticate": "Bearer"})
    return Principal(d["perfil"], int(d["sub"]), d["papel"])


def exigir(*papeis: str):
    """RBAC: permite apenas os papéis informados."""
    def dep(p: Principal = Depends(principal_atual)) -> Principal:
        if p.papel not in papeis:
            raise HTTPException(403, "Seu perfil não tem permissão para esta ação")
        return p
    return dep

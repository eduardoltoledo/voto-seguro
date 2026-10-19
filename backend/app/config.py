"""Configuração central. Segredos vêm do ambiente; em produção são obrigatórios."""
import base64
import hashlib
import os
import socket


def _chave(nome: str) -> bytes:
    """Lê uma chave de 32 bytes (base64) do ambiente. Em dev deriva uma chave fixa."""
    valor = os.getenv(nome)
    if valor:
        bruto = base64.b64decode(valor)
        if len(bruto) != 32:
            raise RuntimeError(f"{nome} deve ter 32 bytes em base64")
        return bruto
    if os.getenv("APP_ENV", "dev") == "production":
        raise RuntimeError(f"{nome} é obrigatório em produção")
    return hashlib.sha256(f"chave-somente-dev:{nome}".encode()).digest()


class Settings:
    ENV = os.getenv("APP_ENV", "dev")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./voto_dev.db")
    DATABASE_REPLICA_URL = os.getenv("DATABASE_REPLICA_URL", "")
    INSTANCE_ID = os.getenv("INSTANCE_ID", socket.gethostname())

    AES_KEY = _chave("AES_KEY")          # AES-256-GCM: CPF, título, nome, segredo TOTP
    INDEX_KEY = _chave("INDEX_KEY")      # HMAC para índice cego (busca por CPF sem decifrar)
    JWT_KEY = _chave("JWT_KEY")          # assinatura dos JWT
    BOLETIM_KEY = _chave("BOLETIM_KEY")  # assinatura HMAC do boletim de urna

    ACCESS_MIN = int(os.getenv("ACCESS_TOKEN_MINUTES", "10"))
    MFA_TOKEN_MIN = 5
    REFRESH_HORAS = int(os.getenv("REFRESH_TOKEN_HOURS", "8"))
    MAX_FALHAS = int(os.getenv("MAX_LOGIN_FAILURES", "5"))
    BLOQUEIO_MIN = int(os.getenv("LOCKOUT_MINUTES", "15"))

    COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    TRUST_PROXY = os.getenv("TRUST_PROXY", "false").lower() == "true"
    SEED_DEMO = os.getenv("SEED_DEMO", "false").lower() == "true"
    ISSUER = "voto-seguro"


settings = Settings()

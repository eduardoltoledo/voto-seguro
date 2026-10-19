"""TOTP (RFC 6238) em biblioteca padrão, com proteção contra reutilização de código."""
import base64
import hashlib
import hmac
import os
import struct
import time
from urllib.parse import quote

PASSO = 30
DIGITOS = 6


def gerar_segredo() -> str:
    return base64.b32encode(os.urandom(20)).decode().rstrip("=")


def _hotp(segredo: str, contador: int) -> str:
    chave = base64.b32decode(segredo + "=" * (-len(segredo) % 8), casefold=True)
    mac = hmac.new(chave, struct.pack(">Q", contador), hashlib.sha1).digest()
    off = mac[-1] & 0x0F
    num = (struct.unpack(">I", mac[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** DIGITOS)
    return f"{num:0{DIGITOS}d}"


def codigo_atual(segredo: str, agora: float | None = None) -> str:
    return _hotp(segredo, int((agora or time.time()) // PASSO))


def verificar(segredo: str, codigo: str, agora: float | None = None,
              janela: int = 1, ultimo_passo: int | None = None) -> int | None:
    """Retorna o passo (time-step) aceito ou None. Rejeita passos já usados (anti-replay)."""
    atual = int((agora or time.time()) // PASSO)
    for passo in range(atual - janela, atual + janela + 1):
        if ultimo_passo is not None and passo <= ultimo_passo:
            continue
        if hmac.compare_digest(_hotp(segredo, passo), codigo):
            return passo
    return None


def uri_provisionamento(segredo: str, conta: str, emissor: str = "VotoSeguro") -> str:
    return (f"otpauth://totp/{quote(emissor)}:{quote(conta)}?secret={segredo}"
            f"&issuer={quote(emissor)}&digits={DIGITOS}&period={PASSO}")

"""Criptografia em repouso: AES-256-GCM + índice cego (HMAC-SHA256)."""
import base64
import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def cifrar(chave: bytes, texto: str, contexto: str = "") -> str:
    """AES-256-GCM com nonce aleatório de 96 bits; `contexto` entra como dado autenticado."""
    nonce = os.urandom(12)
    ct = AESGCM(chave).encrypt(nonce, texto.encode(), contexto.encode())
    return base64.urlsafe_b64encode(nonce + ct).decode()


def decifrar(chave: bytes, token: str, contexto: str = "") -> str:
    bruto = base64.urlsafe_b64decode(token.encode())
    return AESGCM(chave).decrypt(bruto[:12], bruto[12:], contexto.encode()).decode()


def indice_cego(chave: bytes, valor: str) -> str:
    """Como o AES-GCM é aleatório, buscamos por HMAC determinístico do valor."""
    return hmac.new(chave, valor.encode(), hashlib.sha256).hexdigest()


def sha256_hex(texto: str) -> str:
    return hashlib.sha256(texto.encode()).hexdigest()

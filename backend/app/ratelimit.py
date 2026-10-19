"""Rate limiting por IP (janela deslizante, em memória por instância).

Defesa em profundidade: o Nginx aplica `limit_req` (vale entre instâncias);
este limitador protege a API caso seja acessada sem passar pelo balanceador.
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import settings


def ip_cliente(request: Request) -> str:
    if settings.TRUST_PROXY:  # só confiar em X-Real-IP quando atrás do nosso Nginx
        ip = request.headers.get("x-real-ip")
        if ip:
            return ip[:45]
    return request.client.host if request.client else "desconhecido"


class Limitador:
    def __init__(self, maximo: int, janela_s: int):
        self.maximo, self.janela = maximo, janela_s
        self._h: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def reset(self):
        with self._lock:
            self._h.clear()

    def __call__(self, request: Request) -> None:
        ip, t = ip_cliente(request), time.monotonic()
        with self._lock:
            fila = self._h[ip]
            while fila and t - fila[0] > self.janela:
                fila.popleft()
            if len(fila) >= self.maximo:
                espera = int(self.janela - (t - fila[0])) + 1
                raise HTTPException(429, "Muitas requisições. Aguarde e tente novamente.",
                                    headers={"Retry-After": str(espera)})
            fila.append(t)
            if len(self._h) > 10000:
                for k in [k for k, v in self._h.items() if not v]:
                    del self._h[k]


TODOS = {
    "login": Limitador(10, 60),
    "mfa": Limitador(10, 60),
    "cadastro": Limitador(5, 60),
    "voto": Limitador(20, 60),
    "publico": Limitador(60, 60),
}
limitar_login, limitar_mfa, limitar_cadastro = TODOS["login"], TODOS["mfa"], TODOS["cadastro"]
limitar_voto, limitar_publico = TODOS["voto"], TODOS["publico"]

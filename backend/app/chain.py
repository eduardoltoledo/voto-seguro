"""Cadeias de hash (estilo blockchain simplificado) para votos e logs de auditoria.

Funções puras (sem banco) para serem testáveis e reutilizadas pelo verificador.
"""
import hashlib
from dataclasses import dataclass


def _h(*partes) -> str:
    return hashlib.sha256("|".join(str(p) for p in partes).encode()).hexdigest()


def genesis_votos(sessao_id: int) -> str:
    return _h("genesis-votos", sessao_id)


GENESIS_LOGS = _h("genesis-logs")


def hash_voto(seq, sessao_id, candidato_id, nonce, recibo_hash, prev_hash) -> str:
    cand = "BRANCO" if candidato_id is None else candidato_id
    return _h("voto", seq, sessao_id, cand, nonce, recibo_hash, prev_hash)


def hash_log(seq, ts, evento, ator_tipo, ator_id, ip, detalhes, prev_hash) -> str:
    return _h("log", seq, ts, evento, ator_tipo or "", ator_id if ator_id is not None else "",
              ip or "", detalhes, prev_hash)


def calcular_voto(r: dict) -> str:
    return hash_voto(r["seq"], r["sessao_id"], r["candidato_id"], r["nonce"],
                     r["recibo_hash"], r["prev_hash"])


def calcular_log(r: dict) -> str:
    return hash_log(r["seq"], r["ts"], r["evento"], r["ator_tipo"], r["ator_id"],
                    r["ip"], r["detalhes"], r["prev_hash"])


@dataclass
class Resultado:
    ok: bool
    total: int
    quebra_em_seq: int | None = None
    motivo: str | None = None
    ultimo_hash: str | None = None

    def como_dict(self) -> dict:
        return self.__dict__.copy()


def verificar_cadeia(registros, calcular, genesis: str) -> Resultado:
    """Percorre os registros em ordem de seq e recomputa cada hash."""
    prev, esperado, total = genesis, 1, 0
    for r in registros:
        if r["seq"] != esperado:
            return Resultado(False, total, esperado, "sequência com lacuna (registro removido?)")
        if r["prev_hash"] != prev:
            return Resultado(False, total, r["seq"], "encadeamento quebrado")
        if calcular(r) != r["hash"]:
            return Resultado(False, total, r["seq"], "conteúdo do registro foi alterado")
        prev, esperado, total = r["hash"], esperado + 1, total + 1
    return Resultado(True, total, ultimo_hash=prev)

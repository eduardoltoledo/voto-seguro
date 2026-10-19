import re


def normalizar(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _dv(digitos: str) -> str:
    soma = sum(int(d) * p for d, p in zip(digitos, range(len(digitos) + 1, 1, -1)))
    resto = (soma * 10) % 11
    return str(0 if resto == 10 else resto)


def gerar_dvs(base9: str) -> str:
    d1 = _dv(base9)
    return base9 + d1 + _dv(base9 + d1)


def validar(cpf: str) -> bool:
    cpf = normalizar(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    return cpf == gerar_dvs(cpf[:9])

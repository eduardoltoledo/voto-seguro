"""Dados de DEMONSTRAÇÃO (SEED_DEMO=true). Nunca usar em produção.

Candidatos e eleitores são fictícios. Os segredos TOTP abaixo são fixos e públicos de propósito,
para que a demonstração em sala não dependa de um app autenticador (veja docs/ e README).
"""
from sqlalchemy import func, select

from . import cpf as cpfmod
from .config import settings
from .crypto import cifrar, indice_cego
from .models import Candidato, Eleitor, SessaoVotacao, TseSimulado, UsuarioAdmin
from .security import hash_senha

SENHA_DEMO = "Demo@Seguro2026!"
SEGREDO_ADMIN = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
SEGREDO_AUDITOR = "KRSXG5CTMVRXEZLUKRSXG5CTMVRXEZLU"
SEGREDO_ELEITORES = "MFRGGZDFMZTWQ2LKMFRGGZDFMZTWQ2LK"

CANDIDATOS = [(13, "Helena Duarte", "Partido Horizonte"), (22, "Marcos Veloso", "Aliança Civil"),
              (45, "Ana Beatriz Lemos", "Movimento Federal"), (77, "Roberto Quintana", "Frente Popular")]
NOMES = ["Carla Mendes Souza", "João Pedro Alves", "Fernanda Lima Costa", "Ricardo Teixeira",
         "Patrícia Gomes Rocha", "Lucas Ferreira Dias", "Mariana Nogueira", "Tiago Barros Pinto"]


def cpf_demo(i: int) -> str:
    return cpfmod.gerar_dvs(f"{111222330 + i:09d}")


def titulo_demo(i: int) -> str:
    return f"{100000000000 + i:012d}"


def popular_demo(db) -> None:
    if db.scalar(select(func.count()).select_from(Candidato)):
        return  # já populado
    for n, nome, partido in CANDIDATOS:
        db.add(Candidato(numero=n, nome=nome, partido=partido))
    for i, nome in enumerate(NOMES):
        db.add(TseSimulado(cpf=cpf_demo(i), titulo=titulo_demo(i), nome=nome,
                           situacao="SUSPENSO" if i == len(NOMES) - 1 else "REGULAR"))
    # Os 3 primeiros eleitores já vêm cadastrados (MFA com segredo fixo de demonstração)
    for i, nome in enumerate(NOMES[:3]):
        c, t = cpf_demo(i), titulo_demo(i)
        db.add(Eleitor(cpf_hash=indice_cego(settings.INDEX_KEY, c), cpf_enc=cifrar(settings.AES_KEY, c, "cpf"),
                       titulo_hash=indice_cego(settings.INDEX_KEY, t), titulo_enc=cifrar(settings.AES_KEY, t, "titulo"),
                       nome_enc=cifrar(settings.AES_KEY, nome, "nome"), senha_hash=hash_senha(SENHA_DEMO),
                       totp_secret_enc=cifrar(settings.AES_KEY, SEGREDO_ELEITORES, "totp")))
    db.add(UsuarioAdmin(usuario="mesario", nome="Mesário Demo", papel="ADMIN", senha_hash=hash_senha(SENHA_DEMO),
                        totp_secret_enc=cifrar(settings.AES_KEY, SEGREDO_ADMIN, "totp")))
    db.add(UsuarioAdmin(usuario="fiscal", nome="Fiscal Demo", papel="AUDITOR", senha_hash=hash_senha(SENHA_DEMO),
                        totp_secret_enc=cifrar(settings.AES_KEY, SEGREDO_AUDITOR, "totp")))
    db.add(SessaoVotacao(titulo="Eleição Presidencial 2026 - 1º turno (demo)", status="ABERTA"))
    db.commit()

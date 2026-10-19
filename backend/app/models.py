from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def agora() -> datetime:
    """UTC ingênuo (naive) para comparar de forma consistente em PostgreSQL e SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class TseSimulado(Base):
    """Base externa simulada do TSE (em produção seria uma API de terceiros)."""
    __tablename__ = "tse_simulado"
    id: Mapped[int] = mapped_column(primary_key=True)
    cpf: Mapped[str] = mapped_column(String(11), unique=True, index=True)
    titulo: Mapped[str] = mapped_column(String(12))
    nome: Mapped[str] = mapped_column(String(120))
    situacao: Mapped[str] = mapped_column(String(12), default="REGULAR")  # REGULAR|SUSPENSO|CANCELADO


class Eleitor(Base):
    __tablename__ = "eleitor"
    id: Mapped[int] = mapped_column(primary_key=True)
    cpf_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # índice cego
    cpf_enc: Mapped[str] = mapped_column(Text)
    titulo_hash: Mapped[str] = mapped_column(String(64), unique=True)
    titulo_enc: Mapped[str] = mapped_column(Text)
    nome_enc: Mapped[str] = mapped_column(Text)
    senha_hash: Mapped[str] = mapped_column(Text)
    totp_secret_enc: Mapped[str] = mapped_column(Text)
    totp_ultimo_passo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elegivel: Mapped[bool] = mapped_column(Boolean, default=True)
    ja_votou: Mapped[bool] = mapped_column(Boolean, default=False)  # sem data/hora: evita correlação
    tentativas_falhas: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)


class UsuarioAdmin(Base):
    __tablename__ = "usuario_admin"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario: Mapped[str] = mapped_column(String(40), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    papel: Mapped[str] = mapped_column(String(10))  # ADMIN | AUDITOR
    senha_hash: Mapped[str] = mapped_column(Text)
    totp_secret_enc: Mapped[str] = mapped_column(Text)
    totp_ultimo_passo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tentativas_falhas: Mapped[int] = mapped_column(Integer, default=0)
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class RefreshToken(Base):
    __tablename__ = "refresh_token"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    perfil: Mapped[str] = mapped_column(String(10))  # eleitor | admin
    sujeito_id: Mapped[int] = mapped_column(Integer)
    familia: Mapped[str] = mapped_column(String(32), index=True)
    expira_em: Mapped[datetime] = mapped_column(DateTime)
    revogado: Mapped[bool] = mapped_column(Boolean, default=False)


class Candidato(Base):
    __tablename__ = "candidato"
    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[int] = mapped_column(Integer, unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    partido: Mapped[str] = mapped_column(String(80))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class SessaoVotacao(Base):
    __tablename__ = "sessao_votacao"
    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(10), default="ABERTA")  # ABERTA | FECHADA
    aberta_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    fechada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    boletim_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class TokenVotacao(Base):
    """Credencial descartável. NÃO referencia o eleitor e NÃO tem data/hora."""
    __tablename__ = "token_votacao"
    id: Mapped[int] = mapped_column(primary_key=True)
    sessao_id: Mapped[int] = mapped_column(ForeignKey("sessao_votacao.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    usado: Mapped[bool] = mapped_column(Boolean, default=False)


class Voto(Base):
    """Sem vínculo com eleitor/token e sem timestamp. Cada voto aponta para o hash anterior."""
    __tablename__ = "voto"
    __table_args__ = (UniqueConstraint("sessao_id", "seq"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    sessao_id: Mapped[int] = mapped_column(ForeignKey("sessao_votacao.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    candidato_id: Mapped[int | None] = mapped_column(ForeignKey("candidato.id"), nullable=True)  # NULL = branco
    nonce: Mapped[str] = mapped_column(String(32))
    recibo_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class LogAuditoria(Base):
    __tablename__ = "log_auditoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, unique=True)
    ts: Mapped[str] = mapped_column(String(32))
    evento: Mapped[str] = mapped_column(String(40), index=True)
    ator_tipo: Mapped[str | None] = mapped_column(String(10), nullable=True)
    ator_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    detalhes: Mapped[str] = mapped_column(Text)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))

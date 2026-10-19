"""Criação do esquema + gatilhos que tornam `voto` e `log_auditoria` append-only no próprio banco."""
from sqlalchemy import text

from .models import Base

TABELAS_IMUTAVEIS = ("voto", "log_auditoria")


def _triggers_postgres(conn):
    conn.execute(text("""
        CREATE OR REPLACE FUNCTION bloquear_alteracao() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION USING
                MESSAGE = 'Tabela ' || TG_TABLE_NAME || ' e append-only; operacao ' || TG_OP || ' bloqueada',
                ERRCODE = 'integrity_constraint_violation';
        END; $$ LANGUAGE plpgsql;
    """))
    for t in TABELAS_IMUTAVEIS:
        conn.execute(text(f"DROP TRIGGER IF EXISTS {t}_append_only ON {t}"))
        conn.execute(text(f"CREATE TRIGGER {t}_append_only BEFORE UPDATE OR DELETE ON {t} "
                          f"FOR EACH ROW EXECUTE FUNCTION bloquear_alteracao()"))
        conn.execute(text(f"DROP TRIGGER IF EXISTS {t}_no_truncate ON {t}"))
        conn.execute(text(f"CREATE TRIGGER {t}_no_truncate BEFORE TRUNCATE ON {t} "
                          f"FOR EACH STATEMENT EXECUTE FUNCTION bloquear_alteracao()"))


def _triggers_sqlite(conn):
    for t in TABELAS_IMUTAVEIS:
        for op in ("UPDATE", "DELETE"):
            conn.execute(text(f"CREATE TRIGGER IF NOT EXISTS {t}_no_{op.lower()} BEFORE {op} ON {t} "
                              f"BEGIN SELECT RAISE(ABORT, 'tabela {t} é append-only'); END"))


def _privilegios_postgres(conn, app_user: str):
    """Defesa em profundidade: a conta usada pela API não pode alterar/apagar votos nem logs,
    nem mesmo se a aplicação for comprometida (SQL injection, RCE)."""
    if not app_user.isidentifier():
        raise ValueError("APP_DB_USER inválido")
    conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {app_user}"))
    conn.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {app_user}"))
    conn.execute(text(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {app_user}"))
    conn.execute(text(f"REVOKE UPDATE, DELETE, TRUNCATE ON {', '.join(TABELAS_IMUTAVEIS)} FROM {app_user}"))


def inicializar(engine, app_user: str | None = None) -> None:
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            _triggers_postgres(conn)
            if app_user:
                _privilegios_postgres(conn, app_user)
        elif engine.dialect.name == "sqlite":
            _triggers_sqlite(conn)

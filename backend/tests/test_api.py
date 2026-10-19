"""Testes de integração da API (SQLite em memória de arquivo temporário).

Requer as dependências do requirements.txt (rodam dentro do container ou em um venv):
    docker compose run --rm --no-deps backend1 python -m unittest tests.test_api -v
"""
import importlib.util
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DISPONIVEL = all(importlib.util.find_spec(m) for m in ("fastapi", "sqlalchemy", "argon2", "httpx"))


@unittest.skipUnless(DISPONIVEL, "dependências da API não instaladas")
class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp()
        os.environ.update(DATABASE_URL=f"sqlite:///{cls._tmp}/t.db", SEED_DEMO="true", COOKIE_SECURE="false",
                          APP_ENV="dev", DATABASE_REPLICA_URL="")
        from fastapi.testclient import TestClient
        from app import ratelimit, seed, totp
        from app.main import app
        cls.seed, cls.totp, cls.ratelimit = seed, totp, ratelimit
        cls._cm = TestClient(app)
        cls.c = cls._cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._cm.__exit__(None, None, None)

    def setUp(self):
        for l in self.ratelimit.TODOS.values():
            l.reset()

    def entrar(self, perfil, ident, segredo, passo_extra=0):
        r = self.c.post("/auth/login", json={"perfil": perfil, "identificador": ident, "senha": self.seed.SENHA_DEMO})
        self.assertEqual(r.status_code, 200, r.text)
        import time
        cod = self.totp.codigo_atual(segredo, time.time() + 30 * passo_extra)
        r2 = self.c.post("/auth/mfa", json={"mfa_token": r.json()["mfa_token"], "codigo": cod})
        self.assertEqual(r2.status_code, 200, r2.text)
        return {"Authorization": "Bearer " + r2.json()["access_token"]}

    def test_fluxo_completo(self):
        s = self.seed
        el = self.entrar("eleitor", s.cpf_demo(0), s.SEGREDO_ELEITORES)
        adm = self.entrar("admin", "mesario", s.SEGREDO_ADMIN)
        fis = self.entrar("admin", "fiscal", s.SEGREDO_AUDITOR)

        # RBAC
        self.assertEqual(self.c.get("/admin/painel", headers=el).status_code, 403)
        self.assertEqual(self.c.get("/auditoria/verificar", headers=el).status_code, 403)
        self.assertEqual(self.c.post("/admin/sessao/fechar", headers=fis).status_code, 403)
        self.assertEqual(self.c.get("/auditoria/verificar").status_code, 401)

        # votação
        cands = self.c.get("/votacao/candidatos").json()["candidatos"]
        tok = self.c.post("/votacao/token", headers=el)
        self.assertEqual(tok.status_code, 200)
        token = tok.json()["token"]
        v = self.c.post("/votacao/votar", json={"token": token, "tipo": "candidato", "candidato_id": cands[0]["id"]})
        self.assertEqual(v.status_code, 201, v.text)
        recibo = v.json()["recibo"]
        self.assertTrue(self.c.post("/votacao/recibo/verificar", json={"recibo": recibo}).json()["encontrado"])

        # fraudes
        self.assertEqual(self.c.post("/votacao/token", headers=el).status_code, 409)
        self.assertEqual(self.c.post("/votacao/votar", json={"token": token, "tipo": "branco"}).status_code, 403)
        ev = [e["evento"] for e in self.c.get("/auditoria/logs?limite=50", headers=fis).json()]
        self.assertIn("TENTATIVA_VOTO_DUPLICADO", ev)
        self.assertIn("TENTATIVA_VOTO_REJEITADA", ev)

        # o conteúdo do voto não aparece em nenhum log
        logs_txt = str(self.c.get("/auditoria/logs?limite=500", headers=fis).json())
        self.assertNotIn(recibo, logs_txt)

        # outro eleitor: voto em branco
        el2 = self.entrar("eleitor", s.cpf_demo(1), s.SEGREDO_ELEITORES)
        t2 = self.c.post("/votacao/token", headers=el2).json()["token"]
        self.assertEqual(self.c.post("/votacao/votar", json={"token": t2, "tipo": "branco"}).status_code, 201)

        # integridade e apuração
        self.assertTrue(self.c.get("/auditoria/verificar", headers=fis).json()["ok"])
        b = self.c.post("/admin/sessao/fechar", headers=adm)
        self.assertEqual(b.status_code, 200, b.text)
        self.assertEqual(b.json()["total_votos"], 2)
        self.assertEqual(b.json()["resultado"]["brancos"], 1)
        bol = self.c.get(f"/admin/boletim/{b.json()['sessao_id']}", headers=fis).json()
        self.assertTrue(bol["assinatura_valida"])
        self.assertEqual(self.c.post("/votacao/token", headers=el2).status_code, 409)  # sessão fechada
        self.assertTrue(self.c.get("/auditoria/verificar", headers=fis).json()["ok"])

    def test_login_invalido_e_bloqueio(self):
        s = self.seed
        for _ in range(5):
            r = self.c.post("/auth/login", json={"perfil": "eleitor", "identificador": s.cpf_demo(2), "senha": "errada"})
            self.assertEqual(r.status_code, 401)
        r = self.c.post("/auth/login", json={"perfil": "eleitor", "identificador": s.cpf_demo(2), "senha": s.SENHA_DEMO})
        self.assertEqual(r.status_code, 401)  # bloqueado, mesmo com a senha certa

    def test_jwt_de_mfa_nao_acessa_rotas(self):
        s = self.seed
        r = self.c.post("/auth/login", json={"perfil": "admin", "identificador": "fiscal", "senha": s.SENHA_DEMO})
        h = {"Authorization": "Bearer " + r.json()["mfa_token"]}
        self.assertEqual(self.c.get("/auditoria/verificar", headers=h).status_code, 401)

    def test_triggers_append_only(self):
        from sqlalchemy import text
        from app.database import engine
        with self.assertRaises(Exception):
            with engine.begin() as c:
                c.execute(text("DELETE FROM log_auditoria"))


if __name__ == "__main__":
    unittest.main()

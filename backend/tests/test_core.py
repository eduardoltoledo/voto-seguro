"""Testes do núcleo criptográfico e das cadeias de hash.   python -m unittest tests.test_core -v"""
import base64
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import chain, cpf, crypto, totp  # noqa: E402


def _seed_ou_pula(tc):
    try:
        from app import seed
        return seed
    except ModuleNotFoundError as e:  # sqlalchemy ausente fora do container
        tc.skipTest(f"dependência ausente: {e.name}")


def montar_votos(n=5, sessao=1):
    votos, prev = [], chain.genesis_votos(sessao)
    for i in range(1, n + 1):
        r = dict(seq=i, sessao_id=sessao, candidato_id=(i % 3) or None, nonce=f"n{i}",
                 recibo_hash=f"r{i}", prev_hash=prev)
        r["hash"] = chain.calcular_voto(r)
        prev = r["hash"]
        votos.append(r)
    return votos


class TestCrypto(unittest.TestCase):
    def test_aes_roundtrip_e_contexto(self):
        k = os.urandom(32)
        ct = crypto.cifrar(k, "12345678909", "cpf")
        self.assertNotIn("12345678909", ct)
        self.assertEqual(crypto.decifrar(k, ct, "cpf"), "12345678909")
        with self.assertRaises(Exception):
            crypto.decifrar(k, ct, "titulo")
        with self.assertRaises(Exception):
            crypto.decifrar(os.urandom(32), ct, "cpf")

    def test_cifra_nao_deterministica_e_indice_deterministico(self):
        k = os.urandom(32)
        self.assertNotEqual(crypto.cifrar(k, "x"), crypto.cifrar(k, "x"))
        self.assertEqual(crypto.indice_cego(k, "x"), crypto.indice_cego(k, "x"))

    def test_adulteracao_do_texto_cifrado_e_detectada(self):
        k = os.urandom(32)
        raw = bytearray(base64.urlsafe_b64decode(crypto.cifrar(k, "segredo")))
        raw[-1] ^= 1
        with self.assertRaises(Exception):
            crypto.decifrar(k, base64.urlsafe_b64encode(bytes(raw)).decode())


class TestCpf(unittest.TestCase):
    def test_validacao(self):
        self.assertTrue(cpf.validar("529.982.247-25"))
        self.assertFalse(cpf.validar("529.982.247-24"))
        self.assertFalse(cpf.validar("111.111.111-11"))
        self.assertFalse(cpf.validar("123"))

    def test_gerar_dvs(self):
        self.assertEqual(cpf.gerar_dvs("529982247"), "52998224725")


class TestTotp(unittest.TestCase):
    def test_vetor_rfc6238(self):
        seg = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # "12345678901234567890" em base32
        self.assertEqual(totp.codigo_atual(seg, 59), "287082")  # 94287082 truncado a 6 dígitos

    def test_janela_e_replay(self):
        seg, t = totp.gerar_segredo(), 1_700_000_000
        cod = totp.codigo_atual(seg, t)
        passo = totp.verificar(seg, cod, agora=t)
        self.assertIsNotNone(passo)
        self.assertIsNone(totp.verificar(seg, cod, agora=t, ultimo_passo=passo))
        self.assertIsNone(totp.verificar(seg, cod, agora=t + 300))

    def test_segredos_da_demo_sao_base32_validos(self):
        seed = _seed_ou_pula(self)
        for s in (seed.SEGREDO_ADMIN, seed.SEGREDO_AUDITOR, seed.SEGREDO_ELEITORES):
            self.assertEqual(len(totp.codigo_atual(s)), 6)

    def test_cpfs_da_demo_sao_validos(self):
        seed = _seed_ou_pula(self)
        for i in range(8):
            self.assertTrue(cpf.validar(seed.cpf_demo(i)))


class TestChain(unittest.TestCase):
    def test_cadeia_integra(self):
        r = chain.verificar_cadeia(montar_votos(), chain.calcular_voto, chain.genesis_votos(1))
        self.assertTrue(r.ok)
        self.assertEqual(r.total, 5)

    def test_detecta_alteracao_de_voto(self):
        v = montar_votos()
        v[2]["candidato_id"] = 99
        r = chain.verificar_cadeia(v, chain.calcular_voto, chain.genesis_votos(1))
        self.assertFalse(r.ok)
        self.assertEqual(r.quebra_em_seq, 3)

    def test_detecta_remocao_no_meio(self):
        v = montar_votos()
        del v[1]
        r = chain.verificar_cadeia(v, chain.calcular_voto, chain.genesis_votos(1))
        self.assertFalse(r.ok)
        self.assertEqual(r.quebra_em_seq, 2)

    def test_detecta_recalculo_parcial(self):
        v = montar_votos()
        original = copy.deepcopy(v)
        v[1]["candidato_id"] = 99
        v[1]["hash"] = chain.calcular_voto(v[1])
        r = chain.verificar_cadeia(v, chain.calcular_voto, chain.genesis_votos(1))
        self.assertFalse(r.ok)
        self.assertEqual(r.quebra_em_seq, 3)
        self.assertNotEqual(v[1]["hash"], original[1]["hash"])

    def test_truncamento_so_e_visto_pela_ancora(self):
        """Remover os ÚLTIMOS votos mantém a cadeia válida: por isso o fechamento grava a âncora."""
        v = montar_votos()
        ancora = (len(v), v[-1]["hash"])
        r = chain.verificar_cadeia(v[:-2], chain.calcular_voto, chain.genesis_votos(1))
        self.assertTrue(r.ok)
        self.assertNotEqual((r.total, r.ultimo_hash), ancora)

    def test_cadeia_de_logs(self):
        logs, prev = [], chain.GENESIS_LOGS
        for i in range(1, 4):
            r = dict(seq=i, ts=f"2026-10-0{i}T10:00:00", evento="LOGIN", ator_tipo="eleitor",
                     ator_id=i, ip="1.1.1.1", detalhes="{}", prev_hash=prev)
            r["hash"] = chain.calcular_log(r)
            prev = r["hash"]
            logs.append(r)
        self.assertTrue(chain.verificar_cadeia(logs, chain.calcular_log, chain.GENESIS_LOGS).ok)
        logs[1]["ip"] = "6.6.6.6"
        self.assertFalse(chain.verificar_cadeia(logs, chain.calcular_log, chain.GENESIS_LOGS).ok)


if __name__ == "__main__":
    unittest.main()

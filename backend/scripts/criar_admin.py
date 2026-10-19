"""Cria um mesário/administrador ou auditor com MFA.  Uso:
   python -m scripts.criar_admin <usuario> "<Nome>" ADMIN|AUDITOR
A senha é pedida no terminal; o segredo TOTP é exibido uma única vez."""
import getpass
import sys

from app import totp
from app.config import settings
from app.crypto import cifrar
from app.database import SessionLocal
from app.models import UsuarioAdmin
from app.security import hash_senha, senha_forte

if len(sys.argv) != 4 or sys.argv[3] not in ("ADMIN", "AUDITOR"):
    raise SystemExit(__doc__)
usuario, nome, papel = sys.argv[1:4]
senha = getpass.getpass("Senha: ")
if not senha_forte(senha):
    raise SystemExit("Senha fraca (10+ caracteres, maiúscula, minúscula, número e símbolo).")
segredo = totp.gerar_segredo()
with SessionLocal() as db:
    db.add(UsuarioAdmin(usuario=usuario, nome=nome, papel=papel, senha_hash=hash_senha(senha),
                        totp_secret_enc=cifrar(settings.AES_KEY, segredo, "totp")))
    db.commit()
print("Criado. Cadastre no app autenticador:", totp.uri_provisionamento(segredo, usuario))
print("Segredo:", segredo)

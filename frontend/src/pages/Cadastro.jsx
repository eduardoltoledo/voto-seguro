import React, { useEffect, useState } from 'react'
import QRCode from 'qrcode'
import { post } from '../api.js'
import { Alerta, Campo, Copiavel } from '../ui.jsx'

export default function Cadastro({ voltar }) {
  const [f, setF] = useState({ cpf: '', titulo: '', senha: '' })
  const [erro, setErro] = useState('')
  const [mfa, setMfa] = useState(null)
  const [qr, setQr] = useState('')
  const [ocupado, setOcupado] = useState(false)

  useEffect(() => { if (mfa) QRCode.toDataURL(mfa.mfa_uri, { margin: 1, width: 220 }).then(setQr) }, [mfa])

  const enviar = async e => {
    e.preventDefault(); setErro(''); setOcupado(true)
    try { setMfa(await post('/auth/cadastro', f)) } catch (x) { setErro(x.message) } finally { setOcupado(false) }
  }

  if (mfa) return (
    <section className="cartao estreito">
      <h1>Configure o segundo fator</h1>
      <p>Escaneie o código no seu aplicativo autenticador (Google Authenticator, Authy, 2FAS…). Ele será exigido em todo acesso.</p>
      {qr && <img className="qr" src={qr} alt="QR code para o aplicativo autenticador" width="220" height="220" />}
      <p>Sem câmera? Digite o segredo manualmente:</p>
      <p className="segredo">{mfa.mfa_segredo}</p>
      <Copiavel valor={mfa.mfa_segredo} rotulo="Copiar segredo" />
      <Alerta tipo="aviso">Guarde o segredo agora: ele não será exibido novamente.</Alerta>
      <button className="btn btn-primario" onClick={voltar}>Já configurei, ir para o login</button>
    </section>
  )

  const set = k => e => setF({ ...f, [k]: e.target.value })
  return (
    <section className="cartao estreito">
      <h1>Cadastro do eleitor</h1>
      <p>Seus dados são conferidos na base do TSE e guardados criptografados.</p>
      <form onSubmit={enviar}>
        <Campo rotulo="CPF" value={f.cpf} onChange={set('cpf')} inputMode="numeric" required placeholder="000.000.000-00" />
        <Campo rotulo="Título de eleitor" value={f.titulo} onChange={set('titulo')} inputMode="numeric" required placeholder="12 dígitos" />
        <Campo rotulo="Crie uma senha" type="password" value={f.senha} onChange={set('senha')} autoComplete="new-password" required minLength={10}
          dica="Mínimo de 10 caracteres, com maiúscula, minúscula, número e símbolo." />
        <Alerta>{erro}</Alerta>
        <button className="btn btn-primario" disabled={ocupado}>Validar e cadastrar</button>
        <button type="button" className="btn btn-leve" onClick={voltar}>Cancelar</button>
      </form>
    </section>
  )
}

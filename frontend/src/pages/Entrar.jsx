import React, { useState } from 'react'
import { post } from '../api.js'
import { Alerta, Campo } from '../ui.jsx'

export default function Entrar({ aoEntrar, irCadastro }) {
  const [perfil, setPerfil] = useState('eleitor')
  const [ident, setIdent] = useState('')
  const [senha, setSenha] = useState('')
  const [mfaToken, setMfaToken] = useState(null)
  const [codigo, setCodigo] = useState('')
  const [erro, setErro] = useState('')
  const [ocupado, setOcupado] = useState(false)

  const enviar = async fn => { setErro(''); setOcupado(true); try { await fn() } catch (e) { setErro(e.message) } finally { setOcupado(false) } }

  const etapaSenha = e => { e.preventDefault(); enviar(async () => {
    const d = await post('/auth/login', { perfil, identificador: ident, senha }); setSenha(''); setMfaToken(d.mfa_token) }) }
  const etapaMfa = e => { e.preventDefault(); enviar(async () => {
    aoEntrar(await post('/auth/mfa', { mfa_token: mfaToken, codigo })) }) }

  if (mfaToken) return (
    <section className="cartao estreito">
      <h1>Verificação em duas etapas</h1>
      <p>Digite o código de 6 dígitos do seu aplicativo autenticador.</p>
      <form onSubmit={etapaMfa}>
        <Campo rotulo="Código" value={codigo} onChange={e => setCodigo(e.target.value.replace(/\D/g, '').slice(0, 6))}
          inputMode="numeric" autoComplete="one-time-code" autoFocus required pattern="\d{6}" className="codigo" />
        <Alerta>{erro}</Alerta>
        <button className="btn btn-primario" disabled={ocupado || codigo.length !== 6}>Confirmar código</button>
        <button type="button" className="btn btn-leve" onClick={() => { setMfaToken(null); setCodigo(''); setErro('') }}>Voltar</button>
      </form>
    </section>
  )

  return (
    <section className="cartao estreito">
      <h1>Entrar</h1>
      <div className="troca" role="tablist" aria-label="Tipo de acesso">
        {[['eleitor', 'Sou eleitor'], ['admin', 'Mesário ou fiscal']].map(([k, t]) =>
          <button key={k} role="tab" aria-selected={perfil === k} onClick={() => { setPerfil(k); setIdent(''); setErro('') }}>{t}</button>)}
      </div>
      <form onSubmit={etapaSenha}>
        <Campo rotulo={perfil === 'eleitor' ? 'CPF' : 'Usuário'} value={ident} onChange={e => setIdent(e.target.value)}
          inputMode={perfil === 'eleitor' ? 'numeric' : 'text'} autoComplete="username" required
          placeholder={perfil === 'eleitor' ? '000.000.000-00' : ''} />
        <Campo rotulo="Senha" type="password" value={senha} onChange={e => setSenha(e.target.value)}
          autoComplete="current-password" required />
        <Alerta>{erro}</Alerta>
        <button className="btn btn-primario" disabled={ocupado}>Continuar</button>
      </form>
      {perfil === 'eleitor' && <p className="rodape-cartao">Primeiro acesso? <button className="link" onClick={irCadastro}>Cadastre-se com seu título de eleitor</button></p>}
    </section>
  )
}
